from refscan.lib.Reference import Reference


def test_eq():
    ref_a = Reference(
        source_collection_name="foo_set",
        source_class_name="Foo",
        source_field_name="owns",
        target_collection_name="bar_set",
        target_class_name="Bar",
    )
    ref_b = Reference(
        source_collection_name="foo_set",
        source_class_name="Foo",
        source_field_name="owns",
        target_collection_name="bar_set",
        target_class_name="Baz",  # not "Bar"
    )
    ref_c = Reference(
        source_collection_name="foo_set",
        source_class_name="Foo",
        source_field_name="owns",
        target_collection_name="bar_set",
        target_class_name="Bar",
    )

    # Focus on `==`.
    assert ref_a == ref_a
    assert ref_a != ref_b
    assert ref_a == ref_c

    assert ref_b != ref_a
    assert ref_b == ref_b
    assert ref_b != ref_c

    assert ref_c == ref_a
    assert ref_c != ref_b
    assert ref_c == ref_c

    # Focus on `in`.
    assert ref_a in [ref_a, ref_b, ref_c]
    assert ref_b in [ref_a, ref_b, ref_c]
    assert ref_c in [ref_a, ref_b, ref_c]

    assert ref_a not in [ref_b]

    # Focus on `is`.
    assert ref_a is ref_a
    assert ref_a is not ref_c  # equal, but not identical
