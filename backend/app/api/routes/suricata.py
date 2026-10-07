from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin
from app.db.database import get_session
from app.db.models import Action, Chain, FirewallRule, Protocol, RuleSource, SuricataConfig, User
from app.schemas.suricata import (
    BlockIpRequest,
    CommandResponse,
    RuleSourceWrite,
    StatusResponse,
    SuricataConfigWrite,
)
from app.services import audit, suricata_service
from app.services.nftables_engine import RuleValidationError, render_rule

router = APIRouter(prefix="/api/suricata", tags=["suricata"], dependencies=[Depends(get_current_user)])


@router.get("/config", response_model=SuricataConfig)
def get_config(session: Session = Depends(get_session)) -> SuricataConfig:
    return suricata_service.get_config(session)


@router.put("/config", response_model=SuricataConfig, dependencies=[Depends(require_admin)])
def update_config(
    data: SuricataConfigWrite, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> SuricataConfig:
    config = suricata_service.get_config(session)
    config.enabled = data.enabled
    config.nfqueue_num = data.nfqueue_num
    config.home_net = data.home_net
    session.add(config)
    session.commit()
    session.refresh(config)
    try:
        suricata_service.write_config(config)
    except OSError as exc:
        raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, f"No se pudo escribir suricata.yaml: {exc}")
    suricata_service.write_systemd_override(config)
    audit.log(session, user.username, "suricata.config", f"enabled={config.enabled} queue={config.nfqueue_num}")
    return config


@router.get("/status", response_model=StatusResponse)
def status_view(session: Session = Depends(get_session)) -> StatusResponse:
    config = suricata_service.get_config(session)
    return StatusResponse(enabled=config.enabled, active=suricata_service.service_is_active())


@router.post("/service/{action}", response_model=CommandResponse, dependencies=[Depends(require_admin)])
def service_action(
    action: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> CommandResponse:
    if action not in ("start", "stop", "restart"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Acción no soportada (start/stop/restart)")
    result = suricata_service.service_action(action)
    audit.log(session, user.username, f"suricata.service.{action}", result.message, ok=result.ok)
    return CommandResponse(ok=result.ok, message=result.message)


@router.get("/sources", response_model=list[RuleSource])
def list_sources(session: Session = Depends(get_session)) -> list[RuleSource]:
    return list(session.exec(select(RuleSource)))


@router.post("/sources", response_model=RuleSource, dependencies=[Depends(require_admin)])
def create_source(
    data: RuleSourceWrite, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> RuleSource:
    source = RuleSource(**data.model_dump())
    session.add(source)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"La fuente '{data.name}' ya existe") from exc
    session.refresh(source)
    audit.log(session, user.username, "suricata.source.create", f"name={source.name}")
    return source


@router.delete("/sources/{source_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_source(
    source_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    source = session.get(RuleSource, source_id)
    if source is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Fuente no encontrada")
    session.delete(source)
    session.commit()
    audit.log(session, user.username, "suricata.source.delete", f"name={source.name}")


@router.get("/sources/catalog", response_model=CommandResponse)
def sources_catalog() -> CommandResponse:
    """Lista las fuentes conocidas por suricata-update (ET Open, abuse.ch, etc.)."""
    result = suricata_service.list_available_sources()
    return CommandResponse(ok=result.ok, message=result.message)


@router.post("/sources/sync", response_model=CommandResponse, dependencies=[Depends(require_admin)])
def sync_sources(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> CommandResponse:
    result = suricata_service.sync_rule_sources(session)
    audit.log(session, user.username, "suricata.sources.sync", result.message, ok=result.ok)
    return CommandResponse(ok=result.ok, message=result.message)


@router.get("/alerts")
def alerts(limit: int = 100) -> list[dict]:
    return suricata_service.read_alerts(limit=min(limit, 500))


@router.post("/block", response_model=FirewallRule, dependencies=[Depends(require_admin)])
def block_ip(
    data: BlockIpRequest, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> FirewallRule:
    rule = FirewallRule(
        chain=Chain.forward,
        action=Action.drop,
        protocol=Protocol.any,
        src_ip=data.ip,
        priority=10,
        comment=data.comment or f"bloqueo manual desde alerta: {data.ip}",
    )
    try:
        render_rule(rule)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.add(rule)
    session.commit()
    session.refresh(rule)
    audit.log(session, user.username, "suricata.block_ip", f"ip={data.ip}")
    return rule
