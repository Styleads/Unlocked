import pytest

from fakes import load_schemes  # in fakes.py, not here: "conftest" clashes across test folders
from member2.models import SchemeRecord


@pytest.fixture
def schemes() -> dict[str, SchemeRecord]:
    # Fresh copies per test, so no test can leak mutations into another.
    return load_schemes()
