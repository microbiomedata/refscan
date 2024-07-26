from typing import Optional
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

    # Note: This field contains the name of the collection, if any, in which the targeted document was found.
    #       Its name was designed to emphasize that it is _not_ a collection that the schema allows the document
    #       to exist in, but is instead the collection the document _actually_ exists in. The fact that the latter
    #       is not among the former is why there is a `Violation` instance describing this reference.
    #
    name_of_collection_containing_target: Optional[str] = field()
