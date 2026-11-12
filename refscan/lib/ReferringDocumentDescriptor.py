from typing import TypedDict

from bson import ObjectId


class ReferringDocumentDescriptor(TypedDict):
    """
    A custom type that describes the items of the list returned by the function,
    `refscan.scanner.identify_referring_documents`.

    Docs: https://typing.python.org/en/latest/spec/typeddict.html
    """

    source_collection_name: str
    """The name of the collection in which the referring document resides."""

    source_class_name: str
    """The name of the class of which the referring document represent an instance."""

    source_document_object_id: ObjectId
    """The value in the referring document's `_id` field."""

    source_document_id: str
    """The value in the referring document's `id` field."""
