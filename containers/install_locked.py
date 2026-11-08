"""Build-only export of locked wheel hashes, without another package resolver."""
from pathlib import Path
import subprocess
import sys
import tomllib

lock = tomllib.loads(Path("/tmp/uv.lock").read_text())
requirements = []
for package in lock["package"]:
    if package["source"] == {"virtual": "."}:
        continue
    if package["source"] != {"registry": "https://pypi.org/simple"}:
        raise SystemExit("unsupported dependency source")
    hashes = [wheel["hash"] for wheel in package["wheels"]]
    if not hashes or any(not value.startswith("sha256:") for value in hashes):
        raise SystemExit("locked wheels require SHA-256 hashes")
    requirements.append(
        f"{package['name']}=={package['version']} "
        + " ".join(f"--hash={value}" for value in hashes)
    )
Path("/tmp/requirements.txt").write_text("\n".join(requirements) + "\n")
subprocess.run([
    sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
    "--no-cache-dir", "--only-binary=:all:", "--require-hashes", "--no-deps",
    "-r", "/tmp/requirements.txt",
], check=True)
