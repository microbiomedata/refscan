from dataclasses import dataclass, field


@dataclass(frozen=True, order=True)
class Reference:
    """
    A generic reference to a document in a collection.

    Note: `frozen` means the instances are immutable.
    Note: `order` means the instances have methods that help with sorting. For example, an `__eq__` method that
          can be used to compare instances of the class as thought they were tuples of those instances' fields.
    """

    source_collection_name: str = field()  # e.g. "study_set"
    source_class_name: str = field()  # e.g. "Study"
    source_field_name: str = field()  # e.g. "part_of"
    target_collection_name: str = field()  # e.g. "study_set" (reminder: a study can be part of another study)
    target_class_name: str = field()  # e.g. "Study"
