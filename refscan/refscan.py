from pathlib import Path
from typing import List, Optional
from typing_extensions import Annotated

import typer
import linkml_runtime

from refscan.lib.Finder import Finder
from refscan.lib.constants import console
from refscan.lib.helpers import (
    connect_to_database,
    get_collection_names_from_schema,
    derive_schema_class_name_from_document,
    init_progress_bar,
    get_lowercase_key,
    print_section_header,
    get_names_of_classes_eligible_for_collection,
    get_names_of_classes_in_effective_range_of_slot,
)
from refscan.lib.Reference import Reference
from refscan.lib.ReferenceList import ReferenceList
from refscan.lib.Violation import Violation
from refscan.lib.ViolationList import ViolationList
from refscan import get_package_metadata

app = typer.Typer(
    help="Scans the NMDC MongoDB database for referential integrity violations.",
    add_completion=False,  # hides the shell completion options from `--help` output
    rich_markup_mode="markdown",  # enables use of Markdown in docstrings and CLI help
)

app_version = get_package_metadata("Version")


def display_app_version_and_exit(is_active: bool = False) -> None:
    r"""
    Displays the app's version number, then exits.

    Note: The `is_active` flag will be `True` if the program was
          invoked with the associated CLI option.

    Reference: https://typer.tiangolo.com/tutorial/options/version/
    """
    if is_active:
        console.print(f"[white]{app_version}[/white]")
        raise typer.Exit()


@app.command("scan")
def scan(
    # Reference: https://typer.tiangolo.com/tutorial/parameter-types/path/
    schema_file_path: Annotated[
        Path,
        typer.Option(
            "--schema",
            dir_okay=False,
            writable=False,
            readable=True,
            resolve_path=True,
            help="Filesystem path at which the YAML file representing the schema is located.",
        ),
    ],
    database_name: Annotated[
        str,
        typer.Option(
            help="Name of the database.",
        ),
    ] = "nmdc",
    mongo_uri: Annotated[
        str,
        typer.Option(
            envvar="MONGO_URI",
            help=(
                "Connection string for accessing the MongoDB server. If you have Docker installed, "
                "you can spin up a temporary MongoDB server at the default URI by running: "
                "`$ docker run --rm --detach -p 27017:27017 mongo`"
            ),
        ),
    ] = "mongodb://localhost:27017",
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show verbose output.",
        ),
    ] = False,
    # Reference: https://typer.tiangolo.com/tutorial/multiple-values/multiple-options/
    skip_source_collection: Annotated[
        Optional[List[str]],
        typer.Option(
            "--skip-source-collection",
            "--skip",
            help=(
                "Name of collection you do not want to search for referring documents. "
                "Option can be used multiple times."
            ),
        ),
    ] = None,
    reference_report_file_path: Annotated[
        Optional[Path],
        typer.Option(
            "--reference-report",
            dir_okay=False,
            writable=True,
            readable=False,
            resolve_path=True,
            help="Filesystem path at which you want the program to generate its reference report.",
        ),
    ] = "references.tsv",
    violation_report_file_path: Annotated[
        Optional[Path],
        typer.Option(
            "--violation-report",
            dir_okay=False,
            writable=True,
            readable=False,
            resolve_path=True,
            help="Filesystem path at which you want the program to generate its violation report.",
        ),
    ] = "violations.tsv",
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=display_app_version_and_exit,
            is_eager=True,  # tells Typer to process this option first
            help="Show version number and exit.",
        ),
    ] = None,
    user_wants_to_skip_scan: Annotated[
        bool,
        typer.Option(
            "--no-scan",
            help="Generate a reference report, but do not scan the database for violations.",
        ),
    ] = False,
    user_wants_to_locate_misplaced_documents: Annotated[
        bool,
        typer.Option(
            "--locate-misplaced-documents",
            help=(
                "For each referenced document not found in any of the collections the schema _allows_, "
                "also search for it in all _other_ collections."
            ),
        ),
    ] = False,
):
    """
    Scans the NMDC MongoDB database for referential integrity violations.
    """
    # Instantiate a `linkml_runtime.SchemaView` bound to the specified schema.
    if verbose:
        console.print(f"Schema YAML file: {schema_file_path}")
    schema_view = linkml_runtime.SchemaView(schema_file_path)

    # Show high-level information about the application and schema.
    console.print(f"refscan version: {app_version}")
    console.print(f"Schema version: {schema_view.schema.version}")

    # Show a header on the console, to tell the user which stage of execution we're entering.
    print_section_header(console, text="Identifying references")

    # Make a more self-documenting alias for the CLI option that can be specified multiple times.
    names_of_source_collections_to_skip: list[str] = [] if skip_source_collection is None else skip_source_collection

    # Get a list of collection names (technically, `Database` slot names) from the schema.
    # e.g. ["study_set", ...]
    collection_names = get_collection_names_from_schema(schema_view)
    console.print(f"Collections described by schema: {len(collection_names)}")

    # For each collection, determine the names of the classes whose instances can be stored in that collection.
    collection_name_to_class_names = {}  # example: { "study_set": ["Study"] }
    for collection_name in sorted(collection_names):
        collection_name_to_class_names[collection_name] = get_names_of_classes_eligible_for_collection(
            schema_view=schema_view,
            collection_name=collection_name,
        )

    # Initialize the list of references. A reference is effectively a "foreign key" (i.e. a pointer).
    references = ReferenceList()

    # For each class whose instances can be stored in each collection, determine which of its slots can be a reference.
    sorted_collection_names_to_class_names = sorted(collection_name_to_class_names.items(), key=get_lowercase_key)
    for collection_name, class_names in sorted_collection_names_to_class_names:
        for class_name in class_names:
            for slot_name in schema_view.class_slots(class_name):

                # Get the slot definition in the context of its use on this particular class.
                slot_definition = schema_view.induced_slot(slot_name=slot_name, class_name=class_name)

                # Determine the slot's "effective" range, taking into account its `any_of` constraint (if it has one).
                names_of_eligible_target_classes = get_names_of_classes_in_effective_range_of_slot(
                    schema_view=schema_view,
                    slot_definition=slot_definition,
                )

                # For each of those classes whose instances can be stored in any collection, catalog a reference.
                for name_of_eligible_target_class in names_of_eligible_target_classes:
                    for target_collection_name, class_names_in_collection in collection_name_to_class_names.items():
                        if name_of_eligible_target_class in class_names_in_collection:
                            reference = Reference(
                                source_collection_name=collection_name,
                                source_class_name=class_name,
                                source_field_name=slot_name,
                                target_collection_name=target_collection_name,
                                target_class_name=name_of_eligible_target_class,
                            )
                            references.append(reference)

    console.print(f"References described by schema: {len(references)}")

    num_collections_having_references = references.count_source_collections()
    console.print(f"Collections containing references: {num_collections_having_references}")
    console.print()  # newline

    # Create a reference report in TSV format.
    console.print(f"Writing reference report: {reference_report_file_path}")
    references.dump_to_tsv_file(file_path=reference_report_file_path)

    # Display a table of references.
    if verbose:
        console.print(references.as_table())

    # If the user opted to skip the scanning step, exit the script.
    if user_wants_to_skip_scan:
        console.print()
        console.print("Skipping scan and exiting.")
        console.print()
        raise typer.Exit(code=0)

    print_section_header(console, text="Scanning for violations")

    # Get a dictionary that maps source class names to the names of their fields that can contain references.
    reference_field_names_by_source_class_name = references.get_reference_field_names_by_source_class_name()

    # Initialize a progress bar.
    custom_progress = init_progress_bar()

    # Connect to the MongoDB server and verify the database is accessible.
    mongo_client = connect_to_database(mongo_uri, database_name)

    db = mongo_client.get_database(database_name)

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

                                if user_wants_to_locate_misplaced_documents:
                                    names_of_ineligible_collections = list(
                                        set(collection_names) - set(target_collection_names)
                                    )
                                    name_of_collection_containing_target_document = (
                                        finder.check_whether_document_having_id_exists_among_collections(
                                            collection_names=names_of_ineligible_collections, document_id=target_id
                                        )
                                    )

                                violation = Violation(
                                    source_collection_name=source_collection_name,
                                    source_field_name=field_name,
                                    source_document_object_id=source_document_object_id,
                                    source_document_id=source_document_id,
                                    target_id=target_id,
                                    name_of_collection_containing_target=name_of_collection_containing_target_document,
                                )
                                source_collections_and_their_violations[source_collection_name].append(violation)
                                if verbose:
                                    console.print(
                                        f"Failed to find document having `id` '{target_id}' "
                                        f"among collections: {target_collection_names}. "
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

    # Close the connection to the MongoDB server.
    mongo_client.close()

    print_section_header(console, text="Summarizing results")

    # Make a list of all violations among all collections.
    all_violations = ViolationList()
    for collection_name, violations in sorted(source_collections_and_their_violations.items(), key=get_lowercase_key):
        all_violations.extend(violations)

        # Print a message indicating the number of violations in this collection.
        num_violations = len(violations)
        color_name = "white" if num_violations == 0 else "red"
        console.print(
            f"Number of violations in {collection_name}: "
            f"[{color_name} not bold]{num_violations}[/{color_name} not bold]"
        )

        if verbose:
            console.print(violations)

    num_all_violations = len(all_violations)
    color_name = "white" if num_all_violations == 0 else "red"
    console.print()  # newline
    console.print(f"Total violations: " f"[{color_name}]{num_all_violations}[/{color_name}]")
    console.print()  # newline

    # Create a TSV-formatted violation report that lists all violations among all collections.
    console.print(f"Writing violation report: {violation_report_file_path}")
    all_violations.dump_to_tsv_file(file_path=violation_report_file_path)
    console.print()  # newline


if __name__ == "__main__":
    app()
