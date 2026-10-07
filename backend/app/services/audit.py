"""Registro de auditoría: quién hizo qué. Se llama explícitamente desde las rutas
que cambian estado (reglas, apply, config de Suricata/WireGuard, usuarios, login),
no automáticamente vía middleware, para poder incluir detalle útil por acción."""

from sqlmodel import Session

from app.db.models import AuditLog


def log(session: Session, username: str, action: str, detail: str | None = None, ok: bool = True) -> None:
    session.add(AuditLog(username=username, action=action, detail=detail, ok=ok))
    session.commit()
