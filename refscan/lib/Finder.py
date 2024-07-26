from typing import List, Optional

from pymongo.database import Database


class Finder:
    r"""
    A class that can be used to find a document in a MongoDB database,
    in a way that uses past searches to try to speed up future searches.
    """

    def __init__(self, database: Database):
        self.db = database

        # Initialize a variable we can use to keep track of the collections in which we most recently found targeted
        # documents.
        #
        # Note: This will enable us to _start_ searching in these same collections next time.
        #
        self.names_of_collections_most_recently_found_in = []
        self.cache_size = 2  # we'll cache up to 2 collection names

    def check_whether_document_having_id_exists_among_collections(
        self, document_id: str, collection_names: List[str]
    ) -> Optional[str]:
        r"""
        Checks whether any document in any of the specified collections has the specified value in its `id` field.
        Returns the name of the first collection, if any, containing such a document. If none of the collections
        contain such a document, the function returns `None`.

        References:
        - https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection.find_one
        """
        names_of_collections_to_search = collection_names.copy()

        # Make a concise alias.
        cache = self.names_of_collections_most_recently_found_in

        # If any cached collection name is among the ones eligible to search, move it to the front of list.
        for cached_collection_name in reversed(cache):  # goes in reverse, so latest addition ends up in front
            if cached_collection_name in collection_names:
                names_of_collections_to_search.remove(cached_collection_name)
                names_of_collections_to_search.insert(0, cached_collection_name)  # makes it the first item

        # Search the collections in their current order.
        name_of_collection_containing_target_document = None
        query_filter = dict(id=document_id)
        for collection_name in names_of_collections_to_search:

            # If we found the document, cache the collection name and stop searching.
            if self.db.get_collection(collection_name).find_one(query_filter, projection=["_id"]) is not None:
                name_of_collection_containing_target_document = collection_name

                # Put this collection name at the front/start of the cache.
                if len(cache) == 0 or cache[0] != collection_name:
                    if collection_name in cache:  # if it's elsewhere in the cache, remove it from the cache
                        cache.remove(collection_name)
                    cache = [collection_name] + cache[0 : self.cache_size - 1]  # prepends item, dropping any excess
                    self.names_of_collections_most_recently_found_in = cache  # persists it to the instance attribute
                break

        return name_of_collection_containing_target_document
