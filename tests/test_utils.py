import doctest

from rss_to_webhook import utils


def test_docstring() -> None:
    doctest_results = doctest.testmod(utils)
    assert doctest_results.failed == 0
