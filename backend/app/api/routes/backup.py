from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app.api.deps import require_admin
from app.db.database import get_session
from app.db.models import User
from app.services import audit, backup_service

router = APIRouter(prefix="/api/backup", tags=["backup"], dependencies=[Depends(require_admin)])


@router.get("")
def export_backup(session: Session = Depends(get_session), admin: User = Depends(require_admin)) -> dict:
    audit.log(session, admin.username, "backup.export")
    return backup_service.export_all(session)


@router.post("/restore", status_code=status.HTTP_204_NO_CONTENT)
def restore_backup(
    data: dict, session: Session = Depends(get_session), admin: User = Depends(require_admin)
) -> None:
    # restore_all borra y recarga la tabla de usuarios (incluido el propio admin
    # autenticado): capturamos el nombre antes de que esa fila quede obsoleta.
    admin_username = admin.username
    try:
        backup_service.restore_all(session, data)
    except backup_service.RestoreError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    audit.log(session, admin_username, "backup.restore", ok=True)
