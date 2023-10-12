import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--side-effects",
        action="store_true",
        default=False,
        help="run tests that have side effects, like posting to discord",
    )
    parser.addoption(
        "--slow",
        action="store_true",
        default=False,
        help="run slow tests",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "side_effects: mark test as using real APIs (has side effects)"
    )
    config.addinivalue_line("markers", "slow_benchmark: mark benchmark as slow to run")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--side-effects"):
        skip_real = pytest.mark.skip(reason="need --side-effects option to run")
        for item in items:
            if "side_effects" in item.keywords:
                item.add_marker(skip_real)
    if not config.getoption("--slow"):
        skip_slow = pytest.mark.skip(reason="need --slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
