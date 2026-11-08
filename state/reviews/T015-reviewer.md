# T015 independent reviewer

Candidate: `a5c0096345a7a50a0904bcb5be6bd3998d64fdbb` in `.worktrees/T015`, compared with `272ce58`.
Verdict: **APPROVE** for the T015 static deployment/configuration scope. No P0/P1 findings.

## Findings

None. The fixed candidate is clean. Its eight changed files are limited to `compose.yaml` and `containers/`, within the task's ownership; application code, contracts, dependency locks and task/status documents are unchanged.

## Review evidence

Reviewed the complete candidate diff against the T015 context pack, task acceptance row, approved architecture/resource limits, security/resource contract, frozen component protocol and T008 image lock.

- The explicit `mcpbench` project owns an internal bridge network and its sole persistent DB volume. PostgreSQL has no published port, external volume/network, host data directory or unrelated workload attachment. MCP publishes only `127.0.0.1:18081:8080`; evaluator and MCP join only the private DB network. No Ollama service, model mount or native configuration mutation is defined.
- Agent and verifier use the approved host networking arrangement without published ports or private DB attachment. Their shared entrypoint clears the environment with `env -i` and restores only the five protocol-allowlisted variables. Their fixed `run`/`verify` argument arrays match the frozen component protocol. Host networking's broad OS reach is explicitly documented as a residual risk; endpoint enforcement and no-listener behavior remain application/runtime obligations.
- Agent/verifier each receive exactly their own read-only request, read-only capability and writable output binds, with separate source variables. They receive no evaluator/fixture/oracle/DB secret or run-parent mount. Evaluator receives only its private run-specific control and output directories; service/bootstrap credentials are distinct private file inputs. Missing default inputs use absent `/nonexistent/mcpbench/` paths with `create_host_path: false`, rather than generated example secrets or automatically created host directories. Trusted path/type/symlink/identity validation is correctly left to the launcher.
- All services specify non-root numeric UID/GID, dropped capabilities, no-new-privileges, read-only roots, restart disabled, PID caps, bounded tmpfs and local logs. There are no privileged/container-runtime/socket/device/host-PID mounts or supplementary group additions. Memory/CPU caps match the approved table: DB/evaluator 512 MiB and 0.5 CPU, MCP 256 MiB and 0.5 CPU, agent/verifier 512 MiB and 1 CPU; equal memory/swap limits prevent an additional swap allowance.
- The PostgreSQL image and all external build bases exactly match T008's linux/amd64 digest references. Local build tags are explicitly described as mutable outputs, use `pull_policy: never`, and require verified frozen output image IDs before trusted launches. Go build contexts exclude evaluator/oracle/artifact material; only the requested binary is copied into each final Go image. The evaluator intentionally receives private evaluation/contracts/DB source. Its build helper exports exact locked package versions and wheel hashes, rejects unexpected registries and invokes pip with hashes, binary-only installation and no dependency resolution. No image build or package installation was executed during review.
- Existing fail-closed entrypoints are preserved. PostgreSQL health checks claim connection liveness only; MCP health checking is disabled rather than substituting fake readiness. No SQL/init script, fabricated result, seed-ready marker, auto migration or service restart loop is added.
- Container documentation distinguishes rendering/static validation from startup, effective groups/caps/identities, initial volume writability, least-privilege DB roles, readiness, artifact quotas, path validation and connectivity. Future command forms are service-scoped, explicitly gated and do not include teardown/prune. They describe conditional verifier/cleanup sequencing rather than claiming shell commands implement settlement or runtime authorization.

## Independent checks and residual limits

The orchestrator serves as independent tester for rendered Compose and negative configuration checks. That report's actual PASS remains necessary before integration/task completion; this review did not duplicate execution checks. Reviewer operations were read-only Git/file inspection, with only this report written.

Builds, image pulls, startup, SQL, inference and all actual runtime security/readiness checks are **UNRUN**. In particular, a named volume declaration does not prove DB UID999 can initialize the fresh data path, numeric user/cap settings do not prove effective runtime permissions, a private network declaration does not prove allocated subnet/ownership/connectivity, and bounded tmpfs/logging does not enforce the 100 MiB result-artifact cap. The candidate explicitly reserves those checks for the appropriate admitted runtime gates. Future launches also require trusted output image identity and narrow path/secret provisioning; Compose interpolation itself does not enforce those policies.

No contract drift or unresolved review finding was identified. Approval does not authorize builds, workload startup, deployment, inference or task completion.
