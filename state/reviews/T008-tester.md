# T008 independent tester report

Date: 2026-11-08. Overall gate: **PASS** for the T008 scaffold acceptance criteria.
Candidate: `faaadeb2b42f4005e467e2064bdc1c766b409291`, compared with `c258e09`, frozen worktree `/home/sfkim/projects/mcpbench/.worktrees/T008`. HEAD matched before testing; source worktree remained clean afterward. No tests or candidate source were added/changed. Only this report was written; existing ignored binary outputs were rebuilt. No observed candidate defects, no required criterion BLOCKED.

## Admission and execution bounds

Read AGENTS.md, tester role, T008 context pack, evaluation plan, task row, implementation admission/stop rules, host audit and candidate checks/pins/stubs. Existing `artifacts/admission/t008/admission.json` is PASS: 60.328-second sample, minimum available RAM 23.599 GiB, zero swap pages in/out, all baseline checks true. Before compilation independently refreshed `free -b`, project `df -B1`, `docker ps -a --format ...` and read-only Ollama `/api/ps`: 25,244,532,736 bytes available RAM, 245,858,775,040 bytes free disk, 19 container states consistent with baseline, no resident model. Retained pre-existing unhealthy Immich ML condition. This was the assigned bounded cached compilation lease, not new runtime admission or inference authorization.

Final read-only Docker state inspection compared full container IDs, status, declared health and OOM flags against the admitted sample: all 19 exact matches. Final available RAM 23.514 GiB and disk 228.973 GiB. An initial tester comparison used abbreviated IDs against full baseline IDs and failed its key assertion; rerunning with `docker ps -aq --no-trunc` corrected the tester command and passed. This was not a candidate/service failure.

## Acceptance criteria and actual results

| Criterion | Result | Independent evidence |
| --- | --- | --- |
| Exact Go module, official SDK, DB driver and checksums | PASS | go.mod selects Go 1.26.8, official `github.com/modelcontextprotocol/go-sdk v1.8.0`, `github.com/jackc/pgx/v5 v5.11.0`; `go mod verify` verified all cached modules. Tagged serial compilation/vet and both binary builds passed. |
| Dependencies retained through tidy | PASS | `GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off go mod tidy -diff` exited 0 with no diff. Reservation imports retain selected libraries without linking them into executable stubs. |
| Python exact direct versions and full lock preserve validators | PASS | Offline uv lock check passed. Independent TOML parsing checked all five existing `contracts/requirements.txt` versions against both project direct requirements and lock versions. Every non-project locked package has wheels with SHA-256 hashes. Installed isolated `.venv` matches attrs 25.4.0, jsonschema 4.19.2, jsonschema-specifications 2023.12.1, referencing 0.36.2, rpds-py 0.27.1, psycopg and psycopg-binary 3.3.8. Binary psycopg reports libpq 180006. |
| Exact native versions recorded | PASS | Actual `go version`: go1.26.8 linux/amd64; `python3.14 --version`: 3.14.4; `uv --version`: 0.13.4; `make --version`: GNU Make 4.4.1. Match dependency document. Make verifies required Go/Python/uv versions and prevents automatic toolchain/interpreter downloads. |
| SDK-supported wire protocol and separate schema version | PASS | Verified actual cached v1.8.0 `mcp/shared.go`: latest/default is 2026-07-28; supported versions match dependency document. `go mod verify` authenticates cached source against recorded checksums. Contracts are unchanged, including independent `schema_version: 1`. Runtime negotiation is UNRUN. |
| Four official image tags/platform digests | PASS | Read-only authenticated Docker Hub token/registry JSON requests independently verified each current tag index, unique Linux/amd64 child, child manifest, config descriptor/config and version metadata; recomputed SHA-256 over actual response bytes and checked digest headers where present. Full tag@manifest reference matches lock. Details below. No image layers requested. |
| Empty boundaries and fail-closed commands | PASS | Read all added Go entrypoints/dependency imports and Python runner; behavior is stderr plus exit 2, with no network/listener/SQL or billing path. Nine subprocess invocations (below) all exited 2, stdout empty, bounded nonempty stderr under 200 bytes, within 5-second timeouts. Boundary packages contain documentation/reservation imports only. |
| Clear setup/check commands and minimal scope | PASS | README, Makefile and DEPENDENCIES document setup versus checks and gates. No Compose, migrations, strategies, telemetry framework, retrieval/embedding/vector dependencies or live implementation added. No fake invoice success. Setup was inspected only, not rerun. |
| Existing contracts and fixture code/data unchanged | PASS | `git diff --name-only c258e09..HEAD -- contracts eval/fixtures` returned empty. `git diff --check c258e09..HEAD` passed. |
| Existing 46 tests and fixture CLI in isolated locked environment | PASS | Actual `make check`: all 46 unittest cases passed in 2.579s; fixture CLI passed four fictional development tasks and seed `8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`. No behavioral tests invented for placeholders. |

## Commands and results

From the frozen candidate worktree:

```sh
GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off make check
GOMAXPROCS=2 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off go mod tidy -diff
```

Both exited 0. `make check` actually executed offline uv lock validation, module verification, `go test -mod=readonly -p 1 -tags=dependencies ./...`, matching Go vet, serial agent/server binary builds, `uv run --locked --offline --no-sync python -m unittest contracts.tests.test_contracts eval.fixtures.test_fixtures`, and the existing fixture validation CLI. Go reports no test files: compilation/vet are the relevant scaffold check, not runtime correctness tests.

An independent Python stdlib script parsed project/lock requirements, checked unchanged protected paths, and used `subprocess.run(..., capture_output=True, timeout=5)` to exercise:

- `bin/agent` without arguments, and `run` / `verify` with `--request /absent --auth /absent --output /absent`.
- `bin/billing-mcp` without arguments and with `--invalid`.
- `.venv/bin/python -B -m eval.runner` with each of `prepare`, `settle-grade`, `finalize`, `--invalid`.

All nine passed the required exit-code/stdout/stderr checks. A separate subprocess confirmed interpreter prefix is the candidate-local `.venv`, actual package versions listed above, and binary psycopg implementation. Source inspection establishes absence of network/billing actions; these subprocess checks alone do not prove future runtime safety.

## Registry identity verification

Independent Python urllib requests used `auth.docker.io/token` and `registry-1.docker.io/v2/library/<name>/manifests/<tag-or-digest>` with OCI/Docker index/manifest Accept types, followed only by each config JSON blob. Byte-level SHA-256, platform selection and declared environment metadata all matched `config/images.lock.json`:

| Role / official tag | Verified Linux/amd64 manifest digest | Verified version metadata |
| --- | --- | --- |
| Go builder / golang:1.26.8-bookworm | `sha256:26de5cf8eac40c12a1ff8de1a634971b4654fd881225eed7ace643b8c769f2f5` | GOLANG_VERSION=1.26.8 |
| Python evaluator / python:3.14.4-slim-bookworm | `sha256:db5942d111df72110e7a67da3fc5159e83ac85cd24808b91bdc4769e166ed1b7` | PYTHON_VERSION=3.14.4 |
| PostgreSQL / postgres:17-bookworm | `sha256:73bedc9eaa0121b92b9b26bb52e5141b3f6f37479c7ef913c0160455763ca80a` | PG_MAJOR=17, PG_VERSION=17.11-1.pgdg12+2 |
| Go runtime / debian:bookworm-slim | `sha256:c67e92c8099ba22853ab4cfda7cfb494d253d6012ca82dee98ba8976772af018` | No environment version claimed; digest is identity |

## Explicitly UNRUN

No setup/install, global dependency changes, image pull/build, container startup, service changes, model pull/inference, SQL migration, PostgreSQL connection/oracle/reset, MCP negotiation/tools/auth, actual evaluator lifecycle or billing execution ran. These remain downstream DAG gates and are not implied by T008 PASS. Fresh-install reproducibility was not rerun by this tester; the installed locked local environment and offline lock/checksum validation were directly checked. Image metadata is not image runtime validation.
