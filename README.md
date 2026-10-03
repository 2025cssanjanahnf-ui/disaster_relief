# Disaster Relief Resource Management System

A centralized, responsive emergency resource allocation, prioritization, and delivery coordination web application developed for disaster response teams and relief centers.

Developed as a college CSE 2nd-year project with a clean, understandable, and robust tech stack without unnecessary frameworks or complicated dependencies.

---

## 🌟 Key Features

1. **Role-Based Access Control (RBAC):**
   - **Administrator:** Full visibility over incoming emergency requests, warehouse resource inventories, rule-based prioritization, stock matching, supply allocation, delivery dispatch, and deficit alerts.
   - **Relief Center / Requester:** Streamlined interface to submit urgent emergency requests, track allocation and transit progress in real-time, and check delivery status.

2. **Rule-Based Emergency Priority System:**
   - Evaluates urgency levels (*Critical*, *High*, *Medium*, *Low*), requested scale, supply category (e.g., Medical & Emergency supplies), vulnerable population indicators (infants, casualties, elderly), and elapsed waiting time.
   - Computes a deterministic priority score and human-readable priority classification (`CRITICAL`, `HIGH`, `MEDIUM`, `LOW`). Critical medical requests automatically receive highest priority.

3. **Resource Shortage Detection:**
   - Real-time demand aggregation:
     $$\text{Expected Demand} = \sum \text{Requested Quantities for Active Pending/Approved Requests}$$
     $$\text{Shortage} = \text{Expected Demand} - \text{Available Quantity}$$
   - Generates prominent shortage alerts on the admin dashboard and inventory catalog whenever active demand exceeds current depot stock.

4. **Resource Matching & Allocation:**
   - Matches incoming relief requests with warehouses and distribution depots holding sufficient inventory in the closest proximity.
   - Deducts physical inventory upon allocation with strict validation preventing negative or over-allocation.

5. **Delivery Dispatch & Transit Tracking:**
   - Manages physical dispatch: Request $\rightarrow$ Allocation $\rightarrow$ Delivery Assignment (Driver & Vehicle) $\rightarrow$ In Transit $\rightarrow$ Delivered.
   - Captures driver name, vehicle registration, dispatch timestamp, and delivery completion confirmation.

6. **Automated Escalation Protocol:**
   - Unattended critical requests that remain unassigned beyond a configurable threshold (e.g., 30 minutes) are automatically flagged as **Escalated**.
   - Displays high-visibility warning banners with elapsed waiting times and elevates them to the top of the admin response queue.

7. **Duplicate Request Detection:**
   - Detects existing pending requests for the same resource category and identical or similar geographic coordinates/shelter names.
   - Displays a confirmation prompt allowing field requesters to verify before submitting duplicate orders.

8. **Offline Request Caching & Automatic Synchronization:**
   - Utilizes browser `localStorage` to catch and save emergency requests if internet connectivity is lost in the field.
   - Automatically synchronizes queued requests with the FastAPI backend when connectivity returns, displaying a confirmation message.

---

## 🛠️ Tech Stack

- **Backend:** Python 3.10+, FastAPI, SQLAlchemy 2.x, SQLite, Pydantic, Jinja2Templates
- **Frontend:** HTML5 Semantic Structure, Vanilla CSS3 (Custom Responsive Design System), Vanilla JavaScript (Offline Caching & Auto-Sync)
- **Authentication:** JWT (JSON Web Tokens) stored in secure HTTP-only cookies, password hashing via `pwdlib` with Argon2
- **Environment & Storage:** `python-dotenv`, SQLite database file (`disaster_relief.db`)

---

## 📁 Project Structure

```
disaster-relief/
│
├── main.py                 # FastAPI application entrypoint & lifespan events
├── database.py             # SQLAlchemy engine, declarative base, and session generator
├── models.py               # ORM Models: User, Resource, ReliefRequest, Delivery
├── schemas.py              # Pydantic validation schemas
├── auth.py                 # Argon2 hashing & JWT encoding/decoding utilities
├── dependencies.py         # DB session, JWT cookie extraction, and RBAC guards
├── services.py             # Business logic: priority scoring, shortage detection, matching
├── seed.py                 # Demo seed generator (Admin, Requester, Resources, Requests)
├── test_app.py             # 16-step end-to-end automated test runner
├── requirements.txt        # Pinned dependencies
├── .env                    # Environment variables (JWT secret, escalation timeout)
├── .gitignore              # Git exclusions
├── disaster_relief.db      # SQLite database file
│
├── routers/
│   ├── __init__.py
│   ├── auth.py             # Login, register, logout, profile
│   ├── dashboard.py        # Unified Admin & Requester operational dashboards
│   ├── resources.py        # Resource inventory catalog and CRUD
│   ├── requests.py         # Emergency request creation, lifecycle, matching, allocation
│   └── deliveries.py       # Delivery transit tracking and status progression
│
├── templates/
│   ├── base.html           # Master layout with navbar, offline banner, and toast container
│   ├── login.html          # Authentication with 1-click demo autofill
│   ├── register.html       # Requester registration
│   ├── dashboard.html      # Admin summary metrics, shortages, and requester tracker
│   ├── resources.html      # Warehouse inventory table with shortage tags
│   ├── resource_form.html  # Resource registration & edit form
│   ├── requests.html       # Request queue filtered by status and urgency
│   ├── request_form.html   # Emergency request submission with duplicate detection
│   ├── request_detail.html # Request lifecycle timeline, matching stock, and dispatch
│   ├── deliveries.html     # Vehicle transit tracking and status updates
│   └── profile.html        # Account details and password management
│
└── static/
    ├── css/
    │   └── style.css       # Clean, accessible, emergency-focused design system
    └── js/
        └── app.js          # Offline detection, localStorage queue, and duplicate checks
```

---

## 🚀 Installation & Setup

### 1. Clone or Open Workspace Directory
```powershell
cd disaster-relief
```

### 2. Create Virtual Environment
```powershell
python -m venv venv
```

### 3. Activate Virtual Environment
**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```
*(Or Command Prompt: `venv\Scripts\activate.bat`)*

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 4. Install Dependencies
```powershell
python -m pip install -r requirements.txt
```

### 5. Environment Configuration (.env)
A `.env` file is already created in the project root:
```ini
SECRET_KEY=disaster_relief_secure_jwt_secret_key_college_project_2026
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440
ESCALATION_TIMEOUT_MINUTES=30
DATABASE_URL=sqlite:///./disaster_relief.db
PORT=8000
```

### 6. Initialize & Seed Database
Run the seed script to create all database tables and populate sample demo resources, emergency requests, and deliveries:
```powershell
python seed.py
```

### 7. Run the Application Server
```powershell
uvicorn main:app --reload
```
*(Or simply run `python main.py`)*

Open your browser at:
👉 **`http://127.0.0.1:8000`** *(or `http://127.0.0.1:8001` if port 8000 is occupied on your system)*

---

## 🔑 Demo Login Credentials

The application includes pre-configured demo accounts for academic evaluation:

| Role | Username | Password | Notes |
|---|---|---|---|
| **Administrator** | `admin` | `admin123` | Full administrative control, shortage alerts, resource allocation, and dispatch |
| **Relief Requester** | `requester` | `requester123` | Relief camp coordinator, request creation, status tracking |
| **Field Medic** | `field_medic` | `medic123` | Field hospital requester account |

> **Note:** The login screen provides **1-Click Autofill** buttons (`Use Admin` and `Use Requester`) for rapid testing.

---

## 🔄 Core Disaster Relief Workflow

```
[Emergency Request]
        ↓
[Priority Evaluation (Rule-Based Score & Urgency Classification)]
        ↓
[Check Resource Availability & Shortages]
        ↓
[Resource Matching (Nearest Depot with Stock)]
        ↓
[Admin Approval]
        ↓
[Resource Allocation (Stock Automatically Deducted)]
        ↓
[Delivery Assignment (Driver & Vehicle Details)]
        ↓
[In Transit]
        ↓
[Delivered]
```

- **Rejection Pathway:** Admin can reject non-emergency or duplicate requests with a documented reason.
- **Escalation Pathway:** Unattended critical requests trigger the **Escalated** state with waiting time indicators.

---

## 🧪 Running Automated Tests

Run the test suite to verify all 16 core requirements:
```powershell
python test_app.py
```
Outputs:
```
========================================
RUNNING DISASTER RELIEF SYSTEM TESTS
========================================
[PASS] 1. Unauthenticated dashboard access redirects to /login
[PASS] 2. Admin login successful and HTTP-only cookie issued
[PASS] 3. Admin dashboard renders with metrics and shortage alerts
[PASS] 4. Requester login and dashboard display verified
[PASS] 5. Duplicate request detection verified
[PASS] 6. Emergency request created successfully
[PASS] 7. Priority score correctly computed
[PASS] 8. Admin approved request
[PASS] 9. Stock allocated and inventory decreased
[PASS] 10. Insufficient stock error handled and prevented over-allocation
[PASS] 11. Delivery assigned to driver with vehicle details
[PASS] 12. Complete delivery workflow verified (Assigned -> In Transit -> Delivered)
[PASS] 13. Offline localStorage sync API verified
[PASS] 14. Admin resource creation verified
[PASS] 15. Admin resource editing verified
[PASS] 16. Admin resource deletion verified
========================================
ALL 16 TESTS PASSED SUCCESSFULLY! 100%
========================================
```
