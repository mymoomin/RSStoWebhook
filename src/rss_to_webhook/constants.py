import aiohttp

# Default FireFox user agent, to pretend to be human and pass bot checks
NORMAL_HUMAN_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:96.0) Gecko/20100101 Firefox/96.0"
)

CUSTOM_USER_AGENT = "rss-to-webhook update checker"

DEFAULT_GET_HEADERS = {
    # Use our own user agent -- aiohttp's default one is blocked by Tumblr as seen in
    # [192de2b](https://github.com/mymoomin/RSStoWebhook/commit/192de2b456810174aa09b6feac6a7b05f695a001)
    # and not having one causes errors with a lot of sites, as seen in
    # [c45d8b7](https://github.com/mymoomin/RSStoWebhook/commit/c45d8b7a8cdb3507f0a407f2e453e1ebde284e14).
    # This used to just use FireFox's, but that felt like bad form.
    # If this starts getting 403s, I will switch back to pretending to be human
    "User-Agent": CUSTOM_USER_AGENT,
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
