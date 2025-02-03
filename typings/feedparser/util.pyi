from time import struct_time
from typing import Literal, Required, TypedDict, type_check_only

@type_check_only
class Feed(TypedDict, total=False):
    title: str
    subtitle: str

@type_check_only
class Entry(TypedDict, total=False):
    link: str
    id: str
    title: str
    published: str
    published_parsed: struct_time
    author: str

class FeedParserDict(TypedDict):
    bozo: Literal[False, 1, True]
    encoding: str
    entries: list[Entry]
    feed: Feed
    version: str
