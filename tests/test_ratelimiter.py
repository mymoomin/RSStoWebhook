import json
import os
import time
from collections.abc import Generator

import pytest
from dotenv import load_dotenv
from requests import HTTPError
from responses import RequestsMock

from rss_to_webhook.check_feeds_and_update import RateLimiter
from rss_to_webhook.discord_types import Message

load_dotenv(".env.example")
WEBHOOK_URL = os.environ["WEBHOOK_URL"]
SD_WEBHOOK_URL = os.environ["SD_WEBHOOK_URL"]


@pytest.fixture
def message() -> Message:
    return {
        "embeds": [{
            "color": 0,
            "title": "**Test Page**",
            "url": "https://example.com",
            "description": "New Test Comic!",
        }],
        "username": "Tester",
        "avatar_url": "https://i.imgur.com/XYbqy7f.png",
        "content": "<@everyone>",
    }


@pytest.fixture
def webhook() -> Generator[RequestsMock, None, None]:
    with RequestsMock(assert_all_requests_are_fired=False) as responses:
        responses.post(
            WEBHOOK_URL,
            status=200,
            headers={
                "x-ratelimit-limit": "5",
                "x-ratelimit-remaining": "4",
                "x-ratelimit-reset-after": "0.399",
            },
        )
        yield responses


@pytest.fixture
def measure_sleep(monkeypatch: pytest.MonkeyPatch) -> list[float]:
    sleeps = []

    def log_sleep(time: float) -> None:
        sleeps.append(time)

    monkeypatch.setattr(time, "sleep", log_sleep)
    return sleeps


def test_pauses_at_hidden_rate_limit(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    rate_limiter = RateLimiter()
    start = time.time()
    for _i in range(30):
        rate_limiter.post(WEBHOOK_URL, message)
    duration = time.time() - start
    # At this point, the sleep is queued for the next iteration
    assert len(measure_sleep) == 0
    rate_limiter.post(WEBHOOK_URL, message)
    # And here the sleep has taken place
    assert len(measure_sleep) == 1
    assert measure_sleep[0] <= RateLimiter.fuzzed_window
    assert duration + measure_sleep[0] >= RateLimiter.fuzzed_window
    assert duration + measure_sleep[0] < RateLimiter.fuzzed_window + 1


def test_pauses_repeatedly_at_hidden_rate_limit(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    runs = 61
    rate_limiter = RateLimiter()
    for _i in range(runs):
        rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == (runs - 1) // 30
    assert all(
        RateLimiter.fuzzed_window - 0.5 < sleep_duration < RateLimiter.fuzzed_window
        for sleep_duration in measure_sleep
    )


def test_only_pauses_when_rate_limited(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    rate_limiter = RateLimiter()
    rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == 0
    webhook.post(
        WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "1",
        },
    )
    # queues delay
    rate_limiter.post(WEBHOOK_URL, message)
    webhook.post(
        WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "1",
            "x-ratelimit-reset-after": "1",
        },
    )
    # experiences delay but doesn't queue a delay
    rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == 1
    assert measure_sleep[0] == 1
    # no delay
    rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == 1


def test_buckets_rate_limits_by_url(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    rate_limiter = RateLimiter()
    webhook.post(
        SD_WEBHOOK_URL,
        status=200,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "1",
        },
    )
    rate_limiter.post(WEBHOOK_URL, message)
    rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == 0
    rate_limiter.post(SD_WEBHOOK_URL, message)
    rate_limiter.post(SD_WEBHOOK_URL, message)
    assert len(measure_sleep) == 1
    rate_limiter.post(WEBHOOK_URL, message)
    assert len(measure_sleep) == 1
    rate_limiter.post(SD_WEBHOOK_URL, message)
    # The number of times SD_WEBHOOK_URL has been posted to, minus one
    assert len(measure_sleep) == 2  # noqa: PLR2004


def test_raises_exception_on_error(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    rate_limiter = RateLimiter()
    error_message = (
        '{"message": "Invalid Form Body", "code": 50035, "errors": {"embeds": {"0":'
        ' {"url": {"_errors": [{"code": "URL_TYPE_INVALID_URL", "message": "Not a well'
        ' formed URL."}]}}}}}'
    )
    webhook.post(
        SD_WEBHOOK_URL,
        status=400,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "1",
            "x-ratelimit-reset-after": "1",
        },
        body=json.dumps(error_message),
    )
    webhook.post(
        SD_WEBHOOK_URL,
        status=400,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "0",
            "x-ratelimit-reset-after": "1",
        },
        body=json.dumps(error_message),
    )
    message["embeds"][0]["url"] = "https://urls don't have spaces.com"
    with pytest.raises(HTTPError):
        rate_limiter.post(SD_WEBHOOK_URL, message)


def test_raises_exception_on_429(
    message: Message, webhook: RequestsMock, measure_sleep: list[float]
) -> None:
    rate_limiter = RateLimiter()
    error_message = (
        '{"message": "Invalid Form Body", "code": 50035, "errors": {"embeds": {"0":'
        ' {"url": {"_errors": [{"code": "URL_TYPE_INVALID_URL", "message": "Not a well'
        ' formed URL."}]}}}}}'
    )
    webhook.post(
        SD_WEBHOOK_URL,
        status=429,
        headers={
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "1",
            "x-ratelimit-reset-after": "1",
        },
        body=json.dumps(error_message),
    )
    webhook.post(
        SD_WEBHOOK_URL,
        status=400,
        headers={
            "retry-after": "1",
            "x-ratelimit-limit": "5",
            "x-ratelimit-remaining": "4",
            "x-ratelimit-reset-after": "0.399",
            "x-ratelimit-scope": "shared",
        },
        json={
            "message": "The resource is being rate limited.",
            "retry_after": 0.529,
            "global": False,
        },
    )
    message["embeds"][0]["url"] = "https://urls don't have spaces.com"
    with pytest.raises(HTTPError) as e:
        rate_limiter.post(SD_WEBHOOK_URL, message)
    assert "429" in str(e.value)
