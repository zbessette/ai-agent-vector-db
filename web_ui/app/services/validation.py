"""Pydantic models for all web UI request validation."""
from datetime import datetime
import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_\-]{0,63}$")


class FieldSpec(BaseModel):
    field_name: str = Field(min_length=1, max_length=64)
    field_type: str
    required: bool = False
    description: str = ""
    filterable: bool = True

    @field_validator("field_type")
    @classmethod
    def _valid_type(cls, v):
        allowed = {"string", "string[]", "int", "float", "bool"}
        if v not in allowed:
            raise ValueError(f"field_type must be one of {sorted(allowed)}")
        return v


class NamespaceCreateRequest(BaseModel):
    name: str
    description: str = Field(default="", max_length=2000)
    embedding_instructions: str = Field(min_length=1, max_length=4000)
    include_context: bool = True
    fields: list[FieldSpec] = []

    @field_validator("name")
    @classmethod
    def _valid_name(cls, v):
        if not NAME_PATTERN.match(v):
            raise ValueError("name must match ^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")
        return v


class NamespaceUpdateRequest(BaseModel):
    description: Optional[str] = Field(default=None, max_length=2000)
    embedding_instructions: Optional[str] = Field(default=None, max_length=4000)
    include_context: Optional[bool] = None


class EntryCreateRequest(BaseModel):
    original_text: str = Field(min_length=1, max_length=100_000)
    entry_type: str = Field(min_length=1, max_length=64)
    payload: dict[str, Any] = {}


class EntryUpdateRequest(EntryCreateRequest):
    pass


class SearchRequest(BaseModel):
    query: str = Field(min_length=1, max_length=10_000)
    namespace: Optional[str] = None
    top_k: int = Field(default=10, ge=1, le=100)
    threshold: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    filters: dict[str, Any] = {}


class ReportRequest(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    namespace: str
    columns: list[str] = Field(min_length=1)
    entry_type: Optional[str] = None
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    max_rows: int = Field(default=1000, ge=1, le=10_000)
    format: str = Field(default="html")

    @field_validator("format")
    @classmethod
    def _valid_format(cls, v):
        if v not in {"html", "csv", "json"}:
            raise ValueError("format must be one of html, csv, json")
        return v

    @model_validator(mode="after")
    def _date_range(self):
        if self.date_from and self.date_to:
            try:
                df = datetime.fromisoformat(self.date_from)
                dt = datetime.fromisoformat(self.date_to)
            except ValueError as e:
                raise ValueError(f"Invalid ISO date: {e}")
            if df > dt:
                raise ValueError("date_from must be <= date_to")
        return self
