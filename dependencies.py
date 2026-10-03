from typing import Optional
from fastapi import Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import decode_access_token


def get_token_from_request(request: Request) -> Optional[str]:
    """Retrieve JWT token from HTTP-only cookie or Authorization header."""
    # 1. Check HTTP-only cookie first
    token = request.cookies.get("access_token")
    if token:
        # Strip 'Bearer ' if present
        if token.startswith("Bearer "):
            token = token[7:]
        return token

    # 2. Check Authorization Header as fallback (useful for API/testing)
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header[7:]

    return None


def get_current_user_optional(
    request: Request,
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Return the current logged-in user if token is valid, else None."""
    token = get_token_from_request(request)
    if not token:
        return None

    payload = decode_access_token(token)
    if not payload:
        return None

    username = payload.get("sub")
    if not username:
        return None

    user = db.query(User).filter(User.username == username).first()
    return user


def get_current_user(
    request: Request,
    db: Session = Depends(get_db)
) -> User:
    """Ensure user is authenticated; if not, raise 401 or redirect to login."""
    user = get_current_user_optional(request, db)
    if not user:
        # Redirect to login for non-API web page requests
        is_api = request.url.path.startswith("/api") or "/api/" in request.url.path
        if not is_api and request.method == "GET":
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": f"/login?next={request.url.path}"}
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required. Please login."
        )
    return user


def get_current_admin_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """Ensure authenticated user has ADMIN role."""
    if current_user.role.upper() != "ADMIN":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access forbidden: Admin authorization required."
        )
    return current_user
