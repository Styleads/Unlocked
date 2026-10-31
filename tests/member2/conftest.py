import json
from pathlib import Path

import pytest

from member2.models import SchemeRecord

FIXTURES = Path(__file__).parent / "fixtures" / "schemes.json"


def load_schemes() -> dict[str, SchemeRecord]:
    data = json.loads(FIXTURES.read_text(encoding="utf-8"))
    return {s["id"]: SchemeRecord.model_validate(s) for s in data["schemes"]}


@pytest.fixture
def schemes() -> dict[str, SchemeRecord]:
    # Fresh copies per test, so no test can leak mutations into another.
    return load_schemes()
