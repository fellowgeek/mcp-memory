"""
Database layer for MCP-Memory server.
Handles SQLite operations, schema initialization, and FTS5 full-text indexing.
"""

from datetime import datetime, timezone
import json
import os
import sqlite3
from typing import Any, Dict, List, Optional, Union

from okf_engine import (
    get_memory_file_path,
    parse_okf,
    remove_memory_from_disk,
    serialize_okf,
    sync_memory_to_disk,
)

from pathlib import Path

BASE_DIR = Path(__file__).parent.resolve()

def get_project_root() -> Path:
    """Returns the project root directory, or falls back to user home if cwd is root '/' or unwritable."""
    env_root = os.getenv("MCP_MEMORY_PROJECT_ROOT")
    if env_root:
        p = Path(env_root).expanduser().resolve()
        if p != Path("/") and os.access(p, os.W_OK):
            return p

    try:
        cwd = Path.cwd().resolve()
        if cwd != Path("/") and os.access(cwd, os.W_OK):
            return cwd
    except Exception:
        pass

    fallback = Path.home() / ".mcp_memory"
    try:
        fallback.mkdir(parents=True, exist_ok=True)
    except Exception:
        pass
    return fallback

def get_default_db_path(override_root: Optional[Union[str, Path]] = None) -> str:
    if override_root is None and "DEFAULT_DB_PATH" in globals() and DEFAULT_DB_PATH != _INITIAL_DB_PATH:
        return DEFAULT_DB_PATH
    raw_db_path = os.getenv("MCP_MEMORY_DB_PATH", ".mcp_memory/memories.db")
    if os.path.isabs(raw_db_path):
        return str(Path(raw_db_path).expanduser().resolve())
    root = Path(override_root).expanduser().resolve() if override_root else get_project_root()
    return str((root / raw_db_path).resolve())

def get_default_memories_dir(override_root: Optional[Union[str, Path]] = None) -> str:
    if override_root is None and "DEFAULT_MEMORIES_DIR" in globals() and DEFAULT_MEMORIES_DIR != _INITIAL_MEM_DIR:
        return DEFAULT_MEMORIES_DIR
    raw_mem_dir = os.getenv("MCP_MEMORY_DIR", "memory")
    if os.path.isabs(raw_mem_dir):
        return str(Path(raw_mem_dir).expanduser().resolve())
    root = Path(override_root).expanduser().resolve() if override_root else get_project_root()
    return str((root / raw_mem_dir).resolve())

_INITIAL_DB_PATH = str((get_project_root() / os.getenv("MCP_MEMORY_DB_PATH", ".mcp_memory/memories.db")).resolve()) if not os.path.isabs(os.getenv("MCP_MEMORY_DB_PATH", "")) else str(Path(os.getenv("MCP_MEMORY_DB_PATH", "")).expanduser().resolve())
_INITIAL_MEM_DIR = str((get_project_root() / os.getenv("MCP_MEMORY_DIR", "memory")).resolve()) if not os.path.isabs(os.getenv("MCP_MEMORY_DIR", "")) else str(Path(os.getenv("MCP_MEMORY_DIR", "")).expanduser().resolve())

DEFAULT_DB_PATH = get_default_db_path()
DEFAULT_MEMORIES_DIR = get_default_memories_dir()


def get_connection(db_path: Optional[str] = None) -> sqlite3.Connection:
    target_path = db_path if db_path is not None else get_default_db_path()
    abs_path = os.path.abspath(os.path.expanduser(target_path))
    parent_dir = os.path.dirname(abs_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)
    conn = sqlite3.connect(abs_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Optional[str] = None) -> None:
    """Initialize SQLite schema including memories table and FTS5 search index."""
    target_path = db_path if db_path is not None else get_default_db_path()
    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        
        # Enable WAL mode for performance
        cursor.execute("PRAGMA journal_mode=WAL;")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                key TEXT NOT NULL,
                namespace TEXT NOT NULL DEFAULT 'default',
                okf_payload TEXT NOT NULL,
                tags TEXT NOT NULL DEFAULT '[]',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (key, namespace)
            );
            """
        )

        # Full-Text Search virtual table
        cursor.execute(
            """
            CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
                key UNINDEXED,
                namespace UNINDEXED,
                tags,
                okf_payload
            );
            """
        )

        # Triggers to keep FTS index synced with memories table
        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                INSERT INTO memories_fts(rowid, key, namespace, tags, okf_payload)
                VALUES (new.rowid, new.key, new.namespace, new.tags, new.okf_payload);
            END;
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = old.rowid;
            END;
            """
        )

        cursor.execute(
            """
            CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                DELETE FROM memories_fts WHERE rowid = old.rowid;
                INSERT INTO memories_fts(rowid, key, namespace, tags, okf_payload)
                VALUES (new.rowid, new.key, new.namespace, new.tags, new.okf_payload);
            END;
            """
        )

        conn.commit()


def store_memory(
    key: str,
    content: Union[str, Dict[str, Any]],
    tags: Optional[List[str]] = None,
    namespace: str = "default",
    concept_type: Optional[str] = None,
    title: Optional[str] = None,
    description: Optional[str] = None,
    resource: Optional[str] = None,
    status: Optional[str] = None,
    stale_after: Optional[str] = None,
    sources: Optional[List[Dict[str, Any]]] = None,
    usage_window: Optional[Dict[str, str]] = None,
    verified: Optional[Union[Dict[str, Any], List[Dict[str, Any]]]] = None,
    generated_by: Optional[str] = None,
    runtime: Optional[str] = None,
    parameters: Optional[List[Dict[str, Any]]] = None,
    executor: Optional[Dict[str, Any]] = None,
    attester: Optional[Dict[str, Any]] = None,
    computation: Optional[str] = None,
    db_path: Optional[str] = None,
    memories_dir: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Store or update a memory record in SQLite formatted as OKF v0.2 and sync to disk .md file."""
    target_path = db_path if db_path is not None else get_default_db_path(override_root=project_root)
    target_dir = memories_dir if memories_dir is not None else get_default_memories_dir(override_root=project_root)

    # Resolve the destination before touching SQLite so a key or namespace that
    # cannot be written raises here rather than after the row is committed.
    # sync_memory_to_disk recomputes the same path; this call is for the check.
    get_memory_file_path(key=key, namespace=namespace, base_dir=target_dir)

    init_db(target_path)
    now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    tags_list = tags if tags is not None else []
    tags_json = json.dumps(tags_list)

    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        
        # Check existing record to preserve created_at
        cursor.execute(
            "SELECT created_at FROM memories WHERE key = ? AND namespace = ?",
            (key, namespace),
        )
        row = cursor.fetchone()
        created_at = row["created_at"] if row else now_iso

        okf_payload = serialize_okf(
            key=key,
            content=content,
            tags=tags_list,
            namespace=namespace,
            concept_type=concept_type,
            title=title,
            description=description,
            resource=resource,
            status=status,
            stale_after=stale_after,
            sources=sources,
            usage_window=usage_window,
            verified=verified,
            generated_by=generated_by,
            runtime=runtime,
            parameters=parameters,
            executor=executor,
            attester=attester,
            computation=computation,
            created_at=created_at,
            updated_at=now_iso,
        )

        cursor.execute(
            """
            INSERT INTO memories (key, namespace, okf_payload, tags, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(key, namespace) DO UPDATE SET
                okf_payload = excluded.okf_payload,
                tags = excluded.tags,
                updated_at = excluded.updated_at
            """,
            (key, namespace, okf_payload, tags_json, created_at, now_iso),
        )
        conn.commit()

    # Sync OKF Markdown file to disk
    file_path = sync_memory_to_disk(key=key, namespace=namespace, okf_payload=okf_payload, base_dir=target_dir)

    return {
        "key": key,
        "namespace": namespace,
        "tags": tags_list,
        "created_at": created_at,
        "updated_at": now_iso,
        "okf_payload": okf_payload,
        "file_path": file_path,
    }


def retrieve_memory(
    key: str,
    namespace: str = "default",
    db_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Retrieve a memory record by key and namespace."""
    target_path = db_path if db_path is not None else get_default_db_path(override_root=project_root)
    init_db(target_path)
    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT key, namespace, okf_payload, tags, created_at, updated_at FROM memories WHERE key = ? AND namespace = ?",
            (key, namespace),
        )
        row = cursor.fetchone()
        if not row:
            return None

        parsed = parse_okf(row["okf_payload"])
        parsed["created_at"] = row["created_at"]
        parsed["updated_at"] = row["updated_at"]
        return parsed


def search_memories(
    query: Optional[str] = None,
    tags: Optional[List[str]] = None,
    namespace: Optional[str] = None,
    limit: int = 10,
    db_path: Optional[str] = None,
    project_root: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Search memories using SQLite FTS5 or SQL filtering.
    Filters by query keywords, tags list, and optional namespace.
    """
    target_path = db_path if db_path is not None else get_default_db_path(override_root=project_root)
    init_db(target_path)
    results = []

    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        
        sql_conditions = []
        params: List[Any] = []

        if namespace:
            sql_conditions.append("m.namespace = ?")
            params.append(namespace)

        if query and query.strip():
            # Clean query term for FTS matching
            escaped_terms = [term.replace('"', '""') for term in query.strip().split()]
            fts_query = " ".join(f'"{t}"*' for t in escaped_terms)
            sql = """
                SELECT m.key, m.namespace, m.okf_payload, m.tags, m.created_at, m.updated_at
                FROM memories m
                JOIN memories_fts fts ON m.rowid = fts.rowid
                WHERE memories_fts MATCH ?
            """
            params.insert(0, fts_query)

            if sql_conditions:
                sql += " AND " + " AND ".join(sql_conditions)

            sql += " ORDER BY rank LIMIT ?"
            params.append(limit * 2) # Fetch extra candidate records for tag filtering if needed
        else:
            sql = "SELECT key, namespace, okf_payload, tags, created_at, updated_at FROM memories m"
            if sql_conditions:
                sql += " WHERE " + " AND ".join(sql_conditions)
            sql += " ORDER BY updated_at DESC LIMIT ?"
            params.append(limit * 2)

        try:
            cursor.execute(sql, params)
            rows = cursor.fetchall()
        except sqlite3.OperationalError:
            # Fallback to LIKE search if FTS query syntax error occurs
            like_sql = "SELECT key, namespace, okf_payload, tags, created_at, updated_at FROM memories m WHERE 1=1"
            like_params: List[Any] = []
            if query:
                like_sql += " AND (m.key LIKE ? OR m.okf_payload LIKE ?)"
                like_params.extend([f"%{query}%", f"%{query}%"])
            if namespace:
                like_sql += " AND m.namespace = ?"
                like_params.append(namespace)
            like_sql += " ORDER BY updated_at DESC LIMIT ?"
            like_params.append(limit * 2)
            cursor.execute(like_sql, like_params)
            rows = cursor.fetchall()

        for row in rows:
            parsed = parse_okf(row["okf_payload"])
            record_tags = parsed.get("tags", [])
            
            # Check tag filters
            if tags:
                if not any(tag in record_tags for tag in tags):
                    continue

            results.append({
                "key": row["key"],
                "namespace": row["namespace"],
                "tags": record_tags,
                "created_at": row["created_at"],
                "updated_at": row["updated_at"],
                "okf_payload": row["okf_payload"],
                "parsed": parsed,
            })

            if len(results) >= limit:
                break

    return results


def delete_memory(
    key: str,
    namespace: str = "default",
    db_path: Optional[str] = None,
    memories_dir: Optional[str] = None,
    project_root: Optional[str] = None,
) -> bool:
    """Delete a memory record by key and namespace from SQLite and disk."""
    target_path = db_path if db_path is not None else get_default_db_path(override_root=project_root)
    target_dir = memories_dir if memories_dir is not None else get_default_memories_dir(override_root=project_root)

    # Same check as store_memory: a key we cannot resolve must not drop the row.
    get_memory_file_path(key=key, namespace=namespace, base_dir=target_dir)

    init_db(target_path)
    with get_connection(target_path) as conn:
        cursor = conn.cursor()
        cursor.execute(
            "DELETE FROM memories WHERE key = ? AND namespace = ?",
            (key, namespace),
        )
        conn.commit()
        deleted = cursor.rowcount > 0

    if deleted:
        remove_memory_from_disk(key=key, namespace=namespace, base_dir=target_dir)

    return deleted
