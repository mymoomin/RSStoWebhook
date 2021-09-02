from typing import TypedDict


class Author(TypedDict):
    name: str
    url: str


class Comic(TypedDict):
    name: str
    url: str
    role_id: int
    color: int
    author: Author
    last_entries: list[str]
    hash: bytes
