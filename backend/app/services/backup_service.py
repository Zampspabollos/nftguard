"""Exporta/importa toda la configuración de nftguard como JSON: reglas, NAT,
config y fuentes de Suricata, config y peers de WireGuard, usuarios.

El fichero de backup es sensible: incluye hashes de contraseña y claves privadas
de WireGuard. Se trata con el mismo nivel de confianza que el propio fichero de
base de datos (quien lo tiene ya podría suplantar el backend)."""

from datetime import datetime, timezone
from typing import Any

from sqlmodel import Session, select

from app.db.models import (
    FirewallRule,
    PortForward,
    RuleSource,
    SuricataConfig,
    User,
    WireguardPeer,
    WireguardServerConfig,
)

_BACKUP_VERSION = 1

_TABLES = {
    "users": User,
    "firewall_rules": FirewallRule,
    "port_forwards": PortForward,
    "suricata_config": SuricataConfig,
    "rule_sources": RuleSource,
    "wireguard_config": WireguardServerConfig,
    "wireguard_peers": WireguardPeer,
}


class RestoreError(ValueError):
    pass


def export_all(session: Session) -> dict[str, Any]:
    data: dict[str, Any] = {
        "version": _BACKUP_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
    }
    for key, model in _TABLES.items():
        rows = session.exec(select(model)).all()
        data[key] = [row.model_dump(mode="json") for row in rows]
    return data


def restore_all(session: Session, data: dict[str, Any]) -> None:
    if data.get("version") != _BACKUP_VERSION:
        raise RestoreError(f"Versión de backup no soportada: {data.get('version')!r}")
    for key in _TABLES:
        if key not in data or not isinstance(data[key], list):
            raise RestoreError(f"Falta o es inválida la sección '{key}' en el backup")

    try:
        # model_validate() (a diferencia de model(**row)) aplica la coerción de
        # Pydantic: sin ella, un datetime serializado como string en el JSON del
        # backup llega tal cual hasta el INSERT y SQLite lo rechaza.
        parsed = {key: [model.model_validate(row) for row in data[key]] for key, model in _TABLES.items()}
    except (TypeError, ValueError) as exc:
        raise RestoreError(f"Datos de backup inválidos: {exc}") from exc

    # Reemplazo completo: sin relaciones cruzadas (FK) entre estas tablas, así que
    # el orden de borrado/recarga no importa.
    for model in _TABLES.values():
        for row in session.exec(select(model)).all():
            session.delete(row)
    session.commit()

    for rows in parsed.values():
        for row in rows:
            session.add(row)
    session.commit()
