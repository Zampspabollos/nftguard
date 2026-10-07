from datetime import datetime, timezone
from enum import Enum

from sqlmodel import Field, SQLModel


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True, unique=True)
    password_hash: str
    is_admin: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Chain(str, Enum):
    input = "input"
    forward = "forward"


class Protocol(str, Enum):
    any = "any"
    tcp = "tcp"
    udp = "udp"
    icmp = "icmp"


class Action(str, Enum):
    accept = "accept"
    drop = "drop"
    reject = "reject"


class FirewallRule(SQLModel, table=True):
    """Regla L3/L4 para las cadenas input/forward."""

    id: int | None = Field(default=None, primary_key=True)
    priority: int = Field(default=100, index=True)
    enabled: bool = True
    chain: Chain = Chain.forward
    action: Action = Action.accept
    protocol: Protocol = Protocol.any

    src_iface: str | None = None
    dst_iface: str | None = None
    src_ip: str | None = None  # IP o CIDR, None = any
    dst_ip: str | None = None
    src_port: str | None = None  # puerto o rango "1000-2000", None = any
    dst_port: str | None = None

    rate_limit: str | None = None  # ej. "10/minute", None = sin límite
    log: bool = False

    # Fase 2: si está activo, los paquetes nuevos que matchean se desvían a Suricata
    # vía NFQUEUE en lugar de aplicarse directamente la acción.
    inspect_l7: bool = False

    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SuricataConfig(SQLModel, table=True):
    """Configuración global de Suricata. Fila única (id=1)."""

    id: int | None = Field(default=1, primary_key=True)
    enabled: bool = False
    nfqueue_num: int = 100
    home_net: str = "192.168.10.0/24"


class RuleSource(SQLModel, table=True):
    """Fuente de firmas para suricata-update (nombre registrado o URL cruda,
    p. ej. un .rules hospedado en un repo de GitHub)."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True, unique=True)
    url: str | None = None  # None = fuente registrada en el índice de suricata-update
    enabled: bool = True
    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class PortForward(SQLModel, table=True):
    """Redirección de puertos (DNAT) WAN -> host interno."""

    id: int | None = Field(default=None, primary_key=True)
    enabled: bool = True
    protocol: Protocol = Protocol.tcp
    wan_port: str = Field(index=True)  # puerto o rango en la interfaz WAN
    dst_ip: str
    dst_port: str
    comment: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class WireguardServerConfig(SQLModel, table=True):
    """Configuración del servidor WireGuard (wg0). Fila única (id=1). El par de
    claves se genera automáticamente la primera vez que se lee esta config."""

    id: int | None = Field(default=1, primary_key=True)
    enabled: bool = False
    private_key: str
    public_key: str
    listen_port: int = 51820
    server_ip: str = "10.8.0.1"
    network_cidr: str = "10.8.0.0/24"
    dns: str | None = None
    endpoint_host: str | None = None  # host/IP pública a la que se conectan los clientes
    client_allowed_ips: str = "192.168.10.0/24"  # redes a las que el cliente enruta vía VPN


class WireguardPeer(SQLModel, table=True):
    """Un cliente VPN. La clave privada se guarda para poder volver a mostrar la
    config/QR más adelante: quien tiene acceso al backend ya controla nftables y
    Suricata, así que no es una superficie de exposición adicional relevante."""

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    enabled: bool = True
    private_key: str
    public_key: str
    address: str  # ej. "10.8.0.2/32"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditLog(SQLModel, table=True):
    """Registro de acciones con efecto sobre el sistema (login, cambios de reglas,
    apply, gestión de Suricata/WireGuard/usuarios). Solo lectura desde la API."""

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), index=True)
    username: str
    action: str = Field(index=True)
    detail: str | None = None
    ok: bool = True
