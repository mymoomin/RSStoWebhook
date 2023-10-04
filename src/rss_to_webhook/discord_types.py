from typing import Required, TypedDict


class Embed(TypedDict):
    color: int  # valid hexcode
    title: str
    url: str  # Valid url
    description: str


class Message(TypedDict, total=False):
    content: str
    username: str
    avatar_url: str  # Valid url
    embeds: Required[list[Embed]]


class Extras(TypedDict, total=False):
    content: str
    color: int
    username: str | None
    avatar_url: str | None
