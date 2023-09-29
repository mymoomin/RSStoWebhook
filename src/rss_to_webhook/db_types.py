from typing import NotRequired, TypedDict

from bson import ObjectId


class Author(TypedDict):
    name: str
    url: str


class Comic(TypedDict):
    _id: ObjectId
    name: str
    url: str
    role_id: NotRequired[int]
    color: NotRequired[int]
    author: NotRequired[Author]
    last_entries: list[str]
    hash: bytes
    thread_id: NotRequired[int]
    etag: NotRequired[str]
    last_modified: NotRequired[str]
