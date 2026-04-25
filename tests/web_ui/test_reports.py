from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from web_ui.app.services.reports import (
    ReportResult, generate_report, render_csv, render_json,
)
from web_ui.app.services.validation import ReportRequest


def _entry(eid, payload):
    return {"id": eid, "payload": payload}


@pytest.fixture
def storage_with_entries():
    storage = MagicMock()
    storage.list_entries.return_value = [
        _entry("u1", {
            "original_text": "first",
            "entry_type": "note",
            "category": "a",
            "created_at": "2026-04-10T00:00:00+00:00",
        }),
        _entry("u2", {
            "original_text": "second",
            "entry_type": "decision",
            "category": "b",
            "created_at": "2026-04-15T00:00:00+00:00",
        }),
        _entry("u3", {
            "original_text": "third",
            "entry_type": "note",
            "category": "a",
            "created_at": "2026-04-20T00:00:00+00:00",
        }),
    ]
    return storage


def test_generate_report_projects_columns(storage_with_entries):
    req = ReportRequest(
        title="My report",
        namespace="alpha",
        columns=["id", "category", "created_at"],
        max_rows=100,
    )
    result = generate_report(storage_with_entries, req)
    assert isinstance(result, ReportResult)
    assert result.title == "My report"
    assert result.columns == ["id", "category", "created_at"]
    assert result.row_count == 3
    assert result.rows[0] == ["u1", "a", "2026-04-10T00:00:00+00:00"]


def test_generate_report_filters_by_entry_type(storage_with_entries):
    req = ReportRequest(
        title="Notes only",
        namespace="alpha",
        columns=["id"],
        entry_type="note",
        max_rows=100,
    )
    result = generate_report(storage_with_entries, req)
    assert result.row_count == 2
    assert [r[0] for r in result.rows] == ["u1", "u3"]


def test_generate_report_filters_by_date_range(storage_with_entries):
    req = ReportRequest(
        title="Mid range",
        namespace="alpha",
        columns=["id"],
        date_from="2026-04-12T00:00:00+00:00",
        date_to="2026-04-18T00:00:00+00:00",
        max_rows=100,
    )
    result = generate_report(storage_with_entries, req)
    assert result.row_count == 1
    assert result.rows[0][0] == "u2"


def test_generate_report_caps_max_rows(storage_with_entries):
    req = ReportRequest(
        title="Cap",
        namespace="alpha",
        columns=["id"],
        max_rows=2,
    )
    result = generate_report(storage_with_entries, req)
    assert result.row_count == 2


def test_generate_report_includes_generated_at_utc(storage_with_entries):
    req = ReportRequest(title="t", namespace="alpha", columns=["id"], max_rows=10)
    result = generate_report(storage_with_entries, req)
    assert result.generated_at.tzinfo is not None
    assert result.generated_at.tzinfo.utcoffset(result.generated_at).total_seconds() == 0


def test_render_csv_includes_title_and_timestamp_header():
    result = ReportResult(
        title="My report",
        generated_at=datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        namespace="alpha",
        columns=["id", "x"],
        rows=[["u1", 1], ["u2", 2]],
        row_count=2,
        filters_applied={},
    )
    csv_text = render_csv(result)
    lines = csv_text.splitlines()
    assert lines[0].startswith("# title:")
    assert "My report" in lines[0]
    assert lines[1].startswith("# generated_at:")
    assert "2026-04-24T12:00:00" in lines[1]
    assert lines[2] == "id,x"
    assert lines[3] == "u1,1"


def test_render_json_round_trips():
    import json
    result = ReportResult(
        title="t",
        generated_at=datetime(2026, 4, 24, 12, 0, 0, tzinfo=timezone.utc),
        namespace="alpha",
        columns=["id"],
        rows=[["u1"]],
        row_count=1,
        filters_applied={"entry_type": "note"},
    )
    parsed = json.loads(render_json(result))
    assert parsed["title"] == "t"
    assert parsed["generated_at"] == "2026-04-24T12:00:00+00:00"
    assert parsed["columns"] == ["id"]
    assert parsed["row_count"] == 1
    assert parsed["filters_applied"] == {"entry_type": "note"}
