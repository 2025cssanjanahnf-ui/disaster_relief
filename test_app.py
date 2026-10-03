import sys
from fastapi.testclient import TestClient
from main import app
from database import SessionLocal
from models import User, Resource, ReliefRequest, Delivery

def run_tests():
    print("========================================")
    print("RUNNING DISASTER RELIEF SYSTEM TESTS")
    print("========================================")

    client = TestClient(app)

    # 1. Test Unauthenticated Access Redirect
    res = client.get("/dashboard", follow_redirects=False)
    assert res.status_code in [302, 307], f"Expected redirect, got {res.status_code}"
    print("[PASS] 1. Unauthenticated dashboard access redirects to /login")

    # 2. Test Login as Admin
    admin_login = client.post("/login", data={"username": "admin", "password": "admin123"}, follow_redirects=False)
    assert admin_login.status_code == 302, f"Expected 302 on login, got {admin_login.status_code}"
    assert "access_token" in admin_login.cookies, "Expected access_token cookie to be set"
    admin_cookies = admin_login.cookies
    print("[PASS] 2. Admin login successful and HTTP-only cookie issued")

    # 3. Test Admin Dashboard with Token
    dash_res = client.get("/dashboard", cookies=admin_cookies)
    assert dash_res.status_code == 200, f"Expected 200, got {dash_res.status_code}"
    assert "Disaster Relief Operations Dashboard" in dash_res.text
    assert "Pending Requests" in dash_res.text
    assert "Resource Shortage Alerts" in dash_res.text
    print("[PASS] 3. Admin dashboard renders with metrics and shortage alerts")

    # 4. Test Login as Requester
    req_login = client.post("/login", data={"username": "requester", "password": "requester123"}, follow_redirects=False)
    assert req_login.status_code == 302
    req_cookies = req_login.cookies
    req_dash = client.get("/dashboard", cookies=req_cookies)
    assert req_dash.status_code == 200
    assert "Relief Center Dashboard" in req_dash.text
    assert "Create Emergency Request" in req_dash.text
    print("[PASS] 4. Requester login and dashboard display verified")

    # 5. Test Duplicate Detection API
    db = SessionLocal()
    water_res = db.query(Resource).filter(Resource.name.like("%Water%")).first()
    assert water_res is not None
    dup_res = client.get(
        f"/requests/check-duplicate?resource_id={water_res.id}&location=Evacuation Camp B",
        cookies=req_cookies
    )
    assert dup_res.status_code == 200
    dup_data = dup_res.json()
    assert dup_data["exists"] is True, f"Expected duplicate found, got {dup_data}"
    print(f"[PASS] 5. Duplicate request detection verified: {dup_data['message']}")

    # 6. Test Creating a New Emergency Request (High Priority Medical)
    med_res = db.query(Resource).filter(Resource.category == "Medical").first()
    create_req_res = client.post(
        "/requests/create",
        data={
            "resource_id": med_res.id,
            "requested_quantity": 20,
            "location": "Sector 14 Shelter Base",
            "urgency": "Critical",
            "description": "Critical infant medical emergency, urgent pediatric dressings needed",
            "confirmed_duplicate": "yes"
        },
        cookies=req_cookies,
        follow_redirects=False
    )
    assert create_req_res.status_code == 302
    new_req_id = int(create_req_res.headers["location"].split("/")[-1].split("?")[0])
    print(f"[PASS] 6. Emergency request #{new_req_id} created successfully")

    # Verify priority score was calculated
    new_req = db.query(ReliefRequest).filter(ReliefRequest.id == new_req_id).first()
    assert new_req is not None
    assert new_req.priority_score >= 80.0, f"Expected Critical score >= 80, got {new_req.priority_score}"
    assert new_req.priority_level == "CRITICAL"
    print(f"[PASS] 7. Priority score correctly computed: {new_req.priority_score} (Level: {new_req.priority_level})")

    # 8. Test Admin Approving Request
    appr_res = client.post(f"/requests/{new_req_id}/approve", cookies=admin_cookies, follow_redirects=False)
    assert appr_res.status_code == 302
    db.refresh(new_req)
    assert new_req.status == "Approved"
    print(f"[PASS] 8. Admin approved request #{new_req_id}")

    # 9. Test Resource Allocation & Stock Deduction
    initial_stock = med_res.quantity_available
    alloc_res = client.post(
        f"/requests/{new_req_id}/allocate",
        data={"allocated_resource_id": med_res.id},
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert alloc_res.status_code == 302
    db.refresh(new_req)
    db.refresh(med_res)
    assert new_req.status == "Resource Allocated"
    assert med_res.quantity_available == initial_stock - 20, f"Stock did not decrease properly: {med_res.quantity_available} vs {initial_stock - 20}"
    print(f"[PASS] 9. Stock allocated and inventory decreased from {initial_stock} to {med_res.quantity_available}")

    # 10. Test Insufficient Stock Error
    fail_req = ReliefRequest(
        resource_id=med_res.id,
        requested_quantity=99999,
        location="Nowhere",
        urgency="High",
        priority_score=50.0,
        status="Approved",
        requested_by=1
    )
    db.add(fail_req)
    db.commit()
    db.refresh(fail_req)
    fail_alloc = client.post(
        f"/requests/{fail_req.id}/allocate",
        data={"allocated_resource_id": med_res.id},
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert fail_alloc.status_code == 302
    assert "Insufficient+stock" in fail_alloc.headers["location"]
    print("[PASS] 10. Insufficient stock error handled and prevented over-allocation")

    # 11. Test Assign Delivery
    assign_res = client.post(
        f"/requests/{new_req_id}/assign-delivery",
        data={
            "assigned_to": "Officer Vikram Singh",
            "vehicle_details": "4x4 Emergency Patrol DL-01-9988"
        },
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert assign_res.status_code == 302
    db.refresh(new_req)
    assert new_req.status == "Delivery Assigned"
    deliv = db.query(Delivery).filter(Delivery.request_id == new_req_id).first()
    assert deliv is not None
    assert deliv.status == "Assigned"
    print(f"[PASS] 11. Delivery assigned to {deliv.assigned_to} with vehicle {deliv.vehicle_details}")

    # 12. Test Delivery In Transit -> Delivered
    transit_res = client.post(
        f"/deliveries/{deliv.id}/status",
        data={"new_status": "In Transit"},
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert transit_res.status_code == 302
    db.refresh(deliv)
    db.refresh(new_req)
    assert deliv.status == "In Transit"
    assert new_req.status == "In Transit"

    delivered_res = client.post(
        f"/deliveries/{deliv.id}/status",
        data={"new_status": "Delivered"},
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert delivered_res.status_code == 302
    db.refresh(deliv)
    db.refresh(new_req)
    assert deliv.status == "Delivered"
    assert new_req.status == "Delivered"
    assert deliv.delivered_at is not None
    print(f"[PASS] 12. Complete delivery workflow verified (Assigned -> In Transit -> Delivered)")

    # 13. Test Offline Sync Endpoint
    sync_payload = {
        "requests": [
            {
                "resource_id": water_res.id,
                "requested_quantity": 50,
                "location": "Offline Village Relief Point 5",
                "urgency": "High",
                "description": "Queued in localStorage while offline"
            }
        ]
    }
    sync_res = client.post("/requests/api/sync", json=sync_payload, cookies=req_cookies)
    assert sync_res.status_code == 200
    sync_data = sync_res.json()
    assert sync_data["synced_count"] == 1
    print(f"[PASS] 13. Offline localStorage sync API verified ({sync_data['message']})")

    # 14. Test Resource CRUD
    create_res = client.post(
        "/resources/create",
        data={
            "name": "Generator 5kW Fuel Unit",
            "category": "Emergency Supplies",
            "quantity_available": 10,
            "location": "West Power Depot"
        },
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert create_res.status_code == 302
    created_res = db.query(Resource).filter(Resource.name == "Generator 5kW Fuel Unit").first()
    assert created_res is not None
    assert created_res.quantity_available == 10
    print(f"[PASS] 14. Admin resource creation verified (ID #{created_res.id})")

    edit_res = client.post(
        f"/resources/{created_res.id}/edit",
        data={
            "name": "Generator 5kW Fuel Unit (Restocked)",
            "category": "Emergency Supplies",
            "quantity_available": 15,
            "location": "West Power Depot"
        },
        cookies=admin_cookies,
        follow_redirects=False
    )
    assert edit_res.status_code == 302
    db.refresh(created_res)
    assert created_res.quantity_available == 15
    print("[PASS] 15. Admin resource editing verified")

    del_res = client.post(f"/resources/{created_res.id}/delete", cookies=admin_cookies, follow_redirects=False)
    assert del_res.status_code == 302
    assert db.query(Resource).filter(Resource.id == created_res.id).first() is None
    print("[PASS] 16. Admin resource deletion verified")

    db.close()
    print("========================================")
    print("ALL 16 TESTS PASSED SUCCESSFULLY! 100%")
    print("========================================")

if __name__ == "__main__":
    run_tests()
