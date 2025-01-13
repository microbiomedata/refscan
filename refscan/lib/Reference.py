from dataclasses import dataclass, field


@dataclass(frozen=True, order=True)
class Reference:
    """
    A generic reference to a document in a collection.

    Note: `frozen` means the instances are immutable.
    Note: `order` means the instances have methods that help with sorting. For example, an `__eq__` method that
          can be used to compare instances of the class as though they were tuples of those instances' fields.
    """

    source_collection_name: str = field()  # e.g. "study_set"
    source_class_name: str = field()  # e.g. "Study"
    source_field_name: str = field()  # e.g. "part_of"
    target_collection_name: str = field()  # e.g. "study_set" (reminder: a study can be part of another study)
    target_class_name: str = field()  # e.g. "Study"

    def __eq__(self, other):
        r"""
        Determines whether an instance of this class is equal to the specified "other" value.

        Note: This method dictates what will happen under the hood when the `==` operator is used.
              Reference: https://docs.python.org/3/reference/datamodel.html#object.__eq__
        """

        if not isinstance(other, Reference):
            return False
        else:
            return (
                self.source_collection_name == other.source_collection_name
                and self.source_class_name == other.source_class_name
                and self.source_field_name == other.source_field_name
                and self.target_collection_name == other.target_collection_name
                and self.target_class_name == other.target_class_name
            )
