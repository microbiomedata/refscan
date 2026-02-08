import mongomock
import pytest

from refscan.lib.Finder import Finder


def test_finder_finds_documents():
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    # Seed database.
    db["foo_set"].insert_many(
        [
            {"id": "a"},
            {"id": "b"},
            {"id": "c"},
        ]
    )
    db["bar_set"].insert_many(
        [
            {"id": "d"},
            {"id": "e"},
            {"id": "f"},
        ]
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="a",
            collection_names=["foo_set", "bar_set"],  # multiple collections
        )
        == "foo_set"
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="f",
            collection_names=["bar_set"],  # one collection
        )
        == "bar_set"
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="a",
            collection_names=[],  # no collections
        )
        is None
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="a",
            collection_names=["bar_set"],  # wrong collection
        )
        is None
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="a",
            collection_names=["qux_set"],  # nonexistent collection
        )
        is None
    )

    assert (
        finder.check_whether_document_having_id_exists_among_collections(
            document_id="g",  # nonexistent id
            collection_names=["foo_set", "bar_set"],
        )
        is None
    )


def test_finder_finds_documents_having_type_and_value_in_field():
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    # Seed database.
    db["company_set"].insert_many(
        [
            {"id": "a", "type": "refscan:Company"},
            {"id": "b", "type": "refscan:Company"},
            {"id": "c", "type": "refscan:Company", "owns_shares_of": "a"},
        ]
    )
    db["person_set"].insert_many(
        [
            {"id": "d", "type": "refscan:Employee", "works_for": "a"},
            {"id": "e", "type": "refscan:Employee", "works_for": "a"},
            {"id": "f", "type": "refscan:Employee", "works_for": "b"},
            {"id": "g", "type": "refscan:Investor", "owns_shares_of": ["a", "b"]},
            {"id": "h", "type": "refscan:Investor", "owns_shares_of": "a"},
        ]
    )

    document_descriptors = finder.find_documents_having_type_and_value_in_field(
        collection_name="person_set",
        type_and_field_name_tuples=[
            ("refscan:Employee", "works_for"),
        ],
        value="a",
    )
    assert len(document_descriptors) == 2
    assert set(d["id"] for d in document_descriptors) == {"d", "e"}

    # Test case: Include the name of a field whose value is sometimes a list and sometimes a string.
    document_descriptors = finder.find_documents_having_type_and_value_in_field(
        collection_name="person_set",
        type_and_field_name_tuples=[
            ("refscan:Investor", "owns_shares_of"),
        ],
        value="a",
    )
    assert len(document_descriptors) == 2
    assert set(d["id"] for d in document_descriptors) == {"g", "h"}

    # Test case: Include multiple `type`-and-`field_name` tuples.
    document_descriptors = finder.find_documents_having_type_and_value_in_field(
        collection_name="person_set",
        type_and_field_name_tuples=[
            ("refscan:Employee", "works_for"),
            ("refscan:Investor", "owns_shares_of"),
        ],
        value="a",
    )
    assert len(document_descriptors) == 4
    assert set(d["id"] for d in document_descriptors) == {"d", "e", "g", "h"}

    # Test case: Specify a collection that does not contain documents of the specified type.
    document_descriptors = finder.find_documents_having_type_and_value_in_field(
        collection_name="company_set",
        type_and_field_name_tuples=[
            ("refscan:Employee", "works_for"),
        ],
        value="a",
    )
    assert len(document_descriptors) == 0

    # Test case: Specify a collection that does not contain documents of the specified type,
    #            although it does contain documents having fields having the specified name.
    document_descriptors = finder.find_documents_having_type_and_value_in_field(
        collection_name="company_set",
        type_and_field_name_tuples=[
            ("refscan:Employee", "owns_shares_of"),
        ],
        value="a",
    )
    assert len(document_descriptors) == 0


@pytest.mark.xfail(raises=NotImplementedError)
def test_finder_finds_documents_within_session():
    r"""
    TODO: Consider introducing a real MongoDB server into the test suite, and then
          implementing a test demonstrating the use of a MongoDB session.
    """
    raise NotImplementedError(
        "The test suite uses mongomock instead of a real MongoDB server, and mongomock does not support sessions."
    )


def test_finder_manages_queue_correctly():
    r"""
    Note: This test targets internal functionality of the class.
    """
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    assert finder.cache_size == 2

    # Case: Inserting collection name into empty queue.
    assert finder.cached_collection_names_where_recently_found == []
    finder._set_name_of_collection_most_recently_found_in("a_set")
    assert finder.cached_collection_names_where_recently_found == ["a_set"]

    # Case: Inserting collection name into nonempty queue.
    finder._set_name_of_collection_most_recently_found_in("b_set")
    assert finder.cached_collection_names_where_recently_found == ["b_set", "a_set"]

    # Case: Inserting collection name already at front of queue.
    finder._set_name_of_collection_most_recently_found_in("b_set")
    assert finder.cached_collection_names_where_recently_found == ["b_set", "a_set"]

    # Case: Inserting collection name not at front of queue.
    finder._set_name_of_collection_most_recently_found_in("a_set")
    assert finder.cached_collection_names_where_recently_found == ["a_set", "b_set"]

    # Case: Inserting excessive collection name.
    finder._set_name_of_collection_most_recently_found_in("c_set")
    assert finder.cached_collection_names_where_recently_found == ["c_set", "a_set"]


def test_finder_optimizes_collection_search_order():
    r"""
    Note: This test targets internal functionality of the class.
    """
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    finder.cached_collection_names_where_recently_found = ["a_set", "b_set", "c_set"]
    assert finder._optimize_collection_search_order(["c_set", "d_set", "a_set"]) == ["a_set", "c_set", "d_set"]


def test_finder_id_caching_disabled_by_default():
    r"""
    Verify that ID caching is disabled by default, meaning queries always hit the database
    and no data is stored in the cache dictionary.
    """
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    # Verify caching is disabled by default
    assert finder.enable_id_caching is False

    # Seed database
    db["test_set"].insert_one({"id": "test-001"})

    # First query should find the document
    result = finder.check_whether_document_having_id_exists_among_collections(
        document_id="test-001",
        collection_names=["test_set"],
    )
    assert result == "test_set"

    # Cache should remain empty since caching is disabled
    assert finder.cached_id_presence_by_collection == {}

    # Second query should also hit the database (not use cache)
    result = finder.check_whether_document_having_id_exists_among_collections(
        document_id="test-001",
        collection_names=["test_set"],
    )
    assert result == "test_set"

    # Cache should still be empty
    assert finder.cached_id_presence_by_collection == {}


def test_finder_id_caching_when_enabled():
    r"""
    Verify that when ID caching is enabled, the Finder caches presence/absence
    information and uses it to avoid redundant database queries.
    """
    db = mongomock.MongoClient().db
    finder = Finder(database=db, enable_id_caching=True)

    # Verify caching is enabled
    assert finder.enable_id_caching is True

    # Seed database
    db["test_set"].insert_one({"id": "test-001"})

    # First query should find the document
    result = finder.check_whether_document_having_id_exists_among_collections(
        document_id="test-001",
        collection_names=["test_set"],
    )
    assert result == "test_set"

    # Cache should now contain the presence information
    assert "test_set" in finder.cached_id_presence_by_collection
    assert finder.cached_id_presence_by_collection["test_set"]["test-001"] is True

    # Query for a non-existent document
    result = finder.check_whether_document_having_id_exists_among_collections(
        document_id="test-002",
        collection_names=["test_set"],
    )
    assert result is None

    # Cache should now also contain the absence information
    assert finder.cached_id_presence_by_collection["test_set"]["test-002"] is False

    # Verify the cache is being used by checking internal method
    assert finder._get_cached_id_presence_in_collection("test_set", "test-001") is True
    assert finder._get_cached_id_presence_in_collection("test_set", "test-002") is False


def test_finder_id_caching_memory_usage():
    r"""
    Verify that with caching disabled, the cache dictionary doesn't accumulate data
    even after many queries, ensuring minimal memory usage.
    """
    db = mongomock.MongoClient().db
    finder_no_cache = Finder(database=db, enable_id_caching=False)
    finder_with_cache = Finder(database=db, enable_id_caching=True)

    # Seed database with multiple documents
    test_ids = [f"test-{i:03d}" for i in range(100)]
    db["test_set"].insert_many([{"id": doc_id} for doc_id in test_ids[:50]])

    # Query many documents with caching disabled
    for doc_id in test_ids:
        finder_no_cache.check_whether_document_having_id_exists_among_collections(
            document_id=doc_id,
            collection_names=["test_set"],
        )

    # Query many documents with caching enabled
    for doc_id in test_ids:
        finder_with_cache.check_whether_document_having_id_exists_among_collections(
            document_id=doc_id,
            collection_names=["test_set"],
        )

    # With caching disabled, the cache should remain empty
    assert finder_no_cache.cached_id_presence_by_collection == {}

    # With caching enabled, the cache should contain all queried IDs
    assert len(finder_with_cache.cached_id_presence_by_collection["test_set"]) == 100
