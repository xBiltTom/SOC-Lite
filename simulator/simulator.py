"""Generador de eventos ficticios para el laboratorio SOC-Lite."""
import json
import os
import random
import signal
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
if __package__:
    from .scenarios import additional_scenarios
else:
    from scenarios import additional_scenarios

SCENARIOS = {
    "ssh": ("5710", 12, "Fuerza bruta SSH: múltiples intentos fallidos contra una cuenta privilegiada", "SRV-WEB01", 22, 5),
    "ransomware": ("100001", 14, "Posible ransomware: cifrado masivo de archivos en un recurso compartido", "SRV-FILE01", 445, 5),
    "benign": ("5706", 7, "Inicio de sesión fallido de un script de monitoreo con credenciales vencidas", "SRV-MON01", 22, 2),
    "portscan": ("92052", 10, "Escaneo de puertos: múltiples intentos de conexión a servicios internos", "FW-PERIMETRO", 443, 4),
    "powershell": ("100010", 12, "PowerShell ofuscado ejecutado en una estación de trabajo", "WKS-CONTAB01", 443, 4),
    "web_exploit": ("31103", 12, "Posible explotación web: intento de SQL injection contra el portal", "SRV-WEB02", 443, 5),
    "dns": ("100020", 8, "Consulta DNS inusual a un dominio recientemente registrado", "WKS-VENTAS01", 53, 3),
    "malware": ("100030", 13, "Malware detectado en un archivo descargado por un usuario", "WKS-RRHH01", 443, 4),
    "privilege": ("100040", 11, "Escalada de privilegios: usuario agregado al grupo de administradores", "SRV-AD01", 389, 5),
    "exfiltration": ("100050", 13, "Posible exfiltración: volumen inusual de datos hacia un destino externo", "SRV-FILE02", 443, 5),
    "login": ("100060", 10, "Acceso fuera del horario habitual a una cuenta administrativa", "SRV-AD02", 3389, 4),
    "firewall": ("2501", 7, "Firewall bloqueó una conexión saliente no autorizada", "FW-PERIMETRO", 8443, 3),
}
SCENARIOS.update(additional_scenarios())


def make_event(name):
    rule_id, level, description, host, port, criticality = SCENARIOS[name]
    return {
        "id": f"demo-{name}-{uuid.uuid4().hex[:12]}",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": "wazuh",
        "rule": {"id": rule_id, "level": level, "description": description},
        "agent": {"name": host, "criticality": criticality},
        "data": {"srcip": f"203.0.113.{random.randint(1, 254)}", "dstip": f"10.0.4.{random.randint(1, 254)}", "dstport": port, "protocol": "udp" if port == 53 else "tcp"},
        "demo": True,
        "demo_scenario": name,
    }


def shuffled_scenarios():
    names = list(SCENARIOS)
    random.shuffle(names)
    return names


def main():
    interval = float(os.environ.get("SIMULATOR_INTERVAL_SECONDS", "30"))
    if interval < 1:
        raise ValueError("El intervalo mínimo es 1 segundo")
    url = os.environ.get("SIMULATOR_WEBHOOK_URL", "http://n8n:5678/webhook/soc-lite-ingest")
    stopped = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    print(f"Simulador iniciado; intervalo={interval}s; escenarios={len(SCENARIOS)}", flush=True)
    while not stopped.is_set():
        for name in shuffled_scenarios():
            if stopped.is_set():
                return
            event = make_event(name)
            request = urllib.request.Request(url, data=json.dumps(event).encode(), headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=100) as response:
                    result = json.load(response)
                print(f"{name}: {result.get('status')} alerta={result.get('alert_id')}", flush=True)
            except (urllib.error.URLError, OSError, ValueError) as exc:
                print(f"{name}: no se pudo enviar ({exc}); se intentará con el siguiente evento", flush=True)
            if stopped.wait(interval):
                return


if __name__ == "__main__":
    main()
