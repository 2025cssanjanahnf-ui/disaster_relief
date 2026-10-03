import os
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import func
from models import ReliefRequest, Resource, Delivery, User

ESCALATION_TIMEOUT_MINUTES = int(os.getenv("ESCALATION_TIMEOUT_MINUTES", "30"))


def calculate_priority_score(
    urgency: str,
    category: str,
    requested_quantity: int,
    description: Optional[str] = None,
    created_at: Optional[datetime] = None
) -> float:
    """
    Simple rule-based priority evaluation.
    Rule logic:
    - Urgency level base score
    - Medical/Emergency category bonus
    - Scale of requested quantity
    - Critical medical special multiplier (highest priority)
    - Vulnerable populations / emergency keywords in description
    - Waiting time elapsed bonus (+1 point per 10 mins elapsed)
    """
    score = 0.0

    # 1. Urgency Base Score
    urgency_lower = (urgency or "").strip().lower()
    if urgency_lower == "critical":
        score += 50.0
    elif urgency_lower == "high":
        score += 30.0
    elif urgency_lower == "medium":
        score += 15.0
    else:  # low
        score += 5.0

    # 2. Category Modifier
    category_lower = (category or "").strip().lower()
    if "medical" in category_lower or "emergency" in category_lower:
        score += 30.0
    elif "water" in category_lower or "food" in category_lower:
        score += 20.0
    elif "shelter" in category_lower:
        score += 15.0
    elif "clothing" in category_lower:
        score += 5.0
    else:
        score += 10.0

    # 3. Critical Medical Bonus (Guarantees Critical Medical is top priority)
    if urgency_lower == "critical" and ("medical" in category_lower or "emergency" in category_lower):
        score += 25.0

    # 4. Quantity Scale Modifier
    if requested_quantity >= 500:
        score += 15.0
    elif requested_quantity >= 100:
        score += 10.0
    elif requested_quantity >= 50:
        score += 5.0

    # 5. Keywords for vulnerable populations / severe conditions
    if description:
        desc_lower = description.lower()
        urgent_keywords = ["infant", "child", "children", "elderly", "trauma", "severe", "injured", "outbreak", "casualty", "pregnant", "perishing"]
        for kw in urgent_keywords:
            if kw in desc_lower:
                score += 5.0
                break

    # 6. Waiting Time Modifier
    if created_at:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        elapsed_minutes = max(0, int((now - created_at).total_seconds() // 60))
        # Add 1 point per 15 minutes of waiting time (capped at 25 points)
        waiting_bonus = min(25.0, (elapsed_minutes / 15.0) * 1.0)
        score += waiting_bonus

    return round(score, 1)


def check_and_update_escalations(db: Session) -> int:
    """
    Checks for critical requests that remain unassigned/unattended for longer
    than ESCALATION_TIMEOUT_MINUTES. Marks them as 'Escalated' and updates score.
    Returns count of updated requests.
    """
    now = datetime.now(timezone.utc)
    candidates = db.query(ReliefRequest).filter(
        ReliefRequest.urgency == "Critical",
        ReliefRequest.status.in_(["Pending", "Approved"])
    ).all()

    escalated_count = 0
    for req in candidates:
        created = req.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        elapsed_minutes = (now - created).total_seconds() // 60
        if elapsed_minutes >= ESCALATION_TIMEOUT_MINUTES:
            req.status = "Escalated"
            req.updated_at = now
            # Recalculate priority with waiting time and escalation boost
            req.priority_score = calculate_priority_score(
                req.urgency,
                req.resource.category if req.resource else "General",
                req.requested_quantity,
                req.description,
                req.created_at
            ) + 15.0  # escalation urgency bonus
            escalated_count += 1

    if escalated_count > 0:
        db.commit()

    return escalated_count


def get_resource_shortages(db: Session) -> List[Dict[str, Any]]:
    """
    Calculates expected demand and shortage for each resource inventory.
    Expected Demand = sum of requested quantities for pending, approved, or escalated requests.
    Shortage = Expected Demand - Available Quantity
    """
    resources = db.query(Resource).all()
    shortages = []

    for res in resources:
        # Sum quantities for active unmet requests
        pending_demand = db.query(func.coalesce(func.sum(ReliefRequest.requested_quantity), 0)).filter(
            ReliefRequest.resource_id == res.id,
            ReliefRequest.status.in_(["Pending", "Approved", "Escalated"])
        ).scalar() or 0

        shortage = pending_demand - res.quantity_available
        if shortage > 0:
            shortages.append({
                "resource_id": res.id,
                "resource_name": res.name,
                "category": res.category,
                "location": res.location,
                "available_quantity": res.quantity_available,
                "expected_demand": pending_demand,
                "shortage": shortage,
                "alert_message": f"{res.name} shortage: {shortage} units at {res.location}"
            })

    # Sort descending by largest shortage
    shortages.sort(key=lambda s: s["shortage"], reverse=True)
    return shortages


def find_matching_resources_for_request(db: Session, request: ReliefRequest) -> List[Dict[str, Any]]:
    """
    Finds and ranks resources in stock that can satisfy the request.
    Ranking criteria:
    1. Exact same resource type / name or category
    2. Location suitability (matching location first)
    3. Stock sufficiency (quantity_available >= requested_quantity)
    """
    target_res = request.resource
    if not target_res:
        return []

    # Find resources with same name or same category
    candidates = db.query(Resource).filter(
        (Resource.name.ilike(f"%{target_res.name}%")) |
        (Resource.category == target_res.category)
    ).all()

    results = []
    req_loc_lower = (request.location or "").lower()

    for cand in candidates:
        is_same_name = (cand.name.lower() == target_res.name.lower())
        cand_loc_lower = cand.location.lower()
        is_location_match = (
            req_loc_lower in cand_loc_lower or
            cand_loc_lower in req_loc_lower or
            any(w in cand_loc_lower for w in req_loc_lower.split() if len(w) > 3)
        )
        has_sufficient_stock = (cand.quantity_available >= request.requested_quantity)

        # Calculate a suitability score
        match_score = 0
        if is_same_name:
            match_score += 50
        else:
            match_score += 20  # same category alternative

        if is_location_match:
            match_score += 30  # proximity bonus

        if has_sufficient_stock:
            match_score += 20
        elif cand.quantity_available > 0:
            match_score += 5

        results.append({
            "resource": cand,
            "is_same_name": is_same_name,
            "is_location_match": is_location_match,
            "has_sufficient_stock": has_sufficient_stock,
            "match_score": match_score
        })

    # Sort candidates by suitability match score descending
    results.sort(key=lambda x: x["match_score"], reverse=True)
    return results


def check_duplicate_request(db: Session, resource_id: int, location: str) -> Optional[ReliefRequest]:
    """
    Checks if a pending, approved, or escalated request for the same resource
    at the same/similar location exists.
    """
    clean_loc = (location or "").strip().lower()
    active_requests = db.query(ReliefRequest).filter(
        ReliefRequest.resource_id == resource_id,
        ReliefRequest.status.in_(["Pending", "Approved", "Escalated"])
    ).all()

    for req in active_requests:
        req_loc = (req.location or "").strip().lower()
        if clean_loc == req_loc or clean_loc in req_loc or req_loc in clean_loc:
            return req
    return None
