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
