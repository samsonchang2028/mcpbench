# T001/T007 independent review

Candidate: `8ca76690813198578083c73824668f700ed7b5c8`, compared with
`b9db1c9cb874fe512ef6290b6a045c25cb1011f5`, in `.worktrees/T001-T007`.
Verdict: **APPROVE** for the T001/T007 admission evidence candidate.
No open P0/P1 findings; no material P2/P3 findings.

Reviewed both changed files, the supplied context pack, AGENTS.md,
agents/reviewer.md, T001/T007/T040 acceptance rows, and IMPLEMENTATION_PLAN's
admission and stop rules. Applied token-efficient-coding. Both worktree files
were byte-checked against the frozen commit. No candidate, Git, host-service,
container, model or configuration changes were made during review.

## Evidence and readiness

- **T001 storage evidence:** `user_supplied_model_storage` retains the authenticated
  user-provided commands, resolved model path, device, filesystem, mount point and
  229G available observation. The unavailable command timestamp and lack of an
  independent sfkim traversal are explicit. The supplied evidence legitimately
  resolves the previously inaccessible model target; it does not change Unix
  access permissions. Fresh `disk` output independently records the same device
  for project, actual Docker root and model parent, with 245,558,616,064 bytes
  (228.69 GiB) available. No symlink onto a different model filesystem is inferred.
- **T001 inventory:** retained `containers_before`/`containers_after`,
  `docker_stats`, `networks`, `volumes`, `listeners` and `routes` provide the
  required workload, limits, health, storage and network observations.
  Ollama version/tag/show/ps evidence identifies server 0.40.13, installed
  qwen3.5:9b, Q4_K_M and digest
  `56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.
  Metadata advertises tools; the candidate does not claim successful tool calling.
- **T007 resource sample:** independently recomputed from all 31 `samples`:
  60.055557 seconds, minimum MemAvailable 26,948,460,544 bytes (25.09771 GiB),
  two swap-in pages in exactly one interval, zero swap-out, and CPU busy
  7.381341%. This satisfies the 60-second, 20 GiB and no-sustained-swap rules.
  Available disk exceeds the separate 20 GiB threshold.
- **T007 regression check:** all 19 before/after container records compare equal,
  including identity, start time, state, OOM flag, health and limits: 15 running,
  four exited. Immich ML remains unhealthy; other declared health checks remain
  healthy. NVML's driver/library mismatch is explicitly retained as an existing
  constraint. Neither observation warrants unrelated host repairs or GPU claims.
- **T007 collision and sharing checks:** retained inventories contain no mcpbench
  project or proposed mcpbench_db/mcpbench_pgdata resources. Independently checked
  172.30.77.0/24 against every retained Docker subnet and non-default host route:
  no overlap. Listener inventory has no TCP 18081 listener and shows native
  Ollama at 127.0.0.1:11434; its connection inspection has only the header.
  Both model-residency snapshots are empty, so no rival resident model would be
  displaced at those observations. Proposed publication stays loopback-only and
  the database stays unpublished.

## Limits and following gates

Admission is a time-sensitive observation, not a reservation or exclusive-use
guarantee. Immediate pre-call refresh of resources, service health and Ollama
residency/sharing remains required. Actual loaded-model memory is unmeasured;
the API's 6,550,825,550-byte size must not be used as inference RAM. If measured
model memory exceeds 12 GiB, recalculate the budget before further launch work.

The bounded T040 probe still requires its own implementation, retained response,
independent validation and two-second monitoring. Preserve the reviewed 120-second
deadline, 4096 context and 512 output caps, and abort for RAM below 8 GiB for three
samples, sustained swap over three samples, MCPBench OOM, or existing-service
health regression. Continue observing after cancellation without forced unload.
CPU timeout remains a failed probe rather than a waived capability requirement.

Live inference, valid tool output, runtime memory, Compose startup and application
tests were **UNRUN** in this review and are not T001/T007 acceptance claims.
No required evidence for this fixed admission candidate remains missing. This
review does not complete either DAG node, authorize startup, or replace the
independent tester and orchestrator integration gates.
