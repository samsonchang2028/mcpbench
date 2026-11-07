# Shared assumptions — approved documentation wave

Planning baseline for T003, T004 and T005. The user's latest instructions override
older planning text. These are documentation decisions, not verified runtime facts.
No application code, Docker operations, dependency installs or live calls are
authorized. T006's machine-readable contracts remain future work.

## Fixed product and evaluation assumptions

- Preserve the research question and four strategies: full context, semantic top-k,
  hybrid (authorization/metadata + keywords + vectors), and hierarchical domains.
- V1 first proves the three-tool draft-invoice smoke slice, then ten executable
  tools. Only after baseline gates add retrieval implementations and larger catalogs.
- Go implements the MCP server and small tool-calling agent; Python implements
  evaluation preparation, reset, independent grading, artifacts and summaries.
- V1 uses structured JSONL, run IDs, call IDs and deterministic artifacts. No
  OpenTelemetry SDK, Jaeger or collector. Those are v2 and are not prerequisites.
- Fixture: CUST-001; SVC-CONSULT × 2 at 12,500 cents; USD, tax zero, total
  25,000 cents; invoice 2026-11-07, due 2026-11-21; exactly one draft, no other
  writes, final answer identifies the persisted ID. Replay the same idempotency
  key without another write. Server owns all money and state validation.
- Baseline has billing-reader and billing-drafter synthetic principals; every
  tool call receives independent server ACL and trusted run/tenant validation.
  User/model text cannot choose credentials, principal, database/schema or URLs.
- Every attempt uses its own benchmark-owned database/schema and seed fingerprint.
  Failed reset prevents execution. Save result/snapshot evidence before cleanup;
  final cleanup restores the fingerprint. No shared/homelab volume resets.

## Process and trust boundaries

Design a private-network Python evaluator container with benchmark DB access and
a separate Go agent container. The trusted host-side launcher owns Compose
lifecycle and sequences evaluator prepare → agent execute → evaluator grade/reset.
It is part of the evaluation control plane, never a model-exposed tool. Neither
container receives the Docker socket or privilege. Container launch/monitoring
implementation remains future O-owned integration work, not work in this wave.

Use a bounded versioned JSON request/result protocol via run-specific files or
stdin/stdout controlled by that launcher. Python owns orchestration/grading policy;
the launcher handles process transport only. Mount only sanitized request and
agent event/result paths into the Go container, excluding expected states,
grader data, evaluator credentials and parent artifact directories. No secrets in
agent stdout/logs. Launch argument/env allowlists and exact schema are frozen at
T006. Record agent exit status; no-result/crash still receives a failed attempt
record and evaluator cleanup. No runtime agent can request arbitrary launches.

The Go agent uses host networking only to call native Ollama on loopback and MCP
on loopback candidate 18081; it opens no listener and has no DB credentials.
PostgreSQL is private, with no published host port; MCP reaches it on the private
Compose network. The Python evaluator reaches DB on that private network, not
through the agent. The trusted launcher carries only run-scoped synthetic auth
and routing metadata to the agent/MCP boundary. Host networking reduces isolation;
fixed application endpoints are not OS egress enforcement. Document residual risk.

## Resource and measurement assumptions

The existing IMPLEMENTATION_PLAN admission/abort policy remains binding: >=20 GiB
available RAM, >=20 GiB free on relevant filesystems, a 60-second sample with no
sustained swapping or health regression; reserve >=8 GiB while running. Native
Ollama memory is outside container caps. Model identity/residency, driver usability,
workloads and ports remain unverified. Never infer host capability from sandbox
permission errors. No pulls, unloads, config changes or public bindings.

Proposed caps: PostgreSQL 512 MiB/0.5 CPU; MCP 256 MiB/0.5 CPU; agent
512 MiB/1 CPU; Python evaluator 512 MiB/0.5 CPU, serial attempts. Proposed model
estimate 8–12 GiB until measured. Requests: supported context 4096, output 512,
temperature 0; <=8 model turns, <=12 calls, 5-second DB/tool deadlines,
120-second model deadline and 300-second task deadline. At most one transient
retry under the same total budget, preserving write idempotency. Record supported
seed/thinking/keep-alive settings without changing global Ollama configuration.

Use UTC timestamps, monotonic durations, schema/fixture/catalog/model/config hashes,
structured outcomes and null unavailable metrics. Keep retrieval, reasoning and
execution evidence distinct; permit uncertain or multiple failure labels. Include
all routing/retry costs; dollar/energy claims need actual rates/measurements.

T040 is an early future probe after T007 and separate user approval: one bounded
native Ollama request with a harmless synthetic `probe_echo` function, strict
returned name/argument validation and local echo computation. No MCP server or
billing write is needed. Its success does not replace T023's real invoice oracle.

## Completion boundary

Each implementer modifies only its assigned files and reports assumptions or
conflicts to O. O alone changes this shared baseline, graph, plans and state.
Review/test frozen candidates independently. Unresolved contract decisions block
T006; do not mark it DONE merely because these prose documents pass review.
