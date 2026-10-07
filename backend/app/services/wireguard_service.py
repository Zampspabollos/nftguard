"""Gestión de WireGuard: generación de claves, render de wg0.conf, control del
servicio (`wg-quick@wg0.service`) y config/QR por peer.

Las claves se generan con la librería `cryptography` (curve25519) en vez de invocar
`wg genkey`/`wg pubkey`: son el mismo formato (32 bytes en base64) y así no depende
de tener el binario `wg` instalado solo para crear un par de claves.
"""

import base64
import ipaddress
import re
from io import BytesIO
from pathlib import Path

import qrcode
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.core.config import settings
from app.db.models import WireguardPeer, WireguardServerConfig
from app.services.shell import CommandResult, run as _run

_HOSTNAME_RE = re.compile(r"^[a-zA-Z0-9.\-]{1,255}$")


class WireguardValidationError(ValueError):
    pass


def generate_keypair() -> tuple[str, str]:
    private_key = X25519PrivateKey.generate()
    priv_bytes = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_bytes = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw, format=serialization.PublicFormat.Raw
    )
    return base64.b64encode(priv_bytes).decode(), base64.b64encode(pub_bytes).decode()


def get_config(session: Session) -> WireguardServerConfig:
    config = session.get(WireguardServerConfig, 1)
    if config is not None:
        return config

    # La UI puede disparar varias peticiones en paralelo (config+status+...) en su
    # primera carga; sin fila todavía, más de una podría intentar crearla a la vez.
    # Si perdemos la carrera, simplemente releemos la fila que ganó.
    private_key, public_key = generate_keypair()
    config = WireguardServerConfig(
        id=1, private_key=private_key, public_key=public_key, client_allowed_ips=settings.lan_network
    )
    session.add(config)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        config = session.get(WireguardServerConfig, 1)
        assert config is not None
        return config
    session.refresh(config)
    return config


def _validate_cidr(value: str, field: str) -> ipaddress.IPv4Network:
    try:
        return ipaddress.ip_network(value, strict=False)
    except ValueError as exc:
        raise WireguardValidationError(f"{field} inválido: {value!r}") from exc


def _validate_ip(value: str, field: str) -> str:
    try:
        ipaddress.ip_address(value)
    except ValueError as exc:
        raise WireguardValidationError(f"{field} inválido: {value!r}") from exc
    return value


def validate_config(config: WireguardServerConfig) -> None:
    network = _validate_cidr(config.network_cidr, "network_cidr")
    _validate_ip(config.server_ip, "server_ip")
    if ipaddress.ip_address(config.server_ip) not in network:
        raise WireguardValidationError("server_ip debe pertenecer a network_cidr")
    _validate_cidr(config.client_allowed_ips, "client_allowed_ips")
    if config.dns:
        _validate_ip(config.dns, "dns")
    if config.endpoint_host and not _HOSTNAME_RE.match(config.endpoint_host):
        raise WireguardValidationError(f"endpoint_host inválido: {config.endpoint_host!r}")
    if not (0 < config.listen_port <= 65535):
        raise WireguardValidationError("listen_port fuera de rango")


def _next_free_address(session: Session, config: WireguardServerConfig) -> str:
    network = ipaddress.ip_network(config.network_cidr, strict=False)
    used = {ipaddress.ip_interface(p.address).ip for p in session.exec(select(WireguardPeer))}
    used.add(ipaddress.ip_address(config.server_ip))
    for host in network.hosts():
        if host not in used:
            return f"{host}/32"
    raise WireguardValidationError("No quedan IPs libres en la subred de la VPN")


def create_peer(session: Session, name: str) -> WireguardPeer:
    config = get_config(session)
    private_key, public_key = generate_keypair()
    address = _next_free_address(session, config)
    peer = WireguardPeer(name=name, private_key=private_key, public_key=public_key, address=address)
    session.add(peer)
    session.commit()
    session.refresh(peer)
    return peer


def render_server_conf(config: WireguardServerConfig, peers: list[WireguardPeer]) -> str:
    network = ipaddress.ip_network(config.network_cidr, strict=False)
    lines = [
        "# Generado por nftguard. NO editar a mano: se sobrescribe al cambiar la",
        "# config o los peers de WireGuard desde la UI.",
        "[Interface]",
        f"PrivateKey = {config.private_key}",
        f"Address = {config.server_ip}/{network.prefixlen}",
        f"ListenPort = {config.listen_port}",
        "",
    ]
    for peer in peers:
        if not peer.enabled:
            continue
        lines += [
            "[Peer]",
            f"# {peer.name}",
            f"PublicKey = {peer.public_key}",
            f"AllowedIPs = {peer.address}",
            "",
        ]
    return "\n".join(lines)


def render_peer_conf(config: WireguardServerConfig, peer: WireguardPeer) -> str:
    if not config.endpoint_host:
        raise WireguardValidationError(
            "Configura primero el 'host/IP público' (endpoint_host) en la config de WireGuard"
        )
    lines = ["[Interface]", f"PrivateKey = {peer.private_key}", f"Address = {peer.address}"]
    if config.dns:
        lines.append(f"DNS = {config.dns}")
    lines += [
        "",
        "[Peer]",
        f"PublicKey = {config.public_key}",
        f"Endpoint = {config.endpoint_host}:{config.listen_port}",
        f"AllowedIPs = {config.client_allowed_ips}",
        "PersistentKeepalive = 25",
    ]
    return "\n".join(lines)


def peer_qrcode_png(config: WireguardServerConfig, peer: WireguardPeer) -> bytes:
    conf_text = render_peer_conf(config, peer)
    img = qrcode.make(conf_text)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def write_server_conf(session: Session) -> WireguardServerConfig:
    config = get_config(session)
    validate_config(config)
    peers = list(session.exec(select(WireguardPeer)))
    path = Path(settings.wireguard_conf_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_server_conf(config, peers), encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass
    return config


def _unit_name() -> str:
    return f"wg-quick@{settings.wireguard_iface}.service"


def service_action(action: str) -> CommandResult:
    if action not in ("start", "stop", "restart"):
        raise ValueError(f"acción de servicio no soportada: {action}")
    return _run([settings.systemctl_bin, action, _unit_name()])


def service_is_active() -> bool:
    result = _run([settings.systemctl_bin, "is-active", _unit_name()])
    return result.ok and result.message.strip() == "active"


def sync_running_config() -> CommandResult:
    """Si wg0 ya está activo, aplica los cambios sin cortar las conexiones existentes
    (wg syncconf) en vez de reiniciar toda la interfaz."""
    if not service_is_active():
        return CommandResult(ok=True, message="wg0 no está activo; los cambios se aplicarán al iniciar el servicio")

    strip = _run([settings.wg_bin, "strip", settings.wireguard_conf_path])
    if not strip.ok:
        return strip

    tmp_path = Path(settings.wireguard_conf_path).with_suffix(".stripped")
    try:
        tmp_path.write_text(strip.message + "\n", encoding="utf-8")
        return _run([settings.wg_bin, "setconf", settings.wireguard_iface, str(tmp_path)])
    finally:
        tmp_path.unlink(missing_ok=True)


def apply_changes(session: Session) -> CommandResult:
    """Reescribe wg0.conf y, si la interfaz ya está activa, sincroniza en caliente."""
    try:
        write_server_conf(session)
    except OSError as exc:
        return CommandResult(ok=False, message=f"No se pudo escribir {settings.wireguard_conf_path}: {exc}")
    return sync_running_config()
