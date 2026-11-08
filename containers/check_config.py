"""Read-only T015 Compose checks. Never contacts the Docker daemon or builds."""
import json
import os
from pathlib import Path
import subprocess

root = Path(__file__).resolve().parents[1]
command = [
    "docker", "compose", "--env-file", "/dev/null", "-p", "mcpbench",
    "-f", str(root / "compose.yaml"), "--profile", "*", "config", "--format", "json",
]
# Ignore caller interpolation variables and local .env; use absent synthetic paths.
render = subprocess.run(command, check=True, capture_output=True, text=True,
                        env={"PATH": os.environ["PATH"]})
config = json.loads(render.stdout)
lock = json.loads((root / "config/images.lock.json").read_text())["images"]
assert config["name"] == "mcpbench"
services = config["services"]
assert set(services) == {"db", "mcp", "agent", "verifier", "evaluator"}
limits = {"db": (512, .5), "mcp": (256, .5), "agent": (512, 1),
          "verifier": (512, 1), "evaluator": (512, .5)}
for name, service in services.items():
    memory, cpu = limits[name]
    assert int(service["mem_limit"]) == int(service["memswap_limit"]) == memory * 1024**2
    assert float(service["cpus"]) == cpu
    assert service["user"] == ("999:999" if name == "db" else "1000:1000")
    assert service["platform"] == "linux/amd64"
    assert service["read_only"] and service["restart"] == "no"
    assert service["cap_drop"] == ["ALL"]
    assert service["security_opt"] == ["no-new-privileges:true"]
    assert service["pids_limit"] == 128
    assert not any(service.get(key) for key in
                   ("privileged", "cap_add", "devices", "group_add", "pid", "ipc", "extra_hosts", "env_file"))
    if name != "mcp":
        assert not service.get("ports")
    assert service["tmpfs"] and all("size=" in item for item in service["tmpfs"])
    for mount in service.get("volumes", []):
        if mount["type"] == "bind":
            assert mount["source"].startswith("/nonexistent/mcpbench/")
            assert mount["bind"]["create_host_path"] is False
    if name in {"agent", "verifier"}:
        assert service["network_mode"] == "host" and not service.get("networks")
        assert set(service["environment"]) == {"PATH", "LANG", "TZ", "HOME", "TMPDIR"}
        assert service["entrypoint"] == ["/usr/bin/env", "-i", "PATH=/usr/local/bin:/usr/bin:/bin",
                                         "LANG=C.UTF-8", "TZ=UTC", "HOME=/nonexistent", "TMPDIR=/tmp", "/app/agent"]
        assert service["command"] == ["run" if name == "agent" else "verify", "--request",
                                      "/run/mcpbench/request.json", "--auth", "/run/secrets/auth.json",
                                      "--output", "/run/mcpbench/output"]
        mounts = service["volumes"]
        assert len(mounts) == 3
        assert {m["target"]: m.get("read_only", False) for m in mounts} == {
            "/run/mcpbench/request.json": True, "/run/secrets/auth.json": True,
            "/run/mcpbench/output": False}
        assert service["profiles"] == [name]
    else:
        assert set(service["networks"]) == {"db"}
        assert not service.get("network_mode")
assert services["agent"]["volumes"] != services["verifier"]["volumes"]
port, = services["mcp"]["ports"]
assert port["host_ip"] == "127.0.0.1" and port["published"] == "18081" and port["target"] == 8080
assert services["db"]["image"] == lock["postgres"]["reference"]
assert services["db"]["environment"]["POSTGRES_PASSWORD_FILE"] == "/run/secrets/bootstrap-password"
assert services["db"]["healthcheck"]["timeout"] == "3s"
assert services["mcp"]["healthcheck"]["disable"] is True
assert services["evaluator"]["profiles"] == ["evaluator"]
assert services["evaluator"]["command"] == ["prepare"]
assert {m["target"]: m.get("read_only", False) for m in services["evaluator"]["volumes"]} == {
    "/run/mcpbench/control": True, "/run/mcpbench/output": False}
assert config["networks"] == {"db": {"name": "mcpbench_db", "driver": "bridge", "ipam": {}, "internal": True}}
assert config["volumes"] == {"db-data": {"name": "mcpbench_db-data"}}
for filename, roles in {"go.Dockerfile": ["go_builder", "go_runtime"],
                        "evaluator.Dockerfile": ["python_evaluator"]}.items():
    dockerfile = (root / "containers" / filename).read_text()
    references = [line.split()[1] for line in dockerfile.splitlines() if line.startswith("FROM ")]
    assert [ref for ref in references if ref != "runtime"] == [lock[role]["reference"] for role in roles]
    assert "USER 1000:1000" in dockerfile
    assert "HEALTHCHECK" not in dockerfile
for name in ("mcp", "agent", "verifier", "evaluator"):
    assert services[name]["pull_policy"] == "never"
print("PASS: Compose render; 5 identities/limits; private DB; loopback MCP; separate narrow agent/verifier mounts; pinned bases; no daemon/runtime operations")
