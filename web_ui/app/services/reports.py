"""Report generation service: pulls entries from storage, projects to columns, renders to HTML/CSV/JSON."""
import csv
import io
import json
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any

from .validation import ReportRequest


@dataclass
class ReportResult:
    title: str
    generated_at: datetime
    namespace: str
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    filters_applied: dict = field(default_factory=dict)


def _project(entry: dict, columns: list[str]) -> list[Any]:
    payload = entry.get("payload") or {}
    out = []
    for col in columns:
        if col == "id":
            out.append(entry.get("id"))
        elif col in payload:
            out.append(payload.get(col))
        else:
            out.append(None)
    return out


def _entry_passes_filters(entry: dict, req: ReportRequest) -> bool:
    payload = entry.get("payload") or {}
    if req.entry_type and payload.get("entry_type") != req.entry_type:
        return False
    created_at = payload.get("created_at")
    if req.date_from or req.date_to:
        if not created_at:
            return False
        try:
            ts = datetime.fromisoformat(created_at)
        except ValueError:
            return False
        if req.date_from and ts < datetime.fromisoformat(req.date_from):
            return False
        if req.date_to and ts > datetime.fromisoformat(req.date_to):
            return False
    return True


def generate_report(storage, req: ReportRequest) -> ReportResult:
    """Produce a ReportResult from the namespace's entries.

    Pulls entries with a generous fetch cap, applies entry-type and date filters
    in Python, projects to the requested columns, and stops once `max_rows`
    matching rows have been collected.
    """
    fetch_cap = min(req.max_rows * 4, 40_000)
    entries = storage.list_entries(namespace=req.namespace, limit=fetch_cap, offset=None)

    rows: list[list[Any]] = []
    for entry in entries:
        if not _entry_passes_filters(entry, req):
            continue
        rows.append(_project(entry, req.columns))
        if len(rows) >= req.max_rows:
            break

    filters: dict[str, Any] = {}
    if req.entry_type:
        filters["entry_type"] = req.entry_type
    if req.date_from:
        filters["date_from"] = req.date_from
    if req.date_to:
        filters["date_to"] = req.date_to

    return ReportResult(
        title=req.title,
        generated_at=datetime.now(timezone.utc),
        namespace=req.namespace,
        columns=list(req.columns),
        rows=rows,
        row_count=len(rows),
        filters_applied=filters,
    )


def render_csv(result: ReportResult) -> str:
    buf = io.StringIO()
    buf.write(f"# title: {result.title}\n")
    buf.write(f"# generated_at: {result.generated_at.isoformat()}\n")
    writer = csv.writer(buf)
    writer.writerow(result.columns)
    for row in result.rows:
        writer.writerow(row)
    return buf.getvalue()


def render_json(result: ReportResult) -> str:
    payload = asdict(result)
    payload["generated_at"] = result.generated_at.isoformat()
    return json.dumps(payload, default=str)
