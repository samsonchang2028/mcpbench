# Repository map

- AGENTS.md, agents/: task roles and safety boundaries.
- docs/TASK_GRAPH.md: IDs/dependencies/status authority; EXECUTION_PLAN schedules.
- contracts/: approved T006 JSON Schema bundle/catalog, protocol, strict offline
  validator, local tests and examples. CLI: python3 -m contracts.validate NAME FILE.
- eval/fixtures/: approved development seed/tasks/assertions/manifest, static
  corpus validator and tests. CLI: python3 -m eval.fixtures.validate.
- state/CURRENT.md, GOAL.md: resumable goal/current state.
- state/candidates/, reviews/, handoffs/, task-context/: frozen evidence and roles.
- .worktrees/: ignored O-managed task branches.
- go.mod/go.sum,pyproject.toml/uv.lock,config/images.lock.json:approved T008 pins.
- cmd/,internal/:compiling fail-closed command/package boundaries;no billing yet.
- Makefile:admitted setup and offline-capable checks;docs/DEPENDENCIES.md versions.
No SQL/Compose,live evaluator or working server/agent implementation yet.
