# T018 independent runtime tester

Verdict: **PASS for the assigned PostgreSQL and production-backend library lifecycle scope**, after the explicitly authorized third admission attempt. The two earlier RAM gate failures remain preserved; neither was retried without a new instruction. This report does not establish MCP/Go/model workflow correctness or independently authorize task completion.

Fixed candidates: adapter `f2c4dc9fff47567d826275c343dcb1b2b1a066ee` in `.worktrees/T018`; grant/test candidate `8707121b4771183148e59c7abb6496e757b02b20` in `.worktrees/db-grants`. Both worktrees were clean at execution. This tester authored neither the adapter nor the supplied runtime harnesses. Harness copies changed only output filenames; source/copy hashes and exact replacements are in `artifacts/admission/t018/independent-retry3-harnesses.json`.

## Admission and environment — PASS

Fresh admission ran 31 bounded samples over **60.3287 seconds**, with 2.01-second spacing. Every sample had at least 20 GiB available RAM; minimum was **23,943,790,592 bytes (22.2994 GiB)**. Observed swap-in/out deltas were both zero; longest swap activity streak was zero. No model was resident. Project, Docker and verified model filesystem checks each showed **244,901,724,160 bytes free**, above 20 GiB.

All 19 unrelated containers exactly matched the saved admission baseline throughout: IDs, names, status, start times, OOM state and health. Only the exact admitted owned database ID was excluded from that comparison. Its running/healthy/non-OOM state was checked in every sample. The existing unhealthy Immich ML baseline was preserved.

The existing independent verification logic checked ownership and isolation before admission, after admission and after SQL execution:

- Container `86a17f3d5a78e47cedcdd43ea2782c5ac663cdac2e09133bba05130bf372c329`, pinned image `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a`.
- Compose project `mcpbench`, service `db`, explicit project-root working directory and `/home/sfkim/projects/mcpbench/compose.yaml` labels; running and healthy with no OOM.
- 512 MiB memory and memory-plus-swap limits, 0.5 CPU, 128 PIDs; user `999:999`, read-only root filesystem, no privilege flag.
- No published ports; sole network `mcpbench_db`, owned and internal; IP `172.19.0.2` matched bootstrap evidence. Owned `mcpbench_db-data` volume mounted at the expected data path.

Post-runtime verification at **2026-11-09T06:37:06.593412+00:00** again passed identity, limits, health, isolation, RAM and the exact 19-service baseline.

Evidence: `independent-retry3-admission.json`, `independent-retry3-environment-pre.json`, `independent-retry3-environment-post.json`, and `independent-retry3-environment-runtime-post.json`, all under `artifacts/admission/t018/`.

## Actual SQL checks — PASS

Executed from `/home/sfkim/projects/mcpbench`, using the cached T008 environment: **Python 3.14.4, psycopg 3.3.8**.

```sh
.worktrees/T008/.venv/bin/python artifacts/admission/t018/independent_admission_retry3.py
PYTHONPATH=/home/sfkim/projects/mcpbench/.worktrees/db-grants .worktrees/T008/.venv/bin/python artifacts/admission/t018/independent_retry3_postgres.py
PYTHONPATH=/home/sfkim/projects/mcpbench/.worktrees/T018 .worktrees/T008/.venv/bin/python artifacts/admission/t018/independent_retry3_lifecycle.py
.worktrees/T008/.venv/bin/python artifacts/admission/t018/independent_retry3_runtime_post.py
```

All commands exited **0**. PostgreSQL suite: **10 tests passed in 1.803 seconds; 0 errors, 0 failures, 0 skipped**. Real SQL and assertions executed against the owned database using the three dedicated roles. The test-only connection factory selected the verified container IP and asserted each connection's actual database/user; no fake SQL was used. These ten tests cover:

- Required invoice lines and idempotency ledger at commit.
- Foreign keys, quantity/money constraints and atomic rollback.
- Service least privilege and grader read-only/grant enforcement.
- Rollback, upgrade and repeated rollback.
- Effective CONNECT privilege confined to the benchmark database for all three roles.
- Rejection of unexpected tables/columns and restoration to the seed.
- Repeat seeding and migration after reconnecting to the persisted database.
- Actual shared/exclusive registry lock blocking with bounded lock timeouts.
- Valid service invoice insertion and unique idempotency key enforcement.
- Migration checksum rejection.

Evidence: `independent-retry3-postgres-tests.json` and `independent-retry3-postgres-tests.redacted.txt`.

## Production-backend lifecycle — PASS

Unique run: `run-lifecycle-b8db08217c1fd7e23093`. The production adapter's real libpq connections, transactions, driver waits and SQL ran unchanged; only `_resolve` was substituted to bridge the host's missing private `db` alias to the independently verified container IP.

The harness passed preparation and canonical seed fingerprint, agent activation, a service-role transaction holding the shared registry lock and writing a synthetic 25,000-cent draft with line/ledger, acknowledged agent fencing, consistent capture and state grading, verifier activation and acknowledged fencing, unchanged final tables, durable evidence before cleanup, canonical reset, and final `cleaned` registry state with both tokens revoked.

Wrong customer, wrong date and stale settlement generation were each rejected by the oracle. Those negatives mutate captured snapshot copies in memory; they do not establish that separately persisted corrupt database writes were injected. The verifier checks activation/fencing and unchanged state; it does not replay a real MCP verifier call.

Evidence: `independent-retry3-lifecycle.json` plus the unique run's `-plan.json`, `-before-cleanup.json` and `-reset-proof.json` files in the same artifact directory. Cleanup used the registered run's scoped reset and retained its evidence and cleaned registration. The ten PostgreSQL tests used fresh random registered test schemas and their existing scoped cleanup.

## Prior failures and limits

The first attempt failed fresh RAM admission before SQL; its exact failing value was not persisted, and a separately labeled diagnostic showed 19.89 GiB. The second authorized attempt failed its preflight at exactly **21,433,200,640 bytes (19.9612236023 GiB)**, before the 31-sample loop. Both stopped with zero SQL connections. Their original `independent-gate-failure.json`, `independent-resume-admission.json` and `independent-resume-memory-pre.json` artifacts remain unchanged. The successful third attempt is separate evidence, not a replacement for those failures.

No candidate tests or application source were modified. No infrastructure/grants/startup/build/model/inference/native Ollama operations or existing-service changes occurred. Credential files were read internally by the supplied harnesses; credential values were not printed. This independent lane establishes direct SQL/library lifecycle behavior only. Live timeout/lost-ACK fault injection, concurrent duplicate billing requests, real Go money computation, MCP authorization/dispatch, real verifier replay and model behavior are **UNRUN in this lane**. The orchestrator owns integration and task status.
