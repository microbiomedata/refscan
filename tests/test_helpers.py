from rich.progress import Progress
import linkml_runtime

from refscan.lib.helpers import (
    get_lowercase_key,
    init_progress_bar,
    get_collection_names_from_schema,
    get_names_of_classes_eligible_for_collection,
    get_names_of_classes_in_effective_range_of_slot,
)


def test_get_lowercase_key():
    key_value_tuple = ("FOO_bar", "baz")
    assert get_lowercase_key(key_value_tuple) == "foo_bar"


def test_init_progress_bar():
    assert isinstance(init_progress_bar(), Progress)


def test_get_collection_names_from_schema():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/database_class.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    collection_names = get_collection_names_from_schema(schema_view)
    assert len(collection_names) == 2
    assert "biosample_set" in collection_names
    assert "study_set" in collection_names


def test_get_names_of_classes_eligible_for_collection():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/database_class.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "biosample_set")
    assert len(collection_names) == 1
    assert "Biosample" in collection_names

    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "study_set")
    assert len(collection_names) == 1
    assert "Study" in collection_names

    # Focus on the "is_a" hierarchical relationship.
    collection_names = get_names_of_classes_eligible_for_collection(schema_view, "material_entity_set")
    assert len(collection_names) == 2
    assert "Biosample" in collection_names
    assert "MaterialEntity" in collection_names


def test_get_names_of_classes_in_effective_range_of_slot():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/schema_with_any_of.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    # Test: If `any_of` is present, it is used (instead of the slot's `range`)
    #       and all descendant classes are included.
    slot_definition = schema_view.get_slot("favorite_breakfast")
    class_names = get_names_of_classes_in_effective_range_of_slot(schema_view, slot_definition)
    assert len(class_names) == 3
    assert "Fruit" in class_names  # mentioned clas
    assert "Veggie" in class_names  # mentioned class
    assert "Carrot" in class_names  # child class

    # Test: If `any_of` is absent, the slot's `range` is used.
    slot_definition = schema_view.get_slot("favorite_lunch")
    class_names = get_names_of_classes_in_effective_range_of_slot(schema_view, slot_definition)
    assert len(class_names) == 1
    assert "Meat" in class_names

    # Test: When `range` is used, its descendant classes are also included.
    slot_definition = schema_view.get_slot("favorite_dinner")
    class_names = get_names_of_classes_in_effective_range_of_slot(schema_view, slot_definition)
    assert len(class_names) == 5
    assert "Food" in class_names  # mentioned class
    assert "Fruit" in class_names  # child class
    assert "Meat" in class_names
    assert "Veggie" in class_names
    assert "Carrot" in class_names  # grandchild class
