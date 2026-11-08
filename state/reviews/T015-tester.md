# T015 independent tester — PASS
Candidate a5c0096345a7a50a0904bcb5be6bd3998d64fdbb versus272ce58.
Root serves V,not candidate author;candidate remained frozen. No runtime actions.

Actual commands: python3 containers/check_config.py;docker compose --env-file
/dev/null -p mcpbench -f compose.yaml --profile '*' config --quiet; independent
python3 artifacts/tests/t015_independent.py from main (it selects candidate cwd).
Independent test artifact SHA256: 1bacdb4004d78ef4c20ebd9bf6f3ee2818aed9405e75996c81a67ab7e6ed80f5.

PASS: rendered5-service topology;DB internal/unpublished;onlyMCP127.0.0.1port;
nonroot identities;caps dropped/no escalation/readonlyroots;memory/CPU/swap caps;
no privileged/devices/socket/externalvolumes;source-specificnarrowreadonlyinputs
and output mounts;clean agent/verifier environment;official lockedDockerfilebases;
contextallowlists excludeprivate material from agent output image.
PASS:10 unsafe mutated topologies rejected(publicport,privilegedDB,rootagent,
DBsecretinagentenv,broadhostmount,writableagentinput,unboundedswap,extraCAP,
publicDBnetwork,externalvolume). Actualcandidate untouched.
PASS: static checker ignores malicious caller interpolation variables.
PASS: build-only wheel exporter under mocks selects7exacthash-locked packages;
--require-hashes/--only-binary/--no-deps enforced;unapprovedregistrysource and
invalidhashprefix rejected before any mocked install invocation. No installs ran.

Initial independent harness compared rendered string memory values to int and
raised TypeError;corrected to explicitint and reran successfully. Candidate defect
not inferred from tester error. Scope includes source inspection of Dockerfiles,
ignorefiles,buildhelper and README againstapproved contracts;no newP0/P1 found.

UNRUN: imagepull/build,startup,realUID/volumepermissions,effectiveDBgrants,
application/seedreadiness,nativeinference and actualcontainerboundary tests.
Those retainT018/T019/T020 gates. Hostnetwork broad reach and artifactquota/path
validation obligations are documented,not claimed enforced by staticrender.
No schema/seed readiness inferred frompg_isready;MCPstubhealth correctlydisabled.
