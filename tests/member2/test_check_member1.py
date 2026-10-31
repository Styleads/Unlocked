import json
from pathlib import Path

from member2.check_member1 import contract_problems, main

FIXTURES = Path(__file__).parent / "fixtures" / "schemes.json"


def test_fixture_runs_through_pipeline(capsys):
    main(["x", str(FIXTURES)])
    out = capsys.readouterr().out
    assert "4 scheme(s) read." in out
    assert "PIPELINE FAILED" not in out
    assert "demo_scholarship_a:" in out


def test_contract_problems_flags_drift():
    raw = {
        "name": "Demo X", "verification_status": "maybe", "weird": 1,
        "requirements": [{"criterion": "Income below limit"}, "oops"],
        "documents": ["Income Certificate"],
    }
    text = "\n".join(contract_problems(raw))
    for expected in ("missing 'id'", "unexpected field 'weird'", "verification_status",
                     "no source_url", "no verbatim evidence", "requirements[1] is a str",
                     "documents[0] is a plain string"):
        assert expected in text


def test_broken_file_reports_short_errors(tmp_path, capsys):
    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps([{"name": "Demo X", "requirements": ["oops"]}]), encoding="utf-8")
    assert main(["x", str(bad)]) == 1
    out = capsys.readouterr().out
    assert "PIPELINE FAILED" in out
    assert "  - id: Field required" in out
    assert "errors.pydantic.dev" not in out


def test_unreadable_file(tmp_path, capsys):
    assert main(["x", str(tmp_path / "missing.json")]) == 2
