"""Motor de reglas nftables: modelo -> texto nft -> validar -> aplicar.

Diseño: las reglas nunca se interpolan como texto libre en el ruleset. Cada campo se
valida (interfaz, IP/CIDR, puerto) antes de generar el statement nft correspondiente,
y el comentario se escapa. Esto evita que un valor mal formado en la base de datos
rompa el ruleset o inyecte sintaxis nft arbitraria.
"""

import ipaddress
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, PackageLoader, select_autoescape

from app.core.config import settings
from app.db.models import Action, Chain, FirewallRule, PortForward, Protocol

_IFACE_RE = re.compile(r"^[a-zA-Z0-9_.\-]{1,15}$")
_PORT_RE = re.compile(r"^\d{1,5}(-\d{1,5})?$")

_env = Environment(
    loader=PackageLoader("app", "templates"),
    autoescape=select_autoescape(disabled_extensions=(".j2",)),
    trim_blocks=True,
)


class RuleValidationError(ValueError):
    pass


def _validate_iface(value: str | None) -> str | None:
    if value is None:
        return None
    if not _IFACE_RE.match(value):
        raise RuleValidationError(f"Nombre de interfaz inválido: {value!r}")
    return value


def _validate_ip(value: str | None) -> str | None:
    if value is None:
        return None
    try:
        ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise RuleValidationError(f"IP/CIDR inválida: {value!r}") from exc
    return value


def _validate_port(value: str | None) -> str | None:
    if value is None:
        return None
    if not _PORT_RE.match(value):
        raise RuleValidationError(f"Puerto/rango inválido: {value!r}")
    parts = value.split("-")
    for p in parts:
        if not (0 < int(p) <= 65535):
            raise RuleValidationError(f"Puerto fuera de rango: {value!r}")
    return value


def _escape_comment(value: str | None) -> str | None:
    if value is None:
        return None
    return value.replace("\\", "").replace('"', "'")[:120]


def render_rule(rule: FirewallRule, suricata_enabled: bool = False, nfqueue_num: int = 100) -> str:
    parts: list[str] = []

    iif = _validate_iface(rule.src_iface)
    oif = _validate_iface(rule.dst_iface)
    saddr = _validate_ip(rule.src_ip)
    daddr = _validate_ip(rule.dst_ip)
    sport = _validate_port(rule.src_port)
    dport = _validate_port(rule.dst_port)

    if iif:
        parts.append(f'iifname "{iif}"')
    if oif:
        parts.append(f'oifname "{oif}"')
    if saddr:
        parts.append(f"ip saddr {saddr}")
    if daddr:
        parts.append(f"ip daddr {daddr}")

    if rule.protocol != Protocol.any:
        proto = rule.protocol.value
        if rule.protocol in (Protocol.tcp, Protocol.udp):
            if sport:
                parts.append(f"{proto} sport {sport}")
            if dport:
                parts.append(f"{proto} dport {dport}")
            if not sport and not dport:
                # Sin puerto, el statement tcp/udp no aparece por sí solo: hay que
                # fijar el protocolo explícitamente o la regla matchearía cualquier
                # tráfico, no solo tcp/udp.
                parts.append(f"meta l4proto {proto}")
        else:
            # icmp: sin esto, una regla "protocol=icmp" sin más matchers aceptaría
            # o bloquearía TODO el tráfico, no solo icmp.
            parts.append("meta l4proto icmp")
    elif sport or dport:
        raise RuleValidationError("src_port/dst_port requieren protocol tcp o udp")

    if rule.protocol in (Protocol.tcp, Protocol.udp):
        parts.append("ct state new")

    if rule.rate_limit:
        if not re.match(r"^\d+/(second|minute|hour|day)$", rule.rate_limit):
            raise RuleValidationError(f"rate_limit inválido: {rule.rate_limit!r}")
        parts.append(f"limit rate {rule.rate_limit}")

    if rule.log:
        comment_tag = _escape_comment(rule.comment) or f"rule-{rule.id}"
        parts.append(f'log prefix "nftguard[{comment_tag}]: "')

    if rule.inspect_l7 and suricata_enabled:
        # La decisión final (accept/drop) la toma Suricata según sus firmas, no la
        # "action" de esta regla. "bypass" evita bloquear todo el tráfico si Suricata
        # no está escuchando en la cola (p. ej. se ha caído): el tráfico pasa sin
        # inspeccionar en vez de colgarse. Si Suricata está deshabilitado globalmente
        # (más abajo, suricata_enabled=False) la regla usa su acción normal.
        parts.append(f"queue num {nfqueue_num} bypass")
    else:
        action_map = {Action.accept: "accept", Action.drop: "drop", Action.reject: "reject"}
        parts.append(action_map[rule.action])

    comment = _escape_comment(rule.comment)
    if comment:
        parts.append(f'comment "{comment}"')

    return " ".join(parts)


def render_portforward_dnat(pf: PortForward) -> str:
    wan_port = _validate_port(pf.wan_port)
    dst_ip = _validate_ip(pf.dst_ip)
    dst_port = _validate_port(pf.dst_port)
    proto = pf.protocol.value if pf.protocol != Protocol.any else "tcp"
    comment = _escape_comment(pf.comment) or f"pf-{pf.id}"
    return (
        f'iifname "{settings.wan_iface}" {proto} dport {wan_port} '
        f"dnat to {dst_ip}:{dst_port} comment \"{comment}\""
    )


def render_portforward_accept(pf: PortForward) -> str:
    dst_ip = _validate_ip(pf.dst_ip)
    dst_port = _validate_port(pf.dst_port)
    proto = pf.protocol.value if pf.protocol != Protocol.any else "tcp"
    comment = _escape_comment(pf.comment) or f"pf-{pf.id}"
    return (
        f"ip daddr {dst_ip} {proto} dport {dst_port} ct state new accept "
        f'comment "{comment}"'
    )


def render_ruleset(
    rules: list[FirewallRule],
    port_forwards: list[PortForward],
    suricata_enabled: bool = False,
    nfqueue_num: int = 100,
    vpn_enabled: bool = False,
    wg_iface: str = "wg0",
    wg_listen_port: int = 51820,
) -> str:
    enabled_rules = sorted((r for r in rules if r.enabled), key=lambda r: r.priority)
    enabled_pfs = [pf for pf in port_forwards if pf.enabled]

    def _render(r: FirewallRule) -> str:
        return render_rule(r, suricata_enabled=suricata_enabled, nfqueue_num=nfqueue_num)

    input_lines = [_render(r) for r in enabled_rules if r.chain == Chain.input]
    forward_lines = [_render(r) for r in enabled_rules if r.chain == Chain.forward]

    template = _env.get_template("ruleset.nft.j2")
    return template.render(
        mode=settings.mode,
        wan_iface=settings.wan_iface,
        lan_iface=settings.lan_iface,
        web_ui_port=settings.web_ui_port,
        input_rules=input_lines,
        forward_rules=forward_lines,
        portforward_dnat_rules=[render_portforward_dnat(pf) for pf in enabled_pfs],
        portforward_accept_rules=[render_portforward_accept(pf) for pf in enabled_pfs],
        vpn_enabled=vpn_enabled,
        wg_iface=wg_iface,
        wg_listen_port=wg_listen_port,
    )


@dataclass
class ApplyResult:
    ok: bool
    message: str


def _run_nft(args: list[str]) -> ApplyResult | subprocess.CompletedProcess:
    """Ejecuta nft y traduce errores de entorno (binario ausente, sin permisos) en un
    ApplyResult en vez de dejar que la excepción llegue a la API como un 500."""
    try:
        return subprocess.run([settings.nft_bin, *args], capture_output=True, text=True)
    except FileNotFoundError:
        return ApplyResult(
            ok=False,
            message=f"No se encontró el binario nft en {settings.nft_bin}. "
            "¿Está instalado nftables en este equipo?",
        )
    except OSError as exc:
        return ApplyResult(ok=False, message=f"No se pudo ejecutar nft: {exc}")


def validate_ruleset_text(text: str) -> ApplyResult:
    ruleset_dir = Path(settings.ruleset_dir)
    ruleset_dir.mkdir(parents=True, exist_ok=True)
    tmp_path = ruleset_dir / ".validate.nft"
    tmp_path.write_text(text, encoding="utf-8")
    result = _run_nft(["-c", "-f", str(tmp_path)])
    if isinstance(result, ApplyResult):
        return result
    if result.returncode != 0:
        return ApplyResult(ok=False, message=result.stderr.strip())
    return ApplyResult(ok=True, message="ok")


def apply_ruleset_text(text: str) -> ApplyResult:
    """Valida, hace backup del ruleset activo y aplica el nuevo. Si algo falla,
    intenta restaurar el backup para no dejar el firewall en un estado roto."""

    validation = validate_ruleset_text(text)
    if not validation.ok:
        return validation

    ruleset_dir = Path(settings.ruleset_dir)
    ruleset_dir.mkdir(parents=True, exist_ok=True)
    ruleset_path = Path(settings.ruleset_path)
    backup_path = Path(settings.ruleset_backup_path)

    if ruleset_path.exists():
        shutil.copy2(ruleset_path, backup_path)

    ruleset_path.write_text(text, encoding="utf-8")

    result = _run_nft(["-f", str(ruleset_path)])
    if isinstance(result, ApplyResult):
        return result
    if result.returncode != 0:
        if backup_path.exists():
            _run_nft(["-f", str(backup_path)])
        return ApplyResult(ok=False, message=f"apply falló, restaurado backup: {result.stderr.strip()}")

    return ApplyResult(ok=True, message="aplicado")
