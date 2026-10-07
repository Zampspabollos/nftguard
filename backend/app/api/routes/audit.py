from fastapi import APIRouter, Depends
from sqlmodel import Session, select

from app.api.deps import require_admin
from app.db.database import get_session
from app.db.models import AuditLog

router = APIRouter(prefix="/api/audit", tags=["audit"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[AuditLog])
def list_audit(limit: int = 100, session: Session = Depends(get_session)) -> list[AuditLog]:
    limit = min(max(limit, 1), 500)
    return list(
        session.exec(select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(limit))
    )
