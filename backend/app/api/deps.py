from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlmodel import Session, select

from app.core.security import decode_access_token
from app.db.database import get_session
from app.db.models import User

_oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def get_current_user(
    token: str = Depends(_oauth2_scheme), session: Session = Depends(get_session)
) -> User:
    username = decode_access_token(token)
    if username is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido o expirado")
    user = session.exec(select(User).where(User.username == username)).first()
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario no encontrado")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Para endpoints que cambian estado (reglas, apply, config de Suricata/
    WireGuard, gestión de usuarios). Los usuarios de solo lectura pueden ver todo
    pero no modificar nada."""
    if not user.is_admin:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Se requiere rol de administrador")
    return user
