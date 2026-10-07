from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlmodel import Session, select

from app.api.deps import get_current_user
from app.core.rate_limit import clear as clear_failures, is_locked_out, register_failure
from app.core.security import create_access_token, hash_password, verify_password
from app.db.database import get_session
from app.db.models import User
from app.schemas.auth import SetupRequest, Token
from app.schemas.users import SelfPasswordChange
from app.services import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "unknown"


@router.get("/needs-setup")
def needs_setup(session: Session = Depends(get_session)) -> dict:
    user_exists = session.exec(select(User)).first() is not None
    return {"needs_setup": not user_exists}


@router.post("/setup", response_model=Token)
def setup(data: SetupRequest, session: Session = Depends(get_session)) -> Token:
    if session.exec(select(User)).first() is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe un usuario administrador")
    user = User(username=data.username, password_hash=hash_password(data.password), is_admin=True)
    session.add(user)
    session.commit()
    audit.log(session, user.username, "auth.setup", "primer usuario administrador creado")
    return Token(access_token=create_access_token(user.username))


@router.post("/login", response_model=Token)
def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session),
) -> Token:
    client_ip = _client_ip(request)
    locked, retry_after = is_locked_out(client_ip)
    if locked:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Demasiados intentos fallidos desde esta IP. Reintenta en {retry_after}s.",
        )

    user = session.exec(select(User).where(User.username == form_data.username)).first()
    if user is None or not verify_password(form_data.password, user.password_hash):
        register_failure(client_ip)
        audit.log(session, form_data.username, "auth.login", f"ip={client_ip}", ok=False)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Usuario o contraseña incorrectos")

    clear_failures(client_ip)
    audit.log(session, user.username, "auth.login", f"ip={client_ip}", ok=True)
    return Token(access_token=create_access_token(user.username))


@router.get("/me")
def me(user: User = Depends(get_current_user)) -> dict:
    return {"username": user.username, "is_admin": user.is_admin}


@router.put("/password", status_code=status.HTTP_204_NO_CONTENT)
def change_own_password(
    data: SelfPasswordChange,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> None:
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Contraseña actual incorrecta")
    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()
    audit.log(session, user.username, "auth.change_password")
