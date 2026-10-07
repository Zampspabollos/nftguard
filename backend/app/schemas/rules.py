from pydantic import BaseModel

from app.db.models import Action, Chain, Protocol


class FirewallRuleWrite(BaseModel):
    priority: int = 100
    enabled: bool = True
    chain: Chain = Chain.forward
    action: Action = Action.accept
    protocol: Protocol = Protocol.any

    src_iface: str | None = None
    dst_iface: str | None = None
    src_ip: str | None = None
    dst_ip: str | None = None
    src_port: str | None = None
    dst_port: str | None = None

    rate_limit: str | None = None
    log: bool = False
    inspect_l7: bool = False
    comment: str | None = None


class PortForwardWrite(BaseModel):
    enabled: bool = True
    protocol: Protocol = Protocol.tcp
    wan_port: str
    dst_ip: str
    dst_port: str
    comment: str | None = None


class ApplyResponse(BaseModel):
    ok: bool
    message: str
