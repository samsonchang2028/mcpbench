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
    if name == "Catalog":
        tools = value["tools"]
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
        validate("CreateDraftArgs", value["original_arguments"])
        validate("CreateDraftArgs", value["conflict_arguments"])
        _require(payload_hash(value["original_arguments"]) == value["original_request_hash"], "verifier original payload hash mismatch")
        expected = json.loads(json.dumps(value["original_arguments"]))
        quantity = expected["lines"][0]["quantity"]
        expected["lines"][0]["quantity"] += 1 if quantity < 1000 else -1
        _require(expected == value["conflict_arguments"], "verifier conflict differs from constrained quantity change")
    if name == "Event":
        if value["event_type"] in {"tool.completed", "tool.failed", "model.completed"}:
            _require("call_id" in value, "call event lacks correlation")
        data = value["data"]
        if "arguments" in data:
            _require("tool_id" in data, "arguments lack tool identity")
            validate("ToolCall", {"tool_id": data["tool_id"], "arguments": data["arguments"]})
        if "tool_result" in data:
            validate("ToolResult", data["tool_result"])
            _require(data.get("tool_id") == data["tool_result"]["tool_id"], "event result/tool mismatch")
    if name == "EvaluationResult":
        flags = ["agent_settlement_pass", "verifier_settlement_pass", "db_oracle_pass", "answer_pass", "replay_pass", "cleanup_pass"]
        _require(set(value["null_reasons"]) == {key for key in flags if value[key] is None}, "null verdict reason missing or spurious")
        original = all(value[key] is True for key in ["agent_settlement_pass", "db_oracle_pass", "answer_pass", "agent_budget_pass"])
        original = original and value["agent_status"] == "completed" and value["metrics"]["unauthorized_executions"] == 0
        _require(value["task_success"] == original, "task success is not original settled outcome")
        if value["agent_settlement_pass"] is not True:
            _require(value["db_oracle_pass"] is None, "unsettled database assigned authoritative verdict")
        unknown = any(row["code"] == "settlement_unknown" for row in value["failures"])
        if unknown or value["agent_settlement_pass"] is False or value["verifier_settlement_pass"] is False:
            _require(value["quarantined"] and not value["comparison_valid"] and value["cleanup_pass"] is not True, "unknown settlement not quarantined")
        if value["cleanup_pass"] is not True or not value["artifact_complete"]:
            _require(not value["comparison_valid"], "invalid cleanup/artifacts admitted to comparison")
        if value["replay_pass"] is True:
            _require(value["task_success"] and value["verifier_settlement_pass"] is True, "replay claims original repair or unknown final state")
        metrics = value["metrics"]
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
        passed = original and all(value[key] is True for key in ["verifier_settlement_pass", "replay_pass", "cleanup_pass", "artifact_complete", "comparison_valid"])
        if value["overall_status"] == "passed":
            _require(passed and not value["quarantined"] and metrics["verifier_calls"] <= 2 and metrics["post_agent_ms"] is not None and metrics["post_agent_ms"] <= 30000, "smoke PASS lacks required safety evidence")


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
