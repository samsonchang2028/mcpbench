"""Durable, source-local events using the frozen v1 validator."""
import json
import math
import os
import re
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from contracts.validate import validate

REDACTED = "[REDACTED]"
_SENSITIVE = re.compile(r"(?i)(password|passwd|secret|credential|authorization|capability|database_url|pgpass|(^|_)dsn$|(^|_)api[_-]?key$|(^|_)access[_-]token$|(^|_)refresh[_-]token$|^token$)")
_CONTENT = re.compile(r"(?i)(\bbearer\s+\S+|\b(?:password|passwd|secret|token|api[_-]?key|authorization|capability|credential|dsn|database_url|access[_-]token|refresh[_-]token)\s*[=:]\s*\S+|[a-z][a-z0-9+.-]*://[^/\s]*@)")


class LogError(Exception):
    """A sanitized error code; callers must mark artifacts incomplete."""


def redact(value, secrets=()):
    """Copy bounded strict JSON data; remove credential values, retain metrics.

    Redacted credential keys remain keys: the frozen closed Event schema rejects
    forbidden fields rather than disguising an auth envelope as valid telemetry.
    """
    secrets = tuple(secrets)
    if any(type(secret) is not str or not secret for secret in secrets):
        raise LogError("secrets")
    literals = re.compile("|".join(re.escape(secret) for secret in sorted(set(secrets), key=len, reverse=True))) if secrets else None
    budget = [1024**2]

    def visit(item, depth):
        budget[0] -= 1
        if depth > 32 or budget[0] < 0:
            raise LogError("data_limit")
        if isinstance(item, dict):
            if not all(type(key) is str for key in item):
                raise LogError("data_key")
            result = {}
            for key, child in item.items():
                budget[0] -= len(key.encode("utf-8", errors="strict"))
                if budget[0] < 0:
                    raise LogError("data_limit")
                if any(secret in key for secret in secrets):
                    raise LogError("data_key_secret")
                result[key] = REDACTED if _SENSITIVE.search(key) else visit(child, depth + 1)
            return result
        if isinstance(item, (list, tuple)):
            return [visit(child, depth + 1) for child in item]
        if isinstance(item, str):
            budget[0] -= len(item.encode("utf-8", errors="strict"))
            if budget[0] < 0:
                raise LogError("data_limit")
            if _CONTENT.search(item):
                return REDACTED
            return literals.sub(lambda _: REDACTED, item) if literals else item
        if item is None or type(item) in (bool, int):
            return item
        if type(item) is float and math.isfinite(item):
            return item
        raise LogError("data_type")

    try:
        return visit(value, 0)
    except UnicodeError:
        raise LogError("data_unicode") from None


class JsonlWriter:
    """One exclusive file per (run, attempt, source); failed writes poison it.

    Default file-local caps are stricter than the global artifact contract.
    The evaluator must additionally bound the whole run and validate EventStream.
    """
    def __init__(self, path, run_id, attempt_id, source, *, secrets=(),
                 max_bytes=16 * 1024**2, max_line=1024**2, max_events=2500,
                 monotonic=time.monotonic, wall_clock=lambda: datetime.now(timezone.utc)):
        ident = re.compile(r"[a-z][a-z0-9-]{0,63}")
        if not all(type(v) is str and ident.fullmatch(v) for v in (run_id, attempt_id)) or (type(source) is not str or source not in {"launcher", "evaluator", "agent", "mcp"}):
            raise LogError("context")
        if not (type(max_bytes) is int and 1 <= max_bytes <= 100 * 1024**2 and type(max_line) is int and 1 <= max_line <= 1024**2 and type(max_events) is int and 1 <= max_events <= 10000):
            raise LogError("limits")
        secrets = tuple(secrets)
        if any(type(s) is not str or not s for s in secrets):
            raise LogError("secrets")
        self._context = dict(schema_version=1, run_id=run_id, attempt_id=attempt_id, source=source)
        self._secrets, self._mono, self._wall = tuple(secrets), monotonic, wall_clock
        self._start, self._last = monotonic(), 0
        if not math.isfinite(self._start):
            raise LogError("clock")
        self._caps = max_bytes, max_line, max_events
        self._count = self._bytes = 0
        self._error = None
        self._closed = False
        self._open, self._seen = {}, set()
        self._lock = threading.Lock()
        fd = directory = None
        try:
            path = Path(path)
            directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            fd = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                         0o600, dir_fd=directory)
            self._file = os.fdopen(fd, "wb", buffering=0)
            fd = None
            os.fsync(directory)
        except OSError:
            if hasattr(self, "_file"):
                self._file.close()
            raise LogError("open") from None
        finally:
            if fd is not None:
                os.close(fd)
            if directory is not None:
                os.close(directory)

    @property
    def summary(self):
        with self._lock:
            return dict(events=self._count, bytes=self._bytes,
                        artifact_complete=self._closed and self._error is None,
                        error=self._error, closed=self._closed, open_operations=len(self._open))

    def _fail(self, code):
        self._error = self._error or code
        raise LogError(self._error) from None

    def emit(self, event_type, phase, status, data, *, call_id=None, parent_call_id=None):
        with self._lock:
            if self._closed or self._error:
                self._fail("closed" if self._closed else self._error)
            try:
                elapsed = (self._mono() - self._start) * 1000
                if not math.isfinite(elapsed) or elapsed < self._last:
                    self._fail("clock")
                stamp = self._wall()
                if stamp.utcoffset() is None:
                    self._fail("clock")
                event = dict(self._context, event_id=f"{self._context['source']}-{self._count + 1}",
                             sequence=self._count + 1, timestamp=stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z"),
                             event_type=event_type, phase=phase, status=status, elapsed_ms=elapsed,
                             data=redact(data, self._secrets))
                if call_id is not None:
                    event["call_id"] = call_id
                if parent_call_id is not None:
                    event["parent_call_id"] = parent_call_id
                # Credentials must never occupy metadata/identity fields either.
                metadata = json.dumps({k: v for k, v in event.items() if k != "data"})
                if any(secret in metadata for secret in self._secrets):
                    self._fail("metadata_secret")
                validate("Event", event)
                kind, _, suffix = event_type.partition(".")
                key = (kind, call_id)
                if kind in {"model", "tool", "db"}:
                    if suffix == "started":
                        if key in self._seen:
                            self._fail("call_reused")
                    else:
                        start = self._open.get(key)
                        if not start or start["phase"] != phase or start.get("parent_call_id") != parent_call_id:
                            self._fail("correlation")
                        fields = ["tool_id"] if kind == "tool" else ["operation", "transaction_id"] if kind == "db" else ["model_digest", "prompt_hash"] if suffix == "completed" else []
                        if any(start["data"][f] != event["data"][f] for f in fields):
                            self._fail("call_identity")
                raw = json.dumps(event, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
                if len(raw) > self._caps[1] or self._bytes + len(raw) > self._caps[0] or self._count >= self._caps[2]:
                    self._fail("capacity")
                written = self._file.write(raw)
                if written != len(raw):
                    self._fail("short_write")
                os.fsync(self._file.fileno())
                self._count += 1
                self._bytes += len(raw)
                self._last = elapsed
                if kind in {"model", "tool", "db"}:
                    if suffix == "started":
                        self._seen.add(key)
                        self._open[key] = json.loads(raw)
                    else:
                        del self._open[key]
                return event
            except LogError:
                self._error = self._error or "data"
                raise
            except Exception:
                self._fail("event_or_io")

    def close(self):
        with self._lock:
            if self._closed:
                if self._error:
                    raise LogError(self._error)
                return
            try:
                os.fsync(self._file.fileno())
            except Exception:
                self._error = self._error or "sync"
            finally:
                try:
                    self._file.close()
                except Exception:
                    self._error = self._error or "close"
                self._closed = True
            if not self._count:
                self._error = self._error or "empty"
            if self._open:
                self._error = self._error or "unclosed_operation"
            if self._error:
                raise LogError(self._error)
