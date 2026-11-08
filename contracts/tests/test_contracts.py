from copy import deepcopy
import hashlib
import json
from pathlib import Path
import socket
import unittest
from unittest.mock import patch

from jsonschema import Draft202012Validator
from referencing.exceptions import NoSuchResource

from contracts import validate as c


class Contracts(unittest.TestCase):
    def example(self, name):
        return c.load_file(c.ROOT / "v1" / (name + ".example.json"))

    def reject(self, contract, value):
        with self.assertRaises(c.ContractError):
            c.validate(contract, value)

    def test_bundle_and_offline_reference_integrity(self):
        Draft202012Validator.check_schema(c.SCHEMA)
        manifest = c.load_file(c.ROOT / "manifest.json")
        self.assertEqual(manifest["schema_sha256"], hashlib.sha256((c.ROOT / manifest["schema_file"]).read_bytes()).hexdigest())
        self.assertEqual(manifest["catalog_sha256"], hashlib.sha256((c.ROOT / manifest["catalog_file"]).read_bytes()).hexdigest())
        with patch.object(socket, "socket", side_effect=AssertionError("network forbidden")):
            c.validate("Catalog", c.CATALOG)
            with self.assertRaises(NoSuchResource):
                c.REGISTRY.get_or_retrieve("https://unregistered.invalid/remote.json")

    def test_positive_and_adversarial_cases(self):
        cases = c.load_file(c.ROOT / "v1/cases.json")["cases"]
        self.assertGreaterEqual(len(cases), 90)
        for case in cases:
            with self.subTest(case=case["name"]):
                if case["valid"]:
                    c.validate(case["contract"], case["value"])
                else:
                    self.reject(case["contract"], case["value"])

    def test_each_tool_has_input_output_and_error_cases(self):
        cases = c.load_file(c.ROOT / "v1/cases.json")["cases"]
        for name in c.TOOLS:
            for suffix in ["input", "injected-input", "output", "invalid-output", "error", "invalid-error"]:
                self.assertIn(name + "-" + suffix, {case["name"] for case in cases})
        self.assertEqual(len(c.TOOLS), 10)
        self.assertEqual(c.CATALOG["smoke_tool_ids"], ["billing_list_customers", "billing_list_items", c.CREATE])

    def test_duplicate_nonfinite_utf8_and_size_rejected(self):
        invalid = [b'{"x":1,"x":2}', b'{"x":{"a":1,"a":2}}', b'{"x":NaN}', b'{"x":Infinity}', b'{"x":-Infinity}', b'{"x":1e999}', b'\xff', b'"\\ud800"', b'x' * (c.MAX_DOCUMENT_BYTES + 1)]
        for raw in invalid:
            with self.subTest(kind=raw[:16]), self.assertRaises(c.ContractError):
                c.load_bytes(raw)
        with self.assertRaises(c.ContractError):
            c.load_bytes(b'[' * 40 + b'0' + b']' * 40)

    def test_integer_wire_forms_and_unknown_fields(self):
        args = self.example("verification-request")["original_arguments"]
        for bad in [2.0, True, "2", 0, -1, 1001]:
            mutated = deepcopy(args)
            mutated["lines"][0]["quantity"] = bad
            self.reject("CreateDraftArgs", mutated)
        for field in ["unit_price_cents", "total_cents", "idempotency_key", "tenant_id", "schema_name", "url"]:
            self.reject("CreateDraftArgs", {**args, field: "forbidden"})
        self.reject("CreateDraftArgs", {**args, "due_date": 12})

    def test_dates_are_assertions_not_optional_annotations(self):
        for value in ["2026-02-30", "0000-01-01", "2026-1-01", "2026-11-07T00:00:00Z"]:
            self.reject("Date", value)
        for value in ["2026-02-30T00:00:00Z", "2026-11-07T00:00:00+00:00", "2026-11-07T00:00:00", "2026-11-07T24:00:00Z"]:
            self.reject("UTC", value)
        c.validate("Date", "2028-02-29")
        c.validate("UTC", "2026-11-07T23:00:00.123456Z")
        args = self.example("verification-request")["original_arguments"]
        self.reject("CreateDraftArgs", {**args, "due_date": "2026-11-06"})
        self.reject("ListTimesheetsArgs", {"date_from": "2026-11-07", "date_to": "2026-11-06"})

    def test_fixture_hash_order_independence_and_pair(self):
        fixture = self.example("fixture")
        task = self.example("task")
        c.validate_task_fixture(task, fixture)
        reordered = deepcopy(fixture)
        for rows in reordered["seed"].values():
            rows.reverse()
        self.assertEqual(c.seed_hash(fixture), c.seed_hash(reordered))
        reordered["seed"]["items"][0]["unit_price_cents"] += 1
        self.assertNotEqual(c.seed_hash(fixture), c.seed_hash(reordered))
        self.reject("Fixture", reordered)
        task["expected_state"]["lines"][0]["unit_price_cents"] = 12000
        task["expected_state"]["total_cents"] = task["expected_state"]["subtotal_cents"] = 24000
        c.validate("Task", task)  # Its arithmetic alone is valid.
        with self.assertRaises(c.ContractError):
            c.validate_task_fixture(task, fixture)

    def test_canonical_payload_hash_is_explicit_and_stable(self):
        self.assertEqual(c.canonical_bytes({"z": "Café", "a": [1, True, None]}), '{"a":[1,true,null],"z":"Café"}'.encode())
        for value in [{"a": 2.0}, {"a": float("nan")}, {"a": c.MAX_INTEGER + 1}]:
            with self.assertRaises(c.ContractError):
                c.canonical_hash(value)
        args = self.example("verification-request")["original_arguments"]
        reordered = dict(reversed(list(args.items())))
        self.assertEqual(c.payload_hash(args), c.payload_hash(reordered))
        other = deepcopy(args)
        other["lines"][0]["quantity"] = 3
        self.assertNotEqual(c.payload_hash(args), c.payload_hash(other))

    def test_snapshot_references_arithmetic_and_generated_metadata(self):
        snapshot = self.example("snapshot")
        c.validate("Snapshot", snapshot)
        for modify in [
            lambda s: s["tables"]["invoices"][0].update(total_cents=1),
            lambda s: s["tables"]["invoice_lines"][0].update(quantity=3),
            lambda s: s["tables"]["invoice_lines"][0].update(line_number=2),
            lambda s: s["tables"]["projects"][0].update(customer_id="MISSING"),
            lambda s: s["tables"]["idempotency_records"].clear(),
            lambda s: s.update(settlement_generation=None),
        ]:
            bad = deepcopy(snapshot)
            modify(bad)
            self.reject("Snapshot", bad)

    def test_capability_and_mapping_shape_not_security_proof(self):
        mapping = self.example("run-mapping")
        c.validate("RunMapping", mapping)
        for changed in [{"schema_name": "public"}, {"phase": "agent_sealed"}, {"principal_id": "billing-reader"}, {"capability": "not allowed"}]:
            self.reject("RunMapping", {**mapping, **changed})
        # This is a test-only sentinel, never issued or placed in example artifacts.
        auth = {"schema_version": 1, "run_id": mapping["run_id"], "attempt_id": mapping["attempt_id"], "mode": "agent", "capability": "a1" * 32, "idempotency_key": "idem-example-001"}
        c.validate("AuthInput", auth)
        self.reject("AuthInput", {**auth, "capability": "short"})
        event = self.example("event")
        event["data"]["capability"] = auth["capability"]
        self.reject("Event", event)
        request = self.example("agent-request")
        self.reject("AgentRequest", {**request, "expected_state": {}})
        self.reject("AgentRequest", {**request, "database_url": "forbidden"})

    def test_fence_receipt_never_equates_timeout_to_settlement(self):
        receipt = self.example("fence-receipt")
        c.validate("FenceReceipt", receipt)
        for changed in [{"commit_acknowledged": False}, {"elapsed_ms": 5001}, {"remaining_inflight": None}, {"generation": 2}, {"committed_at": None}]:
            self.reject("FenceReceipt", {**receipt, **changed})
        self.reject("FenceReceipt", {**receipt, "status": "unknown"})

    def test_verifier_cannot_choose_another_payload_or_create_path(self):
        verify = self.example("verification-request")
        c.validate("VerificationRequest", verify)
        for changed in [{"original_request_hash": "f" * 64}, {"checks": ["create"]}, {"conflict_arguments": verify["original_arguments"]}]:
            self.reject("VerificationRequest", {**verify, **changed})
        bad = deepcopy(verify)
        bad["conflict_arguments"]["customer_id"] = "CUST-002"
        self.reject("VerificationRequest", bad)

    def test_outcome_does_not_rescue_failed_original_or_fake_unknown_metrics(self):
        summary = self.example("evaluation-result")
        c.validate("EvaluationResult", summary)
        for changed in [{"agent_status": "timeout"}, {"agent_budget_pass": False}, {"agent_settlement_pass": False}, {"verifier_settlement_pass": False}, {"cleanup_pass": False}, {"artifact_complete": False}, {"db_oracle_pass": None}]:
            self.reject("EvaluationResult", {**summary, **changed})
        for key, value in [("post_agent_ms", 30001), ("verifier_calls", 3), ("unauthorized_executions", 1), ("prompt_tokens", 100), ("energy_joules", 10), ("cost_usd", 1.0)]:
            bad = deepcopy(summary)
            bad["metrics"][key] = value
            self.reject("EvaluationResult", bad)

    def test_catalog_permissions_and_task_annotations(self):
        bad = deepcopy(c.CATALOG)
        bad["tools"][0]["permission"] = "billing:draft"
        self.reject("Catalog", bad)
        task = self.example("task")
        self.assertEqual(task["required_tool_ids"], [c.CREATE])
        self.assertEqual(len(task["relevant_tool_ids"]), 3)
        self.reject("Task", {**task, "principal_id": "billing-reader"})
        self.reject("Task", {**task, "relevant_tool_ids": []})

    def test_model_and_verification_budgets_cannot_expand(self):
        request = self.example("agent-request")
        for key, value in [("tool_calls", 13), ("task_timeout_ms", 300001), ("verification_calls", 3), ("verification_retries", 1), ("post_agent_timeout_ms", 30001)]:
            bad = deepcopy(request)
            bad["budgets"][key] = value
            self.reject("AgentRequest", bad)
        c.validate("ProbeEchoArgs", {"text": "mcpbench-v1"})
        self.reject("ProbeEchoArgs", {"text": "arbitrary command", "url": "forbidden"})

    def failure(self, code, stage="verification", disposition="terminal"):
        return {"code": code, "stage": stage, "disposition": disposition, "call_id": None, "attribution": "observed", "reason": "Synthetic regression."}

    def failed_agent(self):
        result = self.example("evaluation-result")
        result.update(task_success=False, overall_status="failed", db_oracle_pass=False, answer_pass=False, verifier_settlement_pass=None, replay_pass=None)
        result["original_assertions"] = [{"name": name, "pass": False, "reason": "Incorrect answer/state."} for name in ["db-oracle", "answer"]]
        result["verification_assertions"] = [row for row in result["verification_assertions"] if row["name"] == "unchanged-state"]
        result["null_reasons"] = {"verifier_settlement_pass": "original_failed", "replay_pass": "original_failed"}
        result["metrics"]["verifier_calls"] = 0
        return result

    def test_independent_verdict_counterexamples(self):
        good = self.example("evaluation-result")
        for assertion_set in ["original_assertions", "verification_assertions"]:
            bad = deepcopy(good)
            bad[assertion_set][0]["pass"] = False
            self.reject("EvaluationResult", bad)
        for change in [{"overall_status": "failed", "replay_pass": False}, {"overall_status": "failed", "quarantined": True}]:
            self.reject("EvaluationResult", {**good, **change})
        for code, stage in [("verification_failed", "verification"), ("cleanup_failed", "cleanup"), ("artifact_incomplete", "operations")]:
            bad = deepcopy(good)
            bad["failures"] = [self.failure(code, stage)]
            self.reject("EvaluationResult", bad)
        bad = deepcopy(good)
        bad["metrics"]["verifier_calls"] = 0
        self.reject("EvaluationResult", bad)
        bad = self.failed_agent()
        for key in ["agent_settlement_pass", "db_oracle_pass", "answer_pass"]:
            bad[key] = None
            bad["null_reasons"][key] = "settlement_unknown"
        for row in bad["original_assertions"]:
            row["pass"] = None
        self.reject("EvaluationResult", bad)  # Neither cleanup nor comparison may remain true.
        bad.update(cleanup_pass=None, final_state_unchanged=None, comparison_valid=False, quarantined=True)
        bad["null_reasons"].update(cleanup_pass="settlement_unknown", final_state_unchanged="settlement_unknown")
        bad["verification_assertions"] = []
        c.validate("EvaluationResult", bad)  # No redundant failure entry is necessary.
        bad["null_reasons"]["agent_settlement_pass"] = "arbitrary escape"
        self.reject("EvaluationResult", bad)

    def test_legitimate_failed_agent_comparisons_and_recovered_errors(self):
        for status, code in [("completed", "state_incorrect"), ("failed", "invalid_arguments"), ("timeout", "model_timeout")]:
            value = self.failed_agent()
            value["agent_status"] = status
            value["agent_budget_pass"] = status != "timeout"
            value["failures"] = [self.failure(code, "agent")]
            c.validate("EvaluationResult", value)
            self.assertTrue(value["comparison_valid"])
        value = self.example("evaluation-result")
        value["failures"] = [self.failure("invalid_arguments", "execution", "recovered")]
        c.validate("EvaluationResult", value)
        value["failures"] = [self.failure("verification_failed", disposition="recovered")]
        self.reject("EvaluationResult", value)
        # Later verification failure preserves original task success but invalidates the comparison.
        value = self.example("evaluation-result")
        value.update(overall_status="failed", comparison_valid=False, replay_pass=False)
        value["verification_assertions"][0]["pass"] = False
        value["failures"] = [self.failure("verification_failed")]
        c.validate("EvaluationResult", value)
        self.assertTrue(value["task_success"])

    def test_read_only_terminal_bundle_and_record_binding(self):
        names = ["read-task", "fixture", "read-run-mapping", "read-evaluation-result", "read-agent-result"]
        bundle = [self.example(name) for name in names]
        c.validate_run_bundle(*bundle)
        for index, mutate in [
            (0, lambda x: x["expected_state"].update(required_record_ids=["MISSING"])),
            (0, lambda x: x["expected_state"].update(record_table="timesheets")),
            (2, lambda x: x.update(workflow_kind="draft_invoice")),
            (3, lambda x: x.update(final_state_unchanged=False)),
            (4, lambda x: x["final_answer"].update(record_ids=["MISSING"])),
        ]:
            bad = deepcopy(bundle)
            mutate(bad[index])
            with self.assertRaises(c.ContractError):
                c.validate_run_bundle(*bad)
        read = self.example("read-evaluation-result")
        read["metrics"]["verifier_calls"] = 1
        self.reject("EvaluationResult", read)
        self.reject("RunMapping", {**bundle[2], "phase": "verifying"})

    def test_catalog_order_membership_and_nonretryable_errors(self):
        for tools in [c.CATALOG["tools"][:3], list(reversed(c.CATALOG["tools"]))]:
            self.reject("Catalog", {**c.CATALOG, "tools": tools})
        for code in c.SCHEMA["$defs"]["ToolError"]["properties"]["code"]["enum"]:
            error = {"code": code, "message": "Synthetic error.", "retryable": True}
            result = {"tool_id": c.CREATE, "is_error": True, "error": error}
            if code in {"db_error", "tool_timeout"}:
                c.validate("ToolError", error)
                c.validate("ToolResult", result)
            else:
                self.reject("ToolError", error)
                self.reject("ToolResult", result)

    def test_control_chain_phase_identity_and_shared_deadline(self):
        chain = self.example("control-chain")
        c.validate("ControlChain", chain)
        mutations = [
            lambda x: x["requests"][2]["budget"].update(anchor_id="new-deadline"),
            lambda x: x["requests"][2]["budget"].update(remaining_ms=30000),
            lambda x: x["requests"][2]["budget"].update(operation_timeout_ms=5001),
            lambda x: x["requests"][2].update(prior_result_id="wrong-result"),
            lambda x: x["results"][1].update(task_id="another-task"),
            lambda x: x["results"][1].update(request_id="another-request"),
            lambda x: x["results"][1].update(workflow_kind="read_only"),
            lambda x: x["results"][1].update(original_pass=False),
            lambda x: x["results"][2].update(fence_receipt=x["results"][1]["fence_receipt"]),
            lambda x: x["exits"][1].update(result_delivery="partial", result_ref=None),
            lambda x: x["exits"][1].update(termination="timed_out", exit_code=None, signal="SIGKILL"),
            lambda x: x["verifier"].update(invoice_id="INV-OTHER"),
            lambda x: x["verifier"].update(calls=0, checks=[]),
            lambda x: x["exits"].pop(),
        ]
        for mutate in mutations:
            bad = deepcopy(chain)
            mutate(bad)
            self.reject("ControlChain", bad)
        for delivery in ["missing", "partial", "malformed", "oversized"]:
            host = self.example("verifier-exit")
            host.update(result_delivery=delivery, result_ref=None)
            c.validate("ProcessExit", host)
        for path in ["/etc/passwd", "control/../secret.json", "control/symlink/../../secret.json", "control/secret.txt"]:
            bad = self.example("control-prepare-request")
            bad["inputs"]["task"]["path"] = path
            self.reject("ControlRequest", bad)
        budget = deepcopy(chain["requests"][1]["budget"])
        budget.update(elapsed_ms=29999, remaining_ms=1, operation_timeout_ms=1)
        c.validate("PostAgentBudget", budget)
        budget.update(elapsed_ms=30001, remaining_ms=0, operation_timeout_ms=0)
        c.validate("PostAgentBudget", budget)  # Retain observed overrun; never clip it.

    def test_event_evidence_and_complete_interrupted_stream(self):
        event = self.example("event")
        self.reject("Event", {**event, "data": {}})
        for kind, source, phase in [("fence.completed", "evaluator", "grading"), ("grading.completed", "evaluator", "grading"), ("process.exited", "launcher", "operations"), ("db.completed", "mcp", "execution"), ("retrieval.completed", "agent", "retrieval")]:
            self.reject("Event", {**event, "event_type": kind, "source": source, "phase": phase, "data": {}})
        stream = self.example("interrupted-trace")
        c.validate_event_stream(stream)
        for mutate in [lambda x: x.pop(), lambda x: x[1].update(event_id=x[0]["event_id"]), lambda x: x[1].update(sequence=3), lambda x: x[1]["data"].update(operation_call_id="unknown-call")]:
            bad = deepcopy(stream)
            mutate(bad)
            with self.assertRaises(c.ContractError):
                c.validate_event_stream(bad)
        started = deepcopy(event)
        started.update(event_type="tool.started", sequence=1, event_id="tool-start", elapsed_ms=0, data={"tool_id":c.CREATE,"arguments":self.example("verification-request")["original_arguments"],"retry_index":0})
        event.update(sequence=2, elapsed_ms=18)
        c.validate_event_stream([started,event])
        bad = deepcopy(event)
        bad["source"] = "launcher"
        self.reject("Event",bad)

    def test_read_and_missing_agent_result_control_paths(self):
        for name in ["read-control-chain", "failed-control-chain"]:
            chain = self.example(name)
            c.validate("ControlChain", chain)
            self.assertIsNone(chain["verifier"])
            self.assertEqual(chain["results"][2]["fence_receipt"]["generation"], 1)
        chain = self.example("failed-control-chain")
        chain["requests"][1]["inputs"]["agent_result"] = self.example("agent-exit")["result_ref"]
        self.reject("ControlChain", chain)

    def test_registered_standalone_examples(self):
        manifest = c.load_file(c.ROOT / "manifest.json")
        registered = {row["file"] for row in manifest["examples"]}
        self.assertEqual(registered, {str(path.relative_to(c.ROOT)) for path in (c.ROOT / "v1").glob("*.example.json")})
        for row in manifest["examples"]:
            with self.subTest(contract=row["contract"], file=row["file"]):
                c.validate(row["contract"], c.load_file(c.ROOT / row["file"]))

    def test_typed_operation_lifecycles_and_required_evidence(self):
        base = self.example("event")
        for kind, source, phase, identity in [
            ("tool", "agent", "execution", {"tool_id": c.CREATE}),
            ("model", "agent", "agent", {"model_digest": "0" * 64, "prompt_hash": "1" * 64}),
            ("db", "mcp", "execution", {"operation": "create_draft", "transaction_id": "tx-001"}),
        ]:
            start_data = deepcopy(identity)
            if kind == "tool":
                start_data.update(arguments=self.example("verification-request")["original_arguments"], retry_index=0)
            start = {**base, "event_id": kind + "-started", "event_type": kind + ".started", "source": source, "phase": phase, "sequence": 1, "elapsed_ms": 0, "data": start_data}
            for suffix in ["completed", "failed", "interrupted"]:
                data = {**identity, "duration_ms": 1}
                if kind == "model":
                    if suffix != "completed":
                        data.pop("model_digest")
                        data.pop("prompt_hash")
                    data.update(prompt_tokens=10 if suffix == "completed" else None, output_tokens=2 if suffix == "completed" else None, counts_unavailable_reason=None if suffix == "completed" else "missing_response")
                if suffix == "completed":
                    if kind == "tool": data["tool_result"] = base["data"]["tool_result"]
                    if kind == "db": data["rows_affected"] = 3
                if suffix == "failed":
                    data["failure"] = self.failure("tool_error", "agent" if kind == "model" else "execution")
                    if kind == "tool": data["tool_result"] = None
                if suffix == "interrupted": data["reason"] = "deadline"
                end = {**start, "event_id": kind + "-" + suffix, "event_type": kind + "." + suffix, "status": "error" if suffix == "failed" else "interrupted" if suffix == "interrupted" else "ok", "sequence": 2, "elapsed_ms": 1, "data": data}
                c.validate_event_stream([start, end])
                for field in data:
                    bad = deepcopy(end)
                    bad["data"].pop(field)
                    self.reject("Event", bad)
        wrong_authority = {**base, "source": "evaluator", "event_type": "db.started", "data": {"operation": "create_draft", "transaction_id": "tx-001"}}
        self.reject("Event", wrong_authority)

    def test_failed_verifier_records_and_observed_process_status(self):
        verifier = self.example("verifier-result")
        verifier.update(status="timeout", calls=1)
        verifier["checks"] = [{"check": "same_payload_replay", "pass": False, "tool_result": None, "failure": self.failure("tool_timeout")}]
        c.validate("VerifierResult", verifier)
        verifier["checks"][0]["failure"] = None
        self.reject("VerifierResult", verifier)
        host = self.example("agent-exit")
        host.update(termination="timed_out", exit_code=0)
        c.validate("ProcessExit", host)  # Deadline hit, then observed normal exit code retained.
        host.update(reaped=False, exit_code=None)
        c.validate("ProcessExit", host)  # Explicitly uncertain; never settlement proof.
        chain = self.example("failed-control-chain")
        chain["exits"][0].update(reaped=False, signal=None)
        self.reject("ControlChain", chain)

    def test_control_terminal_decisions_require_evidence_and_skip_reason(self):
        for name in ["control-blocked-result", "control-quarantine-result"]:
            result = self.example(name)
            c.validate("ControlResult", result)
            self.reject("ControlResult", {**result, "failure": None})
        result = self.example("control-quarantine-result")
        result["outputs"]["agent_snapshot"] = self.example("control-settle-grade-result")["outputs"]["agent_snapshot"]
        self.reject("ControlResult", result)
        chain = self.example("read-control-chain")
        chain["results"][1]["verifier_skip_reason"] = "original_failed"
        self.reject("ControlChain", chain)
        chain = self.example("control-chain")
        chain["requests"][2]["message_id"] = chain["requests"][0]["message_id"]
        self.reject("ControlChain", chain)

    def test_successful_timesheet_read_uses_the_same_read_only_gate(self):
        bundle = [self.example(name) for name in ["read-task", "fixture", "read-run-mapping", "read-evaluation-result", "read-agent-result"]]
        task, fixture, mapping, result, agent = bundle
        record_id = fixture["seed"]["timesheets"][0]["timesheet_id"]
        task.update(prompt="Read this synthetic timesheet.", required_tool_ids=["billing_get_timesheet"], relevant_tool_ids=["billing_get_timesheet"], permitted_tools=["billing_get_timesheet"])
        task["expected_state"].update(record_table="timesheets", required_record_ids=[record_id])
        result["task_hash"] = c.canonical_hash(task)
        mapping["allowed_tools"] = ["billing_get_timesheet"]
        agent["final_answer"]["record_ids"] = [record_id]
        c.validate_run_bundle(*bundle)


if __name__ == "__main__":
    unittest.main()
