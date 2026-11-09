# Current state — approved gateway proven; runtime repairs underway

User approved option A then explicitly resumed.19/40 DONE (T001–T018,T040).
T019 IMPLEMENTING;20 downstream nodes WAITING. Fullv1 incomplete. Controller
API still reported paused on resume; no API supports changing that user flag,
but explicit resume authorizes current work. Automatic continuations use UIActive.

Gateway candidate53c62bd +checker compatibilityfix5c3dd4a frozen in.worktrees/T019.
Independent sourceR APPROVE andV Go/98Python/3checker/staticCompose PASS; original
emptyIPAM checkerfailure retained. Gateway image6ee4a033 built1CPU/2GiB. Newowned
front network9a3f9a21/mcpbench_front172.20.0.0/24 createdafterfreshadmission and
nonoverlap checks. Existing DBnetwork/volumes/services unchanged.

Actual gateway-smoke-01 run-e19ac6733790474c4062544d: gatewayalone published
127.0.0.1:18081; hosthealthPASS,unauthMCP401. MCPinternalonly; gatewayfront+DB,
nomounts,64MiB/.1CPU caps. Sampled gateway1.992MiB/MCP17.79MiB (not peakproof).
RealPythonpreparePASS, three MCPtools/DBcompletion logs; scriptedagentthenfailed
contextguard before4thmodelturn. No native inference. Settlementquarantined.
Rootread-onlyregistryphaseagent_sealed/gen1/tokenrevoked; this isnotpositiveACK
receipt orauthoritytograde/reset. Both failedservices gracefullystoppedexit0,
retainedwithschema/volumes/quarantine. All19unrelatedbaselineunchanged.

Diagnoses: model4request3779bytes+512reserve4291>4096. Removingonly redundant
successmodel-message envelope preservesallbusinessdata andfits3564+512=4076;
actualRunnerofflineoverlay completes4model/3tool/0retries withbudgetsunchanged.
ScriptedCLIalso discarded validfailedresult. Separately,floatreceipt/eventms
reject integercanonicalserialization afterseal andcontaminatefallbackstate;
launcher skippedfailed evaluatorProcessExit journaling. Reports T019-context-
diagnosis.md andT019-settlement-diagnosis.md holdactualoffline reproevidence.

Two exclusive repair worktrees from5c3dd4a: T019-context-fix (Goagent+scriptedCLI)
andT019-settlement-fix (DB/Pythoneval/launcher). Cachedtests only; no furtheractual
runtimeuntil combinedfrozenR/V,newimagebuilds,freshgates. No canonical/hashschema,
modelsettings,4096/512 budgets ormoney changes. Sourceownership inT019context.
Rootactualproofs ignored artifacts/admission/t019/gateway-*; allfailedruninputs
remain underartifacts/t019-gateway-runs/ andoldert019-runs/. DB86a17f3d5a78 healthy;
oldMCP6ecae489 stopped/retained. NewfailedMCPaecc219b andgatewaybe3f8233 retained
stopped. Neverreset/reusequarantine orremovevolumes to obtainpassingresults.
Untracked docs/architecture-diagram.html is userwork;preserve/do notstage.
