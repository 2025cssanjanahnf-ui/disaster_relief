from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from database import get_db
from models import User
from auth import verify_password, get_password_hash, create_access_token
from dependencies import get_current_user_optional, get_current_user

router = APIRouter(tags=["Authentication"])
templates = Jinja2Templates(directory="templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    next: str = "/dashboard",
    current_user: User = Depends(get_current_user_optional)
):
    """Render the login page. Redirect to dashboard if already logged in."""
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    
    error = request.query_params.get("error")
    message = request.query_params.get("message")
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"error": error, "message": message, "next": next, "current_user": None}
    )


@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form(default="/dashboard"),
    db: Session = Depends(get_db)
):
    """Authenticate user credentials and issue an HTTP-only JWT cookie."""
    username = username.strip()
    user = db.query(User).filter(User.username == username).first()

    if not user or not verify_password(password, user.password_hash):
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Invalid username or password. Please verify your credentials.",
                "username": username,
                "next": next,
                "current_user": None
            },
            status_code=status.HTTP_401_UNAUTHORIZED
        )

    # Issue JWT token
    token = create_access_token(data={"sub": user.username, "role": user.role})

    # Redirect to target dashboard
    redirect_target = next if next and next.startswith("/") else "/dashboard"
    response = RedirectResponse(url=redirect_target, status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400  # 24 hours
    )
    return response


@router.get("/register", response_class=HTMLResponse)
async def register_page(
    request: Request,
    current_user: User = Depends(get_current_user_optional)
):
    """Render the registration page."""
    if current_user:
        return RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    return templates.TemplateResponse(
        request=request,
        name="register.html",
        context={"current_user": None}
    )


@router.post("/register")
async def register_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    role: str = Form(default="REQUESTER"),
    db: Session = Depends(get_db)
):
    """Create a new user account with role."""
    username = username.strip()
    if len(username) < 3:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Username must be at least 3 characters long.", "username": username, "current_user": None},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if len(password) < 6:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Password must be at least 6 characters long.", "username": username, "current_user": None},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if password != confirm_password:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": "Passwords do not match.", "username": username, "current_user": None},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        return templates.TemplateResponse(
            request=request,
            name="register.html",
            context={"error": f"Username '{username}' is already taken. Please choose another.", "username": username, "current_user": None},
            status_code=status.HTTP_400_BAD_REQUEST
        )

    clean_role = "ADMIN" if role.upper() == "ADMIN" else "REQUESTER"
    new_user = User(
        username=username,
        password_hash=get_password_hash(password),
        role=clean_role
    )
    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    # Automatically log the user in
    token = create_access_token(data={"sub": new_user.username, "role": new_user.role})
    response = RedirectResponse(url="/dashboard", status_code=status.HTTP_302_FOUND)
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        samesite="lax",
        max_age=86400
    )
    return response


@router.get("/logout")
@router.post("/logout")
async def logout(request: Request):
    """Log out user by clearing the HTTP-only cookie."""
    response = RedirectResponse(url="/login?message=You+have+been+logged+out+successfully.", status_code=status.HTTP_302_FOUND)
    response.delete_cookie("access_token")
    return response


@router.get("/profile", response_class=HTMLResponse)
async def profile_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View user profile and account details."""
    success_msg = request.query_params.get("success")
    error_msg = request.query_params.get("error")
    return templates.TemplateResponse(
        request=request,
        name="profile.html",
        context={
            "current_user": current_user,
            "success": success_msg,
            "error": error_msg
        }
    )


@router.post("/profile/password")
async def change_password(
    request: Request,
    current_password: str = Form(...),
    new_password: str = Form(...),
    confirm_password: str = Form(...),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Change password for authenticated user."""
    if not verify_password(current_password, current_user.password_hash):
        return RedirectResponse(url="/profile?error=Current+password+is+incorrect.", status_code=status.HTTP_302_FOUND)

    if len(new_password) < 6:
        return RedirectResponse(url="/profile?error=New+password+must+be+at+least+6+characters.", status_code=status.HTTP_302_FOUND)

    if new_password != confirm_password:
        return RedirectResponse(url="/profile?error=New+passwords+do+not+match.", status_code=status.HTTP_302_FOUND)

    current_user.password_hash = get_password_hash(new_password)
    db.commit()
    return RedirectResponse(url="/profile?success=Password+updated+successfully.", status_code=status.HTTP_302_FOUND)
