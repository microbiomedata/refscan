import linkml_runtime

from refscan.grapher import load_template, is_class_abstract


def test_load_template():
    template = load_template(r"templates/graph.template.html")
    assert isinstance(template, str)
    assert len(template) > 0


def test_is_class_abstract():
    schema_view = linkml_runtime.SchemaView(schema="tests/schemas/schema_with_abstract_class.yaml")
    assert isinstance(schema_view, linkml_runtime.SchemaView)

    assert is_class_abstract("NamedThing", schema_view) is True
    assert is_class_abstract("Car", schema_view) is False
    assert is_class_abstract("Boat", schema_view) is False
