import aiohttp

# Default FireFox user agent, to pretend to be human and pass bot checks
NORMAL_HUMAN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"
)

DEFAULT_GET_HEADERS = {
    # Disguise our request as human, reducing chance of blocking
    # Possibly unnecessary
    "User-Agent": NORMAL_HUMAN_USER_AGENT,
    # Try to make intermediary caches check that the response is fresh before we get it
    # Not sure if this actually does anything, but I think we've had less issues with
    # Aurora since I enabled it
    "Cache-Control": "no-cache",
    # This fixes a Heisenbug with no clear cause: https://github.com/aio-libs/aiohttp/issues/4581
    # Technically it shouldn't be necessary, and actually including it should make
    # things worse, and yet...
    # Should probably include an x-fail test to see if I can remove this.
    "Connection": "keep-alive",
}

DEFAULT_AIOHTTP_TIMEOUT = aiohttp.ClientTimeout(sock_connect=15, sock_read=10)
