from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import get_db
from models import User, Resource, ReliefRequest, Delivery
from dependencies import get_current_user
from services import check_and_update_escalations, get_resource_shortages

router = APIRouter(tags=["Dashboard"])
templates = Jinja2Templates(directory="templates")


@router.get("/", response_class=HTMLResponse)
async def root_redirect():
    """Redirect home route to dashboard."""
    return RedirectResponse(url="/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render unified role-based dashboard for Admin and Requester."""
    # Run auto-escalation check for critical requests
    check_and_update_escalations(db)

    # ----------------------------------------------------
    # ADMIN VIEW DATA
    # ----------------------------------------------------
    if current_user.role.upper() == "ADMIN":
        pending_count = db.query(ReliefRequest).filter(ReliefRequest.status == "Pending").count()
        critical_count = db.query(ReliefRequest).filter(
            ReliefRequest.urgency == "Critical",
            ReliefRequest.status.notin_(["Delivered", "Rejected"])
        ).count()
        escalated_count = db.query(ReliefRequest).filter(ReliefRequest.status == "Escalated").count()
        total_resources_available = db.query(func.coalesce(func.sum(Resource.quantity_available), 0)).scalar() or 0
        
        # Calculate shortages
        shortages = get_resource_shortages(db)
        shortage_count = len(shortages)
        delivered_count = db.query(ReliefRequest).filter(ReliefRequest.status == "Delivered").count()

        # Critical and Escalated requests for urgent attention
        critical_requests = db.query(ReliefRequest).filter(
            (ReliefRequest.status == "Escalated") |
            (ReliefRequest.urgency == "Critical")
        ).filter(
            ReliefRequest.status.notin_(["Delivered", "Rejected"])
        ).order_by(
            ReliefRequest.status == "Escalated",  # Escalated first
            ReliefRequest.priority_score.desc(),
            ReliefRequest.created_at.asc()
        ).all()

        # Recent Requests
        recent_requests = db.query(ReliefRequest).order_by(
            ReliefRequest.created_at.desc()
        ).limit(10).all()

        # Recent Deliveries
        recent_deliveries = db.query(Delivery).order_by(
            Delivery.assigned_at.desc()
        ).limit(6).all()

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "current_user": current_user,
                "is_admin": True,
                "stats": {
                    "pending": pending_count,
                    "critical": critical_count,
                    "escalated": escalated_count,
                    "available_resources": total_resources_available,
                    "shortages": shortage_count,
                    "delivered": delivered_count
                },
                "critical_requests": critical_requests,
                "shortages": shortages,
                "recent_requests": recent_requests,
                "recent_deliveries": recent_deliveries
            }
        )

    # ----------------------------------------------------
    # REQUESTER VIEW DATA
    # ----------------------------------------------------
    else:
        my_requests = db.query(ReliefRequest).filter(
            ReliefRequest.requested_by == current_user.id
        ).order_by(ReliefRequest.created_at.desc()).all()

        my_pending = sum(1 for r in my_requests if r.status in ["Pending", "Approved", "Escalated"])
        my_in_transit = sum(1 for r in my_requests if r.status in ["Resource Allocated", "Delivery Assigned", "In Transit"])
        my_delivered = sum(1 for r in my_requests if r.status == "Delivered")

        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "current_user": current_user,
                "is_admin": False,
                "my_requests": my_requests,
                "stats": {
                    "pending": my_pending,
                    "in_transit": my_in_transit,
                    "delivered": my_delivered,
                    "total": len(my_requests)
                }
            }
        )
