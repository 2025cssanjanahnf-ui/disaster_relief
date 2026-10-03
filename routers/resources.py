from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from models import Resource, User, ReliefRequest
from dependencies import get_current_user, get_current_admin_user
from services import get_resource_shortages

router = APIRouter(prefix="/resources", tags=["Resources"])
templates = Jinja2Templates(directory="templates")

RESOURCE_CATEGORIES = [
    "Water",
    "Food",
    "Medical",
    "Shelter",
    "Clothing",
    "Emergency Supplies"
]


@router.get("", response_class=HTMLResponse)
async def list_resources(
    request: Request,
    q: Optional[str] = None,
    category: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List inventory resources with search, category filtering, and shortage indicators."""
    query = db.query(Resource)

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Resource.name.ilike(search_term),
                Resource.location.ilike(search_term)
            )
        )

    if category and category.strip() and category != "All":
        query = query.filter(Resource.category == category.strip())

    resources = query.order_by(Resource.category.asc(), Resource.name.asc()).all()

    # Get resource shortages map: resource_id -> shortage dict
    shortages_list = get_resource_shortages(db)
    shortages_map = {s["resource_id"]: s for s in shortages_list}

    success_msg = request.query_params.get("success")
    error_msg = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="resources.html",
        context={
            "current_user": current_user,
            "resources": resources,
            "categories": RESOURCE_CATEGORIES,
            "selected_category": category or "All",
            "search_query": q or "",
            "shortages_map": shortages_map,
            "success": success_msg,
            "error": error_msg
        }
    )


@router.get("/create", response_class=HTMLResponse)
async def create_resource_form(
    request: Request,
    current_user: User = Depends(get_current_admin_user)
):
    """Render form to register new emergency relief resources."""
    return templates.TemplateResponse(
        request=request,
        name="resource_form.html",
        context={
            "current_user": current_user,
            "categories": RESOURCE_CATEGORIES,
            "is_edit": False,
            "resource": None
        }
    )


@router.post("/create")
async def create_resource_submit(
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    quantity_available: int = Form(...),
    location: str = Form(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Create new resource in inventory."""
    name = name.strip()
    category = category.strip()
    location = location.strip()

    if not name or not location:
        return templates.TemplateResponse(
            request=request,
            name="resource_form.html",
            context={
                "current_user": current_user,
                "categories": RESOURCE_CATEGORIES,
                "is_edit": False,
                "resource": None,
                "error": "Resource name and storage location are required."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if quantity_available < 0:
        return templates.TemplateResponse(
            request=request,
            name="resource_form.html",
            context={
                "current_user": current_user,
                "categories": RESOURCE_CATEGORIES,
                "is_edit": False,
                "resource": None,
                "error": "Available quantity cannot be negative."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    new_resource = Resource(
        name=name,
        category=category,
        quantity_available=quantity_available,
        location=location
    )
    db.add(new_resource)
    db.commit()
    db.refresh(new_resource)

    return RedirectResponse(
        url="/resources?success=Resource+added+successfully+to+inventory.",
        status_code=status.HTTP_302_FOUND
    )


@router.get("/{resource_id}/edit", response_class=HTMLResponse)
async def edit_resource_form(
    resource_id: int,
    request: Request,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Render form to update existing resource."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        return RedirectResponse(
            url="/resources?error=Resource+not+found.",
            status_code=status.HTTP_302_FOUND
        )

    return templates.TemplateResponse(
        request=request,
        name="resource_form.html",
        context={
            "current_user": current_user,
            "categories": RESOURCE_CATEGORIES,
            "is_edit": True,
            "resource": resource
        }
    )


@router.post("/{resource_id}/edit")
async def edit_resource_submit(
    resource_id: int,
    request: Request,
    name: str = Form(...),
    category: str = Form(...),
    quantity_available: int = Form(...),
    location: str = Form(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update existing resource."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        return RedirectResponse(
            url="/resources?error=Resource+not+found.",
            status_code=status.HTTP_302_FOUND
        )

    if quantity_available < 0:
        return templates.TemplateResponse(
            request=request,
            name="resource_form.html",
            context={
                "current_user": current_user,
                "categories": RESOURCE_CATEGORIES,
                "is_edit": True,
                "resource": resource,
                "error": "Quantity cannot be negative."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    resource.name = name.strip()
    resource.category = category.strip()
    resource.quantity_available = quantity_available
    resource.location = location.strip()
    db.commit()

    return RedirectResponse(
        url="/resources?success=Resource+inventory+updated+successfully.",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/{resource_id}/delete")
async def delete_resource(
    resource_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Delete a resource if it has no associated active requests or deliveries."""
    resource = db.query(Resource).filter(Resource.id == resource_id).first()
    if not resource:
        return RedirectResponse(
            url="/resources?error=Resource+not+found.",
            status_code=status.HTTP_302_FOUND
        )

    # Check references
    linked_requests = db.query(ReliefRequest).filter(ReliefRequest.resource_id == resource_id).count()
    if linked_requests > 0:
        return RedirectResponse(
            url=f"/resources?error=Cannot+delete+resource+linked+to+{linked_requests}+request(s).",
            status_code=status.HTTP_302_FOUND
        )

    db.delete(resource)
    db.commit()
    return RedirectResponse(
        url="/resources?success=Resource+deleted+successfully.",
        status_code=status.HTTP_302_FOUND
    )


@router.get("/api/all")
async def api_get_all_resources(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """JSON API endpoint returning list of available resources for forms and dynamic matching."""
    resources = db.query(Resource).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "category": r.category,
            "quantity_available": r.quantity_available,
            "location": r.location
        }
        for r in resources
    ]
