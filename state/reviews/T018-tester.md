# T018 independent runtime tester

Verdict: **BLOCKED — fresh resource gate failed before SQL.** No runtime retry was attempted. This does not identify an adapter defect, and it does not invalidate the earlier source approval.

Candidates inspected: adapter `f2c4dc9fff47567d826275c343dcb1b2b1a066ee` in `.worktrees/T018`; database grant/test candidate `8707121` in `.worktrees/db-grants`. Both worktrees were clean. This tester authored neither the adapter nor the supplied runtime harnesses.

## Actual checks

Executed from `/home/sfkim/projects/mcpbench`:

```text
python3 artifacts/admission/t018/independent_verify.py
```

Exit **1**, assertion at line 34: `mem['MemAvailable'] >= 20*1024**3`. This was a fresh `/proc/meminfo` observation after environment verification, not an inference from old audit evidence. The helper did not persist its precise failing RAM value before the assertion. A separate diagnostic at `2026-11-09T06:12:02.263654+00:00` recorded `MemAvailable: 20857084 kB` (about 19.89 GiB), also below 20 GiB. This later observation is not presented as the original failed sample or a successful retry.

The helper had already passed all assertions preceding that resource check:

- Exact owned container `86a17f3d5a78e47cedcdd43ea2782c5ac663cdac2e09133bba05130bf372c329`, pinned image `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`, running/healthy and not OOM-killed.
- Compose project `mcpbench`, service `db`, root project working directory and explicit `/home/sfkim/projects/mcpbench/compose.yaml` labels.
- 512 MiB memory and memory-plus-swap limits, 0.5 CPU, 128 PIDs; user `999:999`, read-only root filesystem, no privilege flag.
- No published ports; sole network `mcpbench_db`, verified owned/internal, with IP matching bootstrap evidence (`172.19.0.2`). Owned `mcpbench_db-data` volume mounted at the expected data directory.
- Exactly 19 unrelated containers matched the saved admission baseline for IDs, names, status, start times, OOM state and health. The pre-existing unhealthy Immich ML status was preserved.

The older `artifacts/admission/t018/admission.json` recorded all admission checks passing after a 60.335-second sample, minimum available RAM 23.385 GiB, five swap-in pages, zero swap-out and longest swap activity streak one. That historical pass does not override the fresh failed RAM assertion. No new 60-second sample was run, and the disk assertion after the RAM check was not reached.

## Runtime acceptance status

| Criterion | Result |
| --- | --- |
| Owned database identity, isolation, limits and no published ports | PASS, live inspection |
| Existing 19-service state/health baseline | PASS, live inspection |
| Fresh 20 GiB RAM prerequisite | FAIL; runtime gate BLOCKED |
| Ten actual PostgreSQL integration cases | UNRUN, 0 executed |
| Production-driver lifecycle, fences, oracle and reset harness | UNRUN |
| SQL connections made by this tester | 0 |

No infrastructure, grants, source, Git, native Ollama or model changes were made. Neither runtime harness was executed; consequently no independent PostgreSQL or lifecycle success artifact is claimed. The ignored helper and `artifacts/admission/t018/independent-gate-failure.json` preserve the verification procedure and failure evidence. Earlier shell discovery also found no `python` alias; using `python3` allowed inspection and the gate check. That command-availability issue was not a runtime test result.

The assigned scope is direct PostgreSQL/library lifecycle validation only. MCP workflow, Go billing execution, real verifier replay and model behavior remain outside this lane. The orchestrator owns renewed admission and task status; this report supplies no T018 completion approval.
