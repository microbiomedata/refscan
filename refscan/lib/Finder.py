from typing import List

from pymongo.database import Database


class Finder:
    r"""
    A class that can be used to find a document in a MongoDB database,
    in a way that uses past searches to try to speed up future searches.
    """

    def __init__(self, database: Database):
        self.db = database

        # Initialize a variable we can use to keep track of the collection in which we most recently found a document.
        #
        # Note: This will enable us to _start_ searching in that same collection (if it's among the eligible ones)
        #       the next time we are trying to find any document.
        #
        self.name_of_most_recently_found_in_collection = None

    def check_whether_document_having_id_exists_among_collections(
        self, document_id: str, collection_names: List[str]
    ) -> bool:
        r"""
        Checks whether any documents in any of the specified collections
        have the specified value in their `id` field. Returns `True` if
        any does; else returns `False`.

        References:
        - https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection.find_one
        """
        names_of_collections_to_search = collection_names.copy()

        # If our cached collection name is among the ones eligible to search, move it to the front of the list.
        cached_collection_name = self.name_of_most_recently_found_in_collection  # makes a more concise alias
        if cached_collection_name in collection_names:
            names_of_collections_to_search.remove(cached_collection_name)
            names_of_collections_to_search.insert(0, cached_collection_name)  # makes it the first item

        # Search the collections in their current order.
        is_found = False
        query_filter = dict(id=document_id)
        for collection_name in names_of_collections_to_search:
            is_found = self.db.get_collection(collection_name).find_one(query_filter, projection=["_id"]) is not None

            # If we found the document, cache the collection name and stop searching.
            if is_found:
                self.name_of_most_recently_found_in_collection = collection_name
                break

        return is_found
