# T014 focused independent re-review

Candidate: `97242472088dc9b88815e5d4cbc114afd870b919` in `.worktrees/T014`,
reviewed against the prior `2db9a23` findings. Verdict: **APPROVE** for this
focused review. No remaining P0/P1 findings identified in the repairs or their
immediate regression surface.

The reviewer inspected source and regression tests only. No source/Git mutation,
runtime request, model call, DB operation or container action was performed.
Independent execution and acceptance of cached checks remain with the orchestrator.

## Findings resolved

* **Expected conflict evidence:** `internal/agent/verify.go` now retains the
  expected error-shaped conflict response as recovered `idempotency_conflict`,
  while real failed checks retain terminal `verification_failed`. The successful
  two-check path no longer contradicts its own verdict. The added wrong-invoice
  branch explicitly preserves terminal evidence even when the tool returned a
  structurally successful response. `TestFixedVerifier` and
  `TestVerifierRejectsWrongInvoice` assert both sides and retain Python trace/result
  parity checks.
* **Calendar and date-order semantics:** `DecodeToolResult` now parses invoice
  date, due date and created_at, rejects year zero, and checks due-date ordering.
  `ValidateEvent` additionally parses the event timestamp. The existing schema
  patterns still constrain spelling and UTC shape; money/reference checks remain
  intact. Negative parity cases now include impossible dates, reversed dates,
  hour 24, second 60 and year zero, alongside a valid draft event. Argument dates
  also reject year zero. These changes close the identified semantic gap without
  weakening the positive path.
* **Verifier startup budget:** `executeWithConnector` records one entry time before
  reading/validating inputs. Its verification context expires at the earlier of
  the entry-relative supplied remaining budget and the absolute UTC deadline.
  Connection inherits that context and its five-second operation cap.
  `VerifySince` consumes the same entry time for later call limits and returned
  elapsed observations, preserving the anchor rather than restarting the budget.
  The scripted startup regression covers successful charged startup, supplied
  remaining-budget exhaustion and earlier wall-deadline exhaustion; it checks
  zero tool calls after exhaustion and authoritative Python artifact parity.
* **FIFO input guard:** `ReadDocument` now opens with O_NONBLOCK and rejects the
  nonregular file before reading. The new FIFO-without-writer test checks prompt
  rejection. Ordinary regular-file handling and no-replace result publication
  remain unchanged.

The production connector still uses the fixed MCP implementation; injection is
limited to the test seam. Verification remains model-free, discovery-free,
two-call bounded and retry-free. The earlier accepted SDK handshake, business
result normalization, auth separation and fixed HTTP endpoints are unchanged.

No live MCP/Ollama/DB success is established by this approval. Combined producer
wiring, mount isolation and actual SQL/settlement remain gated by later tasks.
