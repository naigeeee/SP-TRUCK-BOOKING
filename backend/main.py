"""
SP PH Truck Booking Centralised Operation Request Database
"""

import os
import json
import uuid
from datetime import datetime, timezone, date
from urllib.parse import urlparse, unquote
from typing import Optional
from decimal import Decimal

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware

import pymysql

APP_NAME = "SP PH Truck Booking Centralised Operations"

app = FastAPI(title=APP_NAME, docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

def get_database_url():
    url = os.environ.get("DATABASE_URL")
    if not url:
        return None
    parsed = urlparse(url)
    username = unquote(parsed.username) if parsed.username else ""
    password = unquote(parsed.password) if parsed.password else ""
    return {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": username,
        "password": password,
        "database": parsed.path.lstrip("/") or "",
        "charset": "utf8mb4",
        "cursorclass": pymysql.cursors.DictCursor,
    }

DB_CONFIG = get_database_url()
LOCAL_MODE = DB_CONFIG is None

if LOCAL_MODE:
    print("[LOCAL MODE] No DATABASE_URL found - data not saved between restarts")
else:
    print(f"[DATABASE] Connected: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")

def get_db():
    if LOCAL_MODE:
        return None
    try:
        return pymysql.connect(**DB_CONFIG, connect_timeout=10)
    except Exception as e:
        print(f"[DB ERROR] {e}")
        return None

# ---------------------------------------------------------------------------
# Local in-memory store
# ---------------------------------------------------------------------------

_store = {
    "users": [{"id": 1, "email": "nigel.ng@ninjavan.co", "name": "Nigel Ng", "role": "master_admin", "is_active": True, "created_at": "2026-01-01 00:00:00", "updated_at": "2026-01-01 00:00:00"}],
    "ports": [
        {"id": 1, "name": "Manila Port", "code": "MNL", "location": "Manila, Philippines", "latitude": 14.5995, "longitude": 120.9842, "is_active": True, "created_at": "2026-01-01"},
        {"id": 2, "name": "Cebu Port", "code": "CEB", "location": "Cebu City, Philippines", "latitude": 10.3157, "longitude": 123.8854, "is_active": True, "created_at": "2026-01-01"},
        {"id": 3, "name": "Davao Port", "code": "DVO", "location": "Davao City, Philippines", "latitude": 7.1907, "longitude": 125.4553, "is_active": True, "created_at": "2026-01-01"},
    ],
    "accounts": [
        {"id": 1, "name": "Ninja Van PH", "code": "NVPH", "is_active": True, "created_at": "2026-01-01"},
    ],
    "departments": [
        {"id": 1, "name": "PHCC", "code": "PHCC", "is_active": True, "created_at": "2026-01-01"},
        {"id": 2, "name": "PDFF", "code": "PDFF", "is_active": True, "created_at": "2026-01-01"},
        {"id": 3, "name": "PDFF Provincial", "code": "PDFF Provincial", "is_active": True, "created_at": "2026-01-01"},
        {"id": 4, "name": "3PL XDOC", "code": "3PL XDOC", "is_active": True, "created_at": "2026-01-01"},
    ],
    "packaging_types": [
        {"id": 1, "name": "Pallet", "code": "PLT", "is_active": True, "created_at": "2026-01-01"},
        {"id": 2, "name": "Box", "code": "BOX", "is_active": True, "created_at": "2026-01-01"},
        {"id": 3, "name": "Carton", "code": "CTN", "is_active": True, "created_at": "2026-01-01"},
    ],
    "truck_statuses": [
        {"id": 1, "name": "Pending", "code": "pending", "color": "#F59E0B", "is_active": True},
        {"id": 2, "name": "Allocated", "code": "allocated", "color": "#3B82F6", "is_active": True},
        {"id": 3, "name": "In Transit", "code": "in_transit", "color": "#8B5CF6", "is_active": True},
        {"id": 4, "name": "Delivered", "code": "delivered", "color": "#10B981", "is_active": True},
        {"id": 5, "name": "Cancelled", "code": "cancelled", "color": "#EF4444", "is_active": True},
        {"id": 6, "name": "On Hold", "code": "on_hold", "color": "#6B7280", "is_active": True},
        {"id": 7, "name": "Foul Trip", "code": "foul_trip", "color": "#DC2626", "is_active": True},
    ],
    "truck_types": [
        {"id": 1, "name": "6W Truck", "code": "6W", "max_capacity_kg": 5000, "max_capacity_cbm": 20, "is_active": True, "created_at": "2026-01-01"},
        {"id": 2, "name": "10W Truck", "code": "10W", "max_capacity_kg": 10000, "max_capacity_cbm": 40, "is_active": True, "created_at": "2026-01-01"},
        {"id": 3, "name": "Container 20ft", "code": "C20", "max_capacity_kg": 20000, "max_capacity_cbm": 33, "is_active": True, "created_at": "2026-01-01"},
    ],
    "truck_type_capacities": [
        {"id": 1, "truck_type_id": 1, "packaging_type_id": 1, "max_quantity": 20, "created_at": "2026-01-01"},
        {"id": 2, "truck_type_id": 1, "packaging_type_id": 2, "max_quantity": 100, "created_at": "2026-01-01"},
        {"id": 3, "truck_type_id": 1, "packaging_type_id": 3, "max_quantity": 80, "created_at": "2026-01-01"},
        {"id": 4, "truck_type_id": 2, "packaging_type_id": 1, "max_quantity": 40, "created_at": "2026-01-01"},
        {"id": 5, "truck_type_id": 2, "packaging_type_id": 2, "max_quantity": 200, "created_at": "2026-01-01"},
        {"id": 6, "truck_type_id": 2, "packaging_type_id": 3, "max_quantity": 160, "created_at": "2026-01-01"},
    ],
    "trucks": [
        {"id": 1, "plate_number": "ABC1234", "truck_type_id": 1, "vendor_id": 1, "driver_name": "Juan Dela Cruz", "driver_phone": "+639171234567", "helper_name": "Pedro Santos", "status": "available", "is_active": True, "created_at": "2026-01-15 08:00:00"},
        {"id": 2, "plate_number": "XYZ5678", "truck_type_id": 1, "vendor_id": 1, "driver_name": "Jose Reyes", "driver_phone": "+639181234567", "helper_name": "", "status": "available", "is_active": True, "created_at": "2026-02-20 08:00:00"},
        {"id": 3, "plate_number": "DEF9012", "truck_type_id": 2, "vendor_id": 2, "driver_name": "Miguel Santos", "driver_phone": "+639191234567", "helper_name": "Luis Garcia", "status": "available", "is_active": True, "created_at": "2026-03-10 08:00:00"},
        {"id": 4, "plate_number": "GHI3456", "truck_type_id": 3, "vendor_id": 2, "driver_name": "Carlos Reyes", "driver_phone": "+639201234567", "helper_name": "", "status": "available", "is_active": True, "created_at": "2026-04-05 08:00:00"},
    ],
    "truck_requests": [], "attachments": [], "vendor_rates": [],
    "vendor_evaluations": [], "pending_allocations": [], "vendors": [
        {"id": 1, "name": "ABC Logistics", "contact_person": "Pedro Santos", "phone": "+639171111111", "email": "pedro@abc.com", "address": "Manila", "is_active": True, "created_at": "2026-01-01 08:00:00"},
        {"id": 2, "name": "XYZ Transport", "contact_person": "Luis Garcia", "phone": "+639172222222", "email": "luis@xyz.com", "address": "Cebu", "is_active": True, "created_at": "2026-01-01 08:00:00"},
    ],
    "truck_request_history": [],
    "_cnt": {"users": 1, "ports": 3, "accounts": 1, "departments": 4, "packaging_types": 3,
             "truck_statuses": 7, "truck_types": 3, "truck_type_capacities": 6, "trucks": 4,
             "truck_requests": 0, "attachments": 0, "vendor_rates": 0,
              "vendor_evaluations": 0, "pending_allocations": 0, "vendors": 2, "truck_request_history": 0},
    "_upload": os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"),
}
os.makedirs(_store["_upload"], exist_ok=True)

def nid(t):
    _store["_cnt"][t] = _store["_cnt"].get(t, 0) + 1
    return _store["_cnt"][t]

def nows():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def parse_dt(dt_str):
    if not dt_str: return None
    try: return datetime.fromisoformat(str(dt_str).replace('Z', '+00:00'))
    except: return None

def validate_delivered_chronology(body):
    fields = [
        ("arrived_pickup_datetime", "Arrived Pickup"),
        ("start_loading_datetime", "Start Loading"),
        ("end_loading_datetime", "End Loading"),
        ("arrived_dest_datetime", "Arrived Destination"),
        ("start_unloading_datetime", "Start Unloading"),
        ("end_unloading_datetime", "End Unloading"),
    ]
    prev = None
    for fld, label in fields:
        val = body.get(fld)
        if not val: raise HTTPException(400, f"{label} is required for Delivered status")
        dt = parse_dt(val)
        if not dt: raise HTTPException(400, f"Invalid {label} datetime format")
        if prev and dt < prev[1]:
            raise HTTPException(400, f"{label} ({dt.strftime('%Y-%m-%d %H:%M')}) cannot be earlier than {prev[0]} ({prev[1].strftime('%Y-%m-%d %H:%M')})")
        prev = (label, dt)

def compute_rate(rate_match, dest_port_id):
    if not rate_match: return 0
    if rate_match.get("destination_port_id") == dest_port_id: return rate_match.get("rate_per_trip", 0)
    drops = rate_match.get("destination_drops", [])
    if isinstance(drops, str):
        try: import json; drops = json.loads(drops)
        except: drops = []
    for d in drops:
        if d.get("port_id") == dest_port_id: return d.get("rate_per_trip", 0)
    return rate_match.get("default_rate", 0)

# Status transition rules:
# Pending(1)/Allocated(2) -> can go to: Allocated(2), In Transit(3), Delivered(4), Cancelled(5), On Hold(6), Foul Trip(7)
# In Transit(3) -> can go to: On Hold(6), Foul Trip(7), Delivered(4), Cancelled(5) (NOT Pending, NOT Allocated)
# Foul Trip(7) -> can go to: On Hold(6), Foul Trip(7) (NOT Pending, NOT Allocated)
# Delivered(4)/Cancelled(5) -> can go to: On Hold(6) (NOT Pending, NOT Allocated)
# On Hold(6) -> can go to: In Transit(3), Delivered(4), Cancelled(5), Foul Trip(7) (NOT Pending, NOT Allocated)
VALID_STATUS_TRANSITIONS = {
    1: [2, 3, 4, 5, 6, 7],    # Pending -> Allocated, In Transit, Delivered, Cancelled, On Hold, Foul Trip
    2: [1, 3, 4, 5, 6, 7],    # Allocated -> Pending, In Transit, Delivered, Cancelled, On Hold, Foul Trip
    3: [4, 5, 6, 7],          # In Transit -> Delivered, Cancelled, On Hold, Foul Trip
    4: [6],                    # Delivered -> On Hold
    5: [6],                    # Cancelled -> On Hold
    6: [3, 4, 5, 7],          # On Hold -> In Transit, Delivered, Cancelled, Foul Trip
    7: [6, 7],                 # Foul Trip -> On Hold, Foul Trip
}

def validate_status_transition(old_status_id, new_status_id):
    if old_status_id == new_status_id: return
    allowed = VALID_STATUS_TRANSITIONS.get(old_status_id, [])
    if new_status_id not in allowed:
        status_names = {1: "Pending", 2: "Allocated", 3: "In Transit", 4: "Delivered", 5: "Cancelled", 6: "On Hold", 7: "Foul Trip"}
        raise HTTPException(400, f"Cannot change status from {status_names.get(old_status_id, '?')} to {status_names.get(new_status_id, '?')}")

def compute_trip_id(reqs_on_truck, request_id):
    allocated = [r for r in reqs_on_truck if r.get("status_id") in (2, 3, 4, 5, 7) and r.get("drop_sequence") is not None]
    if not allocated: return None
    allocated.sort(key=lambda x: x.get("drop_sequence", 999))
    first_req = allocated[0]
    first_rn = first_req.get("request_number", "")
    seq = next((r.get("drop_sequence") for r in allocated if r["id"] == request_id), None)
    if seq is None: return None
    letter = chr(64 + seq)
    hash_input = first_rn + str(first_req.get("assigned_truck_id", ""))
    h = abs(hash(hash_input)) % 100000
    base = f"SPT-{h:05d}"
    return f"{base}-{letter}"

def find_best_rate(vendor_id, truck_type_id, origin_port_id, dest_port_id):
    candidates = [vr for vr in _store["vendor_rates"]
        if vr.get("vendor_id") == vendor_id and vr.get("truck_type_id") == truck_type_id
        and vr.get("origin_port_id") == origin_port_id and vr.get("is_active", True)]
    exact = next((vr for vr in candidates if vr.get("destination_port_id") == dest_port_id), None)
    if exact: return exact
    return candidates[0] if candidates else None

def backfill_rate_estimated_costs(vendor_id, truck_type_id, origin_port_id):
    if LOCAL_MODE:
        all_rates = [r for r in _store["vendor_rates"]
            if r.get("vendor_id") == vendor_id and r.get("truck_type_id") == truck_type_id
            and r.get("origin_port_id") == origin_port_id and r.get("is_active", True)]
        if not all_rates: return
        truck_primary_dest = {}
        for r in _store["truck_requests"]:
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                tid = r["assigned_truck_id"]
                ds = r.get("drop_sequence")
                if tid not in truck_primary_dest or (ds is not None and ds == 1):
                    truck_primary_dest[tid] = r.get("destination_port_id")
                if ds is not None and ds == 1:
                    truck_primary_dest[tid] = r.get("destination_port_id")
        for r in _store["truck_requests"]:
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck = next((t for t in _store["trucks"] if t["id"] == r["assigned_truck_id"]), None)
                if truck and truck.get("vendor_id") == vendor_id and truck.get("truck_type_id") == truck_type_id and r.get("origin_port_id") == origin_port_id:
                    primary_dest = truck_primary_dest.get(r["assigned_truck_id"], r.get("destination_port_id"))
                    exact = next((rt for rt in all_rates if rt.get("destination_port_id") == primary_dest), None)
                    rate_match = exact or (all_rates[0] if all_rates else None)
                    if not rate_match: continue
                    eff = str(rate_match.get("effective_date", ""))[:10]
                    exp = str(rate_match.get("expiry_date", ""))[:10]
                    pickup = str(r.get("pickup_datetime", ""))[:10]
                    in_range = True
                    if eff and pickup < eff: in_range = False
                    if exp and pickup > exp: in_range = False
                    if in_range:
                        r["estimated_cost"] = compute_rate(rate_match, r.get("destination_port_id"))
                        if r.get("status_id") in (4, 7):
                            r["actual_cost"] = r["estimated_cost"]
                        else:
                            r["actual_cost"] = 0
                    else:
                        r["estimated_cost"] = 0
                        r["actual_cost"] = 0
    else:
        all_rates = db_q("SELECT * FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND is_active=1", (vendor_id, truck_type_id, origin_port_id))
        if not all_rates: return
        match_reqs = db_q("""SELECT tr.id, tr.assigned_truck_id, tr.destination_port_id, tr.drop_sequence, tr.status_id, DATE(tr.pickup_datetime) as pickup_date FROM truck_requests tr
            JOIN trucks tk ON tr.assigned_truck_id=tk.id
            WHERE tk.vendor_id=%s AND tk.truck_type_id=%s AND tr.origin_port_id=%s AND tr.status_id IN (2,3,4,5,7)""",
            (vendor_id, truck_type_id, origin_port_id))
        truck_primary_dest = {}
        for mr in match_reqs:
            tid = mr.get("assigned_truck_id")
            ds = mr.get("drop_sequence")
            if tid not in truck_primary_dest:
                truck_primary_dest[tid] = mr.get("destination_port_id")
            if ds == 1:
                truck_primary_dest[tid] = mr.get("destination_port_id")
        for mr in match_reqs:
            primary_dest = truck_primary_dest.get(mr.get("assigned_truck_id"), mr.get("destination_port_id"))
            exact = next((r for r in all_rates if r.get("destination_port_id") == primary_dest), None)
            rate_match = exact or (all_rates[0] if all_rates else None)
            if not rate_match: continue
            eff = str(rate_match.get("effective_date", ""))[:10]
            exp = str(rate_match.get("expiry_date", ""))[:10]
            pickup = str(mr.get("pickup_date", ""))[:10]
            in_range = True
            if eff and pickup < eff: in_range = False
            if exp and pickup > exp: in_range = False
            if in_range:
                est = compute_rate(rate_match, mr.get("destination_port_id"))
                db_x("UPDATE truck_requests SET estimated_cost=%s WHERE id=%s", (est, mr["id"]))
                if mr.get("status_id") in (4, 7):
                    db_x("UPDATE truck_requests SET actual_cost=%s WHERE id=%s", (est, mr["id"]))
                else:
                    db_x("UPDATE truck_requests SET actual_cost=0 WHERE id=%s", (mr["id"],))
            else:
                db_x("UPDATE truck_requests SET estimated_cost=0, actual_cost=0 WHERE id=%s", (mr["id"],))

def recalculate_trip_rates(truck_id):
    """Recalculate rates for all active requests on a truck based on the current primary destination."""
    if not truck_id: return
    if LOCAL_MODE:
        truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
        if not truck: return
        active = [r for r in _store["truck_requests"]
            if r.get("assigned_truck_id") == truck_id and r.get("status_id") not in (4, 5)]
        if not active: return
        primary = next((r for r in active if r.get("drop_sequence") == 1), None)
        if not primary: primary = min((r for r in active if r.get("drop_sequence") is not None), key=lambda x: x["drop_sequence"], default=None)
        if not primary: return
        primary_dest = primary.get("destination_port_id")
        rate_match = find_best_rate(truck.get("vendor_id"), truck.get("truck_type_id"), primary.get("origin_port_id"), primary_dest)
        if not rate_match: return
        for r in active:
            r["estimated_cost"] = compute_rate(rate_match, r.get("destination_port_id"))
            if r.get("status_id") == 7:
                r["actual_cost"] = r["estimated_cost"]
            elif r.get("status_id") not in (4, 5):
                r["actual_cost"] = 0
    else:
        truck = db_1("SELECT vendor_id, truck_type_id FROM trucks WHERE id=%s", (truck_id,))
        if not truck: return
        active = db_q("SELECT id, origin_port_id, destination_port_id, drop_sequence, pickup_datetime FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (truck_id,))
        if not active: return
        primary = next((r for r in active if r.get("drop_sequence") == 1), None)
        if not primary: primary = min((r for r in active if r.get("drop_sequence") is not None), key=lambda x: x["drop_sequence"], default=None)
        if not primary: return
        primary_dest = primary.get("destination_port_id")
        rate = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND destination_port_id=%s AND is_active=1",
            (truck["vendor_id"], truck["truck_type_id"], primary["origin_port_id"], primary_dest))
        if not rate:
            rate = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND is_active=1",
                (truck["vendor_id"], truck["truck_type_id"], primary["origin_port_id"]))
        if not rate: return
        for r in active:
            est = compute_rate(rate, r.get("destination_port_id"))
            db_x("UPDATE truck_requests SET estimated_cost=%s WHERE id=%s", (est, r["id"]))
            db_x("UPDATE truck_requests SET actual_cost=%s WHERE id=%s AND status_id=7", (est, r["id"]))
            db_x("UPDATE truck_requests SET actual_cost=0 WHERE id=%s AND status_id NOT IN (4,5,7)", (r["id"],))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def row2d(r):
    if r is None: return None
    if isinstance(r, dict):
        return {k: (v.strftime("%Y-%m-%d %H:%M:%S") if isinstance(v, datetime) else v.strftime("%Y-%m-%d") if isinstance(v, date) else float(v) if isinstance(v, Decimal) else v) for k, v in r.items()}
    return r

def db_q(sql, p=None):
    db = get_db()
    if not db: return []
    try:
        with db.cursor() as c: c.execute(sql, p); return [row2d(r) for r in c.fetchall()]
    finally: db.close()

def db_1(sql, p=None):
    db = get_db()
    if not db: return None
    try:
        with db.cursor() as c: c.execute(sql, p); r = c.fetchone(); return row2d(r)
    finally: db.close()

def db_x(sql, p=None):
    db = get_db()
    if not db: return 0
    try:
        with db.cursor() as c: c.execute(sql, p); db.commit(); return c.rowcount
    finally: db.close()

def db_i(sql, p=None):
    db = get_db()
    if not db: return 0
    try:
        with db.cursor() as c: c.execute(sql, p); db.commit(); return c.lastrowid
    finally: db.close()

def gen_req_no():
    return f"REQ-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:4].upper()}"

def gen_name_from_email(email):
    local = email.split("@")[0]
    parts = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts) if parts else email

def is_hash_name(name):
    if not name or len(name) < 20: return False
    return all(c in "0123456789abcdef" for c in name)

def get_user(request: Request):
    email = request.headers.get("X-Forwarded-Email") or "nigel.ng@ninjavan.co"
    name = request.headers.get("X-Forwarded-User") or email
    if is_hash_name(name):
        name = gen_name_from_email(email)
    if LOCAL_MODE:
        for u in _store["users"]:
            if u["email"] == email:
                if is_hash_name(u["name"]):
                    u["name"] = name
                return u
        uid = nid("users")
        u = {"id": uid, "email": email, "name": name, "role": "normal_user", "is_active": True, "created_at": nows(), "updated_at": nows()}
        _store["users"].append(u)
        return u
    u = db_1("SELECT * FROM users WHERE email=%s", (email,))
    if u:
        if is_hash_name(u["name"]):
            db_x("UPDATE users SET name=%s WHERE id=%s", (name, u["id"]))
            u["name"] = name
        return u
    db_x("INSERT INTO users (email,name,role) VALUES (%s,%s,'normal_user')", (email, name))
    return db_1("SELECT * FROM users WHERE email=%s", (email,))

def require_admin(request):
    u = get_user(request)
    if u["role"] not in ("master_admin", "admin"): raise HTTPException(403, "Admin access required")
    return u

def require_master(request):
    u = get_user(request)
    if u["role"] != "master_admin": raise HTTPException(403, "Master admin access required")
    return u

# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------

@app.get("/health", tags=["system"])
def health():
    return {"status": "ok", "mode": "local" if LOCAL_MODE else "database"}

@app.get("/api/local-mode")
def local_mode():
    return {"local_mode": LOCAL_MODE}

@app.get("/api/me")
def me(request: Request):
    return row2d(get_user(request))

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/users")
def list_users(request: Request):
    if LOCAL_MODE: return [row2d(u) for u in _store["users"] if u.get("is_active")]
    return db_q("SELECT * FROM users WHERE is_active=1 ORDER BY name")

@app.post("/api/users/{uid}/role")
async def set_role(uid: int, request: Request):
    user = require_master(request)
    body = await request.json()
    role = body.get("role")
    if role not in ("admin", "normal_user"): raise HTTPException(400, "Invalid role")
    if LOCAL_MODE:
        for u in _store["users"]:
            if u["id"] == uid: u["role"] = role; u["updated_at"] = nows(); return row2d(u)
        raise HTTPException(404, "User not found")
    db_x("UPDATE users SET role=%s WHERE id=%s", (role, uid))
    return db_1("SELECT * FROM users WHERE id=%s", (uid,))

@app.post("/api/users/{uid}/role-admin")
async def set_role_admin(uid: int, request: Request):
    user = require_admin(request)
    body = await request.json()
    role = body.get("role")
    if role not in ("admin", "normal_user"): raise HTTPException(400, "Invalid role")
    if user["role"] == "admin" and role != "normal_user": raise HTTPException(403, "Admins can only set normal_user")
    if LOCAL_MODE:
        for u in _store["users"]:
            if u["id"] == uid: u["role"] = role; u["updated_at"] = nows(); return row2d(u)
        raise HTTPException(404, "User not found")
    db_x("UPDATE users SET role=%s WHERE id=%s", (role, uid))
    return db_1("SELECT * FROM users WHERE id=%s", (uid,))

@app.put("/api/users/{uid}")
async def update_user(uid: int, request: Request):
    user = require_admin(request)
    body = await request.json()
    name = (body.get("name") or "").strip()
    if not name: raise HTTPException(400, "Name is required")
    if LOCAL_MODE:
        for u in _store["users"]:
            if u["id"] == uid: u["name"] = name; u["updated_at"] = nows(); return row2d(u)
        raise HTTPException(404, "User not found")
    db_x("UPDATE users SET name=%s WHERE id=%s", (name, uid))
    return db_1("SELECT * FROM users WHERE id=%s", (uid,))

# ---------------------------------------------------------------------------
# Master data: Ports, Accounts, Departments, Packaging, Statuses, Truck Types
# ---------------------------------------------------------------------------

for _tbl, _fields, _label in [
    ("ports", ["name", "code", "location", "latitude", "longitude"], "ports"),
    ("accounts", ["name", "code"], "accounts"),
    ("departments", ["name", "code"], "departments"),
    ("packaging_types", ["name", "code", "description"], "packaging-types"),
    ("truck_statuses", ["name", "code", "color"], "truck-statuses"),
]:
    def _make_list(t=_tbl):
        def _fn(request: Request):
            if LOCAL_MODE: return [row2d(x) for x in _store[t]]
            return db_q(f"SELECT * FROM {t} WHERE is_active=1 ORDER BY name")
        return _fn
    def _make_create(t=_tbl, flds=_fields):
        async def _fn(request: Request):
            user = require_admin(request)
            body = await request.json()
            vals = {}
            for f in flds:
                v = body.get(f)
                if isinstance(v, str): v = v.strip()
                if f in ("latitude", "longitude"):
                    vals[f] = float(v) if v not in (None, "", "None") else None
                else:
                    vals[f] = v if v not in (None, "", "None") else ""
            if not all(vals.get(f) for f in flds[:2]): raise HTTPException(400, "Name and code required")
            if LOCAL_MODE:
                code = vals.get("code", "")
                for x in _store[t]:
                    if x.get("code") == code: raise HTTPException(400, "Code exists")
                i = nid(t)
                rec = {"id": i, **vals, "is_active": True, "created_at": nows()}
                _store[t].append(rec)
                return rec
            code = vals.get("code", "")
            existing = db_1(f"SELECT id FROM {t} WHERE code=%s AND is_active=1", (code,))
            if existing: raise HTTPException(400, "Code exists")
            db_x(f"DELETE FROM {t} WHERE code=%s AND is_active=0", (code,))
            cols = ", ".join(flds)
            phs = ", ".join(["%s"] * len(flds))
            i = db_i(f"INSERT INTO {t} ({cols}) VALUES ({phs})", tuple(vals[f] for f in flds))
            return db_1(f"SELECT * FROM {t} WHERE id=%s", (i,))
        return _fn
    def _make_delete(t=_tbl):
        def _fn(tid: int, request: Request):
            require_admin(request)
            if LOCAL_MODE:
                _store[t] = [x for x in _store[t] if x["id"] != tid]
                if t == "truck_types":
                    _store["truck_type_capacities"] = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] != tid]
                return {"ok": True}
            existing = db_1(f"SELECT id FROM {t} WHERE id=%s AND is_active=1", (tid,))
            if not existing: raise HTTPException(404, "Not found")
            try:
                db_x(f"DELETE FROM {t} WHERE id=%s", (tid,))
            except Exception as e:
                if "foreign key constraint" in str(e).lower():
                    raise HTTPException(400, "Cannot delete: this record is referenced by existing records. Remove dependent records first.")
                raise
            return {"ok": True}
        return _fn

    app.add_api_route(f"/api/{_label}", _make_list(), methods=["GET"])
    app.add_api_route(f"/api/{_label}", _make_create(), methods=["POST"])
    app.add_api_route(f"/api/{_label}/{{tid}}", _make_delete(), methods=["DELETE"])

# Explicit PUT routes for master library items
@app.put("/api/ports/{port_id}")
async def update_port(port_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for x in _store["ports"]:
            if x["id"] == port_id:
                for f in ("name", "code", "location", "latitude", "longitude"):
                    if f in body: x[f] = body[f]
                return row2d(x)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code", "location", "latitude", "longitude"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(port_id); db_x(f"UPDATE ports SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM ports WHERE id=%s", (port_id,))

@app.put("/api/accounts/{account_id}")
async def update_account(account_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for x in _store["accounts"]:
            if x["id"] == account_id:
                for f in ("name", "code"):
                    if f in body: x[f] = body[f]
                return row2d(x)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(account_id); db_x(f"UPDATE accounts SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM accounts WHERE id=%s", (account_id,))

@app.put("/api/departments/{dept_id}")
async def update_dept(dept_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for x in _store["departments"]:
            if x["id"] == dept_id:
                for f in ("name", "code"):
                    if f in body: x[f] = body[f]
                return row2d(x)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(dept_id); db_x(f"UPDATE departments SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM departments WHERE id=%s", (dept_id,))

@app.put("/api/packaging-types/{pt_id}")
async def update_pkg(pt_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for x in _store["packaging_types"]:
            if x["id"] == pt_id:
                for f in ("name", "code", "description"):
                    if f in body: x[f] = body[f]
                return row2d(x)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code", "description"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(pt_id); db_x(f"UPDATE packaging_types SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM packaging_types WHERE id=%s", (pt_id,))

@app.put("/api/truck-statuses/{st_id}")
async def update_status(st_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for x in _store["truck_statuses"]:
            if x["id"] == st_id:
                for f in ("name", "code", "color"):
                    if f in body: x[f] = body[f]
                return row2d(x)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code", "color"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(st_id); db_x(f"UPDATE truck_statuses SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM truck_statuses WHERE id=%s", (st_id,))

# Vendors
@app.get("/api/vendors")
def list_vendors(request: Request):
    get_user(request)
    if LOCAL_MODE: return [row2d(v) for v in _store["vendors"]]
    return db_q("SELECT * FROM vendors WHERE is_active=1 ORDER BY name")

@app.post("/api/vendors")
async def create_vendor(request: Request):
    require_admin(request)
    body = await request.json()
    name = body.get("name", "").strip()
    contact_person = body.get("contact_person", "").strip()
    phone = body.get("phone", "").strip()
    email = body.get("email", "").strip()
    address = body.get("address", "").strip()
    if not name: raise HTTPException(400, "Name required")
    if LOCAL_MODE:
        for v in _store["vendors"]:
            if v.get("name","").lower() == name.lower(): raise HTTPException(400, "Vendor exists")
        vid = nid("vendors")
        v = {"id": vid, "name": name, "contact_person": contact_person, "phone": phone, "email": email, "address": address, "is_active": True, "created_at": nows()}
        _store["vendors"].append(v)
        return v
    vid = db_i("INSERT INTO vendors (name,contact_person,phone,email,address) VALUES (%s,%s,%s,%s,%s)", (name, contact_person, phone, email, address))
    return db_1("SELECT * FROM vendors WHERE id=%s", (vid,))

@app.put("/api/vendors/{vid}")
async def update_vendor(vid: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for v in _store["vendors"]:
            if v["id"] == vid:
                for f in ("name", "contact_person", "phone", "email", "address"):
                    if f in body: v[f] = body[f]
                return row2d(v)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "contact_person", "phone", "email", "address"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(vid); db_x(f"UPDATE vendors SET {','.join(sets)} WHERE id=%s", tuple(params))
    return db_1("SELECT * FROM vendors WHERE id=%s", (vid,))

@app.delete("/api/vendors/{vid}")
def delete_vendor(vid: int, request: Request):
    require_admin(request)
    if LOCAL_MODE:
        _store["vendors"] = [v for v in _store["vendors"] if v["id"] != vid]
        return {"ok": True}
    db_x("UPDATE vendors SET is_active=0 WHERE id=%s", (vid,))
    return {"ok": True}

# Truck Types with capacities
@app.get("/api/truck-types")
def list_tt(request: Request):
    if LOCAL_MODE:
        types = [row2d(t) for t in _store["truck_types"]]
        for tt in types:
            tt["capacities"] = [{**row2d(c), "packaging_type_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == c["packaging_type_id"]), "")} for c in _store["truck_type_capacities"] if c["truck_type_id"] == tt["id"]]
        return types
    types = db_q("SELECT * FROM truck_types WHERE is_active=1 ORDER BY name")
    for tt in types:
        tt["capacities"] = db_q("SELECT c.*, pt.name as packaging_type_name FROM truck_type_capacities c JOIN packaging_types pt ON c.packaging_type_id=pt.id WHERE c.truck_type_id=%s", (tt["id"],))
    return types

@app.post("/api/truck-types")
async def create_tt(request: Request):
    require_admin(request)
    body = await request.json()
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()
    if not name or not code: raise HTTPException(400, "Name and code required")
    caps = body.get("capacities", [])
    if LOCAL_MODE:
        for t in _store["truck_types"]:
            if t["code"] == code: raise HTTPException(400, "Code exists")
        tid = nid("truck_types")
        tt = {"id": tid, "name": name, "code": code, "max_capacity_kg": body.get("max_capacity_kg", 0), "max_capacity_cbm": body.get("max_capacity_cbm", 0), "is_active": True, "created_at": nows()}
        _store["truck_types"].append(tt)
        for c in caps:
            cid = nid("truck_type_capacities")
            _store["truck_type_capacities"].append({"id": cid, "truck_type_id": tid, "packaging_type_id": c["packaging_type_id"], "max_quantity": c.get("max_quantity", 0), "created_at": nows()})
        return tt
    existing_tt = db_1("SELECT id FROM truck_types WHERE code=%s AND is_active=1", (code,))
    if existing_tt: raise HTTPException(400, "Code exists")
    db_x("DELETE FROM truck_types WHERE code=%s AND is_active=0", (code,))
    tid = db_i("INSERT INTO truck_types (name,code,max_capacity_kg,max_capacity_cbm) VALUES (%s,%s,%s,%s)", (name, code, body.get("max_capacity_kg", 0), body.get("max_capacity_cbm", 0)))
    for c in caps:
        db_x("INSERT INTO truck_type_capacities (truck_type_id,packaging_type_id,max_quantity) VALUES (%s,%s,%s)", (tid, c["packaging_type_id"], c.get("max_quantity", 0)))
    return db_1("SELECT * FROM truck_types WHERE id=%s", (tid,))

@app.put("/api/truck-types/{tt_id}")
async def update_tt(tt_id: int, request: Request):
    require_admin(request)
    body = await request.json()
    name = body.get("name", "").strip()
    code = body.get("code", "").strip()
    caps = body.get("capacities", None)
    if LOCAL_MODE:
        for t in _store["truck_types"]:
            if t["id"] == tt_id:
                if name: t["name"] = name
                if code: t["code"] = code
                if "max_capacity_kg" in body: t["max_capacity_kg"] = body["max_capacity_kg"]
                if "max_capacity_cbm" in body: t["max_capacity_cbm"] = body["max_capacity_cbm"]
                if caps is not None:
                    _store["truck_type_capacities"] = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] != tt_id]
                    for c in caps:
                        cid = nid("truck_type_capacities")
                        _store["truck_type_capacities"].append({"id": cid, "truck_type_id": tt_id, "packaging_type_id": c["packaging_type_id"], "max_quantity": c.get("max_quantity", 0), "created_at": nows()})
                return row2d(t)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code", "max_capacity_kg", "max_capacity_cbm"):
        if f in body:
            sets.append(f"{f}=%s")
            params.append(body[f].strip() if isinstance(body[f], str) else body[f])
    if sets:
        params.append(tt_id)
        db_x(f"UPDATE truck_types SET {','.join(sets)} WHERE id=%s", tuple(params))
    if caps is not None:
        db_x("DELETE FROM truck_type_capacities WHERE truck_type_id=%s", (tt_id,))
        for c in caps:
            db_x("INSERT INTO truck_type_capacities (truck_type_id,packaging_type_id,max_quantity) VALUES (%s,%s,%s)", (tt_id, c["packaging_type_id"], c.get("max_quantity", 0)))
    return db_1("SELECT * FROM truck_types WHERE id=%s", (tt_id,))

@app.delete("/api/truck-types/{tt_id}")
def delete_tt(tt_id: int, request: Request):
    require_admin(request)
    if LOCAL_MODE:
        _store["truck_types"] = [t for t in _store["truck_types"] if t["id"] != tt_id]
        _store["truck_type_capacities"] = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] != tt_id]
        return {"ok": True}
    db_x("DELETE FROM truck_type_capacities WHERE truck_type_id=%s", (tt_id,))
    db_x("DELETE FROM truck_types WHERE id=%s", (tt_id,))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Trucks (Fleet)
# ---------------------------------------------------------------------------

@app.get("/api/trucks")
def list_trucks(request: Request, status: Optional[str] = None):
    if LOCAL_MODE:
        trucks = [row2d(t) for t in _store["trucks"]]
        for t in trucks:
            t["truck_type_name"] = next((tt["name"] for tt in _store["truck_types"] if tt["id"] == t["truck_type_id"]), "")
            t["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == t.get("vendor_id")), "")
            active_reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5)]
            t["current_requests"] = [{"id": r["id"], "request_number": r["request_number"], "status_id": r["status_id"],
                "status_name": next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), ""),
                "origin_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), ""),
                "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")} for r in active_reqs]
            hist = [h for h in _store["truck_request_history"] if h["truck_id"] == t["id"]]
            t["history_count"] = len(hist)
        if status: trucks = [t for t in trucks if t["status"] == status]
        return trucks
    q = """SELECT t.*, tt.name as truck_type_name, v.name as vendor_name,
        (SELECT COUNT(*) FROM truck_request_history WHERE truck_id=t.id) as history_count
        FROM trucks t LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
        LEFT JOIN vendors v ON t.vendor_id=v.id"""
    w, p = ["WHERE t.is_active=1"], []
    if status: w.append("t.status=%s"); p.append(status)
    trucks = db_q(f"{q} {' '.join(w)} ORDER BY t.plate_number", tuple(p))
    for t in trucks:
        t["current_requests"] = db_q("""SELECT tr.id, tr.request_number, tr.status_id, ts.name as status_name,
            po.name as origin_port_name, pd.name as destination_port_name
            FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
            LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
            WHERE tr.assigned_truck_id=%s AND tr.status_id NOT IN (4,5)""", (t["id"],))
    return trucks

@app.post("/api/trucks")
async def create_truck(request: Request):
    require_admin(request)
    body = await request.json()
    plate = body.get("plate_number", "").strip().upper()
    ttid = body.get("truck_type_id")
    vendor_id = body.get("vendor_id")
    if not plate or not ttid: raise HTTPException(400, "Plate and type required")
    if LOCAL_MODE:
        for t in _store["trucks"]:
            if t["plate_number"] == plate: raise HTTPException(400, "Plate exists")
        tid = nid("trucks")
        truck = {"id": tid, "plate_number": plate, "truck_type_id": ttid, "vendor_id": vendor_id, "driver_name": body.get("driver_name", ""), "driver_phone": body.get("driver_phone", ""), "status": "available", "is_active": True, "created_at": nows(), "updated_at": nows()}
        _store["trucks"].append(truck)
        return truck
    if db_1("SELECT id FROM trucks WHERE plate_number=%s", (plate,)): raise HTTPException(400, "Plate exists")
    tid = db_i("INSERT INTO trucks (plate_number,truck_type_id,vendor_id,driver_name,driver_phone) VALUES (%s,%s,%s,%s,%s)", (plate, ttid, vendor_id, body.get("driver_name", ""), body.get("driver_phone", "")))
    return db_1("SELECT * FROM trucks WHERE id=%s", (tid,))

@app.put("/api/trucks/{tid}")
async def update_truck(tid: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for t in _store["trucks"]:
            if t["id"] == tid:
                old_status = t.get("status")
                for k in ("plate_number", "truck_type_id", "vendor_id", "driver_name", "driver_phone", "status"):
                    if k in body: t[k] = body[k]
                t["updated_at"] = nows()
                if old_status == "assigned" and body.get("status") != "assigned":
                    pending_id = next((s["id"] for s in _store["truck_statuses"] if s["name"] == "Pending"), None)
                    if pending_id:
                        for r in _store["truck_requests"]:
                            if r.get("assigned_truck_id") == tid:
                                r["status_id"] = pending_id
                                r["assigned_truck_id"] = None
                                r["updated_by"] = request.headers.get("X-Forwarded-Email", "")
                                r["updated_at"] = nows()
                return row2d(t)
        raise HTTPException(404, "Not found")
    if "status" in body:
        cur = db_1("SELECT status FROM trucks WHERE id=%s", (tid,))
        old_status = cur.get("status") if cur else None
    sets, params = [], []
    for k in ("plate_number", "truck_type_id", "vendor_id", "driver_name", "driver_phone", "status"):
        if k in body: sets.append(f"{k}=%s"); params.append(body[k])
    if not sets: raise HTTPException(400, "Nothing to update")
    params.append(tid)
    db_x(f"UPDATE trucks SET {','.join(sets)} WHERE id=%s", tuple(params))
    if old_status == "assigned" and body.get("status") != "assigned":
        pending_st = db_1("SELECT id FROM truck_statuses WHERE name='Pending'")
        if pending_st:
            email = request.headers.get("X-Forwarded-Email", "")
            db_x("UPDATE truck_requests SET status_id=%s, assigned_truck_id=NULL, updated_by=%s, updated_at=NOW() WHERE assigned_truck_id=%s",
                 (pending_st["id"], email, tid))
    return db_1("SELECT * FROM trucks WHERE id=%s", (tid,))

@app.delete("/api/trucks/{tid}")
def delete_truck(tid: int, request: Request):
    require_admin(request)
    if LOCAL_MODE:
        _store["trucks"] = [t for t in _store["trucks"] if t["id"] != tid]
        return {"ok": True}
    db_x("UPDATE trucks SET is_active=0 WHERE id=%s", (tid,))
    return {"ok": True}

@app.get("/api/trucks/{tid}/history")
def truck_history(tid: int, request: Request):
    get_user(request)
    if LOCAL_MODE:
        hist = [h for h in _store["truck_request_history"] if h["truck_id"] == tid]
        for h in hist:
            h["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == h.get("origin_port_id")), "")
            h["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == h.get("destination_port_id")), "")
        return sorted(hist, key=lambda x: x.get("archived_at", ""), reverse=True)
    return db_q("""SELECT h.*, po.name as origin_port_name, pd.name as destination_port_name
        FROM truck_request_history h
        LEFT JOIN ports po ON h.origin_port_id=po.id LEFT JOIN ports pd ON h.destination_port_id=pd.id
        WHERE h.truck_id=%s ORDER BY h.archived_at DESC""", (tid,))

def archive_truck_requests(truck_id, email="system"):
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r.get("assigned_truck_id") == truck_id:
                _store["truck_request_history"].append({
                    "id": nid("truck_request_history"), "truck_id": truck_id,
                    "truck_request_id": r["id"], "request_number": r.get("request_number", ""),
                    "requestor_name": r.get("requestor_name", ""), "requestor_email": r.get("requestor_email", ""),
                    "origin_port_id": r.get("origin_port_id"), "destination_port_id": r.get("destination_port_id"),
                    "truck_type_id": r.get("truck_type_id"), "quantity": r.get("quantity", 0),
                    "weight_kg": r.get("weight_kg", 0), "volume_cbm": r.get("volume_cbm", 0),
                    "status_id": r.get("status_id"), "pickup_datetime": r.get("pickup_datetime"),
                    "archived_at": nows(), "archived_by": email})
        return
    reqs = db_q("SELECT id,request_number,requestor_name,requestor_email,origin_port_id,destination_port_id,truck_type_id,quantity,weight_kg,volume_cbm,status_id,pickup_datetime FROM truck_requests WHERE assigned_truck_id=%s", (truck_id,))
    for r in reqs:
        db_i("""INSERT INTO truck_request_history (truck_id,truck_request_id,request_number,requestor_name,requestor_email,
            origin_port_id,destination_port_id,truck_type_id,quantity,weight_kg,volume_cbm,status_id,pickup_datetime,archived_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (truck_id, r["id"], r["request_number"], r["requestor_name"], r["requestor_email"],
             r["origin_port_id"], r["destination_port_id"], r["truck_type_id"], r["quantity"], r["weight_kg"],
             r["volume_cbm"], r["status_id"], r["pickup_datetime"], email))

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
def dashboard(request: Request):
    get_user(request)
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        trucks = _store["trucks"]
        tc = sum(r.get("actual_cost", 0) or 0 for r in reqs)
        recent = [row2d(r) for r in reqs[-10:]][::-1]
        for r in recent:
            r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["status_color"] = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
        return {
            "total_requests": len(reqs),
            "pending_allocation": sum(1 for r in reqs if r.get("status_id") == 1),
            "allocated": sum(1 for r in reqs if r.get("status_id") == 2),
            "in_transit": sum(1 for r in reqs if r.get("status_id") == 3),
            "delivered": sum(1 for r in reqs if r.get("status_id") == 4),
            "cancelled": sum(1 for r in reqs if r.get("status_id") == 5),
            "total_cost": tc,
            "total_trucks": len(trucks),
            "available_trucks": sum(1 for t in trucks if t.get("status") == "available"),
            "busy_trucks": sum(1 for t in trucks if t.get("status") == "busy"),
            "recent_requests": recent,
        }
    stats = db_1("""SELECT COUNT(*) as total_requests,
        SUM(CASE WHEN status_id=1 THEN 1 ELSE 0 END) as pending_allocation,
        SUM(CASE WHEN status_id=2 THEN 1 ELSE 0 END) as allocated,
        SUM(CASE WHEN status_id=3 THEN 1 ELSE 0 END) as in_transit,
        SUM(CASE WHEN status_id=4 THEN 1 ELSE 0 END) as delivered,
        SUM(CASE WHEN status_id=5 THEN 1 ELSE 0 END) as cancelled,
        COALESCE(SUM(actual_cost),0) as total_cost FROM truck_requests""")
    ts = db_1("""SELECT COUNT(*) as total_trucks,
        SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) as available_trucks,
        SUM(CASE WHEN status='busy' THEN 1 ELSE 0 END) as busy_trucks FROM trucks WHERE is_active=1""")
    recent = db_q("""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color
        FROM truck_requests tr LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN truck_statuses ts ON tr.status_id=ts.id ORDER BY tr.created_at DESC LIMIT 10""")
    return {**(stats or {}), **(ts or {}), "recent_requests": recent}

# ---------------------------------------------------------------------------
# Truck Requests
# ---------------------------------------------------------------------------

@app.get("/api/requests")
def list_requests(request: Request, status_id: Optional[int] = None, account_id: Optional[int] = None,
    department_id: Optional[int] = None, origin_port_id: Optional[int] = None,
    destination_port_id: Optional[int] = None, truck_type_id: Optional[int] = None,
    vendor_id: Optional[int] = None, search: Optional[str] = None,
    booking_from: Optional[str] = None, booking_to: Optional[str] = None,
    pickup_from: Optional[str] = None, pickup_to: Optional[str] = None,
    sort_by: str = "created_at", sort_dir: str = "desc", page: int = 1, per_page: int = 50):

    if LOCAL_MODE:
        reqs = [row2d(r) for r in _store["truck_requests"]]
        for r in reqs:
            r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["status_color"] = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["truck_type_name"] = next((t["name"] for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), "")
            r["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == r.get("packaging_type_id")), "")
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == truck.get("vendor_id")),"") if truck else ""
            r["plate_number"] = truck["plate_number"] if truck else ""
            r["updated_by"] = r.get("updated_by", "")
            updater = next((u for u in _store["users"] if u.get("email") == r.get("updated_by")), None)
            r["updated_by_name"] = updater.get("name", "") if updater else r.get("updated_by", "")
            r["updated_by_email"] = r.get("updated_by", "")
            r["updated_at"] = r.get("updated_at", "")
            r["attachments"] = [row2d(a) for a in _store["attachments"] if a.get("truck_request_id") == r["id"]]
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                r["trip_id"] = compute_trip_id(truck_reqs, r["id"])
            else:
                r["trip_id"] = None
        if status_id: reqs = [r for r in reqs if r.get("status_id") == status_id]
        if account_id: reqs = [r for r in reqs if r.get("account_id") == account_id]
        if department_id: reqs = [r for r in reqs if r.get("department_id") == department_id]
        if origin_port_id: reqs = [r for r in reqs if r.get("origin_port_id") == origin_port_id]
        if destination_port_id: reqs = [r for r in reqs if r.get("destination_port_id") == destination_port_id]
        if truck_type_id: reqs = [r for r in reqs if r.get("truck_type_id") == truck_type_id]
        if vendor_id:
            def has_vid(r):
                truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
                return truck and truck.get("vendor_id") == vendor_id
            reqs = [r for r in reqs if has_vid(r)]
        if booking_from: reqs = [r for r in reqs if (r.get("booking_date") or "") >= booking_from]
        if booking_to: reqs = [r for r in reqs if (r.get("booking_date") or "") <= booking_to]
        if pickup_from: reqs = [r for r in reqs if (r.get("pickup_datetime") or "")[:10] >= pickup_from]
        if pickup_to: reqs = [r for r in reqs if (r.get("pickup_datetime") or "")[:10] <= pickup_to]
        if search:
            s = search.lower()
            reqs = [r for r in reqs if s in (r.get("request_number", "") + r.get("requestor_name", "") + r.get("requestor_email", "") + r.get("vendor_name", "") + r.get("plate_number", "") + (r.get("trip_id") or "")).lower()]
        if sort_by == "trip_id":
            reqs.sort(key=lambda x: x.get("trip_id") or "", reverse=(sort_dir == "desc"))
        else:
            reqs.sort(key=lambda x: x.get(sort_by, ""), reverse=(sort_dir == "desc"))
        total = len(reqs)
        start = (page - 1) * per_page
        return {"items": reqs[start:start + per_page], "total": total, "page": page, "per_page": per_page}

    wh, pa = ["1=1"], []
    if status_id: wh.append("tr.status_id=%s"); pa.append(status_id)
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if truck_type_id: wh.append("tr.truck_type_id=%s"); pa.append(truck_type_id)
    if vendor_id: wh.append("tk.vendor_id=%s"); pa.append(vendor_id)
    if booking_from: wh.append("tr.booking_date>=%s"); pa.append(booking_from)
    if booking_to: wh.append("tr.booking_date<=%s"); pa.append(booking_to)
    if pickup_from: wh.append("DATE(tr.pickup_datetime)>=%s"); pa.append(pickup_from)
    if pickup_to: wh.append("DATE(tr.pickup_datetime)<=%s"); pa.append(pickup_to)
    if search: wh.append("(tr.request_number LIKE %s OR tr.requestor_name LIKE %s OR v.name LIKE %s OR tk.plate_number LIKE %s)"); s = f"%{search}%"; pa.extend([s, s, s, s])
    ws = " AND ".join(wh)
    if sort_by not in ("created_at", "request_number", "pickup_datetime", "status_id", "account_name", "department_name", "origin_port_name", "destination_port_name", "truck_type_name", "packaging_type_name", "quantity", "vendor_name", "plate_number", "booking_date", "trip_id"):
        sort_by = "created_at"
    sort_map = {"account_name": "a.name", "department_name": "d.name", "origin_port_name": "po.name", "destination_port_name": "pd.name", "truck_type_name": "tt.name", "packaging_type_name": "pt.name", "quantity": "tr.quantity", "vendor_name": "v.name", "plate_number": "tk.plate_number", "booking_date": "tr.booking_date"}
    if sort_by == "trip_id":
        order_col = "tr.created_at"
    else:
        order_col = sort_map.get(sort_by, f"tr.{sort_by}")
    sd = "DESC" if sort_dir == "desc" else "ASC"
    total = (db_1(f"SELECT COUNT(*) as c FROM truck_requests tr WHERE {ws}", tuple(pa)) or {}).get("c", 0)
    pa.extend([per_page, (page - 1) * per_page])
    items = db_q(f"""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        tt.name as truck_type_name, pt.name as packaging_type_name,
        tk.plate_number, v.name as vendor_name, tr.updated_by, tr.updated_at,
        uu.name as updated_by_name, tr.updated_by as updated_by_email
        FROM truck_requests tr LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id LEFT JOIN ports po ON tr.origin_port_id=po.id
        LEFT JOIN ports pd ON tr.destination_port_id=pd.id LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN users uu ON tr.updated_by=uu.email
        WHERE {ws} ORDER BY {order_col} {sd} LIMIT %s OFFSET %s""", tuple(pa))
    for i in items: i["attachments"] = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (i["id"],))
    for i in items:
        if i.get("assigned_truck_id") and i.get("status_id") in (2, 3, 4, 5, 7):
            truck_reqs = db_q("SELECT id, request_number, status_id, drop_sequence FROM truck_requests WHERE assigned_truck_id=%s", (i["assigned_truck_id"],))
            i["trip_id"] = compute_trip_id(truck_reqs, i["id"])
        else:
            i["trip_id"] = None
    if sort_by == "trip_id":
        items.sort(key=lambda x: x.get("trip_id") or "", reverse=(sort_dir == "desc"))
    return {"items": items, "total": total, "page": page, "per_page": per_page}

@app.get("/api/requests/{rid}")
def get_request(rid: int, request: Request):
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == rid:
                res = row2d(r)
                res["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
                res["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
                res["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
                res["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
                res["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
                res["status_color"] = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
                res["truck_type_name"] = next((t["name"] for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), "")
                res["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == r.get("packaging_type_id")), "")
                res["attachments"] = [row2d(a) for a in _store["attachments"] if a.get("truck_request_id") == rid]
                return res
        raise HTTPException(404, "Not found")
    item = db_1("""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        tt.name as truck_type_name, pt.name as packaging_type_name
        FROM truck_requests tr LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id LEFT JOIN ports po ON tr.origin_port_id=po.id
        LEFT JOIN ports pd ON tr.destination_port_id=pd.id LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        WHERE tr.id=%s""", (rid,))
    if not item: raise HTTPException(404, "Not found")
    item["attachments"] = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (rid,))
    return item

@app.post("/api/requests")
async def create_request(request: Request):
    try:
        user = get_user(request)
        body = await request.json()
        rn = gen_req_no()
        for f in ("account_id", "department_id", "origin_port_id", "destination_port_id", "packaging_type_id"):
            if not body.get(f): raise HTTPException(400, f"{f} required")
        if body.get("quantity", 0) <= 0: raise HTTPException(400, "Quantity must be greater than 0")
        if body.get("origin_port_id") == body.get("destination_port_id"):
            raise HTTPException(400, "Origin port cannot be the same as destination port")
        booking_date = datetime.now().strftime("%Y-%m-%d")
        if LOCAL_MODE:
            rid = nid("truck_requests")
            req = {"id": rid, "request_number": rn, "requestor_email": user["email"], "requestor_name": user["name"],
                "account_id": body["account_id"], "department_id": body["department_id"],
                "origin_port_id": body["origin_port_id"], "destination_port_id": body["destination_port_id"],
                "pickup_datetime": body.get("pickup_datetime"), "delivery_datetime": body.get("delivery_datetime"),
                "call_datetime": body.get("call_datetime"), "customs_cleared_datetime": body.get("customs_cleared_datetime"),
                "booking_date": booking_date,
                "truck_type_id": body.get("truck_type_id"), "packaging_type_id": body.get("packaging_type_id"),
                "quantity": body.get("quantity", 0), "weight_kg": body.get("weight_kg", 0), "volume_cbm": body.get("volume_cbm", 0),
                "special_instructions": body.get("special_instructions", ""), "status_id": body.get("status_id", 1),
                "assigned_truck_id": None, "estimated_cost": body.get("estimated_cost", 0), "actual_cost": 0,
                "trip_date": None, "arrived_pickup_datetime": None, "start_loading_datetime": None,
                "end_loading_datetime": None, "arrived_dest_datetime": None, "start_unloading_datetime": None,
                "end_unloading_datetime": None, "foul_trip_reason": None,
                "created_at": nows(), "updated_at": nows()}
            _store["truck_requests"].append(req)
            pid = nid("pending_allocations")
            _store["pending_allocations"].append({"id": pid, "truck_request_id": rid, "suggested_truck_id": None, "suggestion_reason": "New request", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
            return row2d(req)
        rid = db_i("""INSERT INTO truck_requests (request_number,requestor_email,requestor_name,account_id,department_id,
            origin_port_id,destination_port_id,pickup_datetime,delivery_datetime,call_datetime,customs_cleared_datetime,booking_date,
            truck_type_id,packaging_type_id,quantity,weight_kg,volume_cbm,special_instructions,status_id,estimated_cost)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (rn, user["email"], user["name"], body["account_id"], body["department_id"],
             body["origin_port_id"], body["destination_port_id"], body.get("pickup_datetime"), body.get("delivery_datetime"),
             body.get("call_datetime"), body.get("customs_cleared_datetime"), booking_date,
             body.get("truck_type_id"), body.get("packaging_type_id"), body.get("quantity", 0), body.get("weight_kg", 0),
             body.get("volume_cbm", 0), body.get("special_instructions", ""), body.get("status_id", 1), body.get("estimated_cost", 0)))
        db_i("INSERT INTO pending_allocations (truck_request_id,suggestion_reason) VALUES (%s,'New request')", (rid,))
        return db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))
    except HTTPException:
        raise
    except Exception as e:
        print(f"CREATE REQUEST ERROR: {e}")
        import traceback; traceback.print_exc()
        raise HTTPException(500, str(e))

@app.put("/api/requests/{rid}")
async def update_request(rid: int, request: Request):
    user = get_user(request)
    body = await request.json()
    body["updated_by"] = user.get("email", "")
    body["updated_at"] = nows()
    fields = ("account_id", "department_id", "origin_port_id", "destination_port_id", "pickup_datetime",
              "delivery_datetime", "call_datetime", "customs_cleared_datetime", "booking_date",
              "truck_type_id", "packaging_type_id", "quantity", "weight_kg", "volume_cbm",
              "special_instructions", "status_id", "assigned_truck_id", "estimated_cost", "actual_cost",
              "trip_date", "arrived_pickup_datetime", "start_loading_datetime", "end_loading_datetime",
              "arrived_dest_datetime", "start_unloading_datetime", "end_unloading_datetime", "foul_trip_reason",
              "drop_sequence", "updated_by", "updated_at")
    new_status = body.get("status_id")
    if new_status == 4:
        validate_delivered_chronology(body)
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == rid:
                old_status = r.get("status_id")
                if new_status and old_status: validate_status_transition(old_status, new_status)
                for k in fields:
                    if k in body: r[k] = body[k]
                if new_status == 1 and r.get("assigned_truck_id"):
                    old_tid = r["assigned_truck_id"]
                    reverted_seq = r.get("drop_sequence")
                    r["assigned_truck_id"] = None
                    r["drop_sequence"] = None
                    r["estimated_cost"] = 0
                    r["actual_cost"] = 0
                    r["truck_type_id"] = None
                    has_pa = any(pa["truck_request_id"] == rid and pa.get("is_accepted") is None for pa in _store["pending_allocations"])
                    if not has_pa:
                        pid = nid("pending_allocations")
                        _store["pending_allocations"].append({"id": pid, "truck_request_id": rid, "suggested_truck_id": None, "suggestion_reason": "Reverted to pending", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
                    if reverted_seq:
                        for x in _store["truck_requests"]:
                            if x.get("assigned_truck_id") == old_tid and x.get("drop_sequence") is not None and x["drop_sequence"] > reverted_seq:
                                x["drop_sequence"] -= 1
                    remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == old_tid and x.get("status_id") not in (4, 5)]
                    if not remaining:
                        for t in _store["trucks"]:
                            if t["id"] == old_tid: t["status"] = "available"; break
                    else:
                        recalculate_trip_rates(old_tid)
                if new_status == 4 and r.get("assigned_truck_id"):
                    if r.get("actual_cost", 0) == 0: r["actual_cost"] = r.get("estimated_cost", 0)
                    tid = r["assigned_truck_id"]
                    remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5)]
                    if not remaining:
                        email = request.headers.get("X-Forwarded-Email", "")
                        archive_truck_requests(tid, email)
                        for t in _store["trucks"]:
                            if t["id"] == tid: t["status"] = "available"; break
                        for x in _store["truck_requests"]:
                            if x.get("assigned_truck_id") == tid: x["assigned_truck_id"] = None
                    else:
                        recalculate_trip_rates(tid)
                if new_status == 7:
                    if r.get("actual_cost", 0) == 0: r["actual_cost"] = r.get("estimated_cost", 0)
                return row2d(r)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for k in fields:
        if k in body: sets.append(f"{k}=%s"); params.append(body[k])
    if not sets: raise HTTPException(400, "Nothing to update")
    if new_status:
        cur = db_1("SELECT status_id FROM truck_requests WHERE id=%s", (rid,))
        if cur and cur.get("status_id"): validate_status_transition(cur["status_id"], new_status)
    params.append(rid)
    db_x(f"UPDATE truck_requests SET {','.join(sets)} WHERE id=%s", tuple(params))
    if new_status == 1:
        req = db_1("SELECT assigned_truck_id, drop_sequence FROM truck_requests WHERE id=%s", (rid,))
        if req and req.get("assigned_truck_id"):
            old_tid = req["assigned_truck_id"]
            reverted_seq = req.get("drop_sequence")
            db_x("UPDATE truck_requests SET assigned_truck_id=NULL, drop_sequence=NULL, estimated_cost=0, actual_cost=0, truck_type_id=NULL WHERE id=%s", (rid,))
            if reverted_seq:
                db_x("UPDATE truck_requests SET drop_sequence=drop_sequence-1 WHERE assigned_truck_id=%s AND drop_sequence>%s", (old_tid, reverted_seq))
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (old_tid,))
            if remaining and remaining.get("c", 0) == 0:
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (old_tid,))
            else:
                recalculate_trip_rates(old_tid)
        existing = db_1("SELECT id FROM pending_allocations WHERE truck_request_id=%s AND is_accepted IS NULL", (rid,))
        if not existing:
            db_i("INSERT INTO pending_allocations (truck_request_id,suggestion_reason) VALUES (%s,'Reverted to pending')", (rid,))
    if new_status == 4:
        db_x("UPDATE truck_requests SET actual_cost=estimated_cost WHERE id=%s AND actual_cost=0", (rid,))
        req = db_1("SELECT assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
        if req and req.get("assigned_truck_id"):
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (req["assigned_truck_id"],))
            if remaining and remaining.get("c", 0) == 0:
                email = request.headers.get("X-Forwarded-Email", "")
                archive_truck_requests(req["assigned_truck_id"], email)
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (req["assigned_truck_id"],))
                db_x("UPDATE truck_requests SET assigned_truck_id=NULL WHERE assigned_truck_id=%s", (req["assigned_truck_id"],))
            else:
                recalculate_trip_rates(req["assigned_truck_id"])
    if new_status == 7:
        db_x("UPDATE truck_requests SET actual_cost=estimated_cost WHERE id=%s AND actual_cost=0", (rid,))
    return db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))

@app.delete("/api/requests/{rid}")
def delete_request(rid: int, request: Request):
    get_user(request)
    if LOCAL_MODE:
        req = next((r for r in _store["truck_requests"] if r["id"] == rid), None)
        if not req: raise HTTPException(404, "Not found")
        if req.get("status_id") and req["status_id"] != 1: raise HTTPException(400, "Only pending requests can be deleted")
        truck_id = req.get("assigned_truck_id")
        reverted_seq = req.get("drop_sequence")
        _store["truck_requests"] = [r for r in _store["truck_requests"] if r["id"] != rid]
        _store["attachments"] = [a for a in _store["attachments"] if a.get("truck_request_id") != rid]
        _store["pending_allocations"] = [p for p in _store["pending_allocations"] if p.get("truck_request_id") != rid]
        if truck_id:
            if reverted_seq:
                for x in _store["truck_requests"]:
                    if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["drop_sequence"] > reverted_seq:
                        x["drop_sequence"] -= 1
            remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("status_id") not in (4, 5)]
            if not remaining:
                for t in _store["trucks"]:
                    if t["id"] == truck_id: t["status"] = "available"; break
            else:
                recalculate_trip_rates(truck_id)
        return {"ok": True}
    req = db_1("SELECT assigned_truck_id, drop_sequence, status_id FROM truck_requests WHERE id=%s", (rid,))
    if not req: raise HTTPException(404, "Not found")
    if req.get("status_id") and req["status_id"] != 1: raise HTTPException(400, "Only pending requests can be deleted")
    truck_id = req.get("assigned_truck_id")
    reverted_seq = req.get("drop_sequence")
    if reverted_seq:
        db_x("UPDATE truck_requests SET drop_sequence=drop_sequence-1 WHERE assigned_truck_id=%s AND drop_sequence>%s", (truck_id, reverted_seq))
    db_x("DELETE FROM truck_requests WHERE id=%s", (rid,))
    if truck_id:
        remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (truck_id,))
        if remaining and remaining.get("c", 0) == 0:
            db_x("UPDATE trucks SET status='available' WHERE id=%s", (truck_id,))
        else:
            recalculate_trip_rates(truck_id)
    return {"ok": True}

@app.put("/api/requests/{rid}/drop-sequence")
async def update_drop_sequence(rid: int, request: Request):
    user = get_user(request)
    body = await request.json()
    new_seq = body.get("drop_sequence")
    if not new_seq or new_seq < 1: raise HTTPException(400, "drop_sequence required and must be >= 1")
    if LOCAL_MODE:
        req = next((r for r in _store["truck_requests"] if r["id"] == rid), None)
        if not req or not req.get("assigned_truck_id"): raise HTTPException(400, "Request not allocated to a truck")
        if req.get("status_id") != 2: raise HTTPException(400, "Drop # can only be rearranged for Allocated requests")
        truck_id = req["assigned_truck_id"]
        old_seq = req.get("drop_sequence")
        if old_seq == new_seq: return {"ok": True}
        existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["id"] != rid]
        if new_seq in existing_seqs:
            for x in _store["truck_requests"]:
                if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["id"] != rid:
                    if old_seq and old_seq < new_seq:
                        if x["drop_sequence"] > old_seq and x["drop_sequence"] <= new_seq:
                            x["drop_sequence"] -= 1
                    elif old_seq and old_seq > new_seq:
                        if x["drop_sequence"] >= new_seq and x["drop_sequence"] < old_seq:
                            x["drop_sequence"] += 1
        req["drop_sequence"] = new_seq
        recalculate_trip_rates(truck_id)
        return {"ok": True}
    req = db_1("SELECT assigned_truck_id, drop_sequence, status_id FROM truck_requests WHERE id=%s", (rid,))
    if not req or not req.get("assigned_truck_id"): raise HTTPException(400, "Request not allocated to a truck")
    if req.get("status_id") != 2: raise HTTPException(400, "Drop # can only be rearranged for Allocated requests")
    truck_id = req["assigned_truck_id"]
    old_seq = req.get("drop_sequence")
    if old_seq == new_seq: return {"ok": True}
    existing = db_q("SELECT id, drop_sequence FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence IS NOT NULL AND id!=%s", (truck_id, rid))
    if new_seq in [e["drop_sequence"] for e in existing]:
        if old_seq and old_seq < new_seq:
            db_x("UPDATE truck_requests SET drop_sequence=drop_sequence-1 WHERE assigned_truck_id=%s AND drop_sequence>%s AND drop_sequence<=%s AND id!=%s", (truck_id, old_seq, new_seq, rid))
        elif old_seq and old_seq > new_seq:
            db_x("UPDATE truck_requests SET drop_sequence=drop_sequence+1 WHERE assigned_truck_id=%s AND drop_sequence>=%s AND drop_sequence<%s AND id!=%s", (truck_id, new_seq, old_seq, rid))
    db_x("UPDATE truck_requests SET drop_sequence=%s WHERE id=%s", (new_seq, rid))
    recalculate_trip_rates(truck_id)
    return {"ok": True}

# ---------------------------------------------------------------------------
# Pending Allocations
# ---------------------------------------------------------------------------

@app.get("/api/pending-allocations")
def list_pending(request: Request):
    if LOCAL_MODE:
        result = []
        for pa in _store["pending_allocations"]:
            if pa.get("is_accepted") is not None: continue
            req = next((r for r in _store["truck_requests"] if r["id"] == pa["truck_request_id"]), None)
            if not req: continue
            item = {**row2d(pa)}
            item.update({"request_number": req.get("request_number", ""), "requestor_name": req.get("requestor_name", ""),
                "pickup_datetime": req.get("pickup_datetime", ""), "call_datetime": req.get("call_datetime", ""),
                "origin_port_id": req.get("origin_port_id"),
                "destination_port_id": req.get("destination_port_id"), "truck_type_id": req.get("truck_type_id"),
                "account_id": req.get("account_id"), "department_id": req.get("department_id"),
                "packaging_type_id": req.get("packaging_type_id"), "quantity": req.get("quantity", 0),
                "weight_kg": req.get("weight_kg", 0), "volume_cbm": req.get("volume_cbm", 0),
                "origin_port_name": next((p["name"] for p in _store["ports"] if p["id"] == req.get("origin_port_id")), ""),
                "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == req.get("destination_port_id")), ""),
                "department_name": next((d["name"] for d in _store["departments"] if d["id"] == req.get("department_id")), ""),
                "packaging_type_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == req.get("packaging_type_id")), ""),
                "truck_type_name": next((t["name"] for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), ""),
                "max_capacity_kg": next((t.get("max_capacity_kg", 0) for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), 0),
                "max_capacity_cbm": next((t.get("max_capacity_cbm", 0) for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), 0)})
            same = [r for r in _store["truck_requests"] if r["id"] != req["id"] and r.get("origin_port_id") == req.get("origin_port_id") and r.get("status_id") == 1]
            sug = []
            for sr in same:
                try:
                    dt1 = datetime.fromisoformat(str(req.get("pickup_datetime", "")).replace("Z", "+00:00"))
                    dt2 = datetime.fromisoformat(str(sr.get("pickup_datetime", "")).replace("Z", "+00:00"))
                    if abs((dt1 - dt2).total_seconds()) <= 14400:
                        sug.append({"request_id": sr["id"], "request_number": sr.get("request_number", ""), "requestor_name": sr.get("requestor_name", ""), "pickup_datetime": str(sr.get("pickup_datetime", "")),
                            "packaging_type_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == sr.get("packaging_type_id")), ""),
                            "quantity": sr.get("quantity", 0), "weight_kg": sr.get("weight_kg", 0), "volume_cbm": sr.get("volume_cbm", 0),
                            "reason": f"Same origin, similar pickup time"})
                except: pass
            item["consolidation_suggestions"] = sug
            avail = [t for t in _store["trucks"] if t.get("status") in ("available", "assigned")]
            in_transit_truck_ids = set(r.get("assigned_truck_id") for r in _store["truck_requests"] if r.get("status_id") == 3 and r.get("assigned_truck_id"))
            avail = [t for t in avail if t["id"] not in in_transit_truck_ids]
            truck_list = []
            for t in avail:
                cur_reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5)]
                truck_origins = list(set(r.get("origin_port_id") for r in cur_reqs if r.get("origin_port_id")))
                ttcaps = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] == t.get("truck_type_id")]
                pkg_counts = {}
                for r in cur_reqs:
                    pid = r.get("packaging_type_id")
                    pkg_counts[pid] = pkg_counts.get(pid, 0) + r.get("quantity", 0)
                majority_pkg = max(pkg_counts, key=pkg_counts.get) if pkg_counts else req.get("packaging_type_id")
                cur_qty = pkg_counts.get(majority_pkg, 0)
                cap = next((c["max_quantity"] for c in ttcaps if c["packaging_type_id"] == majority_pkg), 0)
                remaining = (cap - cur_qty) if cap > 0 else 999
                vendor_name = next((v["name"] for v in _store["vendors"] if v["id"] == t.get("vendor_id")), "")
                rate_match = next((r for r in _store["vendor_rates"]
                    if r.get("vendor_id") == t.get("vendor_id") and r.get("truck_type_id") == t.get("truck_type_id")
                    and r.get("origin_port_id") == req.get("origin_port_id")
                    and r.get("is_active", True)), None)
                rate_per_trip = rate_match.get("rate_per_trip", 0) if rate_match else 0
                default_rate = rate_match.get("default_rate", 0) if rate_match else 0
                truck_list.append({"id": t["id"], "plate_number": t["plate_number"],
                    "vendor_name": vendor_name,
                    "vendor_id": t.get("vendor_id"),
                    "truck_type_id": t.get("truck_type_id"),
                    "truck_type_name": next((tt["name"] for tt in _store["truck_types"] if tt["id"] == t.get("truck_type_id")), ""),
                    "status": t.get("status"),
                    "current_qty": cur_qty, "max_qty": cap, "remaining_qty": remaining,
                    "assigned_origins": truck_origins,
                    "rate_per_trip": rate_per_trip, "default_rate": default_rate,
                    "driver_name": t.get("driver_name", ""), "driver_phone": t.get("driver_phone", ""),
                    "majority_pkg_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == majority_pkg), ""),
                    "pkg_capacities": {str(c["packaging_type_id"]): {"max": c["max_quantity"], "current": pkg_counts.get(c["packaging_type_id"], 0)} for c in ttcaps},
                    "current_drops": [{"request_id": r["id"], "request_number": r.get("request_number",""), "drop_sequence": r.get("drop_sequence"), "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")} for r in cur_reqs if r.get("drop_sequence")]})
            truck_list.sort(key=lambda x: x["rate_per_trip"] if x["rate_per_trip"] > 0 else 999999)
            item["available_trucks"] = truck_list
            result.append(item)
        return result
    rows = db_q("""SELECT pa.*, tr.request_number, tr.requestor_name, tr.pickup_datetime, tr.call_datetime,
        tr.origin_port_id, tr.destination_port_id, tr.truck_type_id, tr.account_id, tr.department_id,
        tr.packaging_type_id, tr.quantity, tr.weight_kg, tr.volume_cbm,
        po.name as origin_port_name, pd.name as destination_port_name, d.name as department_name,
        pt.name as packaging_type_name, tt.name as truck_type_name,
        tt.max_capacity_kg, tt.max_capacity_cbm
        FROM pending_allocations pa JOIN truck_requests tr ON pa.truck_request_id=tr.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        WHERE pa.is_accepted IS NULL ORDER BY pa.created_at DESC""")
    for item in rows:
        same = db_q("""SELECT id, request_number, requestor_name, pickup_datetime, quantity, weight_kg, volume_cbm, packaging_type_id
            FROM truck_requests WHERE id!=%s AND origin_port_id=%s AND status_id=1
            AND ABS(TIMESTAMPDIFF(HOUR, pickup_datetime, %s))<=4""", (item["truck_request_id"], item["origin_port_id"], item["pickup_datetime"]))
        for s in same:
            s["packaging_type_name"] = next((p["name"] for p in db_q("SELECT name FROM packaging_types WHERE id=%s", (s["packaging_type_id"],))), "")
        item["consolidation_suggestions"] = [{"request_id": s["id"], "request_number": s["request_number"], "requestor_name": s["requestor_name"], "pickup_datetime": str(s["pickup_datetime"]), "packaging_type_name": s.get("packaging_type_name", ""), "quantity": s.get("quantity", 0), "weight_kg": s.get("weight_kg", 0), "volume_cbm": s.get("volume_cbm", 0), "reason": f"Same origin, similar pickup time"} for s in same]
        avail_trucks = db_q("""SELECT t.id,t.plate_number,t.truck_type_id,t.status,v.name as vendor_name,tt.name as truck_type_name,t.driver_name,t.driver_phone
            FROM trucks t LEFT JOIN vendors v ON t.vendor_id=v.id LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
            WHERE t.status IN ('available','assigned') AND t.is_active=1
            AND t.id NOT IN (SELECT assigned_truck_id FROM truck_requests WHERE status_id=3 AND assigned_truck_id IS NOT NULL)""")
        for at in avail_trucks:
            at_ttcaps = db_q("SELECT packaging_type_id, max_quantity FROM truck_type_capacities WHERE truck_type_id=%s", (at["truck_type_id"],))
            pkg_rows = db_q("SELECT packaging_type_id, SUM(quantity) as total FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5) GROUP BY packaging_type_id", (at["id"],))
            pkg_counts = {r["packaging_type_id"]: r["total"] for r in pkg_rows}
            majority_pkg = max(pkg_counts, key=pkg_counts.get) if pkg_counts else item.get("packaging_type_id")
            cur_qty = pkg_counts.get(majority_pkg, 0)
            cap = next((c["max_quantity"] for c in at_ttcaps if c["packaging_type_id"] == majority_pkg), 0)
            at["current_qty"] = cur_qty
            at["max_qty"] = cap
            at["remaining_qty"] = (cap - cur_qty) if cap > 0 else 999
            at["majority_pkg_name"] = next((p["name"] for p in db_q("SELECT name FROM packaging_types WHERE id=%s", (majority_pkg,))), "")
            at["pkg_capacities"] = {str(c["packaging_type_id"]): {"max": c["max_quantity"], "current": pkg_counts.get(c["packaging_type_id"], 0)} for c in at_ttcaps}
            origins = db_q("SELECT DISTINCT origin_port_id FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (at["id"],))
            at["assigned_origins"] = [o["origin_port_id"] for o in origins if o.get("origin_port_id")]
            rate_row = db_1("""SELECT rate_per_trip, default_rate FROM vendor_rates
                WHERE vendor_id=(SELECT vendor_id FROM trucks WHERE id=%s) AND truck_type_id=%s AND origin_port_id=%s AND is_active=1 LIMIT 1""",
                (at["id"], at["truck_type_id"], item["origin_port_id"]))
            at["rate_per_trip"] = rate_row.get("rate_per_trip", 0) if rate_row else 0
            at["default_rate"] = rate_row.get("default_rate", 0) if rate_row else 0
            at["current_drops"] = db_q("""SELECT tr.id as request_id, tr.request_number, tr.drop_sequence, pd.name as destination_port_name
                FROM truck_requests tr LEFT JOIN ports pd ON tr.destination_port_id=pd.id
                WHERE tr.assigned_truck_id=%s AND tr.status_id NOT IN (4,5) AND tr.drop_sequence IS NOT NULL ORDER BY tr.drop_sequence""", (at["id"],))
        avail_trucks.sort(key=lambda x: x["rate_per_trip"] if x.get("rate_per_trip", 0) > 0 else 999999)
        item["available_trucks"] = avail_trucks
    return rows

@app.post("/api/pending-allocations/{pid}/allocate")
async def allocate(pid: int, request: Request):
    user = get_user(request)
    body = await request.json()
    truck_id = body.get("truck_id")
    consolidate_pa_ids = body.get("consolidate_request_ids", [])
    if not truck_id: raise HTTPException(400, "truck_id required")
    if LOCAL_MODE:
        truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
        for pa in _store["pending_allocations"]:
            if pa["id"] == pid:
                pa["suggested_truck_id"] = truck_id; pa["is_accepted"] = True; pa["allocated_by"] = user["email"]; pa["allocated_at"] = nows()
                for t in _store["trucks"]:
                    if t["id"] == truck_id: t["status"] = "assigned"; break
                for r in _store["truck_requests"]:
                    if r["id"] == pa["truck_request_id"]:
                        r["assigned_truck_id"] = truck_id; r["status_id"] = 2; r["updated_by"] = user["email"]; r["updated_at"] = nows(); r["truck_type_id"] = truck.get("truck_type_id")
                        req_drop_seq = body.get("drop_sequence")
                        if not req_drop_seq:
                            existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["id"] != r["id"]]
                            req_drop_seq = (max(existing_seqs) + 1) if existing_seqs else 1
                        if req_drop_seq:
                            existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["id"] != r["id"]]
                            if req_drop_seq in existing_seqs:
                                for x in _store["truck_requests"]:
                                    if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["drop_sequence"] >= req_drop_seq and x["id"] != r["id"]:
                                        x["drop_sequence"] += 1
                            r["drop_sequence"] = req_drop_seq
                        rate_match = find_best_rate(truck.get("vendor_id"), truck.get("truck_type_id"), r.get("origin_port_id"), r.get("destination_port_id"))
                        if rate_match: r["estimated_cost"] = compute_rate(rate_match, r.get("destination_port_id"))
                        primary_dest_id = r.get("destination_port_id")
                        break
                for cpid in consolidate_pa_ids:
                    cpa = next((p for p in _store["pending_allocations"] if p["id"] == cpid), None)
                    if not cpa: continue
                    crid = cpa["truck_request_id"]
                    for r2 in _store["truck_requests"]:
                        if r2["id"] == crid:
                            r2["assigned_truck_id"] = truck_id; r2["status_id"] = 2; r2["updated_by"] = user["email"]; r2["updated_at"] = nows(); r2["truck_type_id"] = truck.get("truck_type_id")
                            consol_seqs = body.get("consolidate_drop_sequences", {})
                            consol_drop_seq = consol_seqs.get(str(cpid)) or consol_seqs.get(cpid)
                            if consol_drop_seq:
                                existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["id"] != r2["id"]]
                                if consol_drop_seq in existing_seqs:
                                    for x in _store["truck_requests"]:
                                        if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["drop_sequence"] >= consol_drop_seq and x["id"] != r2["id"]:
                                            x["drop_sequence"] += 1
                                r2["drop_sequence"] = consol_drop_seq
                            rate_match2 = find_best_rate(truck.get("vendor_id"), truck.get("truck_type_id"), r2.get("origin_port_id"), primary_dest_id)
                            if rate_match2: r2["estimated_cost"] = compute_rate(rate_match2, r2.get("destination_port_id"))
                            break
                    cpa["suggested_truck_id"] = truck_id; cpa["is_accepted"] = True; cpa["allocated_by"] = user["email"]; cpa["allocated_at"] = nows()
                recalculate_trip_rates(truck_id)
                return {"ok": True}
        raise HTTPException(404, "Not found")
    db_x("UPDATE pending_allocations SET suggested_truck_id=%s,is_accepted=1,allocated_by=%s,allocated_at=NOW() WHERE id=%s", (truck_id, user["email"], pid))
    db_x("UPDATE trucks SET status='assigned' WHERE id=%s", (truck_id,))
    pa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (pid,))
    if pa:
        tr = db_1("SELECT origin_port_id, destination_port_id, truck_type_id FROM truck_requests WHERE id=%s", (pa["truck_request_id"],))
        truck = db_1("SELECT vendor_id, truck_type_id FROM trucks WHERE id=%s", (truck_id,))
        rate = None
        if tr and truck:
            rate = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND destination_port_id=%s AND is_active=1", (truck["vendor_id"], truck["truck_type_id"], tr["origin_port_id"], tr.get("destination_port_id")))
            if not rate:
                rate = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND is_active=1", (truck["vendor_id"], truck["truck_type_id"], tr["origin_port_id"]))
        est = compute_rate(rate, tr.get("destination_port_id")) if rate and tr else 0
        primary_dest_id = tr.get("destination_port_id") if tr else None
        req_drop_seq = body.get("drop_sequence")
        if not req_drop_seq:
            max_seq = db_1("SELECT MAX(drop_sequence) as max_seq FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence IS NOT NULL", (truck_id,))
            req_drop_seq = (max_seq["max_seq"] + 1) if max_seq and max_seq.get("max_seq") else 1
        drop_seq_sql = ""
        drop_seq_params = []
        if req_drop_seq:
            existing = db_1("SELECT drop_sequence FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence=%s", (truck_id, req_drop_seq))
            if existing:
                db_x("UPDATE truck_requests SET drop_sequence=drop_sequence+1 WHERE assigned_truck_id=%s AND drop_sequence>=%s", (truck_id, req_drop_seq))
            drop_seq_sql = ", drop_sequence=%s"
            drop_seq_params = [req_drop_seq]
        db_x(f"UPDATE truck_requests SET assigned_truck_id=%s,status_id=2,updated_by=%s,estimated_cost=%s,truck_type_id=%s,updated_at=NOW(){drop_seq_sql} WHERE id=%s",
             (truck_id, user["email"], est, truck["truck_type_id"])+tuple(drop_seq_params)+(pa["truck_request_id"],))
    for cpid in consolidate_pa_ids:
        cpa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (cpid,))
        if not cpa: continue
        crid = cpa["truck_request_id"]
        ctr = db_1("SELECT origin_port_id, destination_port_id, truck_type_id FROM truck_requests WHERE id=%s", (crid,))
        rate2 = None
        if ctr and truck:
            rate2 = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND destination_port_id=%s AND is_active=1", (truck["vendor_id"], truck["truck_type_id"], ctr["origin_port_id"], primary_dest_id))
            if not rate2:
                rate2 = db_1("SELECT rate_per_trip, default_rate, destination_drops, destination_port_id FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND is_active=1", (truck["vendor_id"], truck["truck_type_id"], ctr["origin_port_id"]))
        est2 = compute_rate(rate2, ctr.get("destination_port_id")) if rate2 and ctr else 0
        consol_seqs = body.get("consolidate_drop_sequences", {})
        consol_drop_seq = consol_seqs.get(str(cpid)) or consol_seqs.get(cpid)
        c_drop_seq_sql = ""
        c_drop_seq_params = []
        if consol_drop_seq:
            c_existing = db_1("SELECT drop_sequence FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence=%s", (truck_id, consol_drop_seq))
            if c_existing:
                db_x("UPDATE truck_requests SET drop_sequence=drop_sequence+1 WHERE assigned_truck_id=%s AND drop_sequence>=%s", (truck_id, consol_drop_seq))
            c_drop_seq_sql = ", drop_sequence=%s"
            c_drop_seq_params = [consol_drop_seq]
        db_x(f"UPDATE truck_requests SET assigned_truck_id=%s,status_id=2,updated_by=%s,estimated_cost=%s,truck_type_id=%s,updated_at=NOW(){c_drop_seq_sql} WHERE id=%s",
             (truck_id, user["email"], est2, truck["truck_type_id"])+tuple(c_drop_seq_params)+(crid,))
        db_x("UPDATE pending_allocations SET suggested_truck_id=%s,is_accepted=1,allocated_by=%s,allocated_at=NOW() WHERE id=%s", (truck_id, user["email"], cpid))
    recalculate_trip_rates(truck_id)
    return {"ok": True}

@app.post("/api/pending-allocations/{pid}/reject")
async def reject_alloc(pid: int, request: Request):
    user = get_user(request)
    body = await request.json()
    reason = body.get("reason", "Rejected")
    if LOCAL_MODE:
        for pa in _store["pending_allocations"]:
            if pa["id"] == pid:
                pa["is_accepted"] = False; pa["allocated_by"] = user["email"]; pa["allocated_at"] = nows(); pa["suggestion_reason"] = reason
                for r in _store["truck_requests"]:
                    if r["id"] == pa["truck_request_id"]: r["status_id"] = 5; break
                return {"ok": True}
        raise HTTPException(404, "Not found")
    db_x("UPDATE pending_allocations SET is_accepted=0,allocated_by=%s,allocated_at=NOW(),suggestion_reason=%s WHERE id=%s", (user["email"], reason, pid))
    pa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (pid,))
    if pa: db_x("UPDATE truck_requests SET status_id=5 WHERE id=%s", (pa["truck_request_id"],))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

@app.post("/api/requests/{rid}/attachments")
async def upload_att(rid: int, request: Request, file: UploadFile = File(...)):
    user = get_user(request)
    if LOCAL_MODE:
        existing = [a for a in _store["attachments"] if a.get("truck_request_id") == rid]
        if len(existing) >= 8: raise HTTPException(400, "Max 8 attachments")
        content = await file.read()
        if sum(a.get("file_size", 0) for a in existing) + len(content) > 25 * 1024 * 1024:
            raise HTTPException(400, "Max 25MB total")
        fid = uuid.uuid4().hex
        ext = os.path.splitext(file.filename or "")[1]
        fn = f"{fid}{ext}"
        fp = os.path.join(_store["_upload"], fn)
        with open(fp, "wb") as f: f.write(content)
        aid = nid("attachments")
        att = {"id": aid, "truck_request_id": rid, "filename": fn, "original_filename": file.filename or "unknown", "file_size": len(content), "file_type": file.content_type or "", "storage_path": fp, "uploaded_by": user["email"], "created_at": nows()}
        _store["attachments"].append(att)
        return row2d(att)
    existing = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (rid,))
    if len(existing) >= 8: raise HTTPException(400, "Max 8 attachments")
    content = await file.read()
    if sum(a.get("file_size", 0) for a in existing) + len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "Max 25MB total")
    fid = uuid.uuid4().hex
    ext = os.path.splitext(file.filename or "")[1]
    fn = f"{fid}{ext}"
    fp = os.path.join(_store["_upload"], fn)
    with open(fp, "wb") as f: f.write(content)
    aid = db_i("""INSERT INTO truck_request_attachments (truck_request_id,filename,original_filename,file_size,file_type,storage_path,uploaded_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s)""", (rid, fn, file.filename or "unknown", len(content), file.content_type or "", fp, user["email"]))
    return db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))

@app.get("/api/attachments/{aid}/download")
def download_att(aid: int, request: Request):
    if LOCAL_MODE:
        att = next((a for a in _store["attachments"] if a["id"] == aid), None)
        if not att: raise HTTPException(404, "Not found")
        fp = att.get("storage_path", "")
        if not os.path.exists(fp): raise HTTPException(404, "File missing")
        return FileResponse(fp, filename=att["original_filename"], media_type=att.get("file_type"))
    att = db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))
    if not att: raise HTTPException(404, "Not found")
    fp = att.get("storage_path", "")
    if not os.path.exists(fp): raise HTTPException(404, "File missing")
    return FileResponse(fp, filename=att["original_filename"], media_type=att.get("file_type"))

@app.delete("/api/attachments/{aid}")
def delete_att(aid: int, request: Request):
    get_user(request)
    if LOCAL_MODE:
        att = next((a for a in _store["attachments"] if a["id"] == aid), None)
        if att and os.path.exists(att.get("storage_path", "")): os.remove(att["storage_path"])
        _store["attachments"] = [a for a in _store["attachments"] if a["id"] != aid]
        return {"ok": True}
    att = db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))
    if att and os.path.exists(att.get("storage_path", "")): os.remove(att["storage_path"])
    db_x("DELETE FROM truck_request_attachments WHERE id=%s", (aid,))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Vendor Rates
# ---------------------------------------------------------------------------

@app.get("/api/vendor-rates")
def list_rates(request: Request, vendor_name: Optional[str] = None, origin_port_id: Optional[int] = None, destination_port_id: Optional[int] = None):
    get_user(request)
    if LOCAL_MODE:
        rates = [row2d(r) for r in _store["vendor_rates"]]
        for r in rates:
            r["truck_type_name"] = next((t["name"] for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
        if vendor_name: rates = [r for r in rates if vendor_name.lower() in (r.get("vendor_name") or "").lower()]
        if origin_port_id: rates = [r for r in rates if r.get("origin_port_id") == origin_port_id]
        if destination_port_id: rates = [r for r in rates if r.get("destination_port_id") == destination_port_id]
        return rates
    wh, pa = ["vr.is_active=1"], []
    if vendor_name: wh.append("vr.vendor_name LIKE %s"); pa.append(f"%{vendor_name}%")
    if origin_port_id: wh.append("vr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("vr.destination_port_id=%s"); pa.append(destination_port_id)
    ws = " AND ".join(wh)
    return db_q(f"""SELECT vr.*, tt.name as truck_type_name, po.name as origin_port_name, pd.name as destination_port_name
        FROM vendor_rates vr LEFT JOIN truck_types tt ON vr.truck_type_id=tt.id
        LEFT JOIN ports po ON vr.origin_port_id=po.id LEFT JOIN ports pd ON vr.destination_port_id=pd.id
        WHERE {ws} ORDER BY vr.vendor_name, vr.effective_date DESC""", tuple(pa))

@app.post("/api/vendor-rates")
async def create_rate(request: Request):
    require_admin(request)
    body = await request.json()
    for f in ("vendor_name", "truck_type_id", "origin_port_id", "destination_port_id", "effective_date"):
        if not body.get(f): raise HTTPException(400, f"{f} required")
    if LOCAL_MODE:
        rid = nid("vendor_rates")
        rate = {"id": rid, "vendor_name": body["vendor_name"], "vendor_id": body.get("vendor_id"),
            "truck_type_id": body["truck_type_id"],
            "origin_port_id": body["origin_port_id"], "destination_port_id": body["destination_port_id"],
            "rate_per_trip": body.get("rate_per_trip", 0),
            "destination_drops": body.get("destination_drops", []),
            "default_rate": body.get("default_rate", 0),
            "effective_date": body["effective_date"],
            "expiry_date": body.get("expiry_date"), "is_active": True, "created_at": nows(), "updated_at": nows()}
        _store["vendor_rates"].append(rate)
        backfill_rate_estimated_costs(body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"])
        return row2d(rate)
    rid = db_i("""INSERT INTO vendor_rates (vendor_name,vendor_id,truck_type_id,origin_port_id,destination_port_id,
        rate_per_trip,default_rate,destination_drops,effective_date,expiry_date) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (body["vendor_name"], body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"], body["destination_port_id"],
         body.get("rate_per_trip", 0), body.get("default_rate", 0),
         json.dumps(body.get("destination_drops", [])) if body.get("destination_drops") else None,
         body["effective_date"], body.get("expiry_date")))
    backfill_rate_estimated_costs(body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"])
    return db_1("SELECT * FROM vendor_rates WHERE id=%s", (rid,))

@app.put("/api/vendor-rates/{rid}")
async def update_rate(rid: int, request: Request):
    require_admin(request)
    body = await request.json()
    if LOCAL_MODE:
        for r in _store["vendor_rates"]:
            if r["id"] == rid:
                for k in ("vendor_name", "vendor_id", "truck_type_id", "origin_port_id", "destination_port_id", "rate_per_trip", "destination_drops", "default_rate", "effective_date", "expiry_date", "is_active"):
                    if k in body: r[k] = body[k]
                r["updated_at"] = nows()
                backfill_rate_estimated_costs(r.get("vendor_id"), r.get("truck_type_id"), r.get("origin_port_id"))
                return row2d(r)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for k in ("vendor_name", "vendor_id", "truck_type_id", "origin_port_id", "destination_port_id", "rate_per_trip", "destination_drops", "default_rate", "effective_date", "expiry_date", "is_active"):
        if k in body: sets.append(f"{k}=%s"); params.append(body[k])
    if not sets: raise HTTPException(400, "Nothing to update")
    params.append(rid)
    db_x(f"UPDATE vendor_rates SET {','.join(sets)} WHERE id=%s", tuple(params))
    updated_rate = db_1("SELECT * FROM vendor_rates WHERE id=%s", (rid,))
    if updated_rate:
        backfill_rate_estimated_costs(updated_rate.get("vendor_id"), updated_rate.get("truck_type_id"), updated_rate.get("origin_port_id"))
    return updated_rate

@app.delete("/api/vendor-rates/{rid}")
def delete_rate(rid: int, request: Request):
    require_admin(request)
    if LOCAL_MODE:
        deleted_rate = next((r for r in _store["vendor_rates"] if r["id"] == rid), None)
        _store["vendor_rates"] = [r for r in _store["vendor_rates"] if r["id"] != rid]
        if deleted_rate:
            for tr in _store["truck_requests"]:
                if tr.get("status_id") in (2, 3) and tr.get("assigned_truck_id"):
                    truck = next((t for t in _store["trucks"] if t["id"] == tr["assigned_truck_id"]), None)
                    if truck and truck.get("vendor_id") == deleted_rate.get("vendor_id") and truck.get("truck_type_id") == deleted_rate.get("truck_type_id") and tr.get("origin_port_id") == deleted_rate.get("origin_port_id"):
                        tr["estimated_cost"] = 0
                        tr["actual_cost"] = 0
        return {"ok": True}
    deleted_rate = db_1("SELECT vendor_id, truck_type_id, origin_port_id FROM vendor_rates WHERE id=%s", (rid,))
    db_x("UPDATE vendor_rates SET is_active=0 WHERE id=%s", (rid,))
    if deleted_rate:
        db_x("""UPDATE truck_requests SET estimated_cost=0, actual_cost=0 WHERE status_id IN (2,3) AND assigned_truck_id IN (
            SELECT id FROM trucks WHERE vendor_id=%s AND truck_type_id=%s) AND origin_port_id=%s""",
            (deleted_rate["vendor_id"], deleted_rate["truck_type_id"], deleted_rate["origin_port_id"]))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Vendor Evaluations (Lead Time Performance)
# ---------------------------------------------------------------------------

def _fmt_duration(start_str, end_str):
    if not start_str or not end_str: return None
    try:
        s = parse_dt(str(start_str))
        e = parse_dt(str(end_str))
        if not s or not e: return None
        diff = (e - s).total_seconds()
        if diff < 0: return None
        hours = int(diff // 3600)
        minutes = int((diff % 3600) // 60)
        return f"{hours}:{minutes:02d}"
    except:
        return None

@app.get("/api/vendor-evaluations")
def list_evals(request: Request, vendor_id: Optional[int] = None, date_from: Optional[str] = None,
    date_to: Optional[str] = None, search: Optional[str] = None, truck_type_id: Optional[int] = None,
    origin_port_id: Optional[int] = None, destination_port_id: Optional[int] = None,
    account_id: Optional[int] = None, department_id: Optional[int] = None):
    get_user(request)
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        results = []
        for r in reqs:
            if r.get("status_id") != 4: continue
            if not r.get("assigned_truck_id"): continue
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            if not truck: continue
            if vendor_id and truck.get("vendor_id") != vendor_id: continue
            if truck_type_id and truck.get("truck_type_id") != truck_type_id and r.get("truck_type_id") != truck_type_id: continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if destination_port_id and r.get("destination_port_id") != destination_port_id: continue
            if account_id and r.get("account_id") != account_id: continue
            if department_id and r.get("department_id") != department_id: continue
            bk = str(r.get("booking_date") or "")[:10]
            if date_from and bk and bk < date_from: continue
            if date_to and bk and bk > date_to: continue
            if search:
                rn = str(r.get("request_number", "")).lower()
                if search.lower() not in rn: continue
            vname = next((v["name"] for v in _store["vendors"] if v["id"] == truck.get("vendor_id")), "")
            ttn = next((t["name"] for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), "")
            if not ttn: ttn = next((t["name"] for t in _store["truck_types"] if t["id"] == truck.get("truck_type_id")), "")
            oname = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            dname = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            acct_name = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            dept_name = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            trip_id = None
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                trip_id = compute_trip_id(truck_reqs, r["id"])
            sn = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            sc = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            results.append({"id": r["id"], "request_number": r.get("request_number", ""),
                "trip_id": trip_id, "drop_sequence": r.get("drop_sequence"),
                "account_name": acct_name, "department_name": dept_name,
                "origin_port_name": oname, "destination_port_name": dname,
                "truck_type_name": ttn, "vendor_name": vname,
                "booking_date": r.get("booking_date"), "status_name": sn, "status_color": sc,
                "pickup_datetime": r.get("pickup_datetime"),
                "lt_customs_to_arrival": _fmt_duration(r.get("customs_cleared_datetime"), r.get("arrived_pickup_datetime")),
                "lt_pickup_to_arrival": _fmt_duration(r.get("pickup_datetime"), r.get("arrived_pickup_datetime")),
                "lt_arrival_to_start_load": _fmt_duration(r.get("arrived_pickup_datetime"), r.get("start_loading_datetime")),
                "lt_start_load_to_end_load": _fmt_duration(r.get("start_loading_datetime"), r.get("end_loading_datetime")),
                "lt_end_load_to_arrived_dest": _fmt_duration(r.get("end_loading_datetime"), r.get("arrived_dest_datetime")),
                "lt_arrived_dest_to_start_unload": _fmt_duration(r.get("arrived_dest_datetime"), r.get("start_unloading_datetime")),
                "lt_start_unload_to_end_unload": _fmt_duration(r.get("start_unloading_datetime"), r.get("end_unloading_datetime")),
                "lt_full_leg": _fmt_duration(r.get("arrived_pickup_datetime"), r.get("end_unloading_datetime")),
            })
        return results
    wh = ["tr.assigned_truck_id IS NOT NULL", "tr.status_id = 4"]
    pa = []
    if vendor_id: wh.append("tk.vendor_id=%s"); pa.append(vendor_id)
    if truck_type_id: wh.append("(tr.truck_type_id=%s OR tk.truck_type_id=%s)"); pa.extend([truck_type_id, truck_type_id])
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if search: wh.append("tr.request_number LIKE %s"); pa.append(f"%{search}%")
    if date_from: wh.append("tr.booking_date>=%s"); pa.append(date_from)
    if date_to: wh.append("tr.booking_date<=%s"); pa.append(date_to)
    ws = " AND ".join(wh)
    rows = db_q(f"""SELECT tr.id, tr.request_number, tr.drop_sequence, tr.booking_date, tr.pickup_datetime,
        tr.status_id, ts.name as status_name, ts.color as status_color,
        a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        COALESCE(tt.name, ttt.name) as truck_type_name, v.name as vendor_name,
        tr.customs_cleared_datetime, tr.arrived_pickup_datetime, tr.start_loading_datetime,
        tr.end_loading_datetime, tr.arrived_dest_datetime, tr.start_unloading_datetime, tr.end_unloading_datetime,
        tr.assigned_truck_id
        FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN accounts a ON tr.account_id=a.id LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id LEFT JOIN truck_types ttt ON tk.truck_type_id=ttt.id
        WHERE {ws} ORDER BY tr.created_at DESC""", tuple(pa))
    for row in rows:
        if row.get("assigned_truck_id") and row.get("status_id") in (2, 3, 4, 5, 7):
            truck_reqs = db_q("SELECT id, request_number, status_id, drop_sequence FROM truck_requests WHERE assigned_truck_id=%s", (row["assigned_truck_id"],))
            row["trip_id"] = compute_trip_id(truck_reqs, row["id"])
        else:
            row["trip_id"] = None
        row["lt_customs_to_arrival"] = _fmt_duration(row.get("customs_cleared_datetime"), row.get("arrived_pickup_datetime"))
        row["lt_pickup_to_arrival"] = _fmt_duration(row.get("pickup_datetime"), row.get("arrived_pickup_datetime"))
        row["lt_arrival_to_start_load"] = _fmt_duration(row.get("arrived_pickup_datetime"), row.get("start_loading_datetime"))
        row["lt_start_load_to_end_load"] = _fmt_duration(row.get("start_loading_datetime"), row.get("end_loading_datetime"))
        row["lt_end_load_to_arrived_dest"] = _fmt_duration(row.get("end_loading_datetime"), row.get("arrived_dest_datetime"))
        row["lt_arrived_dest_to_start_unload"] = _fmt_duration(row.get("arrived_dest_datetime"), row.get("start_unloading_datetime"))
        row["lt_start_unload_to_end_unload"] = _fmt_duration(row.get("start_unloading_datetime"), row.get("end_unloading_datetime"))
        row["lt_full_leg"] = _fmt_duration(row.get("arrived_pickup_datetime"), row.get("end_unloading_datetime"))
    return rows

@app.post("/api/vendor-evaluations")
async def create_eval(request: Request):
    return {"ok": True}

@app.delete("/api/vendor-evaluations/{eid}")
def delete_eval(eid: int, request: Request):
    return {"ok": True}

# ---------------------------------------------------------------------------
# Cost Summary
# ---------------------------------------------------------------------------

@app.get("/api/cost-summary")
def cost_summary(request: Request, date_from: str = Query(...), date_to: str = Query(...),
    account_id: int = Query(...), department_id: int = Query(...),
    origin_port_id: Optional[int] = None, destination_port_id: Optional[int] = None,
    vendor_id: Optional[int] = None, status_id: Optional[int] = None):
    get_user(request)
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        flt = []
        for r in reqs:
            if r.get("account_id") != account_id or r.get("department_id") != department_id: continue
            bk = str(r.get("booking_date") or "")[:10]
            if bk and (bk < date_from or bk > date_to): continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if destination_port_id and r.get("destination_port_id") != destination_port_id: continue
            if status_id and r.get("status_id") != status_id: continue
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            if vendor_id and (not truck or truck.get("vendor_id") != vendor_id): continue
            flt.append(r)
        est_total = 0
        act_total = 0
        req_list = []
        for r in flt:
            sn = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "Unknown")
            sc = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "#6B7280")
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            tt_id = r.get("truck_type_id") or (truck.get("truck_type_id") if truck else None)
            ttn = next((t["name"] for t in _store["truck_types"] if t["id"] == tt_id), "")
            origin_name = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            dest_name = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            vname = next((v["name"] for v in _store["vendors"] if v["id"] == truck.get("vendor_id")), "") if truck else ""
            est = r.get("estimated_cost", 0) or 0
            act = r.get("actual_cost", 0) or 0
            est_total += est
            act_total += act
            rd = {k: r.get(k) for k in ("id", "request_number", "quantity", "weight_kg", "volume_cbm",
                "pickup_datetime", "estimated_cost", "actual_cost", "assigned_truck_id", "status_id",
                "foul_trip_reason", "booking_date")}
            rd["status_name"] = sn
            rd["status_color"] = sc
            rd["truck_type_name"] = ttn
            rd["origin_port_name"] = origin_name
            rd["destination_port_name"] = dest_name
            rd["vendor_name"] = vname
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                rd["trip_id"] = compute_trip_id(truck_reqs, r["id"])
            else:
                rd["trip_id"] = None
            req_list.append(rd)
        return {"total_requests": len(flt), "total_estimated_cost": est_total,
            "total_actual_cost": act_total,
            "requests": req_list}
    wh = ["tr.account_id=%s", "tr.department_id=%s", "tr.booking_date>=%s", "tr.booking_date<=%s"]
    pa = [account_id, department_id, date_from, date_to]
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if vendor_id: wh.append("tk.vendor_id=%s"); pa.append(vendor_id)
    if status_id: wh.append("tr.status_id=%s"); pa.append(status_id)
    ws = " AND ".join(wh)
    s = db_1(f"SELECT COUNT(*) as total_requests,COALESCE(SUM(estimated_cost),0) as total_estimated_cost,COALESCE(SUM(actual_cost),0) as total_actual_cost FROM truck_requests tr LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id WHERE {ws}", tuple(pa))
    reqs = db_q(f"""SELECT tr.*, ts.name as status_name, ts.color as status_color,
        COALESCE(tt.name, ttt.name) as truck_type_name, po.name as origin_port_name, pd.name as destination_port_name,
        v.name as vendor_name
        FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN truck_types ttt ON tk.truck_type_id=ttt.id
        WHERE {ws} ORDER BY tr.created_at DESC""", tuple(pa))
    for i in reqs:
        if i.get("assigned_truck_id") and i.get("status_id") in (2, 3, 4, 5, 7):
            truck_reqs = db_q("SELECT id, request_number, status_id, drop_sequence FROM truck_requests WHERE assigned_truck_id=%s", (i["assigned_truck_id"],))
            i["trip_id"] = compute_trip_id(truck_reqs, i["id"])
        else:
            i["trip_id"] = None
    return {**(s or {}), "requests": reqs}

# ---------------------------------------------------------------------------
# Google Sheets Sync Endpoints (public, no auth — for Apps Script)
# ---------------------------------------------------------------------------

@app.get("/api/sync/masterlist")
def sync_masterlist():
    if LOCAL_MODE:
        reqs = [row2d(r) for r in _store["truck_requests"]]
        for r in reqs:
            r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["truck_type_name"] = next((t["name"] for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), "")
            r["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == r.get("packaging_type_id")), "")
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == truck.get("vendor_id")),"") if truck else ""
            r["plate_number"] = truck["plate_number"] if truck else ""
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                r["trip_id"] = compute_trip_id(truck_reqs, r["id"])
            else:
                r["trip_id"] = None
        return reqs
    return db_q("""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        COALESCE(tt.name, ttt.name) as truck_type_name, pt.name as packaging_type_name,
        v.name as vendor_name, tk.plate_number
        FROM truck_requests tr LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id
        LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN truck_types ttt ON tk.truck_type_id=ttt.id
        ORDER BY tr.created_at DESC""")

@app.get("/api/sync/fleet")
def sync_fleet():
    if LOCAL_MODE:
        result = []
        for t in _store["trucks"]:
            tt = next((x for x in _store["truck_types"] if x["id"] == t.get("truck_type_id")), None)
            v = next((x for x in _store["vendors"] if x["id"] == t.get("vendor_id")), None)
            reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5)]
            result.append({**t, "truck_type_name": tt["name"] if tt else "", "vendor_name": v["name"] if v else "", "active_requests": len(reqs)})
        return result
    return db_q("""SELECT t.*, tt.name as truck_type_name, v.name as vendor_name,
        (SELECT COUNT(*) FROM truck_requests WHERE assigned_truck_id=t.id AND status_id NOT IN (4,5)) as active_requests
        FROM trucks t LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
        LEFT JOIN vendors v ON t.vendor_id=v.id ORDER BY t.plate_number""")

@app.get("/api/sync/rates")
def sync_rates():
    if LOCAL_MODE:
        result = []
        for r in _store["vendor_rates"]:
            v = next((x for x in _store["vendors"] if x["id"] == r.get("vendor_id") or x["name"] == r.get("vendor_name")), None)
            tt = next((x for x in _store["truck_types"] if x["id"] == r.get("truck_type_id")), None)
            po = next((x for x in _store["ports"] if x["id"] == r.get("origin_port_id")), None)
            pd = next((x for x in _store["ports"] if x["id"] == r.get("destination_port_id")), None)
            result.append({**r, "vendor_name": v["name"] if v else r.get("vendor_name",""), "truck_type_name": tt["name"] if tt else "", "origin_port_name": po["name"] if po else "", "destination_port_name": pd["name"] if pd else ""})
        return result
    return db_q("""SELECT r.*, v.name as vendor_name, tt.name as truck_type_name,
        po.name as origin_port_name, pd.name as destination_port_name
        FROM vendor_rates r LEFT JOIN vendors v ON r.vendor_id=v.id
        LEFT JOIN truck_types tt ON r.truck_type_id=tt.id
        LEFT JOIN ports po ON r.origin_port_id=po.id
        LEFT JOIN ports pd ON r.destination_port_id=pd.id ORDER BY v.name""")

@app.get("/api/sync/evaluation")
def sync_evaluation():
    if LOCAL_MODE:
        return []
    return db_q("""SELECT tr.id, tr.request_number, tr.requestor_name, tr.requestor_email,
        tr.pickup_datetime, tr.arrived_dest_datetime, tr.end_unloading_datetime,
        tr.status_id, ts.name as status_name,
        v.name as vendor_name, tk.plate_number,
        po.name as origin_port_name, pd.name as destination_port_name,
        DATEDIFF(tr.end_unloading_datetime, tr.pickup_datetime) as lead_time_days
        FROM truck_requests tr
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id
        LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id
        LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        WHERE tr.status_id=4 ORDER BY tr.end_unloading_datetime DESC""")

@app.get("/api/sync/cost")
def sync_cost():
    if LOCAL_MODE:
        reqs = [row2d(r) for r in _store["truck_requests"]]
        for r in reqs:
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
        return reqs
    return db_q("""SELECT tr.*, ts.name as status_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        v.name as vendor_name, tk.plate_number
        FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        ORDER BY tr.created_at DESC""")

@app.get("/api/sync/ports")
def sync_ports():
    if LOCAL_MODE: return [row2d(x) for x in _store["ports"]]
    return db_q("SELECT * FROM ports WHERE is_active=1 ORDER BY name")

@app.get("/api/sync/accounts")
def sync_accounts():
    if LOCAL_MODE: return [row2d(x) for x in _store["accounts"]]
    return db_q("SELECT * FROM accounts WHERE is_active=1 ORDER BY name")

@app.get("/api/sync/departments")
def sync_departments():
    if LOCAL_MODE: return [row2d(x) for x in _store["departments"]]
    return db_q("SELECT * FROM departments WHERE is_active=1 ORDER BY name")

@app.get("/api/sync/packaging")
def sync_packaging():
    if LOCAL_MODE: return [row2d(x) for x in _store["packaging_types"]]
    return db_q("SELECT * FROM packaging_types WHERE is_active=1 ORDER BY name")

@app.get("/api/sync/statuses")
def sync_statuses():
    if LOCAL_MODE: return [row2d(x) for x in _store["truck_statuses"]]
    return db_q("SELECT * FROM truck_statuses WHERE is_active=1 ORDER BY id")

@app.get("/api/sync/truck-types")
def sync_truck_types():
    if LOCAL_MODE:
        result = []
        for t in _store["truck_types"]:
            caps = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] == t["id"]]
            for c in caps:
                c["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == c["packaging_type_id"]), "")
            result.append({**t, "capacities": caps})
        return result
    rows = db_q("SELECT * FROM truck_types WHERE is_active=1 ORDER BY name")
    for r in rows:
        r["capacities"] = db_q("""SELECT c.*, pt.name as packaging_type_name
            FROM truck_type_capacities c LEFT JOIN packaging_types pt ON c.packaging_type_id=pt.id
            WHERE c.truck_type_id=%s""", (r["id"],))
    return rows

@app.get("/api/sync/vendors")
def sync_vendors():
    if LOCAL_MODE: return [row2d(x) for x in _store["vendors"]]
    return db_q("SELECT * FROM vendors WHERE is_active=1 ORDER BY name")

# ---------------------------------------------------------------------------
# Frontend
# ---------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse, include_in_schema=False)
def homepage():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "index.html")
    try:
        with open(html_path, "r", encoding="utf-8") as f:
            return f.read()
    except FileNotFoundError:
        return "<h1>Frontend not found</h1>"
