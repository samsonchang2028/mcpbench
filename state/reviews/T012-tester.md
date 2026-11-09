# T012 independent tester — PASS scoped cached checks
Fixedcandidate 0fe5bc62ccf3e253847e17d2dea5e2b6ce71356a;rootnotauthor. Commandfromassignedworktree:
MCPBENCH_TEST_PYTHON=/home/sfkim/projects/mcpbench/.worktrees/T008/.venv/bin/python
GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off go test -mod=readonly -p 1 ./... -count=1
Actual billing0.140s,store0.007s,observability3.428s;allpackagesPASS;livePGcasesSKIP. DiffcheckPASS;cleanfixedcandidateafterchecks.
Rootpolled original live executionhandle throughcompletion,no duplicate restart.
R recheck APPROVE separately inT012-reviewer-v2.md. Originalfailedreviews
retained;scope includes focusednegativeregressions for identifiedP1s.
T012active-only/filter-before-cap andinactive-vs-notfound cases pass;T014calendar/
expectedconflict/absolute+startupbudgets/FIFO/Pythonsemanticparity cases pass
whereapplicable. ActualMCP/nativeinference/GoPGworkflow remainUNRUN;scripted
unitchecks arenotlivebenchmarkproof. No installs/SQL/Docker/modelcalls here.
