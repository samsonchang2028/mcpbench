# T014 independent tester — PASS scoped cached checks
Fixedcandidate 97242472088dc9b88815e5d4cbc114afd870b919;rootnotauthor. Commandfromassignedworktree:
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python
GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p 1 ./internal/agent ./internal/ollama ./cmd/agent -count=1
Actual agent3.210s,ollama0.006s,CLI0.850s;PASS. DiffcheckPASS;cleanfixedcandidateafterchecks.
Rootpolled original live executionhandle throughcompletion,no duplicate restart.
R recheck APPROVE separately inT014-reviewer-v2.md. Originalfailedreviews
retained;scope includes focusednegativeregressions for identifiedP1s.
T012active-only/filter-before-cap andinactive-vs-notfound cases pass;T014calendar/
expectedconflict/absolute+startupbudgets/FIFO/Pythonsemanticparity cases pass
whereapplicable. ActualMCP/nativeinference/GoPGworkflow remainUNRUN;scripted
unitchecks arenotlivebenchmarkproof. No installs/SQL/Docker/modelcalls here.
