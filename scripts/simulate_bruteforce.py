#!/usr/bin/env python3
"""Envía una alerta Wazuh ficticia al webhook de laboratorio."""
import argparse
import json
import sys
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:5679/webhook/soc-lite-ingest")
    parser.add_argument("--id", default=None, help="ID del evento para reproducirlo")
    parser.add_argument("--timestamp", default=None, help="Hora ISO para reproducir exactamente el evento")
    args = parser.parse_args()
    payload = {
        "id": args.id or f"demo-ssh-{uuid.uuid4().hex[:12]}",
        "timestamp": args.timestamp or datetime.now(timezone.utc).isoformat(),
        "source": "wazuh",
        "rule": {"id": "5710", "level": 12, "description": "Fuerza bruta SSH simulada: múltiples intentos fallidos"},
        "agent": {"name": "SRV-DEMO-WEB01", "criticality": 5},
        "data": {"srcip": "203.0.113.44", "dstip": "10.0.4.21", "dstport": 22, "protocol": "tcp"},
        "demo": True,
    }
    request = urllib.request.Request(args.url, data=json.dumps(payload).encode(), headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            print(json.dumps({"evento": payload, "respuesta": json.load(response)}, ensure_ascii=False, indent=2))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        print(f"No se pudo procesar la alerta: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
