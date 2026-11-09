# Scripted integration child

This integration-only model drives the real Go agent loop through customer/item
reads and draft creation. Successful model tool messages contain the complete
validated business result. Tool failures retain explicit error envelopes and
cannot produce a scripted successful draft answer.

A valid terminal AgentResult or VerifierResult is published after the event
writer closes, including failed outcomes. The command still exits nonzero for
non-completed status. Setup/validation failures do not invent result documents.
This preserves failure evidence without changing launcher grading or quarantine.

Offline tests inject in-memory connections; they contact no model, MCP, or SQL
service and do not establish runtime integration acceptance:

```
GOMAXPROCS=1 GOTOOLCHAIN=local GOPROXY=off GOSUMDB=off \
  go test -mod=readonly -p 1 ./tests/integration/scripted-agent -count=1
```
