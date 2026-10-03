from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, Depends, Request, Form, status, HTTPException, Query, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import or_
from database import get_db
from models import ReliefRequest, Resource, User, Delivery
from dependencies import get_current_user, get_current_admin_user
from services import (
    calculate_priority_score,
    check_and_update_escalations,
    find_matching_resources_for_request,
    check_duplicate_request
)

router = APIRouter(prefix="/requests", tags=["Requests"])
templates = Jinja2Templates(directory="templates")

STATUS_CHOICES = [
    "Pending",
    "Approved",
    "Rejected",
    "Resource Allocated",
    "Delivery Assigned",
    "In Transit",
    "Delivered",
    "Escalated"
]

URGENCY_CHOICES = ["Critical", "High", "Medium", "Low"]


@router.get("", response_class=HTMLResponse)
async def list_requests(
    request: Request,
    status_filter: Optional[str] = None,
    urgency_filter: Optional[str] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List relief requests. Admin sees all requests with filters; Requester sees their own."""
    # First trigger escalation check
    check_and_update_escalations(db)

    is_admin = (current_user.role.upper() == "ADMIN")
    query = db.query(ReliefRequest)

    if not is_admin:
        query = query.filter(ReliefRequest.requested_by == current_user.id)

    if status_filter and status_filter.strip() and status_filter != "All":
        query = query.filter(ReliefRequest.status == status_filter.strip())

    if urgency_filter and urgency_filter.strip() and urgency_filter != "All":
        query = query.filter(ReliefRequest.urgency == urgency_filter.strip())

    if q and q.strip():
        search_term = f"%{q.strip()}%"
        query = query.join(Resource).filter(
            or_(
                ReliefRequest.location.ilike(search_term),
                ReliefRequest.description.ilike(search_term),
                Resource.name.ilike(search_term)
            )
        )

    # Sort: Escalated & Critical first, then priority_score descending, then creation date descending
    requests_list = query.order_by(
        ReliefRequest.status == "Escalated",
        ReliefRequest.priority_score.desc(),
        ReliefRequest.created_at.desc()
    ).all()

    success_msg = request.query_params.get("success")
    error_msg = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="requests.html",
        context={
            "current_user": current_user,
            "is_admin": is_admin,
            "requests": requests_list,
            "status_choices": STATUS_CHOICES,
            "urgency_choices": URGENCY_CHOICES,
            "selected_status": status_filter or "All",
            "selected_urgency": urgency_filter or "All",
            "search_query": q or "",
            "success": success_msg,
            "error": error_msg
        }
    )


@router.get("/create", response_class=HTMLResponse)
async def create_request_form(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Render emergency resource request creation form."""
    resources = db.query(Resource).order_by(Resource.category.asc(), Resource.name.asc()).all()
    return templates.TemplateResponse(
        request=request,
        name="request_form.html",
        context={
            "current_user": current_user,
            "resources": resources,
            "urgency_choices": URGENCY_CHOICES
        }
    )


@router.post("/create")
async def create_request_submit(
    request: Request,
    resource_id: int = Form(...),
    requested_quantity: int = Form(...),
    location: str = Form(...),
    urgency: str = Form(...),
    description: Optional[str] = Form(None),
    confirmed_duplicate: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Submit a new emergency relief request."""
    location = location.strip()
    description = (description or "").strip()
    urgency = urgency.strip()

    # Form validation
    if not location:
        resources = db.query(Resource).all()
        return templates.TemplateResponse(
            request=request,
            name="request_form.html",
            context={
                "current_user": current_user,
                "resources": resources,
                "urgency_choices": URGENCY_CHOICES,
                "error": "Affected location is required."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    if requested_quantity <= 0:
        resources = db.query(Resource).all()
        return templates.TemplateResponse(
            request=request,
            name="request_form.html",
            context={
                "current_user": current_user,
                "resources": resources,
                "urgency_choices": URGENCY_CHOICES,
                "error": "Requested quantity must be greater than zero."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    target_res = db.query(Resource).filter(Resource.id == resource_id).first()
    if not target_res:
        resources = db.query(Resource).all()
        return templates.TemplateResponse(
            request=request,
            name="request_form.html",
            context={
                "current_user": current_user,
                "resources": resources,
                "urgency_choices": URGENCY_CHOICES,
                "error": "Selected resource was not found."
            },
            status_code=status.HTTP_400_BAD_REQUEST
        )

    # Duplicate detection check if user hasn't explicitly clicked confirm
    if not confirmed_duplicate:
        dup = check_duplicate_request(db, resource_id, location)
        if dup:
            resources = db.query(Resource).all()
            return templates.TemplateResponse(
                request=request,
                name="request_form.html",
                context={
                    "current_user": current_user,
                    "resources": resources,
                    "urgency_choices": URGENCY_CHOICES,
                    "duplicate_warning": f"A similar active request for '{target_res.name}' at '{dup.location}' already exists (Status: {dup.status}). Please verify before submitting.",
                    "form_data": {
                        "resource_id": resource_id,
                        "requested_quantity": requested_quantity,
                        "location": location,
                        "urgency": urgency,
                        "description": description
                    }
                },
                status_code=status.HTTP_200_OK
            )

    # Compute rule-based priority score
    now = datetime.now(timezone.utc)
    score = calculate_priority_score(
        urgency=urgency,
        category=target_res.category,
        requested_quantity=requested_quantity,
        description=description,
        created_at=now
    )

    new_request = ReliefRequest(
        resource_id=resource_id,
        requested_quantity=requested_quantity,
        location=location,
        urgency=urgency,
        description=description,
        priority_score=score,
        status="Pending",
        requested_by=current_user.id,
        created_at=now,
        updated_at=now
    )
    db.add(new_request)
    db.commit()
    db.refresh(new_request)

    return RedirectResponse(
        url=f"/requests/{new_request.id}?success=Emergency+request+submitted+successfully.",
        status_code=status.HTTP_302_FOUND
    )


@router.get("/check-duplicate")
async def api_check_duplicate(
    resource_id: int = Query(...),
    location: str = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """API endpoint to check for similar pending requests before submission."""
    dup = check_duplicate_request(db, resource_id, location)
    if dup:
        return {
            "exists": True,
            "message": f"A similar active request for this resource at '{dup.location}' already exists (Status: {dup.status}). Please verify before submitting.",
            "request_id": dup.id,
            "status": dup.status,
            "created_at": dup.created_at.isoformat()
        }
    return {"exists": False}


@router.post("/api/sync")
async def api_sync_offline_requests(
    payload: Dict[str, Any] = Body(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Synchronize requests saved in browser localStorage when connection is restored.
    Payload: { requests: [ { resource_id, requested_quantity, location, urgency, description } ] }
    """
    items = payload.get("requests", [])
    if not items:
        return {"synced_count": 0, "message": "No offline requests to synchronize."}

    synced_count = 0
    now = datetime.now(timezone.utc)

    for item in items:
        res_id = int(item.get("resource_id", 0))
        qty = int(item.get("requested_quantity", 0))
        loc = (item.get("location") or "").strip()
        urg = item.get("urgency", "Medium").strip()
        desc = (item.get("description") or "").strip()

        if qty <= 0 or not loc:
            continue

        res = db.query(Resource).filter(Resource.id == res_id).first()
        if not res:
            continue

        score = calculate_priority_score(urg, res.category, qty, desc, now)
        req_obj = ReliefRequest(
            resource_id=res_id,
            requested_quantity=qty,
            location=loc,
            urgency=urg,
            description=desc,
            priority_score=score,
            status="Pending",
            requested_by=current_user.id,
            created_at=now,
            updated_at=now
        )
        db.add(req_obj)
        synced_count += 1

    if synced_count > 0:
        db.commit()

    return {
        "synced_count": synced_count,
        "message": f"Successfully synchronized {synced_count} offline request(s) with the server."
    }


@router.get("/{request_id}", response_class=HTMLResponse)
async def request_detail(
    request_id: int,
    request: Request,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """View complete request details, status progression, matching stock, and action controls."""
    relief_req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not relief_req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    is_admin = (current_user.role.upper() == "ADMIN")
    # Requester can only view their own requests
    if not is_admin and relief_req.requested_by != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access forbidden.")

    # Find matching resources with stock
    matching_resources = find_matching_resources_for_request(db, relief_req)

    success_msg = request.query_params.get("success")
    error_msg = request.query_params.get("error")

    return templates.TemplateResponse(
        request=request,
        name="request_detail.html",
        context={
            "current_user": current_user,
            "is_admin": is_admin,
            "relief_request": relief_req,
            "matching_resources": matching_resources,
            "success": success_msg,
            "error": error_msg
        }
    )


@router.post("/{request_id}/approve")
async def approve_request(
    request_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Admin approves a pending or escalated request."""
    req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    if req.status not in ["Pending", "Escalated"]:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Only+Pending+or+Escalated+requests+can+be+approved.",
            status_code=status.HTTP_302_FOUND
        )

    req.status = "Approved"
    req.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/requests/{request_id}?success=Request+approved+successfully.+Next+step:+Allocate+Resource.",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/{request_id}/reject")
async def reject_request(
    request_id: int,
    reason: Optional[str] = Form(None),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Admin rejects a request."""
    req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    if req.status in ["Delivered", "In Transit"]:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Cannot+reject+a+request+already+in+transit+or+delivered.",
            status_code=status.HTTP_302_FOUND
        )

    req.status = "Rejected"
    if reason:
        clean_reason = reason.strip()
        req.description = f"{req.description or ''}\n[Rejection Note]: {clean_reason}".strip()
    req.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/requests/{request_id}?success=Request+has+been+rejected.",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/{request_id}/allocate")
async def allocate_resource(
    request_id: int,
    allocated_resource_id: int = Form(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """
    Allocate resource from selected inventory depot.
    Verifies stock availability and deducts quantity_available.
    """
    req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    if req.status not in ["Pending", "Approved", "Escalated"]:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Cannot+allocate+resource+for+request+in+status+'{req.status}'.",
            status_code=status.HTTP_302_FOUND
        )

    resource = db.query(Resource).filter(Resource.id == allocated_resource_id).first()
    if not resource:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Selected+inventory+resource+not+found.",
            status_code=status.HTTP_302_FOUND
        )

    # Check sufficient stock
    if resource.quantity_available < req.requested_quantity:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Insufficient+stock+available.+Depot+has+{resource.quantity_available}+units,+but+{req.requested_quantity}+units+were+requested.",
            status_code=status.HTTP_302_FOUND
        )

    # Deduct quantity from warehouse inventory
    resource.quantity_available -= req.requested_quantity
    resource.updated_at = datetime.now(timezone.utc)

    # Update request
    req.resource_id = resource.id
    req.status = "Resource Allocated"
    req.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/requests/{request_id}?success=Allocated+{req.requested_quantity}+units+from+{resource.name}+({resource.location}).+Next+step:+Assign+Delivery.",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/{request_id}/assign-delivery")
async def assign_delivery(
    request_id: int,
    assigned_to: str = Form(...),
    vehicle_details: str = Form(...),
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Assign delivery personnel and vehicle details for allocated resource."""
    req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    if req.status != "Resource Allocated":
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Resource+must+be+allocated+before+assigning+delivery.",
            status_code=status.HTTP_302_FOUND
        )

    assigned_to = assigned_to.strip()
    vehicle_details = vehicle_details.strip()

    if not assigned_to or not vehicle_details:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Personnel+name+and+vehicle+details+are+both+required.",
            status_code=status.HTTP_302_FOUND
        )

    # Create delivery record
    now = datetime.now(timezone.utc)
    new_delivery = Delivery(
        request_id=req.id,
        resource_id=req.resource_id,
        assigned_to=assigned_to,
        vehicle_details=vehicle_details,
        status="Assigned",
        assigned_at=now
    )
    db.add(new_delivery)

    req.status = "Delivery Assigned"
    req.updated_at = now
    db.commit()

    return RedirectResponse(
        url=f"/requests/{request_id}?success=Delivery+assigned+to+{assigned_to}+({vehicle_details}).",
        status_code=status.HTTP_302_FOUND
    )


@router.post("/{request_id}/escalate")
async def manual_escalate(
    request_id: int,
    current_user: User = Depends(get_current_admin_user),
    db: Session = Depends(get_db)
):
    """Manually escalate an unattended or high-risk emergency request."""
    req = db.query(ReliefRequest).filter(ReliefRequest.id == request_id).first()
    if not req:
        return RedirectResponse(url="/requests?error=Request+not+found.", status_code=status.HTTP_302_FOUND)

    if req.status in ["Delivered", "Rejected"]:
        return RedirectResponse(
            url=f"/requests/{request_id}?error=Cannot+escalate+delivered+or+rejected+requests.",
            status_code=status.HTTP_302_FOUND
        )

    req.status = "Escalated"
    req.priority_score += 15.0
    req.updated_at = datetime.now(timezone.utc)
    db.commit()

    return RedirectResponse(
        url=f"/requests/{request_id}?success=Request+escalated+to+top+priority.",
        status_code=status.HTTP_302_FOUND
    )
