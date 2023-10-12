import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--slow", action="store_true", default=False, help="run slow tests"
    )
    parser.addoption(
        "--slow-benchmarks",
        action="store_true",
        default=False,
        help="run slow benchmarks",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "slow: mark test as slow to run")
    config.addinivalue_line("markers", "slow_benchmark: mark benchmark as slow to run")


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    if not config.getoption("--slow"):
        skip_slow = pytest.mark.skip(reason="need --slow option to run")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
    if not config.getoption("--slow-benchmarks"):
        skip_benchmark = pytest.mark.skip(reason="need --slow-benchmarks option to run")
        for item in items:
            if "slow_benchmark" in item.keywords:
                item.add_marker(skip_benchmark)
