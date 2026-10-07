from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin
from app.core.config import settings
from app.db.database import get_session
from app.db.models import FirewallRule, PortForward, User
from app.schemas.rules import ApplyResponse, FirewallRuleWrite, PortForwardWrite
from app.services import audit, suricata_service, wireguard_service
from app.services.nftables_engine import (
    RuleValidationError,
    apply_ruleset_text,
    render_portforward_dnat,
    render_rule,
    render_ruleset,
    validate_ruleset_text,
)

router = APIRouter(prefix="/api/rules", tags=["rules"], dependencies=[Depends(get_current_user)])


def _validate_or_400(fn, obj) -> None:
    try:
        fn(obj)
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("", response_model=list[FirewallRule])
def list_rules(session: Session = Depends(get_session)) -> list[FirewallRule]:
    return list(session.exec(select(FirewallRule).order_by(FirewallRule.priority)).all())


@router.post("", response_model=FirewallRule, dependencies=[Depends(require_admin)])
def create_rule(
    data: FirewallRuleWrite, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> FirewallRule:
    rule = FirewallRule(**data.model_dump())
    _validate_or_400(render_rule, rule)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    audit.log(session, user.username, "rule.create", f"id={rule.id} comment={rule.comment!r}")
    return rule


@router.put("/{rule_id}", response_model=FirewallRule, dependencies=[Depends(require_admin)])
def update_rule(
    rule_id: int,
    data: FirewallRuleWrite,
    session: Session = Depends(get_session),
    user: User = Depends(get_current_user),
) -> FirewallRule:
    rule = session.get(FirewallRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regla no encontrada")
    for key, value in data.model_dump().items():
        setattr(rule, key, value)
    _validate_or_400(render_rule, rule)
    session.add(rule)
    session.commit()
    session.refresh(rule)
    audit.log(session, user.username, "rule.update", f"id={rule.id}")
    return rule


@router.delete("/{rule_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_rule(
    rule_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    rule = session.get(FirewallRule, rule_id)
    if rule is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regla no encontrada")
    session.delete(rule)
    session.commit()
    audit.log(session, user.username, "rule.delete", f"id={rule_id}")


@router.get("/portforwards", response_model=list[PortForward])
def list_portforwards(session: Session = Depends(get_session)) -> list[PortForward]:
    return list(session.exec(select(PortForward)).all())


@router.post("/portforwards", response_model=PortForward, dependencies=[Depends(require_admin)])
def create_portforward(
    data: PortForwardWrite, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> PortForward:
    pf = PortForward(**data.model_dump())
    _validate_or_400(render_portforward_dnat, pf)
    session.add(pf)
    session.commit()
    session.refresh(pf)
    audit.log(session, user.username, "portforward.create", f"id={pf.id} wan_port={pf.wan_port}")
    return pf


@router.delete("/portforwards/{pf_id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[Depends(require_admin)])
def delete_portforward(
    pf_id: int, session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> None:
    pf = session.get(PortForward, pf_id)
    if pf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Regla NAT no encontrada")
    session.delete(pf)
    session.commit()
    audit.log(session, user.username, "portforward.delete", f"id={pf_id}")


def _build_ruleset_text(session: Session) -> str:
    rules = list(session.exec(select(FirewallRule)).all())
    port_forwards = list(session.exec(select(PortForward)).all())
    suricata_config = suricata_service.get_config(session)
    wg_config = wireguard_service.get_config(session)
    try:
        return render_ruleset(
            rules,
            port_forwards,
            suricata_enabled=suricata_config.enabled,
            nfqueue_num=suricata_config.nfqueue_num,
            vpn_enabled=wg_config.enabled,
            wg_iface=settings.wireguard_iface,
            wg_listen_port=wg_config.listen_port,
        )
    except RuleValidationError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc


@router.get("/preview")
def preview_ruleset(session: Session = Depends(get_session)) -> dict:
    return {"ruleset": _build_ruleset_text(session)}


@router.post("/validate", response_model=ApplyResponse)
def validate_rules(session: Session = Depends(get_session)) -> ApplyResponse:
    text = _build_ruleset_text(session)
    result = validate_ruleset_text(text)
    return ApplyResponse(ok=result.ok, message=result.message)


@router.post("/apply", response_model=ApplyResponse, dependencies=[Depends(require_admin)])
def apply_rules(
    session: Session = Depends(get_session), user: User = Depends(get_current_user)
) -> ApplyResponse:
    text = _build_ruleset_text(session)
    result = apply_ruleset_text(text)
    audit.log(session, user.username, "rules.apply", result.message, ok=result.ok)
    if not result.ok:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, result.message)
    return ApplyResponse(ok=result.ok, message=result.message)
