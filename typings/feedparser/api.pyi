from datetime import datetime
from time import struct_time

from .util import FeedParserDict

def parse(
    url_file_stream_or_string: str,
    etag: str | None = None,
    modified: str | datetime | struct_time | None = None,
    agent: str | None = None,
    referrer: str | None = None,
    handlers: list | None = None,
    request_headers: dict[str, str] | None = None,
    response_headers: dict[str, str] | None = None,
    resolve_relative_uris: bool | None = None,
    sanitize_html: bool | None = None,
) -> FeedParserDict: ...
