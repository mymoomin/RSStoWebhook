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
    - `dailies` is the list of new entries that haven't yet been posted by the
        daily webhook
    - `last_entries`, `feed_hash`, `etag`, and `last_modified` are caching
        information, used to quickly find new updates when checking the comic's
        RSS feed

    Attributes:
        _id: The id of the record in the database.

        title: The name of the webcomic.
        url: The URL of the comic's RSS feed.

        role_id: The ID of the comic's role on the RSS Discord.
        last_entries: The `constants.MAX_CACHED_ENTRIES` most-recently seen entries.
        color: The colour of the comic's Discord embed, as an integer.
            Must be between 0 and 0xFFFFFF (16777215) or Discord complains.
        username: The username of the comic's webhook posts.
            Normally a character from the comic.
        avatar_url: The avatar URL for a comic's webhook posts.
            Must be a valid URL. Normally a picture of a character from the comic.
        dailies: A list of entries that haven't yet been posted to the daily webhook.
            Each entry's `link` must be a valid URL.
        feed_hash: An mmh3-generated hash of the content of the feed.
            Used to early-exit when the feed is unchanged.
        etag: A caching header RSS feeds can use to say when they haven't changed,
            and return a 304 with no content rather than the full feed, saving
            both us and them bandwidth and time. Sadly very rarely used.
        last_modifed: Similar to the above, the date at which the RSS feed was
            last changed. While the header is intended to always be a date in a
            specific format, it sometimes isn't, and in any case we only use it
            as an opaque string, so it's treated as a string here.

    """

    _id: ObjectId
    title: str
    url: str  # Must be a valid URL
    role_id: int
    thread_id: NotRequired[int]
    color: NotRequired[int]  # Must be between 0 and 0xFFFFF
    username: NotRequired[str]
    avatar_url: NotRequired[str]  # Must be a valid URL
    dailies: list[EntrySubset]  # Must have valid URLs
    last_entries: list[EntrySubset]
    feed_hash: bytes
    etag: NotRequired[str]
    last_modified: NotRequired[str]
