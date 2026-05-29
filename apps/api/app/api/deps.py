from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from jwt import InvalidTokenError
from sqlmodel import Session

from app.core.security import decode_access_token
from app.db.session import get_session
from app.models import User
from app.security.security_context import resolve_user_security_context
from app.security.session_manager import validate_session

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


def get_current_user(
    request: Request,
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session),
) -> User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = decode_access_token(token)
        subject = payload.get("sub")
        user_id = int(subject)
    except (InvalidTokenError, TypeError, ValueError) as exc:
        raise credentials_exception from exc

    user = session.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    try:
        auth_session = validate_session(session, raw_token=token, expected_user_id=user_id)
    except HTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.detail,
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    request.state.auth_session = auth_session
    request.state.security_context = resolve_user_security_context(session, user=user, auth_session=auth_session)

    return user
