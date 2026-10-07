from pydantic import BaseModel


class SuricataConfigWrite(BaseModel):
    enabled: bool
    nfqueue_num: int = 100
    home_net: str


class RuleSourceWrite(BaseModel):
    name: str
    url: str | None = None
    enabled: bool = True
    comment: str | None = None


class BlockIpRequest(BaseModel):
    ip: str
    comment: str | None = None


class CommandResponse(BaseModel):
    ok: bool
    message: str


class StatusResponse(BaseModel):
    enabled: bool
    active: bool
