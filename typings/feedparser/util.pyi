from time import struct_time
from typing import List, Literal, Required, TypedDict, type_check_only

@type_check_only
class Feed(TypedDict, total=False):
    title: str
    subtitle: str

@type_check_only
class Entry(TypedDict, total=False):
    link: Required[str]
    id: str
    title: str
    published: str
    published_parsed: struct_time
    author: str

class FeedParserDict:
    bozo: Literal[False] | Literal[1]
    encoding: str
    entries: List[Entry]
    feed: Feed
    version: str
