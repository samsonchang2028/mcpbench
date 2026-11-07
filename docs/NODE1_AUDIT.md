# Node 1 audit — permission refresh

Observed 2026-11-07 around 14:50–14:55 America/Los_Angeles. Host/service checks
were read-only; normal Git initialization and benchmark documentation/evidence
writes were confined to MCPBench. No service configuration or workload changed.

## Verified capabilities and resources

| Area | Verified evidence | Readiness implication |
| --- | --- | --- |
| Hardware | Dell Precision 5520; i7-7820HQ, 4 cores/8 threads; M1200 PCI device | Laptop-class shared CPU; no accelerator assumption |
| RAM | 30 GiB usable, 5.4 GiB used, about 25 GiB available | Above proposed 20 GiB admission threshold at this snapshot |
| Swap | 8 GiB total, 3.6 GiB occupied | Occupancy alone does not prove current pressure |
| 60-second sample | 30 two-second intervals; cumulative vmstat row excluded; zero swap-in/out throughout; CPU 90–94% idle, I/O wait zero | Numeric sample passes no-sustained-swap criterion; not full T007 admission |
| Earlier sample | Separate 60-second sample saw max swap-in 40 KiB/s and zero swap-out; streak not retained | Do not infer sustained pressure from its maximum; full follow-up sample retained |
| Disk | Root/project, Docker root and `/usr/share/ollama` on 468 GiB ext4 with 229 GiB available; inodes 5% used | Actual model directory target remains unverified; parent filesystem is known |
| Temporary storage | `/tmp` is 16 GiB tmpfs | Avoid large temporary model/build copies |
| Docker | Client/server 29.7.2; Compose v5.4.0; root `/var/lib/docker` | Daemon inspection works as current user |
| Workloads | 19 containers: 15 running, 4 exited; Compose arrstack and immich, plus standalone containers | Existing services inventoried; no MCPBench project/resource found |
| Health baseline | `immich_machine_learning` unhealthy; other declared health checks healthy; some containers have no healthcheck | Existing problem, not caused/fixed by MCPBench; compare against this baseline for regression |
| Existing limits | Inspected containers have no hard Memory/NanoCPUs/CPU quota caps | Headroom can change substantially; experimental limits remain mandatory |
| Resource usage | qBittorrent about 4.63 GiB, Jellyfin 1.17 GiB, FlareSolverr 369 MiB, Immich server 404 MiB; most sampled CPU low, Redis about 10.8% | cgroup/cache accounting differs from host MemAvailable; do not sum these as unique resident RAM |
| Ports | Native Ollama on 127.0.0.1:11434; no listener on candidate 18081; existing 5432 and 8080 occupied | Retain loopback MCP 18081 proposal and no benchmark DB publication; recheck before startup |
| Networks | Docker 172.17.0.0/16, 172.18.0.0/16, 172.39.0.0/24; host also has 10.42.0.0/24 and LAN route | Never reuse existing networks; future subnet selection must check all routes and allocator state |
| Docker storage | Images 23.98 GB; build cache 895.4 MB; no pruning performed | Space observation only; existing volumes preserved |
| Git | No repository existed after old projection disappeared; normal `git init -b main` succeeded; baseline commit e0ce746 | Root resolves to this project; metadata/index/commit writes work; no remote or push |
| Write test | Temporary benchmark-local create/write/fsync/delete passed; docs writable; ignored credential/artifact paths verified | Safe own-project writes confirmed without permission changes |

## Ollama identity and loading

Native service is active; client/server version is **0.40.13**. Installed tag:
**qwen3.5:9b**, family qwen35, 9.0B (metadata count 8,953,803,264), Q4_K_M,
6,550,825,550 bytes on the API's size field. Digest:
`56671c2ab9385f9cfcb404638e32cd62d88e3501d44822208363c010179a3c90`.

`/api/show` advertises completion, vision, tools and thinking, with context capacity
262144. This is metadata, not evidence of valid tool calls or permission to use
that context size. Request budgets remain the reviewed 4096/512 proposal.
`/api/ps` returned an empty model list and no active 11434 connection was observed.
That is a snapshot, not a guarantee of exclusive use during a later trial. Service
cgroup MemoryCurrent was about 4.36 GiB; it is not proof that a model is loaded.
No generation endpoint, model pull, unload or configuration mutation was invoked.

Service user/group is `ollama`, home `/usr/share/ollama`, command `ollama serve`.
No OLLAMA_MODELS override or environment file was returned by service metadata.
The default candidate `/usr/share/ollama/.ollama/models` cannot be traversed by
sfkim. An `is_file` false result under that inaccessible path is **not evidence of
model absence**; API availability is verified. Narrow noninteractive sudo read
checks require interactive authentication and were not completed. No permission,
group, sudo or service configuration was changed. Actual storage path/symlink
resolution and its filesystem/free space need an authorized service-account check.
This is the remaining T001 prerequisite; parent-directory disk space is insufficient
proof of the actual model target.

## GPU and existing-service constraints

`nvidia-smi` now reports **driver/library version mismatch**: loaded kernel module
580.173.02, NVML library 580.178. Unlike the earlier sandbox-limited error, this is
an observed host runtime issue. Do not repair drivers, restart services or assume
GPU offload. CPU feasibility is a future measured probe after admission/approval.
The Immich ML container was unhealthy on both inventory observations; no logs,
restart or health repair was attempted for that unrelated application.

## What caused the previous failures?

- Earlier `.git` was a read-only placeholder/projection; it is now absent and the
  real root mount is writable. Git's failure was a filesystem/sandbox restriction,
  not a Git ownership or safe.directory error. Normal initialization resolved it.
- Earlier socket creation, netlink and system-bus access returned operation-not-
  permitted. Their success after the sandbox was disabled strongly supports the
  Codex sandbox as the main cause. Historical UID/group/access evidence is not
  sufficient to exclude every concurrent Unix permission change.
- Docker socket is now root:docker mode 0660 and sfkim belongs to docker; access
  works without sudo. Earlier nobody:nogroup presentation is consistent with the
  restricted filesystem projection, not proof of the real host socket ownership.
- Ollama API/metadata access now works and requires no service change. The model
  directory denial that remains is an ordinary Unix service-account boundary;
  sudo authentication is not available noninteractively. Preserve that boundary.
- GPU mismatch is a separate host problem. Neither sandbox removal nor working
  Docker/Ollama metadata access establishes accelerator readiness.

## Evidence and next gates

Curated evidence (no container environment dumps or secrets):
`state/audits/2026-11-07-docker-baseline.json`,
`state/audits/2026-11-07-ollama-metadata.json`, and
`state/audits/2026-11-07-resource-refresh.json`.

T001 remains BLOCKED only on actual model-storage target verification. T002 has
normal Git evidence, pending independent documentation-wave validation. T003–T005
can refresh documentation in disjoint files; their earlier accepted contracts stay
valid. T006 contracts, T007 full admission and T040 live capability are not complete.
All startup/build/inference gates must be refreshed at point of execution. T040
still needs separate runtime approval. No application implementation is authorized.

Historical 14:13/14:23 snapshots were partial because of sandbox access; the prior
versions are preserved in Git and candidate evidence, not presented as current facts.
