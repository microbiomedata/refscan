from typing import List, Optional, Dict

from pymongo.database import Database
from pymongo.client_session import ClientSession


class Finder:
    r"""
    A class that can be used to find a document in a MongoDB database, in a way that uses past searches to try to
    speed up future searches.
    """

    def __init__(self, database: Database):
        r"""
        Initializes an instance of the `Finder` class. The instance is bound to the specified MongoDB database.
        """
        self.db = database

        # Initialize our cache of names of collections we most recently found referenced document `id`s in.
        #
        # Note: This is a queue we will use to keep track of which collections we most recently found referenced
        #       document `id`s in. This will enable us to _begin_ searching in those same collections for subsequent
        #       searches. The idea that this will speed things up is based on the assumption that references emanating
        #       from source documents that we process _temporally close_ to one another, likely point to target
        #       documents residing _in the same collections_ as one another.
        #
        self.cached_collection_names_where_recently_found = []
        self.cache_size = 2  # we'll cache up to 2 collection names

        # Initialize our cache of document `id` presences/absences by collection.
        #
        # Note: This is a dictionary we will use to keep track of the referenced `id`s we find in each collection,
        #       and the referenced `id`s we fail to find (i.e. confirm do _not_ exist) in each collection. This will
        #       enable us to avoid querying the database for the same information that we have previously obtained
        #       by querying the database.
        #
        # Note: The top-level items in the dictionary have keys that are collection names and values that are
        #       dictionaries. Each of those dictionaries has keys that are document `id`s and values that are boolean
        #       flags, which indicate whether we know that a document having that `id` exists in that collection
        #       (`True`) or we know that a document having that `id` does _not_ exist in that collection (`False`).
        #       Here's an example value of this attribute:
        #       ```
        #       {
        #           "biosample_set": {"nmdc:bsm-00-000001": True, "nmdc:bsm-00-000002": False},
        #           "study_set": {"nmdc:sty-00-000001": True},
        #       }
        #       ```
        #
        # Note: If this program ever leads to memory consumption (RAM usage) issues in practice, consider
        #       redesigning this cache and/or allowing the user to disable its use.
        #
        self.cached_id_presence_by_collection: Dict[str, Dict[str, bool]] = {}

    def _set_name_of_collection_most_recently_found_in(self, collection_name: str):
        r"""
        Helper function that updates our cache of collection names in which target documents were most recently found,
        so that the specified collection is at the front/start of the list. That will make it so it gets searched first
        next time.
        """
        # Make a concise alias for the instance attribute (both will refer to the same data structure).
        queue = self.cached_collection_names_where_recently_found

        # Check whether either (a) the queue is empty or (b) this collection name is not at the front of the queue.
        # Example: [] is empty, or "b_set" is not the first item in ["a_set", "b_set", "c_set"]
        if len(queue) == 0 or queue[0] != collection_name:

            # If this collection name is already (elsewhere) in the queue, remove it from that position, automatically
            # updating the list indexes of subsequent list items (so there is no "gap" in the list).
            # Example: Removing "b_set" from ["a_set", "b_set", "c_set"] → ["a_set", "c_set"]
            if collection_name in queue:
                queue.remove(collection_name)

            # Prepend this collection name to the beginning of the queue, dropping any excess collection names.
            # Example: Prepending ["b_set"] to ["a_set", "c_set"] → ["b_set", "a_set", "c_set"]
            queue = [collection_name] + queue[0 : self.cache_size - 1]

            # Note: This unnecessary assignment is here only to tell my IDE that `queue` isn't an unused variable.
            self.cached_collection_names_where_recently_found = queue

    def _optimize_collection_search_order(self, names_of_eligible_collections: List[str]) -> List[str]:
        r"""
        Helper function that returns an optimized order in which the specified collections could be searched, in order
        to take advantage of things the instance "remembers" from recent searches.
        """
        ordered_collection_names = names_of_eligible_collections.copy()

        # Iterate over the collection names in the queue, from back (oldest) to front (newest).
        for cached_collection_name in reversed(self.cached_collection_names_where_recently_found):

            # If this cached collection name is among the eligible ones, move it to the front of the list.
            # Example: Since "b_set" is in ["a_set", "b_set", "c_set"] → ["b_set, "a_set", "c_set"]
            if cached_collection_name in names_of_eligible_collections:
                ordered_collection_names.remove(cached_collection_name)
                ordered_collection_names.insert(0, cached_collection_name)

        return ordered_collection_names

    def _set_cached_id_presence_in_collection(self, collection_name: str, document_id: str, is_present: bool) -> None:
        r"""
        Helper function that updates our cache of document `id` presences/absences, setting the presence flag for the
        specified document `id` in the specified collection.
        """
        if collection_name not in self.cached_id_presence_by_collection:
            self.cached_id_presence_by_collection[collection_name] = {}  # creates key if it does not exist
        self.cached_id_presence_by_collection[collection_name][document_id] = is_present

    def _get_cached_id_presence_in_collection(self, collection_name: str, document_id: str) -> Optional[bool]:
        r"""
        Helper function that checks our cache of document `id` presences/absences, returning the presence/absence flag,
        if any, for the specified document `id` in the specified collection.
        """
        if (
            collection_name not in self.cached_id_presence_by_collection
            or document_id not in self.cached_id_presence_by_collection[collection_name]
        ):
            return None
        else:
            return self.cached_id_presence_by_collection[collection_name][document_id]

    def check_whether_document_having_id_exists_among_collections(
        self, document_id: str, collection_names: List[str], client_session: Optional[ClientSession] = None
    ) -> Optional[str]:
        r"""
        Checks whether any document in any of the specified collections has the specified value in its `id` field.
        Returns the name of the first collection, if any, containing such a document. If none of the collections
        contain such a document, the function returns `None`.

        If a `pymongo.client_session.ClientSession` is specified, this function will access the database within
        the context of that session. If a transaction is pending on that session, this feature can be used
        to check whether the specified document _would_ exist if that transaction were to be committed.

        References:
        - https://pymongo.readthedocs.io/en/stable/api/pymongo/collection.html#pymongo.collection.Collection.find_one
        - https://pymongo.readthedocs.io/en/stable/api/pymongo/client_session.html#transactions
        """

        # Initialize the name of the containing collection to `None`.
        name_of_collection_containing_target_document = None

        # Optimize the search order of the collections, based upon the outcomes of recent searches.
        ordered_collection_names = self._optimize_collection_search_order(collection_names)

        # Search the collections.
        query_filter = dict(id=document_id)
        for collection_name in ordered_collection_names:

            # Before querying the database, check our cache of document `id` presences/absences per collection.
            is_id_present: Optional[bool] = self._get_cached_id_presence_in_collection(
                collection_name=collection_name, document_id=document_id
            )

            # If we already know it's _not_ in this collection, stop evaluating this collection and, instead,
            # proceed to evaluate the next collection.
            if is_id_present is False:
                continue  # stop evaluating this collection

            # If we already know it _is_ in this collection, record the collection name, update the cache of names
            # of collections where a referenced document was recently found, and skip searching additional collections.
            if is_id_present is True:
                name_of_collection_containing_target_document = collection_name
                self._set_name_of_collection_most_recently_found_in(collection_name=collection_name)
                break

            # If we find it in the collection in the database, record the collection name, update both (a) the cache
            # of which documents we have found in which collections, and (b) the cache of names of collections where
            # a referenced document was recently found, and skip searching additional collections.
            collection = self.db.get_collection(collection_name)
            if collection.find_one(query_filter, projection=["_id"], session=client_session) is not None:
                name_of_collection_containing_target_document = collection_name

                # Record that a document having this `id` is _present_ in this collection.
                self._set_cached_id_presence_in_collection(
                    collection_name=collection_name, document_id=document_id, is_present=True
                )

                self._set_name_of_collection_most_recently_found_in(collection_name=collection_name)
                break

            # If we made it this far, record that a document having this `id` does _not_ exist in this collection.
            self._set_cached_id_presence_in_collection(
                collection_name=collection_name, document_id=document_id, is_present=False
            )

        return name_of_collection_containing_target_document
