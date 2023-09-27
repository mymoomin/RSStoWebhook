from rss_to_webhook.worker import make_body


def test_happy_path():
    comic = {
        "name": "Test Webcomic",
    }
    entry = {"link": "https://example.com/page/1"}
    body = make_body(comic, entry)
    assert body == {
        "embeds": [
            {
                "color": 0x5C64F4,
                "title": "**Test Webcomic**",
                "url": "https://example.com/page/1",
                "description": "New Test Webcomic!",
            },
        ],
    }
