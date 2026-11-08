# T008 dependency selections

Selected 2026-11-08 for the Node 1 Linux/amd64 scaffold. These pins authorize no
runtime deployment. Admission evidence for this implementation is
`artifacts/admission/t008/admission.json` in the orchestrator checkout; artifacts
are ignored by Git. Refresh the [admission gate](IMPLEMENTATION_PLAN.md) before
future downloads/compilation. No global installs, service/configuration changes,
image-layer downloads, containers, or inference are part of T008.

## Native tools and package locks

| Component | Exact selection | Evidence |
| --- | --- | --- |
| Go | 1.26.8, linux/amd64 | `go version`; `go.mod`; Makefile exact-version check, `GOTOOLCHAIN=local` |
| Python | CPython 3.14.4 | Native `/usr/bin/python3.14`; `.python-version` and exact `requires-python` |
| uv | 0.13.4 | `uv --version`; `tool.uv.required-version`; no Python downloads |
| GNU Make | 4.4.1 observed | `make --version`; recipes use ordinary GNU Make features |
| MCP SDK | `github.com/modelcontextprotocol/go-sdk v1.8.0` | [Official release](https://github.com/modelcontextprotocol/go-sdk/releases/tag/v1.8.0), module source/checksums |
| Go PostgreSQL driver | `github.com/jackc/pgx/v5 v5.11.0` | [Official release](https://github.com/jackc/pgx/releases/tag/v5.11.0), GitHub latest-release metadata |
| Python PostgreSQL driver | `psycopg[binary]==3.3.8` | [PyPI release](https://pypi.org/project/psycopg/3.3.8/), [binary distribution](https://pypi.org/project/psycopg-binary/3.3.8/) |

The official SDK's pinned `go.mod` requires Go >=1.25.0; the installed selected
toolchain satisfies it. `go.sum` records direct and transitive module checksums.
The `dependencies` build-tag files retain library selections through `go mod tidy`
and compile-check them without introducing executable server/store behavior.
Later implementation replaces these reservation imports with actual imports.

`pyproject.toml` preserves every exact version from `contracts/requirements.txt`:
attrs 25.4.0, jsonschema 4.19.2, jsonschema-specifications 2023.12.1,
referencing 0.36.2, and rpds-py 0.27.1. `uv.lock` locks all packages, distributions,
and SHA-256 hashes for CPython 3.14.4 Linux/x86_64. It adds only psycopg 3.3.8 and
its matching binary 3.3.8 distribution. This lock intentionally makes no portability
claim for other Python versions, architectures, or operating systems. `uv sync
--locked --no-build --no-python-downloads` installs wheels into local `.venv`;
missing wheels fail instead of compiling a dependency. The binary driver bundles
libpq (observed `psycopg.pq.version() == 180006`, binary implementation); database
connectivity and PostgreSQL compatibility remain UNRUN until T018.

## MCP wire version

Select **2026-07-28** for the later SDK client/server implementation, the default
of pinned SDK v1.8.0. This is read directly from
[`mcp/shared.go` at v1.8.0](https://github.com/modelcontextprotocol/go-sdk/blob/v1.8.0/mcp/shared.go#L44)
and its [compatibility table](https://github.com/modelcontextprotocol/go-sdk/blob/v1.8.0/README.md#version-compatibility).
The source also supports 2025-11-25, 2025-06-18, 2025-03-26, and 2024-11-05.
Streamable HTTP initialization, capabilities, tools/list and tools/call remain
T013 work; negotiation has not been exercised. No OAuth, roots, sampling or
logging feature is needed for the initial slice. SDK protocol support does not
prove runtime authentication, Host/Origin checks, or schema enforcement.

MCPBench's independent application `schema_version: 1` and all bytes under
`contracts/` remain unchanged. Frozen [component protocol](../contracts/PROTOCOL.md)
continues to govern launch arguments, privileges, billing and settlement.

## Official image metadata

[config/images.lock.json](../config/images.lock.json) records official
`docker.io/library` tag references, multi-platform index digests, selected
Linux/amd64 manifest digests, config digests, and published version metadata.
Use the complete tag@**manifest digest** reference for this architecture;
index digests are provenance, not the selected platform's deployment reference.

Resolution used Docker Hub's token endpoint and authenticated GET requests to
`https://registry-1.docker.io/v2/library/<name>/manifests/<tag-or-digest>` with OCI
and Docker v2 index/manifest Accept types. Exactly one linux/amd64 child was
selected from each index, then its manifest and configuration JSON were fetched
and platform checked. No filesystem layers were requested or downloaded.

| Role | Official tag | Published version metadata |
| --- | --- | --- |
| Go builder | `golang:1.26.8-bookworm` | `GOLANG_VERSION=1.26.8` |
| Python evaluator | `python:3.14.4-slim-bookworm` | `PYTHON_VERSION=3.14.4` |
| PostgreSQL | `postgres:17-bookworm` | `PG_VERSION=17.11-1.pgdg12+2` |
| Go runtime base | `debian:bookworm-slim` | Debian bookworm slim; content identity is its manifest digest |

Moving tags are pinned by digest in the lock, never treated as immutable by name.
Official image sources: [Go](https://github.com/docker-library/golang),
[Python](https://github.com/docker-library/python),
[PostgreSQL](https://github.com/docker-library/postgres), and
[Debian](https://github.com/debuerreotype/docker-debian-artifacts).
Image build, pull, runtime libraries/non-root setup, Compose, and live PostgreSQL
checks remain gated by T015/T018. Metadata proves published identity only.

## Checks

`make setup` requires exact preinstalled native versions, resolves no new lock
versions, downloads verified Go modules and installs locked wheels locally.
`make check` runs offline Python lock validation, Go module checksum verification,
serial Go dependency/package compilation and vet, the existing 46 contract/fixture
unit tests, and the read-only fixture CLI. `GOMAXPROCS=2`, `-p 1`, and serial Make
recipes bound compile parallelism. Go packages currently have no behavior tests;
compilation is not evidence of MCP, billing, DB, evaluator, or live-model success.

Go command and Python evaluator stubs fail closed for all fixed protocol arguments
(and all other arguments), leaving stdout empty and returning code 2. The next DAG
tasks supply actual behavior behind the reserved package boundaries.

## Observed implementation checks — 2026-11-08

- `make setup check`: PASS using the exact native tools above and local `.venv`.
  Locked wheel installation installed seven distributions; `uv lock --check
  --offline`, `go mod verify`, tagged Go compile checks, vet, and both binary builds
  passed. Existing `unittest` suite: **46 tests passed** in 2.523 seconds.
- Fixture CLI: PASS, four development tasks, seed fingerprint
  `8303fb14daf4ae93b75a9df9b2faa56ff9f28ab2d0c489689e9159ad848f9c78`.
- `GOMAXPROCS=2 GOTOOLCHAIN=local go mod tidy -diff`: PASS, no lock/module diff.
  Validator requirement-to-lock parity was checked for all five frozen versions.
- Nine subprocess invocations checked agent run/verify/no arguments, server
  normal/invalid arguments, and evaluator prepare/settle-grade/finalize/invalid
  arguments: all returned 2, with empty stdout and stderr under 200 bytes.
- Pre-download/pre-compile and final resource checks retained about 23.6 GiB
  available RAM and over 228 GiB project filesystem space. All 19 existing
  container states/health remained at the admitted baseline, including the
  pre-existing unhealthy Immich ML container.

Image pulls/builds, container startup, database/MCP integration, migrations,
real evaluator execution, live billing and model inference are **UNRUN** by T008.
Independent review/testing and orchestrator integration are separate gates.
