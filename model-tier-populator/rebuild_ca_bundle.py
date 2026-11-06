"""One-off: rebuild certs/ca-bundle.pem = certifi roots + the endpoint's real issuing CA.

Run from model-tier-populator/ with the project venv:
    .venv\\Scripts\\python.exe rebuild_ca_bundle.py
"""
import ssl
import sys
from pathlib import Path

import certifi

HOST = "ai-gateway.atrad.lk"
CERTS = Path(__file__).parent / "certs"
ROOT_OUT = CERTS / "company-root-ca.pem"
BUNDLE_OUT = CERTS / "ca-bundle.pem"


def main() -> int:
    import socket

    raw = socket.create_connection((HOST, 443), timeout=20)
    ctx = ssl.create_default_context()
    sock = ctx.wrap_socket(raw, server_hostname=HOST)
    try:
        chain = sock._sslobj.get_unverified_chain()
    finally:
        sock.close()

    pems = []
    for cert in chain:
        blob = cert.public_bytes()
        pems.append(blob if isinstance(blob, str) else ssl.DER_cert_to_PEM_cert(blob))

    if len(pems) < 2:
        print(f"error: server sent {len(pems)} certificate(s); expected leaf + issuing CA")
        return 1

    root = pems[-1]
    ROOT_OUT.write_text(root if root.endswith("\n") else root + "\n", encoding="ascii")
    print(f"wrote {ROOT_OUT.name} ({len(root.splitlines())} lines)")

    certifi_pem = Path(certifi.where()).read_text(encoding="ascii")
    if not certifi_pem.endswith("\n"):
        certifi_pem += "\n"
    BUNDLE_OUT.write_text(certifi_pem + "\n" + root, encoding="ascii", newline="\n")
    print(f"wrote {BUNDLE_OUT.name} ({(BUNDLE_OUT.read_text(encoding='ascii').count('BEGIN CERTIFICATE'))} roots)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
