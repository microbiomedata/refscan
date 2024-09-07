from enum import Enum
from pathlib import Path
from typing import Optional
from typing_extensions import Annotated
import json
import base64
from importlib import resources

import typer
import linkml_runtime

from refscan import get_package_metadata
from refscan.lib.constants import console
from refscan.lib.helpers import (
    print_section_header,
    get_collection_names_from_schema,
    get_names_of_classes_eligible_for_collection,
    identify_references,
)
from refscan.refscan import display_app_version_and_exit

app = typer.Typer(
    help="Generates an interactive graph (network diagram) of the references described by a schema.",
    add_completion=False,  # hides the shell completion options from `--help` output
    rich_markup_mode="markdown",  # enables use of Markdown in docstrings and CLI help
)


class Subject(str, Enum):
    r"""The subject (i.e. focal point) of the graph."""

    collection = "collection"
    class_ = "class"


def load_template(resource_path: str) -> str:
    r"""
    Returns the contents of a template file as a string.

    Note: We do this via `importlib.resources` instead of a regular `open()` so
          that the path is accurate both when this script is run in a development
          environment and when this script is run when installed from PyPI,
          instead of it only being accurate in the former case.
          Reference: https://docs.python.org/3.10/library/importlib.html
    """
    package_name = "refscan"
    return resources.files(package_name).joinpath(resource_path).read_text(encoding="utf-8")


def encode_json_value_as_base64_str(json_value: dict | list) -> str:
    r"""Helper function that encodes the specified JSON value as a base64 string."""

    value_as_string = json.dumps(json_value)
    string_as_bytes = value_as_string.encode("utf-8")
    encoded_bytes = base64.b64encode(string_as_bytes)
    encoded_bytes_as_string = encoded_bytes.decode("utf-8")
    return encoded_bytes_as_string


@app.command("graph")
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
            help="Filesystem path at which you want **refgraph** to generate the graph.",
        ),
    ] = "graph.html",
    subject: Annotated[
        Subject,
        typer.Option(
            "--subject",
            case_sensitive=False,
            help="Whether you want each node of the graph to represent a collection or a class.",
        ),
    ] = Subject.collection,
    verbose: Annotated[
        bool,
        typer.Option(
            "--verbose",
            help="Show verbose output.",
        ),
    ] = False,
    version: Annotated[
        Optional[bool],
        typer.Option(
            "--version",
            callback=display_app_version_and_exit,
            is_eager=True,  # tells Typer to process this option first
            help="Show version number and exit.",
        ),
    ] = None,
):
    r"""
    Generates an interactive graph (network diagram) of the references described by a schema.
    """

    print_section_header(console, text="Reading schema")

    # Instantiate a `linkml_runtime.SchemaView` bound to the specified schema.
    if verbose:
        console.print(f"Schema YAML file: {schema_file_path}")
    schema_view = linkml_runtime.SchemaView(schema_file_path)

    # Show high-level information about the schema.
    console.print(f"Schema version: {schema_view.schema.version}")

    # Show a header on the console, to tell the user which stage of execution we're entering.
    print_section_header(console, text="Identifying references")

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

    # Identify the inter-document references that the schema allows to exist.
    references = identify_references(
        schema_view=schema_view, collection_name_to_class_names=collection_name_to_class_names
    )
    console.print(f"References described by schema: {len(references)}")

    console.print(f"References: {len(references)}")
    if verbose:
        console.print(references)

    print_section_header(console, text="Generating graph")

    # Generate a list of elements (i.e. nodes and edges) for use by the `cytoscape` JavaScript library.
    #
    # Note: Nodes are represented like this (here are two examples):
    #       ```
    #       { data: { id: "data_generation_set" } }
    #       { data: { id: "study_set" } }
    #       ```
    #       Edges are represented like this (here is one example):
    #       ```
    #       { data: { id: "data_generation_set__to__study_set", source: "data_generation_set", target: "study_set" } }
    #       ```
    #
    # Reference: https://js.cytoscape.org/#notation/elements-json
    #
    nodes = []
    edges = []
    for r in references:
        # Get the source and target names depending upon the subject of the graph.
        source_name = r.source_collection_name if subject == Subject.collection else r.source_class_name
        target_name = r.target_collection_name if subject == Subject.collection else r.target_class_name

        # Append a node for the source subject if we haven't already done so. Same for the target subject.
        node_ids = [n["data"]["id"] for n in nodes]
        if source_name not in node_ids:
            nodes.append(dict(data=dict(id=source_name)))
        if target_name not in node_ids:
            nodes.append(dict(data=dict(id=target_name)))

        # Append an edge for this source subject-to-target subject relationship if we haven't already done so.
        edge_id = f"{source_name}__to__{target_name}"
        edge_ids = [e["data"]["id"] for e in edges]
        if edge_id not in edge_ids:
            edges.append(dict(data=dict(id=edge_id, source=source_name, target=target_name)))

    console.print(f"Nodes: {len(nodes)}")
    console.print(f"Edges: {len(edges)}")
    console.print()

    elements = nodes + edges  # join the lists

    # Load the HTML template file.
    html_template = load_template(r"templates/graph.template.html")

    # Generate an HTML file (based upon the template) that contains those elements.
    graph_data_json_base64_str = encode_json_value_as_base64_str(elements)
    graph_metadata_json_base64_str = encode_json_value_as_base64_str(
        dict(
            app_version=get_package_metadata("Version"),
            schema_version=schema_view.schema.version,
        )
    )
    html_result = html_template.replace("{{ graph_data_json_base64 }}", graph_data_json_base64_str)
    html_result = html_result.replace("{{ graph_metadata_json_base64 }}", graph_metadata_json_base64_str)

    if verbose:
        console.print(html_result)

    with open(graph_file_path, "w") as f:
        f.write(html_result)

    console.print(f"Graph generated at: {graph_file_path}")
    console.print()


if __name__ == "__main__":
    app()
