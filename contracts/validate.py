"""Strict offline validation for the frozen v1 contracts.

Shape checks, cross-field invariants and bounded wire parsing are all required.
This module never proves a database transaction or settlement actually occurred.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker, validators
from referencing import Registry, Resource
from referencing.exceptions import NoSuchResource

ROOT = Path(__file__).resolve().parent
MAX_DOCUMENT_BYTES = 1_048_576
MAX_INTEGER = 9_007_199_254_740_991
SCHEMA = json.loads((ROOT / "v1/schema.json").read_text())
SCHEMA_ID = SCHEMA["$id"]
CATALOG = json.loads((ROOT / "v1/catalog.json").read_text())
TOOLS = {tool["name"]: tool for tool in CATALOG["tools"]}
CREATE = "billing_create_draft_invoice"
AGENT_COUNT_LIMITS = {"model_calls": 8, "tool_calls": 12, "retries": 1}
TABLE_KEYS = {
    "customers": "customer_id", "items": "item_id", "projects": "project_id",
    "timesheets": "timesheet_id", "invoices": "invoice_id",
    "invoice_lines": "line_id", "idempotency_records": "idempotency_key",
}
PRIVATE = {"AuthInput", "RunMapping"}
SECRET_KEYS = {"authorization", "capability", "password", "api_key", "secret", "dsn", "database_url"}


class ContractError(ValueError):
    """Invalid shape or semantic contract; messages never echo input values."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError(message)


def _no_remote(uri: str) -> Resource:
    raise NoSuchResource(ref=uri)


FORMATS = FormatChecker()


@FORMATS.checks("date", raises=(ValueError, TypeError))
def _date(value: Any) -> bool:
    if not isinstance(value, str):
        return True  # The separate type constraint handles non-strings.
    return bool(re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value)) and dt.date.fromisoformat(value).isoformat() == value


@FORMATS.checks("date-time", raises=(ValueError, TypeError))
def _utc(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(?:\.[0-9]{1,6})?Z", value):
        return False
    if not (int(value[11:13]) < 24 and int(value[14:16]) < 60 and int(value[17:19]) < 60):
        return False
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.utcoffset() == dt.timedelta(0)


StrictValidator = validators.extend(
    Draft202012Validator,
    type_checker=Draft202012Validator.TYPE_CHECKER.redefine(
        "integer", lambda checker, instance: type(instance) is int
    ),
)
REGISTRY = Registry(retrieve=_no_remote).with_resource(SCHEMA_ID, Resource.from_contents(SCHEMA))


def _pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON object key")
        result[key] = value
    return result


def _constant(value: str) -> None:
    raise ContractError("non-finite JSON number")


def load_bytes(raw: bytes) -> Any:
    _require(len(raw) <= MAX_DOCUMENT_BYTES, "document exceeds 1 MiB")
    try:
        result = json.loads(raw.decode("utf-8", errors="strict"), object_pairs_hook=_pairs, parse_constant=_constant)
    except (UnicodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ContractError("invalid UTF-8/JSON document") from exc
    _walk(result)
    return result


def load_file(path: str | Path) -> Any:
    with Path(path).open("rb") as stream:
        return load_bytes(stream.read(MAX_DOCUMENT_BYTES + 1))


def _walk(value: Any, depth: int = 0) -> None:
    _require(depth <= 32, "JSON nesting exceeds 32 levels")
    if isinstance(value, dict):
        for key, child in value.items():
            _require(isinstance(key, str), "object key is not a string")
            _walk(key, depth + 1)
            _walk(child, depth + 1)
        if isinstance(value.get("invoice_date"), str) and isinstance(value.get("due_date"), str):
            _require(value["due_date"] >= value["invoice_date"], "due date precedes invoice date")
        if isinstance(value.get("date_from"), str) and isinstance(value.get("date_to"), str):
            _require(value["date_to"] >= value["date_from"], "filter end precedes start")
    elif isinstance(value, list):
        for child in value:
            _walk(child, depth + 1)
    elif isinstance(value, str):
        try:
            value.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise ContractError("invalid Unicode scalar") from exc
    elif isinstance(value, float):
        _require(math.isfinite(value), "non-finite JSON number")
    elif value is not None:
        _require(type(value) in {bool, int}, "unsupported JSON value")


def canonical_bytes(value: Any) -> bytes:
    """Canonical hashed objects use integer JSON numbers, never float/exponent forms."""
    _walk(value)

    def no_floats(item: Any) -> None:
        _require(not isinstance(item, float), "floating number in canonical hash input")
        if isinstance(item, dict):
            _require(all(key.isascii() for key in item), "non-ASCII canonical object key")
            for child in item.values():
                no_floats(child)
        elif isinstance(item, list):
            for child in item:
                no_floats(child)
        elif type(item) is int:
            _require(abs(item) <= MAX_INTEGER, "integer outside interoperable JSON range")

    no_floats(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def canonical_hash(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def payload_hash(arguments: dict[str, Any]) -> str:
    validate("CreateDraftArgs", arguments)
    return canonical_hash({"tool_id": CREATE, "arguments": arguments})


def schema_name(run_id: str) -> str:
    validate("Identifier", run_id)
    return "r_" + hashlib.sha256(run_id.encode("ascii")).hexdigest()[:32]


def seed_hash(fixture: dict[str, Any]) -> str:
    tables = fixture["seed"]
    ordered = {name: sorted(rows, key=lambda row: row[TABLE_KEYS[name]]) for name, rows in tables.items()}
    return canonical_hash({
        "fixture_version": fixture["fixture_version"], "migration_version": fixture["migration_version"],
        "tenant_id": fixture["tenant_id"], "tables": ordered,
    })


def _no_secret_keys(value: Any) -> None:
    if isinstance(value, dict):
        _require(not any(key.casefold() in SECRET_KEYS for key in value), "secret field in public contract")
        for child in value.values():
            _no_secret_keys(child)
    elif isinstance(value, list):
        for child in value:
            _no_secret_keys(child)


def _invoice(invoice: dict[str, Any], lines: list[dict[str, Any]]) -> None:
    _require(1 <= len(lines) <= 10, "invoice line count")
    _require(sorted(line["line_number"] for line in lines) == list(range(1, len(lines) + 1)), "invoice line ordering")
    _require(len({line["item_id"] for line in lines}) == len(lines), "duplicate invoice item")
    for line in lines:
        _require(line["invoice_id"] == invoice["invoice_id"], "invoice line reference mismatch")
        _require(line["line_total_cents"] == line["quantity"] * line["unit_price_cents"], "line arithmetic mismatch")
    total = sum(line["line_total_cents"] for line in lines)
    _require(total <= MAX_INTEGER, "invoice arithmetic overflow")
    _require(invoice["subtotal_cents"] == invoice["total_cents"] == total, "invoice arithmetic mismatch")


def _tables(tables: dict[str, Any]) -> None:
    index: dict[str, dict[str, Any]] = {}
    for name, key in TABLE_KEYS.items():
        index[name] = {row[key]: row for row in tables[name]}
        _require(len(index[name]) == len(tables[name]), "duplicate table key")
    for row in tables["projects"]:
        _require(row["customer_id"] in index["customers"], "project customer missing")
    for row in tables["timesheets"]:
        _require(row["project_id"] in index["projects"] and row["item_id"] in index["items"], "timesheet reference missing")
    for row in tables["invoice_lines"]:
        _require(row["invoice_id"] in index["invoices"] and row["item_id"] in index["items"], "invoice line reference missing")
    records = {row["invoice_id"]: row for row in tables["idempotency_records"]}
    _require(len(records) == len(tables["idempotency_records"]), "duplicate invoice idempotency binding")
    _require(set(records) == set(index["invoices"]), "invoice/idempotency cardinality mismatch")
    for invoice in tables["invoices"]:
        _require(invoice["customer_id"] in index["customers"], "invoice customer missing")
        lines = [row for row in tables["invoice_lines"] if row["invoice_id"] == invoice["invoice_id"]]
        _invoice(invoice, lines)
        arguments = {key: invoice[key] for key in ["customer_id", "invoice_date", "due_date"]}
        arguments["lines"] = [{"item_id": row["item_id"], "quantity": row["quantity"]} for row in sorted(lines, key=lambda row: row["line_number"])]
        _require(records[invoice["invoice_id"]]["request_hash"] == payload_hash(arguments), "idempotency payload hash mismatch")


def _semantics(name: str, value: Any) -> None:
    if name == "EventStream":
        validate_event_stream(value)
    if name == "ControlChain":
        validate_control_chain(**value)
    if name == "Catalog":
        tools = value["tools"]
        _require(value == CATALOG, "baseline catalog identity, version or order changed")
        _require(len({tool["name"] for tool in tools}) == len(tools), "duplicate catalog tool")
        _require(set(value["smoke_tool_ids"]) <= {tool["name"] for tool in tools}, "missing smoke tool")
        for tool in tools:
            _require(tool == TOOLS[tool["name"]], "catalog tool contract changed without versioned registration")
    if name in {"CreateDraftArgs", "ExpectedInvoice"}:
        _require(len({row["item_id"] for row in value["lines"]}) == len(value["lines"]), "duplicate invoice item")
    if name == "ExpectedState":
        if value["kind"] == "draft_invoice":
            validate("ExpectedInvoice", value)
    if name == "ExpectedInvoice":
        total = sum(row["quantity"] * row["unit_price_cents"] for row in value["lines"])
        _require(total <= MAX_INTEGER and value["subtotal_cents"] == value["total_cents"] == total, "expected-state arithmetic mismatch")
    if name in {"DraftOutput", "GetInvoiceOutput"}:
        _invoice(value["invoice"], value["lines"])
    if name == "ToolCall":
        validate(TOOLS[value["tool_id"]]["input_ref"].split("/")[-1], value["arguments"])
    if name == "ToolResult" and not value["is_error"]:
        validate(TOOLS[value["tool_id"]]["output_ref"].split("/")[-1], value["result"])
    if name in {"Tables", "Fixture", "Snapshot"}:
        _tables(value if name == "Tables" else value["seed"] if name == "Fixture" else value["tables"])
    if name == "Fixture":
        _require(value["seed_hash"] == seed_hash(value), "seed hash mismatch")
    if name == "Snapshot" and value["stage"] in {"agent_only", "final"}:
        _require(value["settlement_generation"] is not None and value["settlement_generation"] >= 1, "authoritative snapshot lacks settlement generation")
    if name == "Task":
        _require(set(value["required_tool_ids"]) <= set(value["relevant_tool_ids"]) <= set(value["permitted_tools"]), "task relevance/permission sets inconsistent")
        if value["principal_id"] == "billing-reader":
            _require(CREATE not in value["permitted_tools"], "reader task includes draft permission")
        validate("ExpectedState", value["expected_state"])
        _require(value["final_answer_rule"] == ("saved_invoice_id" if value["expected_state"]["kind"] == "draft_invoice" else "read_result_ids"), "answer rule does not match expected state")
    if name == "RunManifest":
        _require(set(value["unavailable_versions"]) == {key for key, item in value["versions"].items() if item is None}, "unavailable version annotations inconsistent")
    if name == "RunMapping":
        if value["workflow_kind"] == "read_only":
            _require(CREATE not in value["allowed_tools"] and value["verifier_scope"] is None and value["phase"] not in {"verifying", "final_sealed"}, "read-only mapping enables writes or verifier")
        _require(value["schema_name"] == schema_name(value["run_id"]), "unregistered schema derivation")
        if value["principal_id"] == "billing-reader":
            _require(CREATE not in value["allowed_tools"], "reader mapping includes draft permission")
        phase = value["phase"]
        _require((value["agent_token_sha256"] is not None) == (phase == "executing"), "agent capability phase mismatch")
        _require((value["verifier_token_sha256"] is not None) == (phase == "verifying"), "verifier capability phase mismatch")
        _require((value["verifier_scope"] is not None) == (phase == "verifying"), "verifier scope phase mismatch")
        if phase in {"prepared", "executing"}:
            _require(value["generation"] == 0, "initial registry generation mismatch")
        elif phase in {"agent_sealed", "verifying"}:
            _require(value["generation"] == 1, "agent registry generation mismatch")
        elif phase == "final_sealed":
            _require(value["generation"] == 2, "final registry generation mismatch")
        elif phase == "cleaned":
            _require(value["generation"] >= 1, "cleanup without an acknowledged seal")
    if name == "FenceReceipt":
        if value["status"] == "settled":
            expected = (1, "agent_sealed") if value["fence"] == "agent" else (2, "final_sealed")
            _require((value["generation"], value["phase"]) == expected and value["commit_acknowledged"] and value["remaining_inflight"] == 0 and value["committed_at"] is not None and value["elapsed_ms"] <= 5000, "invalid positive settlement receipt")
        else:
            _require(not value["commit_acknowledged"] and all(value[key] is None for key in ["generation", "phase", "committed_at", "remaining_inflight"]), "uncertain fence makes authoritative claim")
    if name == "VerificationRequest":
        validate("PostAgentBudget", value["budget"])
        validate("CreateDraftArgs", value["original_arguments"])
        validate("CreateDraftArgs", value["conflict_arguments"])
        _require(payload_hash(value["original_arguments"]) == value["original_request_hash"], "verifier original payload hash mismatch")
        expected = json.loads(json.dumps(value["original_arguments"]))
        quantity = expected["lines"][0]["quantity"]
        expected["lines"][0]["quantity"] += 1 if quantity < 1000 else -1
        _require(expected == value["conflict_arguments"], "verifier conflict differs from constrained quantity change")
    if name == "Event":
        data = value["data"]
        if "arguments" in data:
            _require("tool_id" in data, "arguments lack tool identity")
            validate("ToolCall", {"tool_id": data["tool_id"], "arguments": data["arguments"]})
        if data.get("tool_result") is not None:
            validate("ToolResult", data["tool_result"])
            _require(data.get("tool_id") == data["tool_result"]["tool_id"], "event result/tool mismatch")
            if value["event_type"] == "tool.completed":
                _require(not data["tool_result"]["is_error"], "successful completion contains error")
            if value["event_type"] == "tool.failed":
                _require(data["tool_result"]["is_error"], "failed tool contains successful result")
        for key, contract in [("receipt", "FenceReceipt"), ("exit", "ProcessExit"), ("result", "AgentResult"), ("failure", "Failure")]:
            if key in data:
                validate(contract, data[key])
                if key in {"receipt", "exit", "result"}:
                    _require(all(data[key][field] == value[field] for field in ["run_id", "attempt_id"]), "nested event identity mismatch")
        if value["event_type"].startswith("model.") and value["event_type"] != "model.started":
            missing = data["prompt_tokens"] is None or data["output_tokens"] is None
            _require(missing == (data["counts_unavailable_reason"] is not None), "model count availability mismatch")
        if value["event_type"] == "retrieval.completed":
            _require(set(data["exposed_tool_ids"]) <= set(data["authorized_tool_ids"]), "retrieval exposes unauthorized tool")
        if value["event_type"] == "grading.completed" and data["task_success"]:
            _require(_assertions_pass(data["original_assertions"], {"db-oracle", "answer"}), "grading event contradicts original assertions")
        if value["event_type"] == "fence.completed":
            _require((value["status"] == "ok") == (data["receipt"]["status"] == "settled"), "fence event status contradicts receipt")
        if value["event_type"].startswith("db."):
            operation = data["operation"]
            evaluator_operation = operation in {"snapshot", "seal", "reset"}
            _require((value["source"] == "evaluator") == evaluator_operation, "DB operation from wrong authority")
            allowed_phases = {"reset": {"prepare", "cleanup"}, "snapshot": {"grading", "verification"}, "seal": {"grading", "verification"}, "replay": {"verification"}, "create_draft": {"execution"}, "read_tool": {"execution"}}
            _require(value["phase"] in allowed_phases[operation], "DB operation in wrong phase")
    if name == "Failure":
        recoverable = {"unknown_tool", "invalid_arguments", "unauthorized_attempt", "tool_error", "db_error", "tool_timeout", "idempotency_conflict", "protocol_error"}
        _require(value["disposition"] != "recovered" or value["code"] in recoverable, "terminal safety failure marked recovered")
    if name in {"PostAgentBudget", "ControlRequest", "ControlResult", "ProcessExit", "VerifierResult"}:
        _transport_semantics(name, value)
    if name == "EvaluationResult":
        flags = ["agent_settlement_pass", "verifier_settlement_pass", "db_oracle_pass", "answer_pass", "replay_pass", "cleanup_pass", "final_state_unchanged"]
        _require(set(value["null_reasons"]) == {key for key in flags if value[key] is None}, "null verdict reason missing or spurious")
        original = all(value[key] is True for key in ["agent_settlement_pass", "db_oracle_pass", "answer_pass", "agent_budget_pass"])
        original = original and value["setup_pass"] and value["agent_status"] == "completed" and value["metrics"]["unauthorized_executions"] == 0
        for assertion_set in ["original_assertions", "verification_assertions"]:
            rows = value[assertion_set]
            _require(len({row["name"] for row in rows}) == len(rows), "duplicate assertion identity")
        for failure in value["failures"]:
            validate("Failure", failure)
        terminal = {row["code"] for row in value["failures"] if row["disposition"] == "terminal"}
        _require("unauthorized_execution" not in terminal or value["metrics"]["unauthorized_executions"] > 0, "execution safety failure contradicts observed count")
        original_terminal = {row["code"] for row in value["failures"] if row["disposition"] == "terminal" and row["stage"] in {"admission", "prepare", "retrieval", "agent", "execution", "grading"}}
        original = original and not original_terminal
        if original:
            _require(_assertions_pass(value["original_assertions"], {"db-oracle", "answer"}), "original PASS contradicts assertions")
        _require(value["task_success"] == original, "task success is not original settled outcome")
        if value["metrics"]["unauthorized_executions"] > 0:
            _require(value["quarantined"] and not value["comparison_valid"] and value["cleanup_pass"] is not True and "unauthorized_execution" in terminal, "actual unauthorized execution lacks safety stop and quarantine")
        for flag, assertion in [("db_oracle_pass", "db-oracle"), ("answer_pass", "answer")]:
            recorded = [row["pass"] for row in value["original_assertions"] if row["name"] == assertion]
            _require(len(recorded) == 1 and recorded[0] is value[flag], "original assertion and verdict disagree")
            if value[flag] is True:
                _require(_assertions_pass(value["original_assertions"], {assertion}, exact=False), "original verdict lacks passing assertion")
        if value["agent_settlement_pass"] is not True:
            _require(value["db_oracle_pass"] is None, "unsettled database assigned authoritative verdict")
        read_only = value["workflow_kind"] == "read_only"
        not_started = value["agent_status"] == "not_started"
        if read_only or not original:
            reason = "not_started" if not_started else "read_only" if read_only else "original_failed"
            for flag in ["verifier_settlement_pass", "replay_pass"]:
                _require(value[flag] is None and value["null_reasons"][flag] == reason, "inapplicable invoice verifier has a verdict")
            _require(value["metrics"]["verifier_calls"] == 0, "inapplicable verifier was called")
        unknown = "settlement_unknown" in terminal or any(reason == "settlement_unknown" for reason in value["null_reasons"].values())
        unknown = unknown or (not not_started and value["agent_settlement_pass"] is not True)
        if original and not read_only:
            unknown = unknown or value["verifier_settlement_pass"] is not True
        if unknown:
            _require(value["quarantined"] and not value["comparison_valid"] and value["cleanup_pass"] is not True, "unknown settlement not quarantined")
        if not_started:
            _require(value["agent_settlement_pass"] is None and value["null_reasons"]["agent_settlement_pass"] == "not_started", "unstarted agent has settlement claim")
        elif value["agent_settlement_pass"] is None:
            _require(value["null_reasons"]["agent_settlement_pass"] == "settlement_unknown", "unknown agent settlement mislabeled")
        if value["cleanup_pass"] is not True or not value["artifact_complete"]:
            _require(not value["comparison_valid"], "invalid cleanup/artifacts admitted to comparison")
        if value["replay_pass"] is True:
            _require(value["task_success"] and value["verifier_settlement_pass"] is True, "replay claims original repair or unknown final state")
            _require(value["metrics"]["verifier_calls"] == 2 and _assertions_pass(value["verification_assertions"], {"same-payload-replay", "changed-payload-conflict", "unchanged-state"}), "replay lacks both performed passing checks")
        verification_ok = value["replay_pass"] is True if original and not read_only else True
        if read_only or not original:
            _require({row["name"] for row in value["verification_assertions"]} <= {"unchanged-state"}, "skipped verifier claims replay assertions")
        if value["final_state_unchanged"] is True:
            _require(_assertions_pass(value["verification_assertions"], {"unchanged-state"}, exact=False), "final snapshot lacks unchanged-state assertion")
        safety_failure = bool(terminal & {"admission_blocked", "fixture_invalid", "prepare_failed", "reset_failed", "grader_error", "settlement_unknown", "verification_failed", "cleanup_failed", "resource_abort", "artifact_incomplete", "unauthorized_execution"})
        if value["quarantined"]:
            _require(value["cleanup_pass"] is not True, "quarantined state was reset")
        if value["comparison_valid"]:
            _require(value["metrics"]["unauthorized_executions"] == 0 and value["setup_pass"] and not not_started and value["agent_settlement_pass"] is True and value["final_state_unchanged"] is True and not value["quarantined"] and not safety_failure and verification_ok and all(row["pass"] is True for row in value["verification_assertions"]), "comparison contains safety, verification or evidence failure")
        metrics = value["metrics"]
        if metrics["task_latency_ms"] is not None and metrics["task_latency_ms"] > 300000:
            _require(not value["agent_budget_pass"], "known task latency exceeds declared passing agent budget")
        if metrics["missing_token_components"]:
            _require(metrics["prompt_tokens"] is None and metrics["output_tokens"] is None, "missing model counts imputed as complete")
        else:
            _require(metrics["prompt_tokens"] == metrics["known_prompt_tokens"] and metrics["output_tokens"] == metrics["known_output_tokens"], "complete token totals differ from known counts")
        _require((metrics["cost_usd"] is None) == (metrics["cost_basis"] is None), "cost lacks declared measurement/rate basis")
        _require((metrics["energy_joules"] is None) == (metrics["energy_basis"] is None), "energy lacks metered basis")
        if value["agent_status"] == "not_started":
            _require(not value["comparison_valid"], "unexecuted admission request admitted as comparison")
        if metrics["task_latency_ms"] is not None and metrics["lifecycle_latency_ms"] is not None:
            _require(metrics["lifecycle_latency_ms"] >= metrics["task_latency_ms"], "lifecycle duration shorter than agent duration")
        within_post_budget = metrics["post_agent_ms"] is not None and metrics["post_agent_ms"] <= 30000
        if value["comparison_valid"]:
            _require(within_post_budget, "comparison exceeded post-agent deadline")
        passed = original and verification_ok and value["comparison_valid"]
        expected_status = "blocked" if not_started else "passed" if passed else "failed"
        _require(value["overall_status"] == expected_status, "terminal status contradicts workflow verdicts")


def _assertions_pass(rows: list[dict[str, Any]], required: set[str], exact: bool = True) -> bool:
    indexed = {row["name"]: row["pass"] for row in rows}
    return required <= indexed.keys() and all(indexed[name] is True for name in required) and (not exact or all(row["pass"] is True for row in rows))


def _transport_semantics(name: str, value: dict[str, Any]) -> None:
    if name == "PostAgentBudget":
        start = dt.datetime.fromisoformat(value["started_at"].replace("Z", "+00:00"))
        end = dt.datetime.fromisoformat(value["deadline_at"].replace("Z", "+00:00"))
        _require(end - start == dt.timedelta(seconds=30), "post-agent wall correlation deadline changed")
        _require(value["remaining_ms"] == max(0, 30000 - value["elapsed_ms"]), "post-agent remaining budget inconsistent")
        _require(value["operation_timeout_ms"] == min(5000, value["remaining_ms"]), "operation exceeds shared remaining budget")
        return
    budget = value["budget"]
    if budget is not None:
        validate("PostAgentBudget", budget)
    if name in {"ControlRequest", "ControlResult"}:
        prepare = value["phase"] == "prepare"
        _require((budget is None) == prepare, "control phase has wrong deadline applicability")
        if name == "ControlRequest":
            _require((value["prior_result_id"] is None) == prepare, "control prior-result applicability mismatch")
            inputs = set(value["inputs"])
            expected = {"task", "fixture", "config"} if prepare else {"prior_phase_result", "agent_exit"} if value["phase"] == "settle-grade" else {"prior_phase_result"}
            allowed = expected if prepare else expected | ({"agent_result"} if value["phase"] == "settle-grade" else {"verifier_exit", "verifier_result"})
            _require(expected <= inputs <= allowed, "control phase inputs missing or inappropriate")
            if "verifier_result" in inputs:
                _require("verifier_exit" in inputs, "verifier result lacks host exit record")
        else:
            allowed = {"prepare": {"execute_agent", "blocked", "quarantine"}, "settle-grade": {"verify", "finalize", "quarantine"}, "finalize": {"complete", "quarantine"}}
            _require(value["action"] in allowed[value["phase"]], "invalid phase transition")
            outputs = set(value["outputs"])
            if value["failure"] is not None:
                validate("Failure", value["failure"])
                _require(value["failure"]["disposition"] == "terminal", "control failure marked recovered")
            if value["action"] in {"blocked", "quarantine"}:
                _require(value["status"] == "failed" and value["failure"] is not None, "terminal control decision lacks failure evidence")
            if value["action"] in {"execute_agent", "verify"}:
                _require(value["failure"] is None, "failed control action launched child")
            skip = "read_only" if value["workflow_kind"] == "read_only" else "original_failed" if value["original_pass"] is False else None
            _require(value["verifier_skip_reason"] == (skip if value["phase"] != "prepare" and value["action"] not in {"blocked", "quarantine"} else None), "verifier skip decision is inconsistent")
            allowed_outputs = {"prepare": {"agent_request"}, "settle-grade": {"agent_snapshot", "verification_request"}, "finalize": {"evaluation", "final_snapshot"}}
            _require(outputs <= allowed_outputs[value["phase"]], "control output from wrong phase")
            if prepare:
                _require(value["original_pass"] is None and value["fence_receipt"] is None, "prepare contains grading or fence")
            if value["action"] == "execute_agent":
                _require(value["status"] == "completed" and outputs == {"agent_request"}, "prepare lacks agent request")
            if value["action"] == "verify":
                _require(value["workflow_kind"] == "draft_invoice" and value["original_pass"] is True and outputs == {"agent_snapshot", "verification_request"}, "verifier issued without passing original invoice")
            if value["phase"] == "settle-grade" and value["action"] in {"verify", "finalize"}:
                _require(type(value["original_pass"]) is bool, "grade advances without original verdict")
                if value["workflow_kind"] == "draft_invoice" and value["original_pass"]:
                    _require(value["action"] == "verify", "passing invoice skipped verifier")
                receipt = value["fence_receipt"]
                _require(receipt is not None and receipt["status"] == "settled" and receipt["fence"] == "agent" and "agent_snapshot" in outputs, "grade advances without initial settled snapshot")
            if value["action"] == "complete":
                _require(outputs == {"evaluation", "final_snapshot"} and type(value["original_pass"]) is bool, "finalize lacks persisted terminal evidence or original verdict")
            if value["fence_receipt"] is not None:
                validate("FenceReceipt", value["fence_receipt"])
                _require(all(value["fence_receipt"][key] == value[key] for key in ["run_id", "attempt_id"]), "control receipt identity mismatch")
            if outputs & {"agent_snapshot", "final_snapshot"}:
                _require(value["fence_receipt"] is not None and value["fence_receipt"]["status"] == "settled", "authoritative snapshot lacks acknowledged fence")
            if value["phase"] == "settle-grade" and value["original_pass"] is not None:
                _require(value["fence_receipt"] is not None and value["fence_receipt"]["status"] == "settled" and value["fence_receipt"]["fence"] == "agent", "original verdict precedes initial settlement")
            if value["action"] == "quarantine":
                _require(value["status"] == "failed", "quarantine declared completed")
            elif value["action"] != "blocked":
                _require(value["status"] == "completed", "failed control phase advanced")
            if budget is not None and budget["remaining_ms"] == 0:
                _require(value["action"] == "quarantine", "expired control budget advanced")
    if name == "ProcessExit":
        allowed = {"agent": {"run"}, "verifier": {"verify"}, "evaluator": {"prepare", "settle-grade", "finalize"}}
        _require(value["phase"] in allowed[value["child"]], "child/phase mismatch")
        _require((budget is None) == (value["phase"] in {"prepare", "run"}), "process deadline applicability mismatch")
        observed_statuses = int(value["exit_code"] is not None) + int(value["signal"] is not None)
        _require(observed_statuses == int(value["reaped"]), "reaped process lacks one exact observed exit status")
        if value["termination"] == "exited":
            _require(value["reaped"] and value["exit_code"] is not None, "normal exit lacks observed code")
        if value["termination"] == "spawn_failed":
            _require(not value["reaped"] and value["result_delivery"] == "missing", "failed spawn claims child artifacts or exit")
        if value["termination"] == "terminated" and value["reaped"]:
            _require(value["signal"] is not None, "terminated process lacks observed signal")
        _require((value["result_ref"] is not None) == (value["result_delivery"] == "complete"), "delivery claims an unavailable result")
        if value["child"] == "evaluator":
            _require((value["result_message_id"] is not None) == (value["result_delivery"] == "complete"), "evaluator delivery lacks message correlation")
        else:
            _require(value["result_message_id"] is None, "non-control child claims control message ID")
    if name == "VerifierResult":
        _require(len(value["checks"]) == value["calls"], "verifier calls/check count mismatch")
        expected = ["same_payload_replay", "changed_payload_conflict"]
        _require([row["check"] for row in value["checks"]] == expected[:value["calls"]], "verifier checks changed order")
        for row in value["checks"]:
            result = row["tool_result"]
            if row["failure"] is not None:
                validate("Failure", row["failure"])
                _require(row["failure"]["stage"] == "verification" and row["failure"]["disposition"] == "terminal", "verifier failure outside verifier phase")
            if result is None:
                _require(not row["pass"] and row["failure"] is not None, "missing verifier response lacks failure evidence")
                continue
            validate("ToolResult", result)
            _require(result["tool_id"] == CREATE, "verifier used another tool")
            correct = result["is_error"] and result["error"]["code"] == "idempotency_conflict" if row["check"] == "changed_payload_conflict" else not result["is_error"] and result["result"]["invoice"]["invoice_id"] == value["invoice_id"]
            if row["check"] == "same_payload_replay" and not result["is_error"]:
                invoice, lines = result["result"]["invoice"], result["result"]["lines"]
                args = {key: invoice[key] for key in ["customer_id", "invoice_date", "due_date"]}
                args["lines"] = [{"item_id": line["item_id"], "quantity": line["quantity"]} for line in sorted(lines, key=lambda line: line["line_number"])]
                correct = correct and payload_hash(args) == value["original_request_hash"]
            _require(row["pass"] == bool(correct) and (not row["pass"] or row["failure"] is None), "verifier assertion contradicts observed result")
        if value["status"] == "completed":
            _require(value["calls"] == 2 and all(row["pass"] for row in value["checks"]), "completed verifier lacks two passing checks")


def validate_event_stream(events: list[dict[str, Any]]) -> None:
    """Validate a complete bounded trace; individual Event validation is shape/local only."""
    _require(0 < len(events) <= 10000, "event stream size invalid")
    seen, sequence, elapsed, opened, operation_ids = set(), {}, {}, {}, set()
    total_bytes = 0
    identity = (events[0].get("run_id"), events[0].get("attempt_id"))
    for event in events:
        validate("Event", event)
        line_bytes = len(json.dumps(event, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))
        _require(line_bytes <= MAX_DOCUMENT_BYTES, "event exceeds document budget")
        total_bytes += line_bytes + 1
        _require(total_bytes <= 104857600, "event stream exceeds artifact budget")
        _require((event["run_id"], event["attempt_id"]) == identity, "stream identity changed")
        _require(event["event_id"] not in seen, "duplicate event ID")
        seen.add(event["event_id"])
        source = event["source"]
        _require(event["sequence"] == sequence.get(source, 0) + 1, "source sequence gap or reorder")
        _require(event["elapsed_ms"] >= elapsed.get(source, 0), "source monotonic time regressed")
        sequence[source], elapsed[source] = event["sequence"], event["elapsed_ms"]
        kind, _, suffix = event["event_type"].partition(".")
        if kind in {"model", "tool", "db"}:
            key = (source, kind, event["call_id"])
            if suffix == "started":
                _require(key not in operation_ids, "operation ID reused")
                operation_ids.add(key)
                opened[key] = event
            else:
                _require(key in opened, "operation closed without start")
                start = opened.pop(key)
                _require(event["phase"] == start["phase"] and event.get("parent_call_id") == start.get("parent_call_id"), "operation correlation changed")
                fields = ["tool_id"] if kind == "tool" else ["operation", "transaction_id"] if kind == "db" else ["model_digest", "prompt_hash"] if suffix == "completed" else []
                _require(all(start["data"][field] == event["data"][field] for field in fields), "operation identity changed")
        if event["event_type"] == "operation.interrupted":
            data = event["data"]
            key = (data["operation_source"], data["operation_kind"], data["operation_call_id"])
            _require(key in opened, "interruption has no open operation")
            opened.pop(key)
    _require(not opened, "stream has unclosed operations without interrupted marker")


def validate_control_chain(requests: list[dict[str, Any]], results: list[dict[str, Any]], exits: list[dict[str, Any]], verifier: dict[str, Any] | None = None, verification_request: dict[str, Any] | None = None, agent_result: dict[str, Any] | None = None) -> None:
    """Check finalized transport records, not actual process, filesystem or DB behavior."""
    _require(len(requests) == len(results) and 1 <= len(requests) <= 3, "control chain length invalid")
    fields = ["run_id", "attempt_id", "task_id", "task_hash", "config_hash"]
    root = requests[0]
    message_ids = [record["message_id"] for record in requests + results]
    _require(len(set(message_ids)) == len(message_ids), "control message ID reused")
    anchor, last_elapsed = None, 0

    def bind(record: dict[str, Any], contract: str) -> None:
        nonlocal anchor, last_elapsed
        validate(contract, record)
        _require(all(record[key] == root[key] for key in fields), "transport identity changed")
        budget = record.get("budget")
        if budget is not None:
            current = tuple(budget[key] for key in ["anchor_id", "started_at", "deadline_at"])
            _require(anchor is None or anchor == current, "post-agent deadline was restarted")
            anchor = current
            _require(budget["elapsed_ms"] >= last_elapsed, "launcher budget regressed")
            last_elapsed = budget["elapsed_ms"]

    used_exits = set()
    prior = None
    for index, (request, result) in enumerate(zip(requests, results)):
        _require(request["phase"] == ["prepare", "settle-grade", "finalize"][index], "control phases reordered")
        validate("ControlRequest", request)
        _require(request["workflow_kind"] == root["workflow_kind"], "control workflow changed")
        if index:
            _require(request["prior_result_id"] == prior["message_id"], "control prior-result binding changed")
            previous_exit = next(record for record in exits if record["child"] == "evaluator" and record["phase"] == prior["phase"])
            _require(request["inputs"]["prior_phase_result"] == previous_exit["result_ref"], "prior-result artifact differs from host delivered reference")
            _require(prior["action"] in ({"execute_agent"} if index == 1 else {"verify", "finalize"}), "control continued after terminal action")
            child = "agent" if index == 1 else "verifier"
            expected = index == 1 or prior["action"] == "verify"
            matching = [(i, x) for i, x in enumerate(exits) if x["child"] == child]
            _require(len(matching) == int(expected), "missing or unexpected child exit")
            if expected:
                i, exit_record = matching[0]
                used_exits.add(i)
                result_key = "agent_result" if index == 1 else "verifier_result"
                _require((result_key in request["inputs"]) == (exit_record["result_delivery"] == "complete"), "request ignores host delivery outcome")
                if result_key in request["inputs"]:
                    _require(request["inputs"][result_key] == exit_record["result_ref"], "child result artifact binding changed")
                if child == "agent":
                    _require((agent_result is not None) == (exit_record["result_delivery"] == "complete"), "parsed agent result and host delivery disagree")
                    if agent_result is not None:
                        validate("AgentResult", agent_result)
                        _require(all(agent_result[key] == root[key] for key in ["run_id", "attempt_id"]), "parsed agent result identity changed")
                    if result["original_pass"] is True:
                        normal = exit_record["termination"] == "exited" and exit_record["exit_code"] == 0 and exit_record["signal"] is None and exit_record["reaped"]
                        _require(normal and exit_record["duration_ms"] <= 300000 and agent_result is not None and agent_result["status"] == "completed" and "agent_result" in request["inputs"], "original PASS contradicts trusted agent exit or delivered result")
                        _require(all(agent_result["counts"][key] <= limit for key, limit in AGENT_COUNT_LIMITS.items()), "original PASS exceeds observed agent count budget")
                if child == "verifier":
                    _require(verification_request is not None, "verifier has no bounded invocation")
                    if verifier is not None:
                        bind(verifier, "VerifierResult")
                        _require(all(verifier[key] == verification_request[key] for key in ["invoice_id", "idempotency_key", "original_request_hash"]), "verifier escaped registered request scope")
                    _require((verifier is not None) == (exit_record["result_delivery"] == "complete"), "verifier delivery/result mismatch")
                bind(exit_record, "ProcessExit")
                if not exit_record["reaped"]:
                    _require(result["action"] == "quarantine", "unreaped child advanced to grading or cleanup")
                if child == "verifier" and (exit_record["termination"] != "exited" or exit_record["exit_code"] != 0 or exit_record["result_delivery"] != "complete" or exit_record["duration_ms"] > 5000):
                    _require(result["action"] == "quarantine", "uncertain verifier process advanced")
            elif index == 2:
                _require(not ({"verifier_exit", "verifier_result"} & request["inputs"].keys()) and verifier is None, "skipped verifier produced evidence")
        bind(request, "ControlRequest")
        if index == 1 and result["action"] == "verify":
            _require(verification_request is not None, "verifier has no bounded invocation")
            # Generated inside settle-grade, before its result and host exit.
            # Preserve immutable request bytes and enforce the actual causal
            # interval rather than validating this older observation at finalize.
            bind(verification_request, "VerificationRequest")
        bind(result, "ControlResult")
        _require(result["phase"] == request["phase"] and result["workflow_kind"] == request["workflow_kind"] and result["request_id"] == request["message_id"], "phase result binding changed")
        evaluator_exits = [(i, x) for i, x in enumerate(exits) if x["child"] == "evaluator" and x["phase"] == request["phase"]]
        _require(len(evaluator_exits) == 1, "control phase lacks host process exit")
        i, host_exit = evaluator_exits[0]
        used_exits.add(i)
        bind(host_exit, "ProcessExit")
        _require(host_exit["termination"] == "exited" and host_exit["exit_code"] == 0 and host_exit["result_delivery"] == "complete" and host_exit["result_message_id"] == result["message_id"], "untrusted or undelivered control phase result")
        if index and host_exit["duration_ms"] > request["budget"]["operation_timeout_ms"]:
            _require(result["action"] == "quarantine", "overdue evaluator advanced")
        if index == 1 and request["workflow_kind"] == "draft_invoice" and result["original_pass"] is True:
            _require(result["action"] in {"verify", "quarantine"}, "passing invoice skipped verifier")
        if index == 2 and result["action"] == "complete":
            _require(result["original_pass"] == prior["original_pass"], "finalize changed original verdict")
            _require(result["verifier_skip_reason"] == prior["verifier_skip_reason"], "finalize changed verifier applicability")
            receipt = result["fence_receipt"]
            expected_fence = "verifier" if prior["action"] == "verify" else "agent"
            _require(receipt is not None and receipt["status"] == "settled" and receipt["fence"] == expected_fence, "finalize lacks applicable acknowledged fence")
        prior = result
    _require(len(used_exits) == len(exits), "unmatched process exit")
    _require((verification_request is not None) == any(row["action"] == "verify" for row in results), "verification invocation applicability mismatch")


def validate(name: str, value: Any) -> None:
    _require(name in SCHEMA["$defs"], "unknown contract")
    _walk(value)
    validator = StrictValidator({"$ref": SCHEMA_ID + "#/$defs/" + name}, registry=REGISTRY, format_checker=FORMATS)
    errors = list(validator.iter_errors(value))
    if errors:
        raise ContractError("schema violation in " + name)
    if name not in PRIVATE:
        _no_secret_keys(value)
    _semantics(name, value)


def validate_task_fixture(task: dict[str, Any], fixture: dict[str, Any]) -> None:
    validate("Task", task)
    validate("Fixture", fixture)
    _require((task["fixture_id"], task["fixture_version"]) == (fixture["fixture_id"], fixture["fixture_version"]), "task fixture identity mismatch")
    if task["expected_state"]["kind"] == "draft_invoice":
        expected = task["expected_state"]
        customer = next((row for row in fixture["seed"]["customers"] if row["customer_id"] == expected["customer_id"]), None)
        _require(customer is not None and customer["active"], "expected customer missing or inactive")
        items = {row["item_id"]: row for row in fixture["seed"]["items"]}
        for row in expected["lines"]:
            item = items.get(row["item_id"])
            _require(item is not None and item["active"] and item["unit_price_cents"] == row["unit_price_cents"], "expected price/item differs from fixture")
    else:
        expected = task["expected_state"]
        table = expected["record_table"]
        ids = {row[TABLE_KEYS[table]] for row in fixture["seed"][table]}
        _require(set(expected["required_record_ids"]) <= ids, "read expected record missing from fixture")
        table_tools = {
            "customers": {"billing_list_customers", "billing_get_customer"},
            "items": {"billing_list_items"},
            "projects": {"billing_list_projects", "billing_get_project"},
            "timesheets": {"billing_list_timesheets", "billing_get_timesheet"},
            "invoices": {"billing_list_invoices", "billing_get_invoice"},
        }
        _require(bool(table_tools[table] & set(task["relevant_tool_ids"])) and CREATE not in task["permitted_tools"], "read expected table/tool or permissions mismatch")


def validate_run_bundle(task: dict[str, Any], fixture: dict[str, Any], mapping: dict[str, Any], evaluation: dict[str, Any], agent: dict[str, Any] | None) -> None:
    """Cross-bind private task/oracle and public result without leaking them to requests."""
    validate_task_fixture(task, fixture)
    for name, value in [("RunMapping", mapping), ("EvaluationResult", evaluation)]:
        validate(name, value)
    if agent is not None:
        validate("AgentResult", agent)
    kind = task["expected_state"]["kind"]
    _require(mapping["workflow_kind"] == evaluation["workflow_kind"] == kind, "workflow applicability differs from task")
    _require(all((value["run_id"], value["attempt_id"]) == (mapping["run_id"], mapping["attempt_id"]) for value in [evaluation] + ([agent] if agent is not None else [])), "run bundle identity mismatch")
    _require(evaluation["task_id"] == task["task_id"] and evaluation["task_hash"] == canonical_hash(task) and evaluation["fixture_hash"] == canonical_hash(fixture), "run task/fixture hash mismatch")
    _require(mapping["tenant_id"] == fixture["tenant_id"] and mapping["principal_id"] == task["principal_id"] and set(mapping["allowed_tools"]) == set(task["permitted_tools"]), "run permission or tenant binding mismatch")
    if agent is None:
        _require(evaluation["agent_status"] != "completed" and evaluation["answer_pass"] is not True, "missing agent result supplies success evidence")
        return
    _require(evaluation["agent_status"] == agent["status"], "agent outcome binding mismatch")
    if evaluation["agent_budget_pass"]:
        limits = {"model_calls": task["budgets"]["model_turns"], "tool_calls": task["budgets"]["tool_calls"], "retries": task["budgets"]["transient_retries"]}
        _require(all(agent["counts"][key] <= limit for key, limit in limits.items()), "passing budget contradicts parsed agent counts")
    if kind == "read_only" and evaluation["answer_pass"] is True:
        _require(agent["final_answer"]["invoice_id"] is None and set(agent["final_answer"]["record_ids"]) == set(task["expected_state"]["required_record_ids"]), "read answer does not match exact expected record IDs")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("contract", choices=sorted(SCHEMA["$defs"]))
    parser.add_argument("file")
    args = parser.parse_args()
    try:
        validate(args.contract, load_file(args.file))
    except (ContractError, OSError) as exc:
        parser.exit(1, "INVALID: " + str(exc) + "\n")
    print("VALID: " + args.contract)


if __name__ == "__main__":
    main()
