# Node 1 read-only audit

Observed 2026-11-07 at approximately 14:13 America/Los_Angeles. This is a short
snapshot from a restricted session on hostname `node1`, not a capacity guarantee.

| Area | Observed evidence | Implication |
| --- | --- | --- |
| Hardware | Dell Precision 5520; i7-7820HQ; 4 cores, 8 threads | Shared laptop-class CPU; begin with serial inference |
| RAM | 30 GiB usable; 5.4 GiB used; 1.6 GiB free; 25 GiB available | Cache accounts for much of RAM; available is the useful headroom measure |
| Swap | 8 GiB total, 3.6 GiB used | Prior pressure possible; do not clear swap |
| Pressure sample | Two one-second vmstat intervals: zero swap-in/out, 90–92% CPU idle; memory PSI averages 0.00 | No current pressure seen in this brief sample; peaks unknown |
| Load | 0.54 / 0.52 / 0.43; uptime 70 days | Low sampled CPU demand |
| Disk | Root/project ext4: 468 GiB size, 215 GiB used, 229 GiB available; inodes 5% used | Room for a small stack; Docker root and model storage unknown |
| Temporary storage | `/tmp` is tmpfs, 16 GiB capacity | Large temporary builds consume RAM; avoid them |
| GPU | PCI reports Quadro M1200 Mobile and Intel HD 630 | Presence verified; usable VRAM and offload unknown |
| GPU runtime | `nvidia-smi` cannot communicate with NVIDIA driver | May be driver or sandbox access; do not diagnose as a confirmed host driver failure |
| Docker client | 29.7.2; Compose v5.4.0; context `default` | Client availability only |
| Docker daemon | Permission denied on `/var/run/docker.sock` | Running/stopped containers, stats, volumes, image usage, projects and published ports unverified |
| Ports | `ss -lntup` denied netlink access | No port can be declared free |
| Ollama | Binary `/usr/local/bin/ollama`; client 0.40.13 | Server version unknown; client warning is not proof service is down |
| Ollama API | Local socket access denied for `/api/version`, `/api/tags`, `/api/ps`; system bus access denied | Qwen availability, digest, quantization, context and loaded models all unverified |
| Project | Empty `docs/`; no source; `.git` reserved/read-only, not valid Git metadata | Documents can be created; repository initialization blocked |

## Risks before changes

1. Homelab usage can spike during media transcoding, photo processing, or backups.
   Present headroom permits planning, but runtime admission needs workload evidence.
2. A 9B model's resident memory depends on quantization, context and offload. Disk
   model size is not a RAM estimate. CPU inference may be slow; GPU acceleration
   cannot be assumed. Do not repair drivers within this project.
3. Current swap occupancy and a two-second idle sample do not predict behavior
   during model loading. Observe swap activity, available RAM and service health.
4. Docker project names, volumes, network subnets and candidate ports may collide.
   No startup is authorized by an incomplete inventory.
5. Native Ollama may already serve other clients. New requests can queue or evict
   resident models. Verify current loading and shared use before the first call.
6. Session restrictions prevent completing the audit or initializing Git. These
   are access limitations, not findings that services are absent or unhealthy.

## Remaining read-only host checks

Run in an authorized host shell when available. These commands do not start or
stop workloads. Keep output local; do not dump container environments or secrets.

```bash
date -Is
free -h
df -hT .
vmstat 1 5
cat /proc/pressure/memory
docker version
docker info --format 'Root={{.DockerRootDir}} CPUs={{.NCPU}} Memory={{.MemTotal}}'
docker compose ls
docker ps -a --format 'table {{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}'
docker stats --no-stream
docker system df
docker volume ls --format '{{.Name}}'
docker network ls
ss -lntup
nvidia-smi
curl --noproxy '*' --connect-timeout 2 --max-time 5 -fsS http://127.0.0.1:11434/api/version
curl --noproxy '*' --connect-timeout 2 --max-time 5 -fsS http://127.0.0.1:11434/api/tags
curl --noproxy '*' --connect-timeout 2 --max-time 5 -fsS http://127.0.0.1:11434/api/ps
```

After inventory, inspect only relevant non-secret resource limits, project labels
and network subnets. Check free space on the reported Docker root and actual
model storage filesystem. For the exact installed model, `/api/show` can return
metadata without inference; record its capabilities, context, parameter size and
quantization. Do not call generation endpoints during the remaining audit.

Record baseline health of existing services using their already available health
status; do not invent health URLs or send traffic to unrelated applications.
Resolve every unknown above before treating the runtime admission gate as passed.

## Refresh for task graph — 2026-11-07 14:23 America/Los_Angeles

Read-only reinspection confirmed 25 GiB available RAM, 3.6 GiB used swap,
229 GiB available project disk and load 0.39/0.49/0.46. Two one-second vmstat
samples showed zero swap-in/out and 93–94% idle CPU; memory PSI averages were
zero. PCI still reports the M1200; GPU runtime access remains unverified.
Docker, listening-port and Ollama API checks remain denied. Git still reports
no valid repository, with read-only `.git`. Planning documents exist; no source
or Compose implementation exists. No service or runtime change was made.
See TASK_GRAPH.md for the explicit external blockers T001/T002 and prerequisite
gate T007; the short refresh is not the required 60-second admission sample.
