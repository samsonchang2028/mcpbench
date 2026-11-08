"""Synthetic library tests; no real benchmark trace or live components."""
import json
from pathlib import Path
import tempfile
import unittest
from datetime import datetime, timezone

from contracts.validate import load_bytes, validate, validate_event_stream
from observability.jsonl import JsonlWriter, LogError, REDACTED, redact

HASH = "a" * 64
START = dict(model_digest=HASH, prompt_hash=HASH)
END = dict(START, duration_ms=4, prompt_tokens=12, output_tokens=7, counts_unavailable_reason=None)
FAILURE = dict(stage="agent", code="protocol_error", call_id=None, reason="safe category",
               attribution="observed", disposition="terminal")


class WriterTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "events.jsonl"
        self.tick = 10.0

    def writer(self, **kwargs):
        return JsonlWriter(self.path, "run-test", "attempt-test", "agent",
                           monotonic=lambda: self.tick,
                           wall_clock=lambda: datetime(2026, 11, 8, 19, tzinfo=timezone.utc), **kwargs)

    def read(self):
        events = [load_bytes(raw) for raw in self.path.read_bytes().splitlines()]
        for event in events:
            validate("Event", event)
        return events

    def test_durable_sequence_correlation_and_tokens(self):
        writer = self.writer()
        self.assertFalse(writer.summary["artifact_complete"])
        writer.emit("model.started", "agent", "ok", START, call_id="call-one", parent_call_id="parent-one")
        self.tick += .004
        writer.emit("model.completed", "agent", "ok", END, call_id="call-one", parent_call_id="parent-one")
        writer.close()
        writer.close()
        events = self.read()
        validate_event_stream(events)
        self.assertEqual([e["sequence"] for e in events], [1, 2])
        self.assertAlmostEqual(events[1]["elapsed_ms"], 4)
        self.assertEqual(events[1]["data"]["prompt_tokens"], 12)
        self.assertEqual(events[1]["parent_call_id"], "parent-one")
        self.assertEqual(self.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(writer.summary["bytes"], self.path.stat().st_size)
        self.assertTrue(writer.summary["artifact_complete"])

    def test_redaction_nested_keys_strings_and_metrics(self):
        raw = {"password": "p", "nested": [{"reason": "before literal-secret after", "authorization": "x"}],
               "prompt_tokens": 3, "output_tokens": 4, "token": "private"}
        clean = redact(raw, ["literal-secret"])
        self.assertEqual(clean["password"], REDACTED)
        self.assertEqual(clean["nested"][0]["reason"], f"before {REDACTED} after")
        self.assertEqual(clean["prompt_tokens"], 3)
        for text in ("Bearer opaque", "password=unknown", "postgresql://user:pass@db/name", "api_key = unknown"):
            self.assertEqual(redact(text), REDACTED)
        self.assertEqual(raw["password"], "p")

    def test_final_event_validated_after_redaction(self):
        writer = self.writer(secrets=["literal-secret"])
        failure = dict(FAILURE, reason="literal-secret")
        writer.emit("failure", "agent", "error", {"failure": failure})
        writer.close()
        self.assertNotIn(b"literal-secret", self.path.read_bytes())
        self.assertEqual(self.read()[0]["data"]["failure"]["reason"], REDACTED)

    def test_invalid_values_poison_and_preserve_error(self):
        for invalid in (float("nan"), float("inf"), object(), "\ud800"):
            with self.subTest(type=type(invalid).__name__):
                self.path = Path(self.temp.name) / f"invalid-{len(list(Path(self.temp.name).iterdir()))}"
                writer = self.writer()
                with self.assertRaises(LogError):
                    writer.emit("model.started", "agent", "ok", dict(START, extra=invalid), call_id="call-one")
                with self.assertRaises(LogError):
                    writer.close()
                self.assertFalse(writer.summary["artifact_complete"])
                self.assertEqual(writer.summary["events"], 0)

    def test_schema_semantic_and_duration_rejection(self):
        cases = [
            ("model.completed", "agent", "ok", dict(END, duration_ms=-1)),
            ("model.completed", "agent", "ok", dict(END, prompt_tokens=None)),
            ("tool.started", "execution", "ok", {"tool_id": "billing_list_items", "arguments": {"customer_id": "CUST-001"}, "retry_index": 0}),
            ("db.started", "grading", "ok", {"operation": "snapshot", "transaction_id": "tx-one"}),
            ("not.registered", "agent", "ok", {}),
        ]
        for i, args in enumerate(cases):
            self.path = Path(self.temp.name) / f"schema-{i}"
            writer = self.writer()
            with self.assertRaises(LogError):
                writer.emit(*args, call_id="call-one")
            with self.assertRaises(LogError):
                writer.close()

    def test_missing_start_changed_identity_and_reuse(self):
        for change in ("missing", "phase", "parent", "identity", "reuse"):
            self.path = Path(self.temp.name) / change
            writer = self.writer()
            if change != "missing":
                writer.emit("model.started", "agent", "ok", START, call_id="call-one")
            if change == "reuse":
                writer.emit("model.completed", "agent", "ok", END, call_id="call-one")
                action = lambda: writer.emit("model.started", "agent", "ok", START, call_id="call-one")
            else:
                data = dict(END, model_digest="b"*64) if change == "identity" else END
                action = lambda: writer.emit("model.completed", "execution" if change == "phase" else "agent", "ok", data,
                                             call_id="call-one", parent_call_id="parent-other" if change == "parent" else None)
            with self.assertRaises(LogError):
                action()
            with self.assertRaises(LogError):
                writer.close()

    def test_empty_and_open_operation_are_incomplete(self):
        writer = self.writer()
        with self.assertRaisesRegex(LogError, "empty"):
            writer.close()
        self.path = Path(self.temp.name) / "open"
        writer = self.writer()
        writer.emit("model.started", "agent", "ok", START, call_id="call-one")
        with self.assertRaisesRegex(LogError, "unclosed_operation"):
            writer.close()
        self.assertFalse(writer.summary["artifact_complete"])

    def test_caps_and_clock_regression(self):
        for kwargs in ({"max_line": 10}, {"max_bytes": 10}, {"max_events": 1}):
            self.path = Path(self.temp.name) / f"cap-{next(iter(kwargs))}"
            writer = self.writer(**kwargs)
            if "max_events" in kwargs:
                writer.emit("model.started", "agent", "ok", START, call_id="call-one")
            with self.assertRaisesRegex(LogError, "capacity"):
                writer.emit("model.started", "agent", "ok", START, call_id="call-two")
            with self.assertRaises(LogError):
                writer.close()
        self.path = Path(self.temp.name) / "clock"
        writer = self.writer()
        self.tick -= 1
        with self.assertRaisesRegex(LogError, "clock"):
            writer.emit("model.started", "agent", "ok", START, call_id="call-one")
        with self.assertRaises(LogError):
            writer.close()

    def test_exclusive_and_symlink_rejection(self):
        writer = self.writer()
        with self.assertRaisesRegex(LogError, "open"):
            self.writer()
        with self.assertRaises(LogError):
            writer.close()
        self.path.unlink()
        target = Path(self.temp.name) / "target"
        target.write_text("preserve")
        self.path.symlink_to(target)
        with self.assertRaisesRegex(LogError, "open"):
            self.writer()
        self.assertEqual(target.read_text(), "preserve")

    def test_write_short_sync_close_failures(self):
        for fault in ("write", "short", "sync", "close"):
            self.path = Path(self.temp.name) / fault
            writer = self.writer()
            real = writer._file
            class Broken:
                def write(self, raw):
                    if fault == "write":
                        raise OSError("private error secret")
                    return 0 if fault == "short" else real.write(raw)
                def fileno(self):
                    return -1 if fault == "sync" else real.fileno()
                def close(self):
                    real.close()
                    if fault == "close":
                        raise OSError("private close secret")
            writer._file = Broken()
            if fault != "close":
                with self.assertRaises(LogError) as caught:
                    writer.emit("failure", "agent", "error", {"failure": FAILURE})
                self.assertNotIn("private", str(caught.exception))
            else:
                writer.emit("failure", "agent", "error", {"failure": FAILURE})
            with self.assertRaises(LogError):
                writer.close()
            self.assertFalse(writer.summary["artifact_complete"])

    def test_context_limits_secret_metadata_and_timezone(self):
        for kwargs in ({"max_bytes": 0}, {"max_events": 10001}, {"secrets": [""]}):
            with self.assertRaises(LogError):
                self.writer(**kwargs)
        writer = self.writer(secrets=["call-private"])
        with self.assertRaisesRegex(LogError, "metadata_secret"):
            writer.emit("model.started", "agent", "ok", START, call_id="call-private")
        with self.assertRaises(LogError):
            writer.close()


if __name__ == "__main__":
    unittest.main()
