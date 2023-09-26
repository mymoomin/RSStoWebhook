from typing import NotRequired, TypedDict


class Author(TypedDict):
    name: str
    url: str


class Comic(TypedDict):
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


class Extras(TypedDict, total=False):
    content: str
    color: int
    username: str
    avatar_url: str
    thread_id: int
