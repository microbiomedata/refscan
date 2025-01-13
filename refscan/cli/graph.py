from pathlib import Path
from typing import Optional
from typing_extensions import Annotated

import typer
import linkml_runtime

from refscan import grapher
from refscan.lib.constants import console
from refscan.lib.helpers import print_section_header


def graph(
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
    graph_file_path: Annotated[
        Optional[Path],
        typer.Option(
            "--graph",
            dir_okay=False,
            writable=True,
            readable=False,
            resolve_path=True,
            help="Filesystem path at which you want **refscan** to generate the graph.",
        ),
    ] = "graph.html",
    subject: Annotated[
        grapher.Subject,
        typer.Option(
            "--subject",
            case_sensitive=False,
            help="Whether you want each node of the graph to represent a collection or a class.",
        ),
    ] = grapher.Subject.collection,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show verbose output.",
        ),
    ] = False,
):
    r"""
    Generate an interactive graph of the references described by a schema.
    """

    print_section_header(console, text="Reading schema")

    # Instantiate a `linkml_runtime.SchemaView` bound to the specified schema.
    if verbose:
        console.print(f"Schema YAML file: {schema_file_path}")
    schema_view = linkml_runtime.SchemaView(schema_file_path)

    # Show high-level information about the schema.
    console.print(f"Schema version: {schema_view.schema.version}")

    html_result = grapher.graph(
        schema_view=schema_view,
        subject=subject,
        verbose=verbose,
    )

    if verbose:
        console.print(html_result)

    with open(graph_file_path, "w") as f:
        f.write(html_result)

    console.print(f"Graph generated at: {graph_file_path}")
    console.print()
