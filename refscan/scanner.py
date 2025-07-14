from typing import List, Optional, Dict, Set, Tuple

from pymongo.database import Database
from pymongo.client_session import ClientSession
from rich.console import Console
from linkml_runtime import SchemaView

from refscan.lib.Finder import Finder
from refscan.lib.helpers import (
    derive_schema_class_name_from_document,
    get_collection_names_from_schema,
    translate_class_uri_into_schema_class_name,
    translate_schema_class_name_into_class_uri,
    init_progress_bar,
)
from refscan.lib.ReferenceList import ReferenceList
from refscan.lib.Violation import Violation
from refscan.lib.ViolationList import ViolationList
from refscan.lib.constants import console as default_console


def identify_referring_documents(
    document: dict,
    schema_view: SchemaView,
    references: ReferenceList,
    finder: Finder,
    client_session: Optional[ClientSession] = None,
) -> List[dict]:
    r"""
    Identifies documents that reference the specified one.

    Note: This function only searches collections and fields that the _schema_ says
          can reference the specified document. If an arbitrary collection contains
          a document that has a field that contains the `id` of the specified document
          (e.g. the `foo_set` collection contains a document whose `nickname` field
          contains `someIdentifier`), it is not necessarily the case that this function
          will consider that to be a reference. It depends upon what the _schema_ says.

    Note: This can be useful for determining whether the specified document can be safely deleted.

    :param document: The document whose incoming references you want to identify
    :param schema_view: A `SchemaView` bound to the schema
    :param references: A `ReferenceList` derived from the schema
    :param finder: A `Finder` bound to the database being scanned
    :param client_session: A `pymongo.client_session.ClientSession` instance that, if specified, will be used when
                           searching for referring documents. If a transaction happens to be pending on that session,
                           the scan will effectively happen on the database as it _would_ exist if that transaction
                           were to be committed.
    :return: A list of descriptors of documents that reference the specified document
    """

    # Initialize a list of descriptors of documents that reference the specified document.
    referring_document_descriptors = []

    # If the specified document does not have an `id` field, we know it cannot be referenced.
    if "id" not in document:
        return referring_document_descriptors

    # Get the specified document's `id` and derive its schema class name.
    document_id = document["id"]
    document_class_name = derive_schema_class_name_from_document(schema_view, document)
    if document_class_name is None:
        raise ValueError(f"Failed to identify schema class of document having `id`: {document_id}")

    # Identify potential references to the specified document, then group them by their source collection names.
    potential_references_to_document = references.get_by_target_class_name(document_class_name)
    potential_references_by_source_collection = potential_references_to_document.group_by_source_collection_name()

    # For each source collection name, check each of its potential references.
    for collection_name, potential_references_in_collection in potential_references_by_source_collection.items():
        # Make a list of all the distinct `class_uri`-and-`field_name` tuples.
        #
        # Note: Since a `Reference` doesn't have a `source_class_uri` attribute (but it does have a
        #       `source_class_name` attribute), we derive its `class_uri` from that `source_class_name` attribute.
        #
        class_uri_and_field_name_tuples: Set[Tuple[str, str]] = set()
        for potential_reference in potential_references_in_collection:
            class_uri = translate_schema_class_name_into_class_uri(
                schema_view=schema_view, schema_class_name=potential_reference.source_class_name
            )
            if class_uri is None:
                raise ValueError(
                    f"Failed to translate schema class name '{potential_reference.source_class_name}' into class_uri."
                )
            class_uri_and_field_name_tuple = (class_uri, potential_reference.source_field_name)
            class_uri_and_field_name_tuples.add(class_uri_and_field_name_tuple)

        # For each distinct combination of `class_uri` and `field_name`, check whether any documents in this
        # collection both (a) have a `type` value matching that `class_uri` and (b) have the subject document's
        # `id` value in the specified field.
        referring_documents = finder.find_documents_having_type_and_value_in_field(
            collection_name=collection_name,
            type_and_field_name_tuples=list(class_uri_and_field_name_tuples),
            value=document_id,
            client_session=client_session,
        )

        # For each referring document, store a descriptor of it.
        for referring_document in referring_documents:

            # Handle the case where the source document does not have an `id`.
            #
            # Note: As a reminder, according to the NMDC Schema (as of version v11.8.0), documents in the
            #       `functional_annotation_agg` collection do not have an `id` field.
            #       Reference: https://microbiomedata.github.io/nmdc-schema/FunctionalAnnotationAggMember/
            #
            source_document_id = referring_document.get("id", None)
            if not isinstance(source_document_id, str):
                source_document_id = ""

            source_class_name = translate_class_uri_into_schema_class_name(
                schema_view=schema_view,
                class_uri=referring_document["type"],
            )
            document_descriptor = dict(
                source_collection_name=collection_name,
                source_class_name=source_class_name,
                source_document_object_id=referring_document["_id"],
                source_document_id=source_document_id,
            )
            referring_document_descriptors.append(document_descriptor)

    return referring_document_descriptors


def scan_outgoing_references(
    document: dict,
    schema_view: SchemaView,
    references: ReferenceList,
    finder: Finder,
    source_collection_name: str,
    client_session: Optional[ClientSession] = None,
    user_wants_to_locate_misplaced_documents: bool = False,
) -> ViolationList:
    r"""
    Scans the references emanating from the specified document, for referential integrity violations. In other words,
    checks whether all documents references by this one exist in places the schema allows them to exist.

    :param document: The source document from which the references emanate
    :param schema_view: A SchemaView bound to the schema
    :param references: A `ReferenceList` derived from the schema
    :param finder: A `Finder` bound to the database being scanned
    :param source_collection_name: Name of collection in which source document resides (this is included in the
                                   violation report in an attempt to facilitate investigation of violations)
    :param client_session: A `pymongo.client_session.ClientSession` instance that, if specified, will be used when
                           searching for referenced documents. If a transaction happens to be pending on that session,
                           the scan will effectively happen on the database as it _would_ exist if that transaction
                           were to be committed.
    :param user_wants_to_locate_misplaced_documents: Whether the user wants the function to proceed to search illegal
                                                     collections after failing to find the referenced document among
                                                     all the legal collections
    """

    # Initialize a list of violations.
    violations = ViolationList()

    # Get the document's `id` so that we can include it in this script's output.
    source_document_object_id = document["_id"]
    source_document_id: Optional[str] = document["id"] if "id" in document else None

    # Get the document's schema class name so that we can interpret its fields accordingly.
    source_class_name = derive_schema_class_name_from_document(schema_view, document)
    if source_class_name is None:
        raise ValueError(f"Failed to derive schema class name from document having `id`: {source_document_id}")

    # Get the names of that class's fields that can contain references.
    reference_field_names_by_source_class_name = references.get_reference_field_names_by_source_class_name()
    names_of_reference_fields = reference_field_names_by_source_class_name.get(source_class_name, [])

    # Get the names of collections that are described by the schema.
    collection_names = get_collection_names_from_schema(schema_view=schema_view)

    # Check each field that both (a) exists in the document and (b) can contain a reference.
    for field_name in names_of_reference_fields:
        if field_name in document:
            # Determine which collections can contain the referenced document, based upon
            # the schema class of which this source document is an instance.
            target_collection_names = references.get_target_collection_names(
                source_class_name=source_class_name,
                source_field_name=field_name,
            )

            # Handle both the multi-value (array) and the single-value (scalar) case,
            # normalizing the value or values into a list of values in either case.
            if type(document[field_name]) is list:
                target_ids = document[field_name]
            else:
                target_id = document[field_name]
                target_ids = [target_id]  # makes a one-item list

            for target_id in target_ids:
                name_of_collection_containing_target_document = (
                    finder.check_whether_document_having_id_exists_among_collections(
                        collection_names=target_collection_names, document_id=target_id, client_session=client_session
                    )
                )
                if name_of_collection_containing_target_document is None:

                    # If the user wants to locate misplaced documents,
                    # search all illegal collections for the misplaced document.
                    if user_wants_to_locate_misplaced_documents:
                        names_of_ineligible_collections = list(set(collection_names) - set(target_collection_names))
                        name_of_collection_containing_target_document = (
                            finder.check_whether_document_having_id_exists_among_collections(
                                collection_names=names_of_ineligible_collections,
                                document_id=target_id,
                                client_session=client_session,
                            )
                        )

                    # Handle the case where the source document does not have an `id`.
                    #
                    # Note: As a reminder, according to the NMDC Schema (as of version v11.8.0), documents in the
                    #       `functional_annotation_agg` collection do not have an `id` field.
                    #       Reference: https://microbiomedata.github.io/nmdc-schema/FunctionalAnnotationAggMember/
                    #
                    if not isinstance(source_document_id, str):
                        source_document_id = ""

                    # Instantiate a `Violation` containing information about this referential integrity violation.
                    violation = Violation(
                        source_collection_name=source_collection_name,
                        source_class_name=source_class_name,
                        source_field_name=field_name,
                        source_document_object_id=source_document_object_id,
                        source_document_id=source_document_id,
                        target_id=target_id,
                        name_of_collection_containing_target=name_of_collection_containing_target_document,
                    )

                    # Append this violation to the list of this document's violations.
                    violations.append(violation)

    return violations


def scan(
    db: Database,
    schema_view: SchemaView,
    references: ReferenceList,
    names_of_source_collections_to_skip: List[str],
    user_wants_to_locate_misplaced_documents: bool = False,
    console: Console = default_console,
    verbose: bool = False,
) -> Dict[str, ViolationList]:
    """
    Scans the NMDC MongoDB database for referential integrity violations according to the parameters passed in,
    returning a dictionary containing a list of violations for each collection scanned.

    :param db: Database you want to scan for referential integrity violations
    :param schema_view: A SchemaView bound to the schema with which that database complies
                        (except that it may not be compliant in terms of referential integrity)
    :param references: A `ReferenceList` derived from the schema
    :param names_of_source_collections_to_skip: List of source collections to skip
    :param user_wants_to_locate_misplaced_documents: Whether the user wants the function to proceed to search illegal
                                                     collections after failing to find the referenced document among
                                                     all the legal collections
    :param console: A `Console` to which the function can print messages
    :param verbose: Whether you want the function to print a higher-than-normal amount of information to the console
    """

    # Initialize a progress bar.
    custom_progress = init_progress_bar()

    # Make a finder bound to this database.
    # Note: A finder is a wrapper around a database that adds some caching that speeds up searches in some situations.
    finder = Finder(database=db)

    source_collections_and_their_violations: dict[str, ViolationList] = {}
    with custom_progress as progress:

        # Filter out the collections that the schema says can contain references, but that don't exist in the database.
        source_collection_names_in_db = []
        for collection_name in references.get_source_collection_names():
            if db.get_collection(collection_name) is None:
                console.print(f"🤷  [orange]Database lacks collection:[/orange] {collection_name}")
            else:
                source_collection_names_in_db.append(collection_name)

        # Print a message about each collection being skipped.
        for i, collection_name in enumerate(names_of_source_collections_to_skip):
            if i == 0:
                console.print()  # leading newline
            console.print(f"⚠️  [orange][bold]Skipping source collection:[/bold][/orange] {collection_name}")
        console.print()  # newline

        # Process each collection, checking for referential integrity violations;
        # using the reference catalog created earlier to know which collections can
        # contain "referrers" (documents), which of their slots can contain references (fields),
        # and which collections can contain the referred-to "referees" (documents).
        for source_collection_name in sorted(source_collection_names_in_db):

            # If this source collection is one of the ones the user wanted to skip, skip it now.
            if source_collection_name in names_of_source_collections_to_skip:
                continue

            collection = db.get_collection(source_collection_name)

            # Prepare the query we will use to fetch documents from this collection. The documents we will fetch are
            # those that have _any_ of the fields (of classes whose instances are allowed to reside in this collection)
            # that the schema allows to contain a reference to an instance.
            source_field_names = references.get_source_field_names_of_source_collection(source_collection_name)
            or_terms = [{field_name: {"$exists": True}} for field_name in source_field_names]
            query_filter = {"$or": or_terms}
            if verbose:
                console.print(f"{query_filter=}")

            # Ensure the fields we fetch include:
            # - "id" (so we can produce a more user-friendly report later)
            # - "type" (so we can map the document to a schema class)
            additional_field_names_for_projection = []
            if "id" not in source_field_names:
                additional_field_names_for_projection.append("id")
            if "type" not in source_field_names:
                additional_field_names_for_projection.append("type")
            query_projection = source_field_names + additional_field_names_for_projection
            if verbose:
                console.print(f"{query_projection=}")

            # Set up the progress bar for the task of scanning those documents.
            num_relevant_documents = collection.count_documents(query_filter)
            task_id = progress.add_task(
                f"{source_collection_name}",
                total=num_relevant_documents,
                num_violations=0,
                remaining_time_label="remaining",
            )

            # Advance the progress bar by 0 (this makes it so that, even if there are 0 relevant documents, the progress
            # bar does not continue incrementing its "elapsed time" even after a subsequent task has begun).
            progress.update(task_id, advance=0)

            # Initialize the violation list for this collection.
            source_collections_and_their_violations[source_collection_name] = ViolationList()

            # Process each relevant document.
            for document in collection.find(query_filter, projection=query_projection):
                violations = scan_outgoing_references(
                    document=document,
                    schema_view=schema_view,
                    references=references,
                    finder=finder,
                    source_collection_name=source_collection_name,
                    user_wants_to_locate_misplaced_documents=user_wants_to_locate_misplaced_documents,
                )

                # Add these violations—if any—to the list for this source collection.
                source_collections_and_their_violations[source_collection_name].extend(violations)

                # If operating verbosely, print a message about each violation.
                if verbose:
                    for violation in violations:
                        console.print(
                            f"Failed to find document having `id` '{violation.target_id}' "
                            f"among collections allowed by schema. "
                            f"{violation=}"
                        )

                # Advance the progress bar to account for the current document's contribution to the violations count.
                progress.update(
                    task_id,
                    advance=1,
                    num_violations=len(source_collections_and_their_violations[source_collection_name]),
                )

            # Update the progress bar to indicate the current task is complete.
            progress.update(task_id, remaining_time_label="done")

    return source_collections_and_their_violations
