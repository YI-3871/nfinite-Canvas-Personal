"""Bounded, redacted, disk-backed API task tracing for Infinite Canvas."""

from __future__ import annotations

import json
import logging
import os
import queue
import re
import sqlite3
import threading
import time
import urllib.parse
from contextlib import contextmanager
from typing import Any, Dict, Optional


SENSITIVE_KEY = re.compile(
    r"(?:^|_)(?:api_?key|authorization|cookie|set_?cookie|access_?token|refresh_?token|"
    r"id_?token|token|secret|password|passwd|credential|private_?key)(?:$|_)",
    re.I,
)
BASE64ISH = re.compile(r"^[A-Za-z0-9+/=\r\n]+$")
LOGGER = logging.getLogger("infinite_canvas.task_logs")


def _redact_url(value: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(value)
        if parsed.scheme not in {"http", "https"}:
            return value
        pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
        cleaned = []
        for key, item in pairs:
            normalized = key.replace("-", "_").lower()
            sensitive = normalized in {"key", "apikey", "api_key", "token", "access_token", "auth"} or SENSITIVE_KEY.search(normalized)
            cleaned.append((key, "[REDACTED]" if sensitive else item))
        return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urllib.parse.urlencode(cleaned), parsed.fragment))
    except Exception:
        return value


def sanitize_log_value(value: Any, *, key: str = "", depth: int = 0) -> Any:
    """Return a JSON-safe copy without credentials or embedded image bytes."""
    normalized_key = str(key or "").replace("-", "_")
    if SENSITIVE_KEY.search(normalized_key):
        return "[REDACTED]"
    if depth > 10:
        return "[OMITTED: nesting limit]"
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, bytes):
        return f"[OMITTED: {len(value)} binary bytes]"
    if isinstance(value, str):
        if value.startswith("data:"):
            media_type = value[5:].split(";", 1)[0][:80]
            return f"[OMITTED: data URI {media_type or 'unknown'}, {len(value)} chars]"
        if len(value) > 2048 and BASE64ISH.fullmatch(value):
            return f"[OMITTED: probable base64, {len(value)} chars]"
        value = _redact_url(value)
        limit = 100_000 if normalized_key in {"prompt", "text", "content"} else 16_000
        return value if len(value) <= limit else value[:limit] + f"… [truncated {len(value) - limit} chars]"
    if isinstance(value, dict):
        return {str(k): sanitize_log_value(v, key=str(k), depth=depth + 1) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        values = list(value)
        safe = [sanitize_log_value(item, key=normalized_key, depth=depth + 1) for item in values[:200]]
        if len(values) > 200:
            safe.append(f"[OMITTED: {len(values) - 200} more items]")
        return safe
    return sanitize_log_value(str(value), key=normalized_key, depth=depth + 1)


def _json(value: Any) -> str:
    return json.dumps(sanitize_log_value(value), ensure_ascii=False, separators=(",", ":"))


def _loads(value: Optional[str], fallback: Any) -> Any:
    if not value:
        return fallback
    try:
        return json.loads(value)
    except Exception:
        return fallback


class TaskLogStore:
    """Serialize writes through a bounded queue; read pages directly from SQLite."""

    def __init__(
        self,
        db_path: str,
        *,
        max_bytes: int = 500 * 1024 * 1024,
        target_bytes: int = 450 * 1024 * 1024,
        queue_size: int = 1000,
    ) -> None:
        self.db_path = os.path.abspath(db_path)
        self.max_bytes = int(max_bytes)
        self.target_bytes = int(target_bytes)
        self._queue: queue.Queue = queue.Queue(maxsize=max(20, int(queue_size)))
        self._dropped = 0
        self._write_count = 0
        self._closed = False
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._initialize()
        self._thread = threading.Thread(target=self._writer, name="canvas-task-log-writer", daemon=True)
        self._thread.start()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @contextmanager
    def _connection(self):
        conn = self._connect()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def _initialize(self) -> None:
        with self._connection() as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS task_logs (
                    trace_id TEXT PRIMARY KEY,
                    task_id TEXT,
                    canvas_id TEXT,
                    node_id TEXT,
                    source TEXT,
                    kind TEXT,
                    provider_id TEXT,
                    model TEXT,
                    status TEXT,
                    stage TEXT,
                    prompt TEXT,
                    request_json TEXT,
                    response_json TEXT,
                    error_json TEXT,
                    color_json TEXT,
                    upstream_id TEXT,
                    created_at REAL,
                    updated_at REAL,
                    completed_at REAL,
                    duration_ms INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_task_logs_updated ON task_logs(updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_logs_canvas ON task_logs(canvas_id, updated_at DESC);
                CREATE INDEX IF NOT EXISTS idx_task_logs_status ON task_logs(status, updated_at DESC);
                CREATE TABLE IF NOT EXISTS task_log_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trace_id TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    stage TEXT,
                    level TEXT,
                    message TEXT,
                    data_json TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_task_log_events_trace ON task_log_events(trace_id, id);
                CREATE TABLE IF NOT EXISTS task_log_meta (key TEXT PRIMARY KEY, value TEXT);
                """
            )
            if not conn.execute("SELECT value FROM task_log_meta WHERE key='last_cleanup_prompt_at'").fetchone():
                conn.execute(
                    "INSERT INTO task_log_meta(key,value) VALUES('last_cleanup_prompt_at',?)",
                    (str(time.time()),),
                )

    def _put(self, op: str, payload: Dict[str, Any], *, wait: bool = False) -> bool:
        if self._closed:
            return False
        done = threading.Event() if wait else None
        try:
            self._queue.put_nowait((op, sanitize_log_value(payload), done))
        except queue.Full:
            self._dropped += 1
            if self._dropped == 1 or self._dropped % 100 == 0:
                LOGGER.warning("Task log queue is full; dropped events=%s", self._dropped)
            return False
        if done:
            done.wait(2.0)
        return True

    def create(self, trace_id: str, **fields: Any) -> bool:
        payload = {"trace_id": trace_id, **fields}
        return self._put("create", payload)

    def event(
        self,
        trace_id: str,
        stage: str,
        message: str,
        *,
        level: str = "info",
        data: Any = None,
        status: str = "",
        fields: Optional[Dict[str, Any]] = None,
    ) -> bool:
        return self._put("event", {
            "trace_id": trace_id,
            "stage": stage,
            "message": message,
            "level": level,
            "data": data,
            "status": status,
            "fields": fields or {},
        })

    def finish(self, trace_id: str, *, status: str, response: Any = None, error: Any = None,
               color: Any = None, upstream_id: str = "", duration_ms: int = 0) -> bool:
        return self._put("finish", {
            "trace_id": trace_id,
            "status": status,
            "response": response,
            "error": error,
            "color": color,
            "upstream_id": upstream_id,
            "duration_ms": duration_ms,
        })

    def _writer(self) -> None:
        conn = self._connect()
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            while True:
                op, payload, done = self._queue.get()
                try:
                    if op == "stop":
                        return
                    if op == "barrier":
                        pass
                    elif op == "create":
                        self._write_create(conn, payload)
                    elif op == "event":
                        self._write_event(conn, payload)
                    elif op == "finish":
                        self._write_finish(conn, payload)
                    conn.commit()
                    self._write_count += 1
                    if self._write_count % 50 == 0 or self._disk_bytes() > self.max_bytes:
                        self._enforce_cap(conn)
                except Exception:
                    conn.rollback()
                    LOGGER.exception("Failed to persist task log operation=%s", op)
                finally:
                    if done:
                        done.set()
                    self._queue.task_done()
        finally:
            conn.close()

    def _write_create(self, conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
        now = float(item.get("created_at") or time.time())
        conn.execute(
            """INSERT OR REPLACE INTO task_logs(
                trace_id,task_id,canvas_id,node_id,source,kind,provider_id,model,status,stage,
                prompt,request_json,response_json,error_json,color_json,upstream_id,
                created_at,updated_at,completed_at,duration_ms
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                item.get("trace_id", ""), item.get("task_id", ""), item.get("canvas_id", ""),
                item.get("node_id", ""), item.get("source", ""), item.get("kind", "image"),
                item.get("provider_id", ""), item.get("model", ""), item.get("status", "queued"),
                item.get("stage", "queued"), str(item.get("prompt") or ""), _json(item.get("request") or {}),
                "", "", "", "", now, now, None, 0,
            ),
        )
        self._insert_event(conn, item.get("trace_id", ""), now, "queued", "info", "任务已进入队列", {
            "provider_id": item.get("provider_id", ""), "model": item.get("model", "")
        })

    def _insert_event(self, conn: sqlite3.Connection, trace_id: str, created_at: float, stage: str,
                      level: str, message: str, data: Any) -> None:
        conn.execute(
            "INSERT INTO task_log_events(trace_id,created_at,stage,level,message,data_json) VALUES(?,?,?,?,?,?)",
            (trace_id, created_at, stage, level, message, _json(data or {})),
        )

    def _write_event(self, conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
        now = time.time()
        trace_id = str(item.get("trace_id") or "")
        stage = str(item.get("stage") or "")
        status = str(item.get("status") or "")
        fields = item.get("fields") or {}
        assignments = ["stage=?", "updated_at=?"]
        values = [stage, now]
        if status:
            assignments.append("status=?")
            values.append(status)
        column_map = {
            "response": "response_json", "error": "error_json", "color": "color_json",
            "upstream_id": "upstream_id", "duration_ms": "duration_ms",
        }
        for field, column in column_map.items():
            if field not in fields:
                continue
            assignments.append(f"{column}=?")
            value = fields[field]
            values.append(_json(value) if column.endswith("_json") else value)
        values.append(trace_id)
        conn.execute(f"UPDATE task_logs SET {','.join(assignments)} WHERE trace_id=?", values)
        self._insert_event(conn, trace_id, now, stage, str(item.get("level") or "info"),
                           str(item.get("message") or ""), item.get("data") or {})

    def _write_finish(self, conn: sqlite3.Connection, item: Dict[str, Any]) -> None:
        now = time.time()
        trace_id = str(item.get("trace_id") or "")
        status = str(item.get("status") or "failed")
        stage = "completed" if status == "succeeded" else status
        conn.execute(
            """UPDATE task_logs SET status=?,stage=?,response_json=?,error_json=?,color_json=?,
               upstream_id=?,updated_at=?,completed_at=?,duration_ms=? WHERE trace_id=?""",
            (
                status, stage, _json(item.get("response") or {}), _json(item.get("error") or {}),
                _json(item.get("color") or {}), str(item.get("upstream_id") or ""), now, now,
                int(item.get("duration_ms") or 0), trace_id,
            ),
        )
        level = "error" if status == "failed" else "info"
        message = "任务失败" if status == "failed" else "任务完成"
        data = item.get("error") if status == "failed" else {"duration_ms": int(item.get("duration_ms") or 0)}
        self._insert_event(conn, trace_id, now, stage, level, message, data or {})

    def _barrier(self) -> None:
        done = threading.Event()
        try:
            self._queue.put_nowait(("barrier", {}, done))
            done.wait(1.5)
        except queue.Full:
            pass

    def _disk_bytes(self) -> int:
        return sum(os.path.getsize(path) for path in (self.db_path, self.db_path + "-wal", self.db_path + "-shm") if os.path.exists(path))

    def _enforce_cap(self, conn: sqlite3.Connection) -> None:
        if self._disk_bytes() <= self.max_bytes:
            return
        while self._disk_bytes() > self.target_bytes:
            count = int(conn.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0])
            if count <= 0:
                break
            current_bytes = max(1, self._disk_bytes())
            excess_ratio = max(0.05, min(1.0, (current_bytes - self.target_bytes) / current_bytes))
            batch_size = min(count, max(100, int(count * excess_ratio * 1.25)))
            rows = conn.execute(
                "SELECT trace_id FROM task_logs ORDER BY updated_at ASC LIMIT ?",
                (batch_size,),
            ).fetchall()
            if not rows:
                break
            ids = [row[0] for row in rows]
            placeholders = ",".join("?" for _ in ids)
            conn.execute(f"DELETE FROM task_log_events WHERE trace_id IN ({placeholders})", ids)
            conn.execute(f"DELETE FROM task_logs WHERE trace_id IN ({placeholders})", ids)
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            # SQLite keeps deleted pages allocated until VACUUM. Reclaim them so
            # the configured byte cap describes real disk use, not just row count.
            conn.execute("VACUUM")

    def list(self, *, canvas_id: str = "", status: str = "", provider_id: str = "",
             query: str = "", limit: int = 50, offset: int = 0) -> Dict[str, Any]:
        self._barrier()
        limit = max(1, min(200, int(limit)))
        offset = max(0, int(offset))
        where, params = [], []
        if canvas_id:
            where.append("canvas_id=?")
            params.append(canvas_id)
        if status:
            where.append("status=?")
            params.append(status)
        if provider_id:
            where.append("provider_id=?")
            params.append(provider_id)
        if query:
            where.append("(trace_id LIKE ? OR task_id LIKE ? OR model LIKE ? OR prompt LIKE ?)")
            term = f"%{query[:200]}%"
            params.extend([term, term, term, term])
        clause = " WHERE " + " AND ".join(where) if where else ""
        with self._connection() as conn:
            total = int(conn.execute("SELECT COUNT(*) FROM task_logs" + clause, params).fetchone()[0])
            rows = conn.execute(
                """SELECT trace_id,task_id,canvas_id,node_id,source,kind,provider_id,model,status,stage,
                   upstream_id,created_at,updated_at,completed_at,duration_ms,color_json,error_json
                   FROM task_logs""" + clause + " ORDER BY updated_at DESC LIMIT ? OFFSET ?",
                [*params, limit, offset],
            ).fetchall()
        items = []
        for row in rows:
            item = dict(row)
            item["color"] = _loads(item.pop("color_json", ""), {})
            item["error"] = _loads(item.pop("error_json", ""), {})
            items.append(item)
        return {"items": items, "total": total, "limit": limit, "offset": offset}

    def get(self, trace_id: str) -> Optional[Dict[str, Any]]:
        self._barrier()
        with self._connection() as conn:
            row = conn.execute("SELECT * FROM task_logs WHERE trace_id=?", (trace_id,)).fetchone()
            if not row:
                return None
            events = conn.execute(
                "SELECT created_at,stage,level,message,data_json FROM task_log_events WHERE trace_id=? ORDER BY id",
                (trace_id,),
            ).fetchall()
        item = dict(row)
        for column, key, fallback in (
            ("request_json", "request", {}), ("response_json", "response", {}),
            ("error_json", "error", {}), ("color_json", "color", {}),
        ):
            item[key] = _loads(item.pop(column, ""), fallback)
        item["events"] = [{**dict(event), "data": _loads(event["data_json"], {})} for event in events]
        for event in item["events"]:
            event.pop("data_json", None)
        return item

    def storage_info(self) -> Dict[str, Any]:
        self._barrier()
        with self._connection() as conn:
            count = int(conn.execute("SELECT COUNT(*) FROM task_logs").fetchone()[0])
            row = conn.execute("SELECT value FROM task_log_meta WHERE key='last_cleanup_prompt_at'").fetchone()
        last_prompt = float(row[0]) if row and row[0] else time.time()
        now = time.time()
        return {
            "bytes": self._disk_bytes(), "max_bytes": self.max_bytes, "target_bytes": self.target_bytes,
            "count": count, "queue_size": self._queue.qsize(), "dropped_events": self._dropped,
            "last_cleanup_prompt_at": last_prompt,
            "cleanup_prompt_due": count > 0 and now - last_prompt >= 30 * 86400,
        }

    def mark_cleanup_prompt(self) -> None:
        with self._connection() as conn:
            conn.execute("INSERT OR REPLACE INTO task_log_meta(key,value) VALUES('last_cleanup_prompt_at',?)", (str(time.time()),))

    def cleanup(self, scope: str = "all") -> Dict[str, Any]:
        self._barrier()
        with self._connection() as conn:
            if scope == "older_than_30d":
                ids = [row[0] for row in conn.execute("SELECT trace_id FROM task_logs WHERE updated_at<?", (time.time() - 30 * 86400,)).fetchall()]
            else:
                ids = [row[0] for row in conn.execute("SELECT trace_id FROM task_logs").fetchall()]
            if ids:
                for start in range(0, len(ids), 500):
                    chunk = ids[start:start + 500]
                    marks = ",".join("?" for _ in chunk)
                    conn.execute(f"DELETE FROM task_log_events WHERE trace_id IN ({marks})", chunk)
                    conn.execute(f"DELETE FROM task_logs WHERE trace_id IN ({marks})", chunk)
            conn.execute("INSERT OR REPLACE INTO task_log_meta(key,value) VALUES('last_cleanup_prompt_at',?)", (str(time.time()),))
            conn.commit()
            conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            conn.execute("VACUUM")
        return {"deleted": len(ids), "scope": scope, "bytes": self._disk_bytes()}

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        done = threading.Event()
        try:
            self._queue.put(("stop", {}, done), timeout=1.0)
            done.wait(2.0)
        except queue.Full:
            pass
        self._thread.join(timeout=2.0)
