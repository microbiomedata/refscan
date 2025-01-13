from typing import List, Optional, Dict

from pymongo.database import Database
from rich.console import Console
from linkml_runtime import SchemaView

from refscan.lib.Finder import Finder
from refscan.lib.helpers import (
    derive_schema_class_name_from_document,
    init_progress_bar,
)
from refscan.lib.ReferenceList import ReferenceList
from refscan.lib.Violation import Violation
from refscan.lib.ViolationList import ViolationList
from refscan.lib.constants import console as default_console


def scan_outgoing_references(
    document: dict,
    schema_view: SchemaView,
    # TODO: Cache this dictionary, since it is derived from the schema alone.
    reference_field_names_by_source_class_name: Dict[str, List[str]],
    references: ReferenceList,
    finder: Finder,
    collection_names: List[str],
    source_collection_name: str,
    user_wants_to_locate_misplaced_documents: bool = False,
) -> ViolationList:
    r"""
    Scans the references emanating from the specified document, for referential integrity violations. In other words,
    checks whether all documents references by this one exist in places the schema allows them to exist.

    :param document: The source document from which the references emanate
    :param schema_view: A SchemaView bound to the schema
    :param reference_field_names_by_source_class_name: Dictionary mapping class names to lists of reference field names
    :param references: A `ReferenceList` derived from the schema
    :param finder: A `Finder` bound to the database being scanned
    :param user_wants_to_locate_misplaced_documents: Whether the user wants the function to proceed to search illegal
                                                     collections after failing to find the referenced document among
                                                     all the legal collections
    :param source_collection_name: Name of collection in which source document resides (this is included in the
                                   violation report in an attempt to facilitate investigation of violations)
    :param collection_names: List of collection names that are described by the schema
    """

    # Initialize a list of violations.
    violations = ViolationList()

    # Get the document's `id` so that we can include it in this script's output.
    source_document_object_id = document["_id"]
    source_document_id = document["id"] if "id" in document else None

    # Get the document's schema class name so that we can interpret its fields accordingly.
    source_class_name = derive_schema_class_name_from_document(schema_view, document)

    # Get the names of that class's fields that can contain references.
    names_of_reference_fields = reference_field_names_by_source_class_name.get(source_class_name, [])

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
                        collection_names=target_collection_names, document_id=target_id
                    )
                )
                if name_of_collection_containing_target_document is None:

                    # If the user wants to locate misplaced documents,
                    # search all illegal collections for the misplaced document.
                    if user_wants_to_locate_misplaced_documents:
                        names_of_ineligible_collections = list(set(collection_names) - set(target_collection_names))
                        name_of_collection_containing_target_document = (
                            finder.check_whether_document_having_id_exists_among_collections(
                                collection_names=names_of_ineligible_collections, document_id=target_id
                            )
                        )

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
    collection_names: List[str],
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
    :param collection_names: List of collection names that are described by the schema
    :param names_of_source_collections_to_skip: List of source collections to skip
    :param user_wants_to_locate_misplaced_documents: Whether the user wants the function to proceed to search illegal
                                                     collections after failing to find the referenced document among
                                                     all the legal collections
    :param console: A `Console` to which the function can print messages
    :param verbose: Whether you want the function to print a higher-than-normal amount of information to the console
    """

    # Get a dictionary that maps source class names to the names of their fields that can contain references.
    reference_field_names_by_source_class_name = references.get_reference_field_names_by_source_class_name()

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
                    reference_field_names_by_source_class_name=reference_field_names_by_source_class_name,
                    references=references,
                    finder=finder,
                    collection_names=collection_names,
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
