from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from models import Delivery, ReliefRequest, User
from dependencies import get_current_user, get_current_admin_user

router = APIRouter(prefix="/deliveries", tags=["Deliveries"])
templates = Jinja2Templates(directory="templates")

DELIVERY_STATUS_CHOICES = ["Assigned", "In Transit", "Delivered"]


@router.get("", response_class=HTMLResponse)
async def list_deliveries(
    request: Request,
    status_filter: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View and track relief deliveries."""
    is_admin = (current_user.role.upper() == "ADMIN")
    query = db.query(Delivery).join(ReliefRequest)

    if not is_admin:
        query = query.filter(ReliefRequest.requested_by == current_user.id)

    if status_filter and status_filter.strip() and status_filter != "All":
        query = query.filter(Delivery.status == status_filter.strip())

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.filter(
            or_(
                Delivery.assigned_to.ilike(search_term),
                Delivery.vehicle_details.ilike(search_term),
                ReliefRequest.location.ilike(search_term)
            )
        )

    deliveries = query.order_by(
        Delivery.status == "In Transit",
        Delivery.status == "Assigned",
        Delivery.assigned_at.desc()
    ).all()

    success_msg = request.query_params.get("success")
    error_msg = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="deliveries.html",
        context={
            "current_user": current_user,
            "is_admin": is_admin,
            "deliveries": deliveries,
            "status_choices": DELIVERY_STATUS_CHOICES,
            "selected_status": status_filter or "All",
            "search_query": q or "",
            "success": success_msg,
            "error": error_msg
        }
    )


@router.post("/{delivery_id}/status")
async def update_delivery_status(
    delivery_id: int,
    new_status: str = Form(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Update delivery progression status (Assigned -> In Transit -> Delivered)."""
    delivery = db.query(Delivery).filter(Delivery.id == delivery_id).first()
    if not delivery:
        return RedirectResponse(url="/deliveries?error=Delivery+not+found.", status_code=status.HTTP_302_FOUND)

    clean_status = new_status.strip()
    if clean_status not in DELIVERY_STATUS_CHOICES:
        return RedirectResponse(url="/deliveries?error=Invalid+delivery+status.", status_code=status.HTTP_302_FOUND)

    now = datetime.now(timezone.utc)
    delivery.status = clean_status
    if clean_status == "Delivered":
        delivery.delivered_at = now
        if delivery.request:
            delivery.request.status = "Delivered"
            delivery.request.updated_at = now
    elif clean_status == "In Transit":
        delivery.delivered_at = None
        if delivery.request:
            delivery.request.status = "In Transit"
            delivery.request.updated_at = now
    elif clean_status == "Assigned":
        delivery.delivered_at = None
        if delivery.request:
            delivery.request.status = "Delivery Assigned"
            delivery.request.updated_at = now

    db.commit()

    return RedirectResponse(
        url=f"/deliveries?success=Delivery+status+updated+to+'{clean_status}'.",
        status_code=status.HTTP_302_FOUND
    )
