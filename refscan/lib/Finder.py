from typing import List, Optional, Dict

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

        # Initialize a dictionary we can use to keep track of the referenced `id`s we have found in a given collection,
        # and the referenced `id`s we have confirmed do _not_ exist in a given collection.
        #
        # The top-level items have keys that are collection names and values that are dictionaries. The latter
        # dictionaries have keys that are `id` values and values that are boolean flags. The boolean flags indicate
        # whether we have found a document having that `id` in that collection; where `True` means we have,
        # and `False` means we search and _did not_ find such a document in that collection.
        #
        # Example:
        # ```
        # {
        #     "biosample_set": {"bsm-00-000001": True, "bsm-00-000002": False},
        #     "study_set": {"sty-00-000001": True},
        # }
        # ```
        #
        # Note: This will enable us to _avoid_ searching for the same `id` values in the same collections in the future,
        #       decreasing execution time (in exchange for memory consumption).
        #
        # TODO: Measure memory usage when scanning the NMDC database, reverting this perf. optimization if necessary.
        #
        self.cached_id_presence_by_collection: Dict[str, Dict[str, bool]] = {}

    def _set_cached_id_presence_in_collection(self, collection_name: str, document_id: str, is_present: bool) -> None:
        r"""
        Helper function that updates our cache of `id` presences/absences, setting the presence flag for the specified
        document `id` in the specified collection.
        """
        if collection_name not in self.cached_id_presence_by_collection:
            self.cached_id_presence_by_collection[collection_name] = {}
        self.cached_id_presence_by_collection[collection_name][document_id] = is_present

    def _get_cached_id_presence_in_collection(self, collection_name: str, document_id: str) -> Optional[bool]:
        r"""
        Helper function that checks our cache of `id` presences/absences, getting the presence/absence flag, if any,
        for the specified document `id` in the specified collection.
        """
        if (
            collection_name not in self.cached_id_presence_by_collection
            or document_id not in self.cached_id_presence_by_collection[collection_name]
        ):
            return None
        else:
            return self.cached_id_presence_by_collection[collection_name][document_id]

    def check_whether_document_having_id_exists_among_collections(
        self, document_id: str, collection_names: List[str]
    ) -> Optional[str]:
        r"""
        Checks whether any document in any of the specified collections has the specified value in its `id` field.
        Returns the name of the first collection, if any, containing such a document. If none of the collections
        contain such a document, the function returns `None`.

        TODO: This function refers to "cache" as though we are only dealing with one—but we are now dealing with two
              (see the two instance attributes of this class). The outstanding task here is to update the comments
              in this function to be more specific about which cache is being referenced in a given statement.

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

            # Before querying the database, check our in-memory record of `id` presences in this collection.
            is_id_present: Optional[bool] = self._get_cached_id_presence_in_collection(
                collection_name=collection_name, document_id=document_id
            )

            # If we already know it's _not_ in this collection, stop evaluating this collection and, instead,
            # proceed to evaluate the next collection.
            if is_id_present is False:
                continue  # stop evaluating this collection

            # If we _don't know_ whether it is in the collection or not, we can't take any shortcuts. Aw, shucks.
            if is_id_present is None:
                pass

            # If it _is_ in this collection—based on either what we already know, or what we find now—cache
            # the collection name and skip searching additional collections for documents having this `id`.
            collection = self.db.get_collection(collection_name)
            if is_id_present or collection.find_one(query_filter, projection=["_id"]) is not None:
                name_of_collection_containing_target_document = collection_name

                # Put this collection name at the front/start of the cache.
                if len(cache) == 0 or cache[0] != collection_name:
                    if collection_name in cache:  # if it's elsewhere in the cache, remove it from the cache
                        cache.remove(collection_name)
                    cache = [collection_name] + cache[0 : self.cache_size - 1]  # prepends item, dropping any excess
                    self.names_of_collections_most_recently_found_in = cache  # persists it to the instance attribute

                # Record that a document having this `id` _exists_ in this collection.
                # Note: This assignment will be redundant if we got here due to `is_id_present` being `True`.
                self._set_cached_id_presence_in_collection(
                    collection_name=collection_name, document_id=document_id, is_present=True
                )

                break

            # Record that a document having this `id` does _not_ exist in this collection.
            self._set_cached_id_presence_in_collection(
                collection_name=collection_name, document_id=document_id, is_present=False
            )

        return name_of_collection_containing_target_document
