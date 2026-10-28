"""Generador de eventos ficticios para el laboratorio SOC-Lite."""
import itertools
import json
import os
import signal
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

SCENARIOS = {
    "ssh": ("5710", 12, "Fuerza bruta SSH simulada: múltiples intentos fallidos", "SRV-DEMO-WEB01", 22),
    "ransomware": ("100001", 14, "Ransomware simulado: cifrado masivo de archivos", "SRV-DEMO-FILE01", 445),
    "benign": ("5706", 7, "Inicio de sesión fallido simulado de un script de monitoreo", "SRV-DEMO-MON01", 22),
}


def make_event(name):
    rule_id, level, description, host, port = SCENARIOS[name]
    return {
        "id": f"demo-{name}-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "wazuh",
        "rule": {"id": rule_id, "level": level, "description": description},
        "agent": {"name": host, "criticality": 5 if name != "benign" else 2},
        "data": {"srcip": "203.0.113.44", "dstip": "10.0.4.21", "dstport": port, "protocol": "tcp"},
        "demo": True,
        "demo_scenario": name,
    }


def main():
    interval = float(os.environ.get("SIMULATOR_INTERVAL_SECONDS", "30"))
    names = [name.strip() for name in os.environ.get("SIMULATOR_SCENARIOS", "ssh,ransomware,benign").split(",") if name.strip()]
    if interval < 1 or not names or any(name not in SCENARIOS for name in names):
        raise ValueError("Intervalo mínimo 1 segundo; escenarios permitidos: ssh,ransomware,benign")
    url = os.environ.get("SIMULATOR_WEBHOOK_URL", "http://n8n:5678/webhook/soc-lite-ingest")
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    print(f"Simulador iniciado; intervalo={interval}s; escenarios={','.join(names)}", flush=True)
    for name in itertools.cycle(names):
        if stopped.is_set():
            break
        event = make_event(name)
        request = urllib.request.Request(url, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(request, timeout=100) as response:
                result = json.load(response)
            print(f"{name}: {result.get('status')} alerta={result.get('alert_id')}", flush=True)
        except (urllib.error.URLError, OSError, ValueError) as exc:
            print(f"{name}: no se pudo enviar ({exc}); se intentará con el siguiente evento", flush=True)
        if stopped.wait(interval):
            break


if __name__ == "__main__":
    main()
