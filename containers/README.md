# T015 static deployment candidate

Only Compose rendering and static checks have run. Builds, pulls, startup, volume
ownership, effective identities/groups/caps, DB roles/migrations/seed, MCP
readiness, mount permissions, artifact quotas and connectivity are **UNRUN**.
The current Go commands and Python runner exit 2; these images preserve that
behavior. No init SQL, fake invoice result, fake seed-ready marker or auto migration
is installed. `pg_isready` checks connection liveness only. MCP health checking is
explicitly disabled until T019 can connect a real implemented readiness check.
Neither service is safe to treat as application-ready from this candidate alone.

Static validation (no daemon operations):

```sh
python3 containers/check_config.py
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet
git diff --check
```

Compose v5.4.0 rendered all five services and the static checker passed on
2026-11-08. Defaults are deliberately absent `/nonexistent/mcpbench/` paths,
not sample credential files. Every bind has `create_host_path: false` so a missing
input fails instead of creating a directory. No tracked secrets are generated.
The checker clears interpolation environment and disables `.env` loading.

## Images and privileges

Every external image/base uses the linux/amd64 manifest reference in
`config/images.lock.json`. Go builds are serial (`-p 1`, GOMAXPROCS=2), CGO-free;
the agent image contains only the agent binary and pinned Debian runtime. The
Dockerfile-specific context allowlist excludes evaluator/fixtures and runtime
artifacts/secrets from Go builds. Python installs all non-virtual `uv.lock`
packages at exact versions, with locked wheel hashes, binary-only and no resolver
or source compilation. Its context contains only evaluator/contracts/DB source,
lock and build helper. Missing compatible wheels fail the build. No floating
package installs or unrelated host sources are used.

Local image names `mcpbench-{agent,mcp,evaluator}:t015` identify build outputs, not
immutable runtime digests. `pull_policy: never` prevents remote tag substitution.
T018/T019 must build explicitly, record each output image ID and use that reviewed
ID for trusted launches; an unverified preexisting local tag is not trusted.

PostgreSQL runs as the pinned image's UID/GID 999 with PGDATA in a child directory
of its sole project-owned persistent volume. Its socket directory is UID999 tmpfs.
Initial volume writability/official entrypoint behavior remains a T018 check;
never fix a failure by privileged mode, broad host permissions or another workload's
volume. Its bootstrap role is a database initialization administrator, available
only to the trusted host bootstrap operation. No bootstrap password is supplied to
MCP, evaluator or agent. T018 must create/verify the controller, grader and service
roles from the approved DB implementation and prove least privilege independently.
The MCP credential is service-only. Evaluator control files may hold separate
controller and grader credentials; their connection separation is enforced and
validated by T016/T018, not asserted by Compose.

The agent and verifier run as UID/GID1000, no supplementary group additions, no
listener, with cleared five-variable environments. Host networking retains the
approved broad OS network reach: trusted code must enforce the two fixed loopback
endpoints, disable proxies/redirects and expose no URL/shell/file tool. This is
not OS egress confinement. No native Ollama service/config/model mount is present.
All containers drop all capabilities, forbid privilege escalation, have read-only
roots and bounded CPU, memory, swap allowance, PIDs, temp space and Docker logs.
The 100 MiB artifact cap needs the trusted launcher/runtime enforcement; a bind
mount cannot impose a disk quota. Do not claim that the tmpfs or log cap enforces
that artifact budget.

## Trusted per-run input contract

The host launcher owns path generation and validation. For each fresh unpredictable
run ID it creates an ignored `artifacts/runs/<run_id>/` directory mode0700, rejecting
symlinks, path escapes, duplicate IDs, wrong file types and preexisting outputs as
specified by `contracts/PROTOCOL.md`. Compose cannot perform those checks. Never
accept mount paths from the model. Run containers serially and with `--no-deps`.

| Variable | Host input / container target |
| --- | --- |
| `MCPBENCH_BOOTSTRAP_PASSWORD_FILE` | Private synthetic bootstrap password, readable only by trusted host and DB UID999; `/run/secrets/bootstrap-password` RO |
| `MCPBENCH_SERVICE_PGPASS_FILE` | Service-only mode0600 pgpass owned by UID1000; `/run/secrets/service.pgpass` RO |
| `MCPBENCH_AGENT_REQUEST_FILE` | Sanitized agent request file; `/run/mcpbench/request.json` RO |
| `MCPBENCH_AGENT_AUTH_FILE` | UID1000 mode0600 execution capability; `/run/secrets/auth.json` RO |
| `MCPBENCH_AGENT_OUTPUT_DIR` | Fresh UID1000 agent-only directory; `/run/mcpbench/output` RW |
| `MCPBENCH_VERIFIER_REQUEST_FILE` | Bounded verifier request, separate from agent; same request target RO |
| `MCPBENCH_VERIFIER_AUTH_FILE` | Separate UID1000 mode0600 verifier capability; same auth target RO |
| `MCPBENCH_VERIFIER_OUTPUT_DIR` | Fresh separate UID1000 verifier-only directory; same output target RW |
| `MCPBENCH_EVALUATOR_CONTROL_DIR` | Run-specific trusted phase inputs, role pgpass files and config; `/run/mcpbench/control` RO |
| `MCPBENCH_EVALUATOR_OUTPUT_DIR` | Fresh run-specific evaluator-owned outputs; `/run/mcpbench/output` RW |

Never mount the run parent into agent/verifier, reuse their auth/output paths, or
mount evaluator/oracle/DB credentials there. Agent/verifier get exactly three
binds. Evaluator gets two run-specific directories and fixtures baked into its
private image; it has no host-network/Ollama access or container-launch capability.
The exact evaluator private configuration reader/phase transport is T016 work;
these reserved paths do not claim a currently working runner interface. Export
only trusted path values. Keep secret bytes in private files, never environment,
command arguments, rendered configs, Git or prompts.

## Future commands: gated, not executed

Before **every** build/pull/start/inference operation, the orchestrator refreshes
`docs/IMPLEMENTATION_PLAN.md` admission: resources/filesystems, 60-second swap
sample, existing-service health, model sharing/residency, free loopback18081 and
ownership of project `mcpbench`, network `mcpbench_db` and volume
`mcpbench_db-data`. Docker chooses the private network subnet; inspect allocator
and host routes for overlap before creation and inspect the allocated result.
Do not attach any preexisting unverified names or external resources.

The following are exact service-scoped command forms for the trusted orchestrator
**after** exporting validated private paths above and receiving the respective DAG
runtime gate. They do not authorize execution now. Render first and retain only a
redacted config with no secret contents. No `.env` is consumed.

```sh
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet
# T018: explicit pinned DB pull, only after refreshed admission.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml pull db
# Build one image at a time. Inspect/freeze resulting image IDs before any run.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml build evaluator
docker compose --env-file /dev/null -p mcpbench -f compose.yaml up -d --no-deps --no-build --pull never db
# T018 must now apply real T011 migrations/seed and run DB/oracle checks.
# SQL execution commands belong to reviewed T011/T018, not a stub bootstrap here.
# T019: after DB acceptance and implemented Go/evaluator runtime tasks.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml build mcp
docker compose --env-file /dev/null -p mcpbench -f compose.yaml build agent
# First verify each local tag matches its frozen image ID.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml up -d --no-deps --no-build --pull never mcp
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile evaluator run --rm --no-deps --no-build --pull never evaluator prepare
# Agent request/auth/output paths are outputs transported by the trusted launcher.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile agent run --rm --no-deps --no-build --pull never agent
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile evaluator run --rm --no-deps --no-build --pull never evaluator settle-grade
# Only an explicit bounded verify decision permits this distinct capability run.
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile verifier run --rm --no-deps --no-build --pull never verifier
docker compose --env-file /dev/null -p mcpbench -f compose.yaml --profile evaluator run --rm --no-deps --no-build --pull never evaluator finalize
```

The host launcher must enforce absolute deadlines, bounded output, image identity,
path checks, fencing and conditional verifier/cleanup decisions. Sequential shell
commands alone do not implement the protocol, and startup time counts toward the
post-agent deadline. Live inference requires its later DAG admission; deterministic
integration must not accidentally invoke native Ollama. No teardown/prune command
is included; preserve the owned DB volume and all unrelated workloads/evidence.

## T019 source wiring (runtime evidence remains separate)

MCP now has a real `/app/billing-mcp health` command and two additional narrow
binds: `MCPBENCH_MCP_TRACE_CONTROL_DIR` to `/run/mcpbench/trace` RO, and
`MCPBENCH_MCP_OUTPUT_DIR` to `/run/mcpbench/events` RW. Both default to absent
`/nonexistent/mcpbench/` paths with no auto-created bind sources. Agent/verifier
still receive exactly their original three mounts. The evaluator image now
includes the Python observability module required by its implemented lifecycle.

The Go Dockerfile has a separate `scripted-agent` target for T019 only, controlled
by trusted build argument `MCPBENCH_SCRIPTED_SCENARIO` (`smoke`, `wrong-write`,
`lost-reply`). It installs the real-loop deterministic child at `/app/agent`; its
image ID and scripted tag must be recorded distinctly from the production agent.
No model request occurs in this child. Build context admits only that integration
child subtree, retaining all other existing exclusions. Serial Go compilation
uses GOMAXPROCS1. The trusted launcher uses the same hardening, fixed roles and
scoped mounts; see `launcher/README.md`. Source wiring is not a build/startup PASS.


T019 gateway target: `docker build --target gateway -f containers/go.Dockerfile
-t mcpbench-gateway:t019 .` (operator admission required). Only gateway publishes
127.0.0.1:18081 and joins owned normal front + internal DB networks; it has no
mounts. MCP/DB/evaluator remain internal only. Both Compose networks are external
and must already be verified/provisioned by the operator. Gateway uses the same
pinned Go/runtime bases with no new dependency, 64MiB/0.1CPU, read-only/non-root
execution and bounded uncompressed local logs. See `launcher/README.md` for fresh
CID receipts, per-run fixed upstream binding and runtime acceptance evidence.
