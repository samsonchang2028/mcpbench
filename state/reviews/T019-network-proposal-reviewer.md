# T019 network proposal independent review

Candidate: `docs/ARCHITECTURE.md`, section “Pending decision: MCP host access on an internal-only Docker network”, lines 248–297; whole-file Git blob `b19ee82de2888ee0151748ac9b4db02fed38b68e`. Reviewed on 2026-11-09 against AGENTS.md, reviewer instructions, T019 context/task row and the frozen Host/Origin requirements in `contracts/PROTOCOL.md`.

Route: FULL, because this proposes an infrastructure/security boundary change.

Verdict: **APPROVE for presentation as a proposed decision only.** No P0/P1 findings in the proposal. Neither option is authorized for implementation/deployment by this review. User REQ9 approval remains required; T019 remains BLOCKED. Runtime/source acceptance remains UNRUN.

## Recommendation

Prefer **A**, if the user accepts its additional service and measured resource cost. It preserves the existing MCP/DB/evaluator internal-only attachments and confines the new outbound routing to a narrowly implemented gateway. It does add a component able to reach the internal network and the front network; fixed forwarding is an application restriction, not OS egress confinement. Lack of DB credentials limits application authority but does not eliminate network reach or the need to harden/review that component.

**B** is feasible as the smaller runtime/configuration change, but explicitly grants the credential-bearing MCP service outbound routing. Existing URL/tool allowlists cannot restore the prior OS network boundary. Select B only with explicit user acceptance of that tradeoff. Neither option needs host networking for MCP, daemon/firewall changes, a DB-network recreation, public DB publication or Ollama changes.

The supplied actual observation (healthy internal MCP, requested loopback publication, effective `8080/tcp:null`, refused host connection, sole internal network) adequately explains why requested HostConfig alone cannot establish connectivity. The supplied Moby discussion supports the default-gateway explanation. This review did not independently rerun inspection or fetch the discussion; it does not generalize that explanation into a guarantee that either proposed layout is operational on this host.

## Findings and implementation constraints

- **P2 — Gateway acceptance detail, architecture lines 273–294.** Explicitly include transparent handling of the pinned SDK's actual MCP initialization, discovery, tool calls, headers, response/content types and any supported session/stream lifecycle. A fixed HTTP proxy that buffers, rewrites Host/Origin, redirects, or imposes incompatible timeouts could pass health/discovery yet break writes, cancellation or response delivery. Smallest useful follow-up: fixed upstream and explicit path/method allowlist, preserved end-to-end MCP/auth/Host/Origin semantics, bounded body/stream handling, no redirect following or caller-selected destination, and focused positive/negative transport tests before runtime admission. Preserve absolute existing deadlines and retry/idempotency rules; do not add proxy retries for uncertain writes. Health must use a permitted route/Host, without weakening the frozen MCP checks. The proposed fresh full-stack assertions already provide the necessary final billing checks.
- **P2 — Isolation proof, architecture lines 270–294.** Internal-only attachment is necessary evidence for A, but configuration labels alone do not prove effective isolation. At the approved runtime gate, inspect actual attachment/publication identities and use scoped reachability checks to establish the intended host→gateway→MCP path, no direct MCP host publication, and unchanged DB isolation. Verify gateway credential mounts/privileges and inspect the effective front routing. This should stay within MCPBench resources and avoid scans or probes of unrelated services.

No architectural contract drift is proposed: integer-cent billing, server ACLs, control-plane/oracle separation, internal DB and frozen agent localhost endpoint remain intact. Gateway request headers necessarily carry transient caller authorization; “no credential mounts” must not be interpreted as “never handles credentials.” Do not log them or mount reusable control-plane secrets.

## Required evidence after user approval

Freeze the smallest candidate: gateway binary/image using the existing locked Go toolchain (A only), owned front-network wiring and effective publisher, the launcher's corresponding service/health handling, immutable image/config manifests, focused tests, and existing architecture/security/resource documentation. Avoid a generic proxy framework or unrelated launcher refactor. Independently review/test the changed candidate before runtime changes.

The proposed limits (64 MiB/0.1 CPU) remain hypotheses. Apply the existing admission gate before build/start, add the service to total resource accounting, validate the limits under required protocol traffic, and preserve baseline service health and stop rules. No model inference is authorized.

For fair comparison, freeze one selected topology/image/configuration for every strategy, count gateway latency in existing MCP/client timing without double counting, and record its resource cost and failures as shared infrastructure. Do not silently switch A/B between runs or exclude gateway-induced failures. Existing client timing can include the hop without a new JSONL producer/schema.

Require actual loopback-only effective publication (including IPv6 inspection), official SDK discovery/calls, denied-caller zero-write behavior, unchanged credential boundaries and homelab baseline, followed by T019's registered deterministic fresh smoke/replay/conflict/wrong-write/lost-response/concurrency and durable settlement/snapshot/reset evidence. Preserve failed and quarantined attempts. No T019 completion follows from this proposal review.

Checks performed: bounded document/contract review and candidate blob identification only. Tests, Docker/SQL operations, builds, network changes and live model checks: **UNRUN, outside this assignment**. Only this review artifact was written.
