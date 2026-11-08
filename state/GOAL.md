# Active goal: complete MCPBench v1

User authorized autonomous routine implementation, testing, independent review and
integration along the existing DAG. Do not stop for routine task transitions.
DAG eligibility and file ownership, resource admission and safety gates still bind.

## Definition of done mapped to gates

- Go fictional-billing MCP + real Qwen workflows: T018–T025.
- Python independent deterministic DB-state grading/reset: T010,T016,T018,T019.
- Structured JSONL run/call retrieval-selection-execution logs: T017,T021.
- All four comparable retrieval strategies and permission/budget fairness: T026–T032.
- Controlled benchmark comparisons: T033,T039,T034.
- Reproducible failure/resource analysis and report: T035–T038.
- Every required reviewer/tester gate PASS, no unresolved P0/P1.

OpenTelemetry, Jaeger and dashboard are excluded from v1. Existing Node 1 services,
volumes, drivers and native Ollama config remain untouched. Real accounting data,
public ports, privileged agents and agent Docker socket mounts remain forbidden.

## Approval and blocking rules

User authorization supersedes historical routine-wave/probe approval stops, subject
to existing contracts. Stop/request approval for security-sensitive changes,
architecture changes or proceeding with unresolved P0/P1. Do not bypass access or
resource restrictions; mark affected tasks BLOCKED with evidence. Continue other
independent eligible nodes. If no meaningful eligible work remains, report exact
external evidence/decision needed rather than pretending v1 is complete.

## Current bottleneck

T001 actual model-store path/symlink/filesystem/free space remains unreadable by
sfkim and noninteractive sudo requires authentication. User's service-account
read-only evidence can resolve this; no chmod/group/container workaround.
T006 contracts and then T009 fixtures are independent of this runtime blocker.
