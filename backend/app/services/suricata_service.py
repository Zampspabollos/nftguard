"""Gestión de Suricata: config NFQUEUE, fuentes de firmas (suricata-update), control
del servicio systemd y lectura de alertas desde eve.json.

No se llama directamente al motor de Suricata para filtrar: Suricata corre como
servicio systemd en modo IPS escuchando en una cola NFQUEUE que nftables_engine
reserva para las reglas con `inspect_l7=True`. Este módulo solo gestiona su
configuración, firmas y resultados.
"""

import json
from collections import deque
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models import RuleSource, SuricataConfig
from app.services.shell import CommandResult, run as _run

_env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(disabled_extensions=(".j2",)),
    trim_blocks=True,
)


def get_config(session: Session) -> SuricataConfig:
    config = session.get(SuricataConfig, 1)
    if config is not None:
        return config

    # Ver el comentario equivalente en wireguard_service.get_config: la UI puede
    # pedir config+status en paralelo antes de que exista la fila singleton.
    config = SuricataConfig(id=1, home_net=settings.lan_network)
    session.add(config)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        config = session.get(SuricataConfig, 1)
        assert config is not None
        return config
    session.refresh(config)
    return config


def render_suricata_yaml(config: SuricataConfig) -> str:
    template = _env.get_template("suricata.yaml.j2")
    return template.render(
        home_net=config.home_net,
        nfqueue_num=config.nfqueue_num,
        rules_dir=settings.suricata_rules_dir,
        log_dir=settings.suricata_log_dir,
    )


def write_config(config: SuricataConfig) -> None:
    path = Path(settings.suricata_config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_suricata_yaml(config), encoding="utf-8")


def write_systemd_override(config: SuricataConfig) -> CommandResult:
    """El número de cola NFQUEUE se pasa por línea de comandos (-q), no solo en el
    yaml, así que cada cambio de nfqueue_num reescribe también este override."""
    override_dir = Path(settings.suricata_systemd_override_dir)
    try:
        override_dir.mkdir(parents=True, exist_ok=True)
        (override_dir / "override.conf").write_text(
            "[Service]\n"
            "ExecStart=\n"
            f"ExecStart={settings.suricata_bin} -c {settings.suricata_config_path} "
            f"-q {config.nfqueue_num} --pidfile /run/suricata.pid\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return CommandResult(ok=False, message=f"No se pudo escribir el override systemd: {exc}")
    return _run([settings.systemctl_bin, "daemon-reload"])


def service_action(action: str) -> CommandResult:
    if action not in ("start", "stop", "restart"):
        raise ValueError(f"acción de servicio no soportada: {action}")
    return _run([settings.systemctl_bin, action, settings.suricata_service_name])


def service_is_active() -> bool:
    result = _run([settings.systemctl_bin, "is-active", settings.suricata_service_name])
    return result.ok and result.message.strip() == "active"


def list_available_sources() -> CommandResult:
    """Lista las fuentes conocidas por suricata-update (incluye ET Open, abuse.ch,
    etc.). Útil para que la UI ofrezca un desplegable en vez de URLs a mano."""
    return _run([settings.suricata_update_bin, "list-sources"])


def sync_rule_sources(session: Session) -> CommandResult:
    """Sincroniza las fuentes activas en BD con suricata-update y descarga firmas
    al directorio de reglas. Se puede llamar tanto al activar/desactivar una fuente
    como manualmente desde la UI ("Actualizar firmas")."""
    sources = list(session.exec(select(RuleSource)))

    for source in sources:
        if source.url:
            # Fuente "cruda": una URL directa a un .rules (p. ej. un repo de GitHub),
            # se registra como fuente personalizada antes de poder activarla.
            add_result = _run([settings.suricata_update_bin, "add-source", source.name, source.url])
            if not add_result.ok and "already exists" not in add_result.message.lower():
                return add_result
        toggle = "enable-source" if source.enabled else "disable-source"
        _run([settings.suricata_update_bin, toggle, source.name])

    return _run([settings.suricata_update_bin, "--no-test", "-o", settings.suricata_rules_dir])


def read_alerts(limit: int = 100) -> list[dict]:
    """Lee las últimas alertas de eve.json. Usa una ventana deslizante (deque) en
    vez de cargar el fichero entero en memoria, importante en equipos con poca RAM
    cuando el log lleva tiempo acumulando eventos."""
    path = Path(settings.suricata_eve_path)
    if not path.exists():
        return []

    window = deque(maxlen=max(limit * 20, 2000))
    with path.open("r", encoding="utf-8", errors="replace") as fh:
        window.extend(fh)

    alerts: list[dict] = []
    for line in reversed(window):
        line = line.strip()
        if not line:
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if event.get("event_type") != "alert":
            continue
        alert = event.get("alert", {})
        alerts.append(
            {
                "timestamp": event.get("timestamp"),
                "src_ip": event.get("src_ip"),
                "dest_ip": event.get("dest_ip"),
                "proto": event.get("proto"),
                "signature": alert.get("signature"),
                "category": alert.get("category"),
                "severity": alert.get("severity"),
                "action": alert.get("action"),
            }
        )
        if len(alerts) >= limit:
            break
    return alerts
