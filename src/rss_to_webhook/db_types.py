"""TypedDicts representing types of values stored in the database."""


from typing import NotRequired, TypedDict

from bson import ObjectId


class CachingInfo(TypedDict):
    """Represents metadata used for caching.

    Attributes:
        feed_hash: A hash of the RSS feed.
        last_modified: The value of the "Last-Modified" HTTP header. Most
            RSS feeds don't use this header, so it's optional. We use it only
            as an opague string, so we don't store it as a datetime.
        etag: The value of the "ETag" HTTP header. Again, sadly usually not
            used, so it's optional. It is represented as a sequence of bytes
            cast to a string (e.g. '"f56-6062f676a7367-gzip"', so we type it)
            as a string, even thought bytes would be more intuitive for what's
            essentially a hash.
    """

    feed_hash: bytes
    last_modified: NotRequired[str]
    etag: NotRequired[str]


class EntrySubset(TypedDict, total=False):
    """The subset of `Entry` values that are persisted to the database.

    This is a supertype of `Entry`, so we can also use variables of this type
    to store an RSS feed entry if necessary.
    """

    link: str
    id: NotRequired[str]
    title: NotRequired[str]
    published: NotRequired[str]


class Comic(TypedDict):
    """A single comic as stored in the database.

    The attributes mean what they're called and can be divided into a few subsets.

    - `_id` is a surrogate primary key to quickly locate records in the database
    - `title` and `url` are information about the webcomic itself
    - `role_id`, `thread_id`, `color`, `username`, and `avatar_url` are about
        how new entries of the comic are posted to Discord
    - `last_entries`, `feed_hash`, `etag`, and `last_modified` are caching
        information, used to quickly find new updates when checking the comic's
        RSS feed
    - `dailies` is the list of new entries that haven't yet been posted by the
        daily webhook
    """

    _id: ObjectId
    title: str
    url: str  # Must be a valid URL
    role_id: int
    thread_id: NotRequired[int]
    color: NotRequired[int]
    username: NotRequired[str]
    avatar_url: NotRequired[str]  # must be a valid URL
    dailies: list[EntrySubset]
    last_entries: list[EntrySubset]
    feed_hash: bytes
    etag: NotRequired[str]
    last_modified: NotRequired[str]
