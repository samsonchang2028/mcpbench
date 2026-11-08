# Current state — admission complete; tool probe resource-blocked

UTC: 2026-11-08T15:37:22.884599+00:00
DONE T001/T002/T003/T004/T005/T006/T007/T009 (8 tasks).
T001/T007 candidate8ca7669 integrated b845082; independent R APPROVE/V PASS.
Authenticated model-store output accepted; host access boundaries unchanged.

T040 BLOCKED: first real probe t040-20261108-01 safety-aborted at36.204sec
on three consecutive swap-active2sec intervals. Curl SIGTERM -15; no response,
no valid tool call or local result captured. Do not call this tool support PASS
or proof that the model does not support tools. Min available RAM24.79GiB;
all19 container states/health unchanged; existing Immich ML unhealthy persists.
Nine artifact hashes verified independently. Preflight controller timing P1
was repaired/reviewed/retested before inference; no open controller P0/P1.
Actual swapping is an unresolved P1 resource gate; causal workload is unproven.
Native Ollama limits/driver/config unchanged. Model expired under our own30sec
keep-alive; later read-only api/ps empty. No forced unload or retry attempted.
Runtime CPU telemetry was missing and cannot be reconstructed for this attempt;
add /proc/stat/load fields to any future separately reviewed probe.

Evidence: state/audits/2026-11-08-T040-result.json and frozen local
artifacts/probes/t040-20261108-01/hashes.json.
R: state/reviews/T040-result-reviewer.md approves failed evidence, gate BLOCKED.
V: state/reviews/T040-result-tester.md capability FAIL, safety abort PASS.
T008/application work WAITING; zero READY,31 WAITING,1 BLOCKED,8 DONE.
No MCPBench containers/builds/dependency installs/app runtime were started.
Full v1 remains incomplete. First confirmed audit of NEW swap-resource blocker;
previous model-storage blocker was resolved. Goal remains active pending decision.
Resource lease released; do not retry or alter stop thresholds automatically.
