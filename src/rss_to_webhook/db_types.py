from typing import NotRequired, TypedDict

from bson import ObjectId


class CachingInfo(TypedDict):
    feed_hash: bytes
    last_modified: NotRequired[str]
    etag: NotRequired[str]


class EntrySubset(TypedDict):
    link: str
    id: NotRequired[str]
    title: NotRequired[str]
    published: NotRequired[str]


class Comic(TypedDict):
    _id: ObjectId
    title: str
    url: str  # URL but it causes serialisation issues even though it's just a string
    role_id: int
    thread_id: NotRequired[int]
    color: NotRequired[int]
    username: NotRequired[str]
    avatar_url: NotRequired[str]  # URL but it causes serialisation issues
    dailies: list[EntrySubset]
    last_entries: list[EntrySubset]
    feed_hash: bytes
    etag: NotRequired[str]
    last_modified: NotRequired[str]
