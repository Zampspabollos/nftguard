"""Helper compartido para ejecutar binarios externos (suricata-update, systemctl,
wg, ...) traduciendo errores de entorno (binario ausente, timeout, sin permisos) en
un resultado tipado en vez de dejar que la excepción llegue a la API como un 500."""

import subprocess
from dataclasses import dataclass


@dataclass
class CommandResult:
    ok: bool
    message: str


def run(args: list[str], timeout: int = 120) -> CommandResult:
    try:
        proc = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
    except FileNotFoundError:
        return CommandResult(ok=False, message=f"No se encontró el binario: {args[0]}")
    except subprocess.TimeoutExpired:
        return CommandResult(ok=False, message=f"Tiempo de espera agotado: {' '.join(args)}")
    except OSError as exc:
        return CommandResult(ok=False, message=f"No se pudo ejecutar {args[0]}: {exc}")
    if proc.returncode != 0:
        return CommandResult(ok=False, message=(proc.stderr or proc.stdout).strip())
    return CommandResult(ok=True, message=proc.stdout.strip())
