from datetime import datetime

from pydantic import BaseModel, ConfigDict


class WireguardConfigWrite(BaseModel):
    enabled: bool
    listen_port: int = 51820
    server_ip: str
    network_cidr: str
    dns: str | None = None
    endpoint_host: str | None = None
    client_allowed_ips: str


class WireguardConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    enabled: bool
    public_key: str
    listen_port: int
    server_ip: str
    network_cidr: str
    dns: str | None
    endpoint_host: str | None
    client_allowed_ips: str


class PeerCreate(BaseModel):
    name: str


class PeerUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None


class PeerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    enabled: bool
    public_key: str
    address: str
    created_at: datetime


class PeerCreateResponse(BaseModel):
    peer: PeerRead
    config: str


class StatusResponse(BaseModel):
    enabled: bool
    active: bool


class CommandResponse(BaseModel):
    ok: bool
    message: str
