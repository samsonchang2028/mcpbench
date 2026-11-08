# T001/T007 independent tester report

Overall: **PASS** for the frozen admission evidence candidate. Candidate revision `8ca76690813198578083c73824668f700ed7b5c8`; raw admission JSON SHA-256 `7ec97c1c4aab45711f24b8d6560c1138c5c90697a41bab7b84134988ddd5d375`. Tested 2026-11-08T15:30:00.741214+00:00.

Read AGENTS.md, agents/tester.md, context pack, candidate audit, T001/T007 graph rows, admission/stop policy and evaluation plan. Applied token-efficient-coding. No candidate files, Git state, services, native Ollama configuration, container/model residency or permissions changed. Only this report was written. No tests added to the frozen candidate.

| Criterion | Actual result | Independently observed/recomputed evidence |
| --- | --- | --- |
| Frozen candidate | PASS | 8ca76690813198578083c73824668f700ed7b5c8 |
| 60-second sample and cadence | PASS | 31 readings, 60.055557012s; intervals 2.000993–2.002392s |
| Available RAM >=20 GiB | PASS | minimum 26948460544 bytes = 25.09770966 GiB |
| No sustained swapping | PASS | 2 swap-in pages; 0 swap-out pages; longest nonzero streak 1; nonzero intervals [(2, (2, 0))] |
| CPU and recorded summary consistency | PASS | CPU busy 7.38134102%; iowait 3/47173 ticks; guest fields excluded; no CPU admission cutoff is specified |
| Project/Docker/model filesystem space | PASS | All three retained df rows: [['/dev/nvme0n1p2', 'ext4', '501809635328', '230685216768', '245558616064', '/'], ['/dev/nvme0n1p2', 'ext4', '501809635328', '230685216768', '245558616064', '/'], ['/dev/nvme0n1p2', 'ext4', '501809635328', '230685216768', '245558616064', '/']]; authenticated user model df 229G available |
| Actual model target authenticated evidence | PASS | sudo -u ollama readlink -e /usr/share/ollama/.ollama/models => /usr/share/ollama/.ollama/models; sudo -u ollama df -hT /usr/share/ollama/.ollama/models => /dev/nvme0n1p2, ext4, mounted /; user-supplied, no command timestamp, no independent protected traversal |
| Container identity/state/health regression | PASS | Exact before/after curated dictionaries match including IDs, names, image, state, OOMKilled, StartedAt, health, project, limits and ports; Counter({'running': 15, 'exited': 4}) |
| Historical service health baseline | PASS | 19 names/status/health/OOM match 2026-11-07 baseline; unhealthy=['immich_machine_learning'] |
| Workload stats and limits retained | PASS | 15 running-container stats, 19 limit records; current hard limits all zero=True |
| Project/container/network/volume names unused | PASS | 19 containers, 5 networks, 8 volumes; candidate project mcpbench, network mcpbench_db, volume mcpbench_pgdata |
| Subnet nonoverlap | PASS | 172.30.77.0/24; occupied explicit route/network ranges ['10.42.0.0/24', '172.17.0.0/16', '172.18.0.0/16', '172.39.0.0/24', '192.168.1.0/24']; default route correctly excluded |
| Port 18081 unused | PASS | Checked all TCP listeners and published container ports, IPv4/IPv6 |
| Ollama loopback and proposed binding | PASS | Only 127.0.0.1:11434 observed; MCP loopback proposal 127.0.0.1:18081; DB not published (proposal, not rendered Compose proof) |
| Installed exact model and tool metadata | PASS | Ollama 0.40.13; qwen3.5:9b Q4_K_M; digest 56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90; API bytes 6550825550; tools advertised; not runtime proof |
| No resident rival/active Ollama connection | PASS | Empty before/after resident model lists and header-only ss connection result; no shared-workload model needs eviction at these snapshots |
| Read-only command evidence succeeded | PASS | All relevant retained command return codes zero; GPU query separately records known driver/library mismatch |
| Bounded freshness snapshot | PASS | 2026-11-08T15:30:22.658239+00:00; MemAvailable 26965475328 bytes (25.113556 GiB); resident models []; tag/digest unchanged; 19 IDs/start/state/health/OOM unchanged; no active Ollama connections; 18081 free; 11434 loopback only; df: Filesystem     Type        Avail Mounted on / /dev/nvme0n1p2 ext4 245555879936 / / /dev/nvme0n1p2 ext4 245555879936 / / /dev/nvme0n1p2 ext4 245555879936 / |

## Commands and method

- `git -C .worktrees/T001-T007 rev-parse HEAD` and `git ... show --stat --oneline HEAD`: exact frozen revision and two intended changed files confirmed.
- `python` initially returned exit 127 (not installed); corrected to `python3`. No validation relied on that unsuccessful invocation.
- Executed independent `python3` standard-library checks on `state/audits/2026-11-08-admission.json`. The recorded `checks` booleans were not used as verdicts. Parsed all 31 raw samples, computed consecutive monotonic intervals, min RAM, per-interval nonnegative swap counter differences and longest active streak; computed CPU as `100*(sum(delta[:8])-idle_delta-iowait_delta)/sum(delta[:8])`. Compared summary only after recomputation. Parsed every raw df row, Docker stats/volume JSON line, network IPAM subnet and explicit route; checked overlaps via `ipaddress.ip_network.overlaps`. Compared all 19 before/after curated container records for exact equality and mapped prior baseline by name for status/health/OOM comparison. Parsed all TCP local-address fields and Docker published bindings. Checked model name, digest, quantization, API version, tools metadata and empty ps responses.
- The first freshness Docker template failed for containers lacking a Health field (command exit nonzero, no mutation); corrected the optional lookup to `index .State "Health"` and reran the complete freshness check successfully.
- Freshness commands executed from the tester: read `/proc/meminfo`; bounded GET `http://127.0.0.1:11434/api/ps` and `/api/tags`; `df -B1 --output=source,fstype,avail,target /home/sfkim/projects/mcpbench /var/lib/docker /usr/share/ollama`; `ss -H -lnt`; `ss -H -nt '( sport = :11434 or dport = :11434 )'`; `docker ps -aq`; `docker inspect --format` restricted to ID/name/status/OOM/health/StartedAt for the resulting IDs. All subprocesses used 15-second timeout; HTTP requests 5 seconds. Freshness compares all identities/start/state/health/OOM to raw candidate records and rechecks memory, disk, listener and residency conditions.

## Scope and remaining checks

Authenticated model-directory readlink/df evidence is explicitly user-provided; tester did not bypass access or independently traverse that protected directory. Its historical command time is unspecified; current df on the same reported device confirms current free space. Parent-directory df alone was not substituted for actual-target evidence.

GPU acceleration readiness: UNRUN, outside this CPU-only admission candidate; existing NVML mismatch remains a constraint. Actual Qwen tool-call support and inference memory/latency: UNRUN, explicitly T040. Metadata proves advertised support only; the 6.10 GiB model file does not prove runtime memory <12 GiB. One bounded T040 probe requires immediate pre-call refresh plus existing monitoring/abort controls; measured runtime demand >12 GiB requires budget recalculation. Rendered Compose limits/bindings, builds, pulls and startup: UNRUN, future DAG gates; the binding result above is a proposal check only. No unrelated-service repair or model unloading was attempted. Pre-existing unhealthy Immich ML is unchanged, not a newly induced regression. No observed candidate defects or unresolved evidence blockers in assigned T001/T007 criteria.
