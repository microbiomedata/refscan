from pathlib import Path
from typing import List, Optional, Dict
from typing_extensions import Annotated

import typer
import linkml_runtime

from refscan.lib.constants import console
from refscan.lib.helpers import (
    connect_to_database,
    get_collection_name_to_class_names_map,
    get_collection_names_from_schema,
    get_lowercase_key,
    print_section_header,
    identify_references,
)
from refscan.lib.ViolationList import ViolationList
from refscan.scanner import scan as refscan_scan
from refscan import get_package_metadata

app_version = get_package_metadata("Version")


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
    r"""
    Scan the NMDC MongoDB database for referential integrity violations.
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

    # Get a list of collection names (technically, names of `Database` slots that satisfy some criteria)
    # from the schema; e.g. ["study_set", "biosample_set", ...]
    collection_names = get_collection_names_from_schema(schema_view)
    console.print(f"Collections described by schema: {len(collection_names)}")

    # For each collection, determine the names of the classes whose instances can be stored in that collection.
    collection_name_to_class_names = get_collection_name_to_class_names_map(schema_view=schema_view)

    # Identify the inter-document references that the schema allows to exist.
    references = identify_references(
        schema_view=schema_view, collection_name_to_class_names=collection_name_to_class_names
    )
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

    # Connect to the MongoDB server and verify the database is accessible.
    mongo_client = connect_to_database(mongo_uri, database_name)
    db = mongo_client.get_database(database_name)

    # Perform the scan.
    source_collections_and_their_violations: Dict[str, ViolationList] = refscan_scan(
        db=db,
        schema_view=schema_view,
        references=references,
        names_of_source_collections_to_skip=names_of_source_collections_to_skip,
        user_wants_to_locate_misplaced_documents=user_wants_to_locate_misplaced_documents,
        verbose=verbose,
        console=console,
    )

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
