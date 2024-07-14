from dataclasses import dataclass, field


@dataclass(frozen=True, order=True)
class Violation:
    """
    A specific reference that lacks integrity.
    """

    source_collection_name: str = field()
    source_field_name: str = field()
    source_document_object_id: str = field()
    source_document_id: str = field()
    target_id: str = field()
