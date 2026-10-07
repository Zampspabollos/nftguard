from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.db.database import get_session
from app.db.models import User
from app.schemas.users import AdminPasswordReset, UserCreate, UserRead
from app.services import audit

router = APIRouter(prefix="/api/users", tags=["users"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[UserRead])
def list_users(session: Session = Depends(get_session)) -> list[User]:
    return list(session.exec(select(User)))


@router.post("", response_model=UserRead, dependencies=[Depends(require_admin)])
def create_user(
    data: UserCreate, session: Session = Depends(get_session), admin: User = Depends(require_admin)
) -> User:
    user = User(username=data.username, password_hash=hash_password(data.password), is_admin=data.is_admin)
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, f"El usuario '{data.username}' ya existe") from exc
    session.refresh(user)
    audit.log(session, admin.username, "user.create", f"usuario={user.username} admin={user.is_admin}")
    return user


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int, session: Session = Depends(get_session), admin: User = Depends(require_admin)
) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if user.id == admin.id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes eliminar tu propio usuario")
    remaining_admins = session.exec(select(User).where(User.is_admin == True, User.id != user.id)).all()  # noqa: E712
    if user.is_admin and not remaining_admins:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes eliminar el último administrador")
    session.delete(user)
    session.commit()
    audit.log(session, admin.username, "user.delete", f"usuario={user.username}")


@router.put("/{user_id}/password", status_code=status.HTTP_204_NO_CONTENT)
def reset_password(
    user_id: int,
    data: AdminPasswordReset,
    session: Session = Depends(get_session),
    admin: User = Depends(require_admin),
) -> None:
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    user.password_hash = hash_password(data.new_password)
    session.add(user)
    session.commit()
    audit.log(session, admin.username, "user.reset_password", f"usuario={user.username}")
