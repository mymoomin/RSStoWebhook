from typing import Optional, TypedDict


class Author(TypedDict):
    name: str
    url: str


class Comic(TypedDict):
    name: str
    url: str
    role_id: Optional[int]
    color: Optional[int]
    author: Optional[Author]
    last_entries: list[str]
    hash: bytes
    thread_id: Optional[int]


class Extras(TypedDict, total=False):
    content: str
    color: int
    username: str
    avatar_url: str
    thread_id: int


class Entry(TypedDict):
    link: str
    title: Optional[str]
