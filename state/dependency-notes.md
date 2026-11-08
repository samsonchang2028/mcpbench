# Implementation handoff notes

T006 contracts are approved static interfaces, not runtime proof. Use actual
installed-library commands in contracts/README.md; keep SQL/lock/process/mount
proof deferred to admitted T018–T023/T040 gates.

contracts/v1 contains both runtime metadata (schema.json, catalog.json) and
private example/oracle/case data. Future T008/T015 agent builds must include only
the compiled agent and explicitly needed public schema/catalog assets, never a
COPY/embed glob of the repository or contracts examples. eval/fixtures, state
examples, expected results, .env and artifacts must remain absent from the final
agent image as well as its mounts. Evaluator images have a different trusted role.

T009 data must preserve full authorized distractor exposure in baseline tasks,
opaque read answer IDs absent from public prompts/task IDs, and conservative
required/relevant annotations. Later read grading needs successful authorized
read evidence for the target records plus unchanged DB state; agent counters or
merely echoing a supplied ID are not proof of a business read.

Do not relax the model-filesystem admission gate or access private service files
through Docker/privilege tricks. T001 still requires the authorized host evidence.
