"""Host lifecycle for the local protected viewer container; no browser ownership bypass."""

import base64
import hashlib
import ipaddress
import json
import os
import secrets
import shlex
import ssl
import subprocess
import time
from datetime import UTC, datetime, timedelta

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from configuration.settings import (
    PRESENTER_STARTUP_SECONDS,
    ROOT,
    RUNTIME_SHA,
    configured_api_key,
    configured_model,
)

IMAGE = "cayu-campus-viewer:c5816d0"


def docker(*args, check=True):
    result = subprocess.run(["docker", *args], capture_output=True, text=True, timeout=60, check=False)
    if check and result.returncode:
        raise RuntimeError(f"Docker operation failed: {result.stderr[:2000]}")
    return result.stdout.strip()


def private_write(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as handle:
        handle.write(data)


def certificates(root):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Local synthetic catalog viewer")])
    now = datetime.now(UTC)
    cert = (x509.CertificateBuilder().subject_name(name).issuer_name(name)
            .public_key(key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(minutes=5)).not_valid_after(now + timedelta(days=7))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.SubjectAlternativeName([
                x509.DNSName("cayu-control"), x509.IPAddress(ipaddress.ip_address("127.0.0.1")),
            ]), critical=False).sign(key, hashes.SHA256()))
    (root / "certificate.pem").write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    private_write(root / "key.pem", key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode())
    return base64.b64encode(hashlib.sha256(key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo,
    )).digest()).decode()


def configuration(root):
    return json.loads((root / "configuration.json").read_text())


def start_host(root, *, mode="live", sessions=("dinner", "comparison", "rice-lunch", "vegetable-side")):
    if mode != "live":
        raise ValueError("Only live presenter mode is supported")
    if not configured_api_key():
        raise ValueError("Set OPENAI_API_KEY before starting a live viewer host")
    root = root.resolve()
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    (root / "staging").mkdir(mode=0o700)
    pin = certificates(root)
    control = docker(
        "run", "-d", "--init", "--cidfile", str(root / "container.id"),
        "--mount", "type=bind,src=/var/run/docker.sock,dst=/var/run/docker.sock",
        "--mount", f"type=bind,src={ROOT},dst={ROOT},readonly",
        "--mount", f"type=bind,src={root},dst={root}",
        "--env", f"CAMPUS_VIEWER_STATE={root}",
        "--env", f"CAMPUS_DATA_DIR={root / 'data'}",
        "--env", "CAMPUS_BROWSER=1", "--env", "OPENAI_API_KEY",
        "--env", f"CAYU_MODEL={configured_model()}",
        "--env", f"TMPDIR={root / 'staging'}",
        "-p", "127.0.0.1::8443", IMAGE,
    )
    private_write(root / "host.json", json.dumps({"container_id": control}))
    published = json.loads(docker("inspect", control))[0]["NetworkSettings"]["Ports"]["8443/tcp"][0]["HostPort"]
    config = {
        "control_server_container_id": control,
        "origin": f"https://127.0.0.1:{published}",
        "password": secrets.token_urlsafe(24), "viewer_key": secrets.token_hex(32),
        "spki_pin": pin, "view_sessions": list(sessions), "mode": mode,
        "recording_sessions": list(sessions),
        "recording_session": sessions[0] if sessions else None,
        "runtime_sha": RUNTIME_SHA,
    }
    private_write(root / "configuration.json", json.dumps(config))
    start_worker(root)
    tls = ssl.create_default_context(cafile=str(root / "certificate.pem"))
    deadline = time.monotonic() + PRESENTER_STARTUP_SECONDS
    with httpx.Client(base_url=config["origin"], verify=tls, trust_env=False,
                     auth=("local-presenter", config["password"]), timeout=2) as client:
        while time.monotonic() < deadline:
            try:
                if client.get("/api/health").status_code == 200:
                    return config
            except httpx.TransportError:
                pass
            time.sleep(0.2)
    raise RuntimeError("Protected worker did not become healthy; inspect its private worker.log")


def start_worker(root):
    config = configuration(root)
    # Source and state use identical absolute host/container paths for Docker binds.
    command = f"exec python -m operations.viewer_server > {shlex.quote(str(root / 'worker.log'))} 2>&1"
    docker("exec", "-d", "-w", str(ROOT), config["control_server_container_id"],
           "sh", "-c", command)


def stop_worker(root, *, crash=False):
    config = configuration(root)
    worker = json.loads((root / "worker.json").read_text())
    docker("exec", config["control_server_container_id"], "python", "-c",
           "import os,signal,sys; from pathlib import Path; pid=int(sys.argv[1]); "
           "assert Path(f'/proc/{pid}/stat').read_text().rsplit(')',1)[1].split()[19] == sys.argv[2]; "
           "os.kill(pid, int(sys.argv[3]))",
           str(worker["pid"]), worker["start_time"], "9" if crash else "15")


def remove_host(root):
    config = configuration(root)
    networks = json.loads(docker("inspect", config["control_server_container_id"]))[0]["NetworkSettings"]["Networks"]
    if any(name != "bridge" for name in networks):
        raise RuntimeError("Complete the retained Runtime sessions before removing their application host")
    docker("rm", "-f", config["control_server_container_id"])
