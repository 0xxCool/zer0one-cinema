"""Smoke test: package importable and exposes __version__."""
import zer0one_cinema


def test_version_defined() -> None:
    assert isinstance(zer0one_cinema.__version__, str)
    assert len(zer0one_cinema.__version__) > 0
