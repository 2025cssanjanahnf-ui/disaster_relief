import os
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from dotenv import load_dotenv

load_dotenv()

from database import engine, SessionLocal, Base
from seed import seed_database
from routers.auth import router as auth_router
from routers.dashboard import router as dashboard_router
from routers.resources import router as resources_router
from routers.requests import router as requests_router
from routers.deliveries import router as deliveries_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown lifespan handler."""
    # Ensure database schema is created
    Base.metadata.create_all(bind=engine)
    # Seed initial demo records if database is empty
    with SessionLocal() as session:
        seed_database(session)
    yield


app = FastAPI(
    title="Disaster Relief Resource Management System",
    description="Emergency resource allocation, prioritization, and delivery coordination platform",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static assets
os.makedirs("static/css", exist_ok=True)
os.makedirs("static/js", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

templates = Jinja2Templates(directory="templates")

# Register application routers
app.include_router(auth_router)
app.include_router(dashboard_router)
app.include_router(resources_router)
app.include_router(requests_router)
app.include_router(deliveries_router)


# Global Exception Handlers
@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    """Handle 401 Unauthorized by redirecting web requests to login."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(
            url=f"/login?next={request.url.path}&error=Please+login+to+access+this+page.",
            status_code=status.HTTP_302_FOUND
        )
    return JSONResponse(status_code=401, content={"detail": "Authentication required."})


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    """Handle 403 Forbidden with user-friendly message."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(
            url="/dashboard?error=You+do+not+have+permission+to+perform+this+action.",
            status_code=status.HTTP_302_FOUND
        )
    return JSONResponse(status_code=403, content={"detail": str(exc.detail if hasattr(exc, "detail") else "Access forbidden.")})


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    """Handle 404 Not Found gracefully."""
    accept = request.headers.get("accept", "")
    if "text/html" in accept:
        return RedirectResponse(
            url="/dashboard?error=The+requested+page+was+not+found.",
            status_code=status.HTTP_302_FOUND
        )
    return JSONResponse(status_code=404, content={"detail": "Resource not found."})


if __name__ == "__main__":
    import uvicorn
    import socket

    target_port = int(os.getenv("PORT", "8000"))
    # Check if target port is available, otherwise fallback cleanly
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind(("127.0.0.1", target_port))
    except OSError:
        target_port = 8001

    print(f"Starting Disaster Relief Portal on http://127.0.0.1:{target_port}")
    uvicorn.run("main:app", host="127.0.0.1", port=target_port, reload=True)
