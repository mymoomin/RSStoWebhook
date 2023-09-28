import pytest

from rss_to_webhook.db_types import Comic
from rss_to_webhook.worker import get_headers


@pytest.fixture()
def comic() -> Comic:
    return Comic(
        name="Test Webcomic",
        url="https://example.com/rss",
        hash=b"\xa9\x0c\x16\xe5\xe2\x8c6\xdd\x01}K\x85\x1fn\x8e\xd2",
        last_entries=["https://example.com/page/1"],
    )


def test_no_caching_headers(comic: Comic) -> None:
    """
    Tests that when the comic has no caching headers, none are returned
    """
    caching_headers = get_headers(comic)
    assert caching_headers == {}


def test_etag(comic: Comic) -> None:
    """
    Tests that when the comic has only an etag, it is returned with the correct name
    """
    comic["etag"] = "f56-6062f676a7367-gzip"
    caching_headers = get_headers(comic)
    assert caching_headers == {"If-None-Match": "f56-6062f676a7367-gzip"}


def test_last_modified(comic: Comic) -> None:
    """
    Tests that when the comic has only an last-modified, it is returned with
    the correct name
    """
    comic["last_modified"] = "Wed, 22 Mar 2023 00:15:35 GMT"
    caching_headers = get_headers(comic)
    assert caching_headers == {"If-Modified-Since": "Wed, 22 Mar 2023 00:15:35 GMT"}


def test_both_caching_headers(comic: Comic) -> None:
    """
    Tests that when the comic has both caching headers, both are returned
    with the correct names
    """
    comic["etag"] = "f56-6062f676a7367-gzip"
    comic["last_modified"] = "Wed, 22 Mar 2023 00:15:35 GMT"
    caching_headers = get_headers(comic)
    assert caching_headers == {
        "If-None-Match": "f56-6062f676a7367-gzip",
        "If-Modified-Since": "Wed, 22 Mar 2023 00:15:35 GMT",
    }
