from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from database import engine, SessionLocal, Base
from models import User, Resource, ReliefRequest, Delivery
from auth import get_password_hash
from services import calculate_priority_score


def seed_database(db: Session):
    """Seed initial demo data if tables are empty."""
    # Check if admin already exists
    if db.query(User).filter(User.username == "admin").first():
        print("Database already contains demo data. Skipping seed.")
        return

    print("Seeding database with demo users, resources, requests, and deliveries...")
    now = datetime.now(timezone.utc)

    # 1. Demo Users
    admin_user = User(
        username="admin",
        password_hash=get_password_hash("admin123"),
        role="ADMIN",
        created_at=now - timedelta(days=2)
    )
    requester_user = User(
        username="requester",
        password_hash=get_password_hash("requester123"),
        role="REQUESTER",
        created_at=now - timedelta(days=2)
    )
    medic_user = User(
        username="field_medic",
        password_hash=get_password_hash("medic123"),
        role="REQUESTER",
        created_at=now - timedelta(days=1)
    )
    db.add_all([admin_user, requester_user, medic_user])
    db.commit()
    db.refresh(admin_user)
    db.refresh(requester_user)
    db.refresh(medic_user)

    # 2. Demo Resources
    res_water = Resource(
        name="Bottled Drinking Water (1L)",
        category="Water",
        quantity_available=450,
        location="Central Warehouse, Sector 4",
        updated_at=now
    )
    res_food = Resource(
        name="High-Energy Food Rations",
        category="Food",
        quantity_available=300,
        location="Central Warehouse, Sector 4",
        updated_at=now
    )
    res_medical = Resource(
        name="Trauma & First Aid Kits",
        category="Medical",
        quantity_available=75,
        location="North Hospital Depot, Sector 12",
        updated_at=now
    )
    res_blankets = Resource(
        name="Thermal Emergency Blankets",
        category="Shelter",
        quantity_available=200,
        location="East Community Center",
        updated_at=now
    )
    res_kits = Resource(
        name="Comprehensive Emergency Survival Kits",
        category="Emergency Supplies",
        quantity_available=60,
        location="Central Warehouse, Sector 4",
        updated_at=now
    )
    res_tablets = Resource(
        name="Water Purification Tablets (Packs)",
        category="Water",
        quantity_available=50,
        location="South Relief Base",
        updated_at=now
    )
    res_antibiotics = Resource(
        name="Emergency Antibiotics & Antiseptics",
        category="Medical",
        quantity_available=30,
        location="North Hospital Depot, Sector 12",
        updated_at=now
    )

    db.add_all([res_water, res_food, res_medical, res_blankets, res_kits, res_tablets, res_antibiotics])
    db.commit()
    for r in [res_water, res_food, res_medical, res_blankets, res_kits, res_tablets, res_antibiotics]:
        db.refresh(r)

    # 3. Demo Requests

    # Request 1: Critical Medical request (45 mins ago -> Escalated state demonstration)
    req1_time = now - timedelta(minutes=45)
    score1 = calculate_priority_score("Critical", "Medical", 40, "Flash flood trauma casualties", req1_time) + 15.0
    req_critical_med = ReliefRequest(
        resource_id=res_medical.id,
        requested_quantity=40,
        location="Field Clinic Sector 9, Flash Flood Zone",
        urgency="Critical",
        description="Mass casualties from flash flood building collapse. Urgent need for trauma dressings and IV saline kits for injured victims.",
        priority_score=score1,
        status="Escalated",
        requested_by=medic_user.id,
        created_at=req1_time,
        updated_at=now
    )

    # Request 2: High Urgency Water Request (Creates a demand of 500 while available is 450 -> Shortage!)
    req2_time = now - timedelta(minutes=20)
    score2 = calculate_priority_score("High", "Water", 550, "Evacuation camp drinking water shortage", req2_time)
    req_water_shortage = ReliefRequest(
        resource_id=res_water.id,
        requested_quantity=550,
        location="Evacuation Camp B, High School Gym",
        urgency="High",
        description="Over 600 displaced families in gym without safe drinking water. High dehydration risk for children and infants.",
        priority_score=score2,
        status="Pending",
        requested_by=requester_user.id,
        created_at=req2_time,
        updated_at=req2_time
    )

    # Request 3: Medium Urgency Food Request
    req3_time = now - timedelta(hours=1)
    score3 = calculate_priority_score("Medium", "Food", 150, "Daily meal rations", req3_time)
    req_food_approved = ReliefRequest(
        resource_id=res_food.id,
        requested_quantity=150,
        location="East Shelter Zone, Community Hall",
        urgency="Medium",
        description="Standard supplemental nutritional meal packs for 150 sheltered individuals.",
        priority_score=score3,
        status="Approved",
        requested_by=requester_user.id,
        created_at=req3_time,
        updated_at=now
    )

    # Request 4: Blankets Request (Allocated & Delivery Assigned in Transit)
    req4_time = now - timedelta(hours=2)
    score4 = calculate_priority_score("High", "Shelter", 80, "Cold wave approaching", req4_time)
    req_blankets_transit = ReliefRequest(
        resource_id=res_blankets.id,
        requested_quantity=80,
        location="North Relief Shelter, Sector 2",
        urgency="High",
        description="Cold wave forecast tonight. 80 thermal blankets needed for displaced seniors and kids.",
        priority_score=score4,
        status="In Transit",
        requested_by=requester_user.id,
        created_at=req4_time,
        updated_at=now
    )

    # Request 5: Emergency Survival Kits (Delivered)
    req5_time = now - timedelta(hours=4)
    score5 = calculate_priority_score("Medium", "Emergency Supplies", 25, "Search and rescue team base", req5_time)
    req_kits_delivered = ReliefRequest(
        resource_id=res_kits.id,
        requested_quantity=25,
        location="Hilltop Rescue Point 3",
        urgency="Medium",
        description="Search and rescue perimeter station equipment.",
        priority_score=score5,
        status="Delivered",
        requested_by=medic_user.id,
        created_at=req5_time,
        updated_at=now - timedelta(minutes=30)
    )

    db.add_all([req_critical_med, req_water_shortage, req_food_approved, req_blankets_transit, req_kits_delivered])
    db.commit()
    for req in [req_critical_med, req_water_shortage, req_food_approved, req_blankets_transit, req_kits_delivered]:
        db.refresh(req)

    # 4. Demo Deliveries
    delivery1 = Delivery(
        request_id=req_blankets_transit.id,
        resource_id=res_blankets.id,
        assigned_to="Driver Suresh Verma (Relief Unit Alpha)",
        vehicle_details="Disaster Van DL-04-1234",
        status="In Transit",
        assigned_at=now - timedelta(hours=1),
        delivered_at=None
    )

    delivery2 = Delivery(
        request_id=req_kits_delivered.id,
        resource_id=res_kits.id,
        assigned_to="Officer Anita Roy (Quick Response)",
        vehicle_details="Rescue Truck HR-26-9011",
        status="Delivered",
        assigned_at=now - timedelta(hours=3),
        delivered_at=now - timedelta(minutes=30)
    )

    db.add_all([delivery1, delivery2])
    db.commit()
    print("Demo database seeding complete!")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as session:
        seed_database(session)
