from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin
from app.db.database import get_session
from app.db.models import User, WireguardPeer
from app.schemas.wireguard import (
    CommandResponse,
    PeerCreate,
    PeerCreateResponse,
    PeerRead,
    PeerUpdate,
    StatusResponse,
    WireguardConfigRead,
    WireguardConfigWrite,
)
from app.services import audit, wireguard_service
from app.services.wireguard_service import WireguardValidationError

router = APIRouter(prefix="/api/wireguard", tags=["wireguard"], dependencies=[Depends(get_current_user)])


def _apply_or_warn(session: Session) -> str | None:
    """Reescribe wg0.conf y sincroniza. No falla la request si esto no funciona
    (p. ej. wg no instalado): la BD ya quedó consistente, solo avisamos."""
    result = wireguard_service.apply_changes(session)
    return None if result.ok else result.message


@router.get("/config", response_model=WireguardConfigRead)
def get_config(session: Session = Depends(get_session)) -> WireguardConfigRead:
    return wireguard_service.get_config(session)


@router.put("/config", response_model=WireguardConfigRead, dependencies=[Depends(require_admin)])
def update_config(
    data: WireguardConfigWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WireguardConfigRead:
    config = wireguard_service.get_config(session)
    for key, value in data.model_dump().items():
        setattr(config, key, value)
    try:
        wireguard_service.validate_config(config)
    except WireguardValidationError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    session.add(config)
    session.commit()
    session.refresh(config)
    _apply_or_warn(session)
    audit.log(session, user.username, "wireguard.config", f"enabled={config.enabled} port={config.listen_port}")
    return config


@router.get("/status", response_model=StatusResponse)
def status_view(session: Session = Depends(get_session)) -> StatusResponse:
    config = wireguard_service.get_config(session)
    return StatusResponse(enabled=config.enabled, active=wireguard_service.service_is_active())


@router.post("/service/{action}", response_model=CommandResponse, dependencies=[Depends(require_admin)])
def service_action(
    action: str, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> CommandResponse:
    if action not in ("start", "stop", "restart"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Acción no soportada (start/stop/restart)")
    result = wireguard_service.service_action(action)
    audit.log(session, user.username, f"wireguard.service.{action}", result.message, ok=result.ok)
    return CommandResponse(ok=result.ok, message=result.message)


@router.get("/peers", response_model=list[PeerRead])
def list_peers(session: Session = Depends(get_session)) -> list[WireguardPeer]:
    return list(session.exec(select(WireguardPeer)))


@router.post("/peers", response_model=PeerCreateResponse, dependencies=[Depends(require_admin)])
def create_peer(
    data: PeerCreate, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> PeerCreateResponse:
    if not data.name.strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "El peer necesita un nombre")
    try:
        peer = wireguard_service.create_peer(session, data.name.strip())
    except WireguardValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    warning = _apply_or_warn(session)
    config = wireguard_service.get_config(session)
    try:
        conf_text = wireguard_service.render_peer_conf(config, peer)
    except WireguardValidationError as exc:
        conf_text = f"# {exc}"
    message = conf_text if not warning else f"{conf_text}\n# aviso: {warning}"
    audit.log(session, user.username, "wireguard.peer.create", f"name={peer.name} addr={peer.address}")
    return PeerCreateResponse(peer=peer, config=message)


@router.put("/peers/{peer_id}", response_model=PeerRead, dependencies=[Depends(require_admin)])
def update_peer(
    peer_id: int,
    data: PeerUpdate,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> WireguardPeer:
    peer = session.get(WireguardPeer, peer_id)
    if peer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peer no encontrado")
    if data.name is not None:
        peer.name = data.name
    if data.enabled is not None:
        peer.enabled = data.enabled
    session.add(peer)
    session.commit()
    session.refresh(peer)
    _apply_or_warn(session)
    audit.log(session, user.username, "wireguard.peer.update", f"id={peer_id}")
    return peer


@router.delete("/peers/{peer_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_peer(
    peer_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    peer = session.get(WireguardPeer, peer_id)
    if peer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peer no encontrado")
    session.delete(peer)
    session.commit()
    _apply_or_warn(session)
    audit.log(session, user.username, "wireguard.peer.delete", f"id={peer_id}")


@router.get("/peers/{peer_id}/config", dependencies=[Depends(require_admin)])
def peer_config(peer_id: int, session: Session = Depends(get_session)) -> dict:
    peer = session.get(WireguardPeer, peer_id)
    if peer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peer no encontrado")
    config = wireguard_service.get_config(session)
    try:
        return {"config": wireguard_service.render_peer_conf(config, peer)}
    except WireguardValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/peers/{peer_id}/qrcode", dependencies=[Depends(require_admin)])
def peer_qrcode(peer_id: int, session: Session = Depends(get_session)) -> Response:
    peer = session.get(WireguardPeer, peer_id)
    if peer is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Peer no encontrado")
    config = wireguard_service.get_config(session)
    try:
        png = wireguard_service.peer_qrcode_png(config, peer)
    except WireguardValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    return Response(content=png, media_type="image/png")
