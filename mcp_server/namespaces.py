import sqlite3
import uuid
from datetime import datetime, timezone


class NamespaceRegistry:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn
        self.conn.row_factory = sqlite3.Row

    def initialize(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS namespaces (
                id                    TEXT PRIMARY KEY,
                name                  TEXT UNIQUE NOT NULL,
                qdrant_collection     TEXT UNIQUE NOT NULL,
                description           TEXT,
                embedding_instructions TEXT NOT NULL,
                summary_instructions  TEXT,
                include_context       BOOLEAN DEFAULT 1,
                status                TEXT DEFAULT 'proposed',
                created_at            TEXT NOT NULL,
                updated_at            TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS namespace_fields (
                id              TEXT PRIMARY KEY,
                namespace_id    TEXT NOT NULL REFERENCES namespaces(id) ON DELETE CASCADE,
                field_name      TEXT NOT NULL,
                field_type      TEXT NOT NULL,
                required        BOOLEAN DEFAULT 0,
                description     TEXT,
                filterable      BOOLEAN DEFAULT 1,
                UNIQUE(namespace_id, field_name)
            );
        """)
        self.conn.execute("PRAGMA foreign_keys = ON")

    def create(
        self,
        name: str,
        description: str,
        embedding_instructions: str,
        fields: list[dict],
        summary_instructions: str | None = None,
        include_context: bool = True,
        status: str = "proposed",
    ) -> dict:
        existing = self.conn.execute(
            "SELECT id FROM namespaces WHERE name = ?", (name,)
        ).fetchone()
        if existing:
            raise ValueError(f"Namespace '{name}' already exists")

        ns_id = str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()

        self.conn.execute(
            """INSERT INTO namespaces
               (id, name, qdrant_collection, description, embedding_instructions,
                summary_instructions, include_context, status, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (ns_id, name, name, description, embedding_instructions,
             summary_instructions, include_context, status, now, now),
        )

        for field in fields:
            self.conn.execute(
                """INSERT INTO namespace_fields
                   (id, namespace_id, field_name, field_type, required, description, filterable)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (str(uuid.uuid4()), ns_id, field["field_name"], field["field_type"],
                 field.get("required", False), field.get("description", ""),
                 field.get("filterable", True)),
            )

        self.conn.commit()
        return self.get(name)

    def list_all(self) -> list[dict]:
        rows = self.conn.execute(
            "SELECT id, name, description, status, created_at, updated_at FROM namespaces"
        ).fetchall()
        return [dict(row) for row in rows]

    def get(self, name: str) -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM namespaces WHERE name = ?", (name,)
        ).fetchone()
        if row is None:
            return None

        ns = dict(row)
        fields = self.conn.execute(
            "SELECT * FROM namespace_fields WHERE namespace_id = ?", (ns["id"],)
        ).fetchall()
        def coerce_field(f: sqlite3.Row) -> dict:
            d = dict(f)
            d["required"] = bool(d["required"])
            d["filterable"] = bool(d["filterable"])
            return d

        ns["fields"] = [coerce_field(f) for f in fields]
        return ns

    def confirm(self, name: str) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")
        if ns["status"] != "proposed":
            raise ValueError(f"Namespace '{name}' is not in 'proposed' status (current: {ns['status']})")

        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            "UPDATE namespaces SET status = 'active', updated_at = ? WHERE name = ?",
            (now, name),
        )
        self.conn.commit()
        return self.get(name)

    def update(self, name: str, **kwargs) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")

        allowed = {"description", "embedding_instructions", "summary_instructions", "include_context"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if not updates:
            return ns

        now = datetime.now(timezone.utc).isoformat()
        updates["updated_at"] = now

        set_clause = ", ".join(f"{k} = ?" for k in updates)
        values = list(updates.values()) + [name]
        self.conn.execute(f"UPDATE namespaces SET {set_clause} WHERE name = ?", values)
        self.conn.commit()
        return self.get(name)

    def update_proposal(self, name: str, fields: list[dict] | None = None, **kwargs) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")
        if ns["status"] != "proposed":
            raise ValueError(
                f"Cannot update proposal for namespace '{name}': status is '{ns['status']}'. "
                "Only proposed namespaces can have fields updated."
            )

        # Replace fields if provided (None = keep existing, [] = clear all)
        if fields is not None:
            self.conn.execute(
                "DELETE FROM namespace_fields WHERE namespace_id = ?", (ns["id"],)
            )
            for field in fields:
                self.conn.execute(
                    """INSERT INTO namespace_fields
                       (id, namespace_id, field_name, field_type, required, description, filterable)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (str(uuid.uuid4()), ns["id"], field["field_name"], field["field_type"],
                     field.get("required", False), field.get("description", ""),
                     field.get("filterable", True)),
                )

        # Update top-level fields (same as update())
        allowed = {"description", "embedding_instructions", "summary_instructions", "include_context"}
        updates = {k: v for k, v in kwargs.items() if k in allowed and v is not None}
        if updates or fields is not None:
            now = datetime.now(timezone.utc).isoformat()
            updates["updated_at"] = now
            set_clause = ", ".join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [name]
            self.conn.execute(f"UPDATE namespaces SET {set_clause} WHERE name = ?", values)

        self.conn.commit()
        return self.get(name)

    def delete(self, name: str) -> dict:
        ns = self.get(name)
        if ns is None:
            raise ValueError(f"Namespace '{name}' not found")

        self.conn.execute(
            "DELETE FROM namespace_fields WHERE namespace_id = ?", (ns["id"],)
        )
        self.conn.execute(
            "DELETE FROM namespaces WHERE id = ?", (ns["id"],)
        )
        self.conn.commit()
        return {"name": name, "status": ns["status"]}
