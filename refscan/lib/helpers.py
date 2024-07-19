from typing import Optional, List
from functools import cache

from pymongo import MongoClient, timeout
from linkml_runtime import SchemaView, linkml_model
from rich.console import Console
from rich.progress import Progress, TextColumn, MofNCompleteColumn, BarColumn, TimeElapsedColumn, TimeRemainingColumn

from refscan.lib.constants import DATABASE_CLASS_NAME, console


def connect_to_database(mongo_uri: str, database_name: str, verbose: bool = True) -> MongoClient:
    """
    Returns a Mongo client. Raises an exception if the database is not accessible.
    """
    mongo_client: MongoClient = MongoClient(host=mongo_uri, directConnection=True)

    with timeout(5):  # if any message exchange takes > 5 seconds, this will raise an exception
        (host, port_number) = mongo_client.address

        if verbose:
            console.print(f'Connected to MongoDB server: "{host}:{port_number}"')

        # Check whether the database exists on the MongoDB server.
        if database_name not in mongo_client.list_database_names():
            raise ValueError(f'Database "{database_name}" not found on the MongoDB server.')

    return mongo_client


def get_collection_names_from_schema(schema_view: SchemaView) -> list[str]:
    """
    Returns the names of the slots of the `Database` class that describe database collections.

    :param schema_view: A `SchemaView` instance
    """
    collection_names = []

    for slot_name in schema_view.class_slots(DATABASE_CLASS_NAME):
        slot_definition = schema_view.induced_slot(slot_name, DATABASE_CLASS_NAME)

        # Filter out any hypothetical (future) slots that don't correspond to a collection (e.g. `db_version`).
        if slot_definition.multivalued and slot_definition.inlined_as_list:
            collection_names.append(slot_name)

        # Filter out duplicate names. This is to work around the following issues in the schema:
        # - https://github.com/microbiomedata/nmdc-schema/issues/1954
        # - https://github.com/microbiomedata/nmdc-schema/issues/1955
        collection_names = list(set(collection_names))

    return collection_names


def get_names_of_classes_eligible_for_collection(schema_view: SchemaView, collection_name: str) -> list[str]:
    r"""
    Returns a list of the names of the classes whose instances can be stored in the specified collection,
    according to the specified `SchemaView`.
    """
    slot_definition = schema_view.induced_slot(collection_name, DATABASE_CLASS_NAME)
    name_of_eligible_class = slot_definition.range
    names_of_eligible_classes = schema_view.class_descendants(name_of_eligible_class)  # includes own class name
    return names_of_eligible_classes


@cache  # memoizes the decorated function
def translate_class_uri_into_schema_class_name(schema_view: SchemaView, class_uri: str) -> Optional[str]:
    r"""
    Returns the name of the schema class that has the specified value as its `class_uri`.

    Example: "nmdc:Biosample" (a `class_uri` value) -> "Biosample" (a class name)

    References:
    - https://linkml.io/linkml/developers/schemaview.html#linkml_runtime.utils.schemaview.SchemaView.all_classes
    - https://linkml.io/linkml/code/metamodel.html#linkml_runtime.linkml_model.meta.ClassDefinition.class_uri
    """
    schema_class_name = None
    all_class_definitions_in_schema = schema_view.all_classes()
    for class_name, class_definition in all_class_definitions_in_schema.items():
        if class_definition.class_uri == class_uri:
            schema_class_name = class_definition.name
            break
    return schema_class_name


def derive_schema_class_name_from_document(schema_view: SchemaView, document: dict) -> Optional[str]:
    r"""
    Returns the name of the schema class, if any, of which the specified document claims to represent an instance.

    This function is written under the assumption that the document has a `type` field whose value is the `class_uri`
    belonging to the schema class of which the document represents an instance. Slot definition for such a field:
    https://github.com/microbiomedata/berkeley-schema-fy24/blob/fc2d9600/src/schema/basic_slots.yaml#L420-L436
    """
    schema_class_name = None
    if "type" in document and isinstance(document["type"], str):
        class_uri = document["type"]
        schema_class_name = translate_class_uri_into_schema_class_name(schema_view, class_uri)
    return schema_class_name


def init_progress_bar() -> Progress:
    r"""
    Initialize a progress bar that shows the elapsed time, M-of-N completed count, and more.

    Reference: https://rich.readthedocs.io/en/stable/progress.html?highlight=progress#columns
    """
    custom_progress = Progress(
        TextColumn("[progress.description]{task.description}"),
        TextColumn("[red]{task.fields[num_violations]}[/red] violations in"),
        MofNCompleteColumn(),
        TextColumn("source documents"),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        BarColumn(),
        TimeElapsedColumn(),
        TextColumn("elapsed"),
        TimeRemainingColumn(elapsed_when_finished=True),
        TextColumn("{task.fields[remaining_time_label]}"),
        console=console,
        refresh_per_second=1,
    )

    return custom_progress


def get_lowercase_key(key_value_pair: tuple) -> str:
    r"""Returns the key from a `(key, value)` tuple, in lowercase."""
    return key_value_pair[0].lower()


def print_section_header(console: Console, text: str) -> None:
    r"""
    Helper function that prints a vertically-padded,
    labeled, horizontal rule to the specified console.

    Reference: https://rich.readthedocs.io/en/stable/console.html#rules
    """
    console.print("")
    console.rule(f"[bold]{text}[/bold]")
    console.print("")


def get_names_of_classes_in_effective_range_of_slot(
    schema_view: SchemaView, slot_definition: linkml_model.SlotDefinition
) -> List[str]:
    r"""
    Determine the slot's "effective" range, by taking into account its `any_of` constraints (if defined).

    Note: The `any_of` constraints constrain the slot's "effective" range beyond that described by the
          induced slot definition's `range` attribute. `SchemaView` does not seem to provide the result
          of applying those additional constraints, so we do it manually here (if any are defined).
          Reference: https://github.com/orgs/linkml/discussions/2101#discussion-6625646

    Reference: https://linkml.io/linkml-model/latest/docs/any_of/
    """

    # Initialize the list to be empty.
    names_of_eligible_target_classes = []

    # If the `any_of` constraint is defined on this slot, use that instead of the `range`.
    if "any_of" in slot_definition and len(slot_definition.any_of) > 0:
        for slot_expression in slot_definition.any_of:
            # Use the slot expression's `range` to get the specified eligible class name
            # and the names of all classes that inherit from that eligible class.
            if slot_expression.range in schema_view.all_classes():
                own_and_descendant_class_names = schema_view.class_descendants(slot_expression.range)
                names_of_eligible_target_classes.extend(own_and_descendant_class_names)
    else:
        # Use the slot's `range` to get the specified eligible class name
        # and the names of all classes that inherit from that eligible class.
        if slot_definition.range in schema_view.all_classes():
            own_and_descendant_class_names = schema_view.class_descendants(slot_definition.range)
            names_of_eligible_target_classes.extend(own_and_descendant_class_names)

    # Remove duplicate class names.
    names_of_eligible_target_classes = list(set(names_of_eligible_target_classes))

    return names_of_eligible_target_classes
