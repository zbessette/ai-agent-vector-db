import pytest
from pydantic import ValidationError

from web_ui.app.services.validation import (
    EntryCreateRequest, NamespaceCreateRequest, SearchRequest, ReportRequest,
)


def test_entry_create_requires_original_text():
    with pytest.raises(ValidationError):
        EntryCreateRequest(original_text="", entry_type="note", payload={})


def test_entry_create_caps_text_length():
    with pytest.raises(ValidationError):
        EntryCreateRequest(original_text="x" * 100_001, entry_type="note", payload={})


def test_entry_create_normalizes_payload():
    req = EntryCreateRequest(original_text="hi", entry_type="note", payload={"a": 1})
    assert req.payload == {"a": 1}


def test_namespace_create_validates_name_pattern():
    with pytest.raises(ValidationError):
        NamespaceCreateRequest(
            name="bad name with spaces",
            description="x",
            embedding_instructions="$original_text",
            fields=[],
        )


def test_namespace_create_accepts_valid_name():
    req = NamespaceCreateRequest(
        name="ok-name_1",
        description="x",
        embedding_instructions="$original_text",
        fields=[],
    )
    assert req.name == "ok-name_1"


def test_search_request_caps_top_k():
    with pytest.raises(ValidationError):
        SearchRequest(query="hi", namespace="ns", top_k=10_000)


def test_search_request_requires_query():
    with pytest.raises(ValidationError):
        SearchRequest(query="", namespace="ns", top_k=10)


def test_search_request_requires_namespace():
    with pytest.raises(ValidationError):
        SearchRequest(query="hi", top_k=10)


def test_report_request_requires_at_least_one_column():
    with pytest.raises(ValidationError):
        ReportRequest(
            title="t", namespace="ns", columns=[], max_rows=100,
        )


def test_report_request_caps_max_rows():
    with pytest.raises(ValidationError):
        ReportRequest(
            title="t", namespace="ns", columns=["id"], max_rows=20_000,
        )


def test_report_request_rejects_inverted_date_range():
    with pytest.raises(ValidationError):
        ReportRequest(
            title="t", namespace="ns", columns=["id"], max_rows=100,
            date_from="2026-04-30T00:00:00+00:00",
            date_to="2026-04-01T00:00:00+00:00",
        )


def test_namespace_create_allows_empty_fields():
    req = NamespaceCreateRequest(
        name="alpha",
        description="d",
        embedding_instructions="$original_text",
        fields=[],
    )
    assert req.fields == []


def test_namespace_create_preserves_explicit_fields():
    req = NamespaceCreateRequest(
        name="alpha",
        description="d",
        embedding_instructions="$original_text",
        fields=[
            {"field_name": "category", "field_type": "string", "required": True,
             "description": "c", "filterable": True},
        ],
    )
    assert len(req.fields) == 1
    assert req.fields[0].field_name == "category"
