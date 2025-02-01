import mongomock

from refscan.lib.Finder import Finder


def test_instantiation():
    db = mongomock.MongoClient().db
    finder = Finder(database=db)

    assert isinstance(finder, Finder)
    assert len(finder.names_of_collections_most_recently_found_in) == 0
    assert len(finder.cached_id_presence_by_collection.keys()) == 0


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
