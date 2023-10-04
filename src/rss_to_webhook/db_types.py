from typing import Any, NotRequired, Self, TypedDict
from urllib.parse import urlsplit

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


class URL(str):
    def __new__(cls: type[Self], *value: Any) -> Self:  # noqa: ANN401
        if value:
            v0 = value[0]
            if not isinstance(v0, str):
                message = f'Unexpected type for URL: "{type(v0)}"'
                raise TypeError(message)
            scheme, netloc, _path, _query, _fragment = urlsplit(v0)
            if scheme not in {"http", "https"}:
                error = f"{v0}: Invalid URL scheme (can only be 'http' or 'https')"
                raise ValueError(error)
            if "." not in netloc:
                error = f"{v0}: no '.' in netloc"
                raise ValueError(error)

        return str.__new__(cls, *value)


class Comic(TypedDict):
    _id: NotRequired[ObjectId]
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
