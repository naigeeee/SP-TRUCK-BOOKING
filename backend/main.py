"""
SP PH Truck Booking Centralised Operation Request Database
"""

import os
import re
import csv
import io
import json
import uuid
import math
import hashlib
import hmac
import contextvars
import base64
import secrets
import time
from datetime import datetime, timezone, date, timedelta
from urllib.parse import urlparse, unquote
from typing import Optional
from decimal import Decimal

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool

import pymysql

import storage as obj_storage

APP_NAME = "SP PH Truck Booking Centralised Operations"

app = FastAPI(title=APP_NAME, docs_url="/api/docs")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

import traceback as _traceback

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    _traceback.print_exc()
    return JSONResponse(status_code=500, content={"detail": f"Internal server error: {type(exc).__name__}: {exc}"})

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
        {"id": 1, "name": "6W Truck", "code": "6W", "max_capacity_kg": 5000, "max_capacity_cbm": 20, "max_capacity_units": 20, "is_active": True, "created_at": "2026-01-01"},
        {"id": 2, "name": "10W Truck", "code": "10W", "max_capacity_kg": 10000, "max_capacity_cbm": 40, "max_capacity_units": 40, "is_active": True, "created_at": "2026-01-01"},
        {"id": 3, "name": "Container 20ft", "code": "C20", "max_capacity_kg": 20000, "max_capacity_cbm": 33, "max_capacity_units": None, "is_active": True, "created_at": "2026-01-01"},
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
        {"id": 1, "plate_number": "ABC1234", "truck_type_id": 1, "vendor_id": 1, "driver_name": "Juan Dela Cruz", "driver_phone": "+639171234567", "helper_name": "Pedro Santos", "status": "available", "is_active": True, "is_available": True, "created_at": "2026-01-15 08:00:00"},
        {"id": 2, "plate_number": "XYZ5678", "truck_type_id": 1, "vendor_id": 1, "driver_name": "Jose Reyes", "driver_phone": "+639181234567", "helper_name": "", "status": "available", "is_active": True, "is_available": True, "created_at": "2026-02-20 08:00:00"},
        {"id": 3, "plate_number": "DEF9012", "truck_type_id": 2, "vendor_id": 2, "driver_name": "Miguel Santos", "driver_phone": "+639191234567", "helper_name": "Luis Garcia", "status": "available", "is_active": True, "is_available": True, "created_at": "2026-03-10 08:00:00"},
        {"id": 4, "plate_number": "GHI3456", "truck_type_id": 3, "vendor_id": 2, "driver_name": "Carlos Reyes", "driver_phone": "+639201234567", "helper_name": "", "status": "available", "is_active": True, "is_available": True, "created_at": "2026-04-05 08:00:00"},
    ],
    "truck_requests": [], "attachments": [], "manifests": [], "vendor_rates": [],
    "driver_accounts": [], "driver_sessions": {}, "scan_pickup": [], "scan_unload": [],
    "vendor_evaluations": [], "pending_allocations": [], "vendors": [
        {"id": 1, "name": "ABC Logistics", "contact_person": "Pedro Santos", "phone": "+639171111111", "email": "pedro@abc.com", "address": "Manila", "is_active": True, "created_at": "2026-01-01 08:00:00"},
        {"id": 2, "name": "XYZ Transport", "contact_person": "Luis Garcia", "phone": "+639172222222", "email": "luis@xyz.com", "address": "Cebu", "is_active": True, "created_at": "2026-01-01 08:00:00"},
    ],
    "truck_request_history": [],
    "capacity_conversion": {"base_packaging_type_id": 1, "factors": {"1": 1.0, "2": 1.0, "3": 1.0}},
    "role_visibility": {
        "viewer": ["dashboard", "masterlist", "user-guide"],
        "normal_user": ["dashboard", "new-request", "masterlist", "pending", "user-guide"],
        "admin": ["dashboard", "new-request", "masterlist", "pending", "fleet", "rates", "evaluation", "cost", "foul-trip-review", "trip-utilisation", "library", "users", "role-visibility", "vendor-trucks", "driver-accounts", "user-guide"],
        "master_admin": ["dashboard", "new-request", "masterlist", "pending", "fleet", "rates", "evaluation", "cost", "foul-trip-review", "trip-utilisation", "library", "users", "role-visibility", "vendor-trucks", "driver-accounts", "user-guide"]
    },
    "_cnt": {"users": 1, "ports": 3, "accounts": 1, "departments": 4, "packaging_types": 3,
             "truck_statuses": 7, "truck_types": 3, "truck_type_capacities": 6, "trucks": 4,
             "truck_requests": 0, "attachments": 0, "manifests": 0, "vendor_rates": 0,
              "vendor_evaluations": 0, "pending_allocations": 0, "vendors": 2, "truck_request_history": 0,
              "driver_accounts": 0, "scan_pickup": 0, "scan_unload": 0},
    "_seq": {},
    "_upload": os.path.join(os.path.dirname(os.path.abspath(__file__)), "uploads"),
}
os.makedirs(_store["_upload"], exist_ok=True)

# One-time cleanup: legacy Allocated rows that already carry a truck plate and
# vendor were really already on the road -- promote them to In Transit.
if LOCAL_MODE:
    for _r in _store["truck_requests"]:
        if _r.get("status_id") == 2 and _r.get("assigned_truck_id"):
            _tk = next((t for t in _store["trucks"] if t["id"] == _r.get("assigned_truck_id")), None)
            if _tk and _tk.get("plate_number") and (_tk.get("vendor_id") or _r.get("vendor_id")):
                _r["status_id"] = 3

def nid(t):
    _store["_cnt"][t] = _store["_cnt"].get(t, 0) + 1
    return _store["_cnt"][t]

_GMT8 = timezone(timedelta(hours=8))

def nows():
    """Current time as 'YYYY-MM-DD HH:MM:SS' in GMT+8.

    Every timestamp the app writes (and every NOW()/ON UPDATE the database
    session writes, which also runs in +08:00) lands in GMT+8, so the stored
    value is displayed as-is.
    """
    return datetime.now(_GMT8).strftime("%Y-%m-%d %H:%M:%S")

def to_gmt8(v):
    """Stored timestamp -> 'YYYY-MM-DD HH:MM:SS'.

    Storage is already GMT+8, so this only normalises format (ISO 'T'/'Z' and
    fractional seconds) and never shifts the value.
    """
    if not v:
        return v
    if isinstance(v, datetime):
        return v.strftime("%Y-%m-%d %H:%M:%S")
    s = str(v).strip().replace("T", " ").replace("Z", "")
    for fmt, n in (("%Y-%m-%d %H:%M:%S", 19), ("%Y-%m-%d %H:%M", 16), ("%Y-%m-%d", 10)):
        try:
            return datetime.strptime(s[:n], fmt).strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return v

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

def _rate_drops(rate_match):
    drops = (rate_match or {}).get("destination_drops") or []
    if isinstance(drops, str):
        try: drops = json.loads(drops)
        except Exception: drops = []
    return drops if isinstance(drops, list) else []

def _is_first_drop(drop_sequence):
    try:
        return drop_sequence in (None, "") or int(drop_sequence) <= 1
    except (TypeError, ValueError):
        return True

def compute_rate(rate_match, dest_port_id, drop_sequence=None):
    """Price of one request on a given rate card (see rate_basis)."""
    return rate_basis(rate_match, dest_port_id, drop_sequence)[0]

def rate_basis(rate_match, dest_port_id, drop_sequence=None):
    """(amount, basis label) for a request's destination on one rate card.

    - drop 1 (or no trip) going to the card's Main Destination -> Rate/Trip
    - destination listed as an Additional Destination Drop      -> that drop's rate
    - anything else -> Default Rate
    A later drop (2, 3, ...) is an extra stop on the same trip, never a trip of its own:
    it never gets Rate/Trip, even when it goes to the Main Destination."""
    if not rate_match: return 0, ""
    if _is_first_drop(drop_sequence) and rate_match.get("destination_port_id") == dest_port_id:
        return float(rate_match.get("rate_per_trip", 0) or 0), "Rate/Trip"
    for d in _rate_drops(rate_match):
        if isinstance(d, dict) and d.get("port_id") == dest_port_id:
            return float(d.get("rate_per_trip", 0) or 0), "Additional Destination Drop"
    return float(rate_match.get("default_rate", 0) or 0), "Default Rate"

def pick_rate(cards, dest_port_id, primary_dest=None, drop_sequence=None):
    """Choose the rate card that prices a request (cards = in-range active cards for its
    vendor / truck type / origin) and price it. Returns (card, amount, basis).

    Drop 1 (or a request without a trip):
      1. a card whose Main Destination is its destination -> Rate/Trip;
      2. otherwise a card listing the destination as an Additional Destination Drop -> that rate;
      3. otherwise the first card -> Default Rate.
    Drop 2, 3, ... (extra stops, billed on the trip's card - the card whose Main
    Destination is drop 1's destination):
      - destination listed as one of its Additional Destination Drops -> that drop's rate;
      - otherwise -> its Default Rate (also when the stop is the Main Destination again).
      When drop 1's destination has no card: a card listing the stop as a drop, else the
      first card's Default Rate."""
    cards = [c for c in (cards or []) if c]
    if not cards:
        return None, 0, ""
    with_drop = [c for c in cards if any(isinstance(d, dict) and d.get("port_id") == dest_port_id
                                         for d in _rate_drops(c))]
    if _is_first_drop(drop_sequence):
        card = next((c for c in cards if c.get("destination_port_id") == dest_port_id), None)
        if not card:
            card = next((c for c in with_drop if primary_dest and c.get("destination_port_id") == primary_dest),
                        with_drop[0] if with_drop else None)
        if not card:
            card = next((c for c in cards if primary_dest and c.get("destination_port_id") == primary_dest), cards[0])
    else:
        card = next((c for c in cards if primary_dest and c.get("destination_port_id") == primary_dest), None)
        if not card:
            card = with_drop[0] if with_drop else cards[0]
    amt, basis = rate_basis(card, dest_port_id, drop_sequence)
    return card, amt, basis

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

def _trip_letter(seq):
    if not seq or seq < 1:
        return "A"
    if seq <= 26:
        return chr(64 + seq)
    return "A"

def trip_base(tid):
    """Shared base of a trip id ('ABC-00001-A' -> 'ABC-00001'); groups a batch."""
    if not tid:
        return None
    tid = str(tid)
    if tid.startswith("req-"):
        return tid
    head, sep, tail = tid.rpartition("-")
    if sep and len(tail) == 1 and tail.isalpha():
        return head
    return tid

def _advance_seq_state(state, width0=7, value0=1):
    if not state:
        state["width"] = width0
        state["value"] = value0
    s = str(state["value"]).zfill(state["width"])
    if state["value"] >= 10 ** state["width"] - 1:
        state["width"] += 1
        state["value"] = 1
    else:
        state["value"] += 1
    return s

def next_seq_string(key, width0=7, value0=1):
    """Allocate the next zero-padded running sequence for key.

    Starts at width0 digits (e.g. 00001 or 001). When a key reaches all 9s
    for its current width (99999 / 999), the next allocation uses the next
    wider zero-padded field — strings stay unique as the field grows.
    """
    if LOCAL_MODE:
        st = _store["_seq"].setdefault(key, {"width": width0, "value": value0})
        return _advance_seq_state(st, width0, value0)
    db = get_db()
    if not db:
        raise HTTPException(500, "Database unavailable for sequence")
    try:
        with db.cursor() as c:
            for _ in range(8):
                c.execute("SELECT width, next_value FROM id_sequences WHERE seq_key=%s FOR UPDATE", (key,))
                row = c.fetchone()
                if row is None:
                    try:
                        c.execute(
                            "INSERT INTO id_sequences (seq_key, width, next_value) VALUES (%s, %s, %s)",
                            (key, width0, value0 + 1))
                        db.commit()
                        return str(value0).zfill(width0)
                    except Exception:
                        db.rollback()
                        continue
                width = int(row["width"])
                val = int(row["next_value"])
                s = str(val).zfill(width)
                if val >= 10 ** width - 1:
                    c.execute("UPDATE id_sequences SET width=%s, next_value=1 WHERE seq_key=%s",
                              (width + 1, key))
                else:
                    c.execute("UPDATE id_sequences SET next_value=%s WHERE seq_key=%s",
                              (val + 1, key))
                db.commit()
                return s
            raise HTTPException(500, "Could not allocate sequence number")
    finally:
        db.close()

def _prefix_from_name(name):
    name = (name or "").strip()
    first = ""
    for ch in name:
        if ch.isalnum(): first += ch
        elif first: break
    return first.upper() or "SPT"

def trip_prefix_for(truck_id):
    vendor = None
    if truck_id:
        if LOCAL_MODE:
            truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
            if truck:
                vendor = next((v for v in _store["vendors"] if v["id"] == truck.get("vendor_id")), None)
        else:
            vendor = db_1("SELECT v.name as name FROM trucks t LEFT JOIN vendors v ON t.vendor_id=v.id WHERE t.id=%s", (truck_id,))
    return _prefix_from_name((vendor or {}).get("name"))

def trip_prefix_for_vendor(vendor_id):
    if not vendor_id:
        return "SPT"
    if LOCAL_MODE:
        vendor = next((v for v in _store["vendors"] if v["id"] == vendor_id), None)
    else:
        vendor = db_1("SELECT name FROM vendors WHERE id=%s", (vendor_id,))
    return _prefix_from_name((vendor or {}).get("name"))

def next_trip_base(truck_id=None):
    return f"{trip_prefix_for(truck_id)}-{next_seq_string('trip', width0=5)}"

def compute_trip_id(reqs_on_truck, request_id):
    target = next((r for r in reqs_on_truck if r.get("id") == request_id), None)
    if not target:
        return None
    if target.get("trip_id"):
        return target["trip_id"]
    if target.get("drop_sequence") is None or not target.get("assigned_truck_id"):
        return None
    status = target.get("status_id")
    if status in (2, 3):
        allocated = [r for r in reqs_on_truck
                     if r.get("status_id") in (2, 3) and r.get("drop_sequence") is not None]
        if not any(r.get("id") == request_id for r in allocated):
            allocated = [target]
        sibling = next((r for r in allocated if r.get("trip_id")), None)
        if sibling:
            base = sibling["trip_id"].rsplit("-", 1)[0]
            return f"{base}-{_trip_letter(target.get('drop_sequence'))}"
    else:
        # Terminal: inherit only from another terminal on the same truck
        # (same past generation). Never from current actives — truck may
        # have been reused for a later, unrelated trip.
        sibling = next((r for r in reqs_on_truck
                        if r.get("status_id") in (4, 5, 7) and r.get("trip_id")
                        and r.get("drop_sequence") is not None
                        and r.get("id") != request_id), None)
        if sibling:
            base = sibling["trip_id"].rsplit("-", 1)[0]
            return f"{base}-{_trip_letter(target.get('drop_sequence'))}"
        allocated = [target]
    base = next_trip_base(target.get("assigned_truck_id"))
    return f"{base}-{_trip_letter(target.get('drop_sequence'))}"

def resolve_trip_id(row, truck_reqs=None):
    if row is None:
        return None
    if row.get("trip_id"):
        return row["trip_id"]
    if not row.get("assigned_truck_id") or row.get("status_id") not in (2, 3, 4, 5, 7):
        return None
    if truck_reqs is None:
        return None
    tid = compute_trip_id(truck_reqs, row.get("id"))
    if tid and row.get("id"):
        row["trip_id"] = tid
        if LOCAL_MODE:
            for x in _store["truck_requests"]:
                if x.get("id") == row["id"] and not x.get("trip_id"):
                    x["trip_id"] = tid
                    break
        else:
            db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s AND trip_id IS NULL", (tid, row["id"]))
    return tid

def freeze_trip_ids_on_truck(truck_id):
    if not truck_id:
        return
    if LOCAL_MODE:
        active = [x for x in _store["truck_requests"]
                  if x.get("assigned_truck_id") == truck_id
                  and x.get("status_id") in (2, 3)
                  and x.get("drop_sequence") is not None]
        for x in active:
            if not x.get("trip_id"):
                x["trip_id"] = compute_trip_id(active, x["id"])
            if x.get("trip_id") and x.get("drop_sequence"):
                base = x["trip_id"].rsplit("-", 1)[0]
                x["trip_id"] = f"{base}-{_trip_letter(x.get('drop_sequence'))}"
        return
    active = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
        assigned_truck_id, account_id FROM truck_requests
        WHERE assigned_truck_id=%s AND status_id IN (2,3) AND drop_sequence IS NOT NULL""",
        (truck_id,))
    for x in active:
        orig = x.get("trip_id")
        tid = orig or compute_trip_id(active, x["id"])
        if tid and x.get("drop_sequence"):
            base = tid.rsplit("-", 1)[0]
            tid = f"{base}-{_trip_letter(x.get('drop_sequence'))}"
        x["trip_id"] = tid
        if tid and tid != orig:
            db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s", (tid, x["id"]))

# Trip numbering: a trip is a batch of requests sharing the base of the trip id
# ('ACTS-000078-A' -> 'ACTS-000078'). Drop numbers inside a batch are always 1..n
# and the trip letter is the letter of that drop number, so whenever a member leaves
# the batch the rest have to be pushed up together.

def trip_group_rows(base):
    """Still-active members of a trip that carry a drop number."""
    if not base:
        return []
    if LOCAL_MODE:
        return [r for r in _store["truck_requests"]
                if r.get("trip_id") and r.get("drop_sequence") is not None
                and trip_base(r["trip_id"]) == base and r.get("status_id") in (2, 3, 6)]
    rows = db_q("""SELECT id, status_id, drop_sequence, trip_id, assigned_truck_id, vendor_id,
        truck_type_id, origin_port_id, destination_port_id, booking_date FROM truck_requests
        WHERE status_id IN (2,3,6) AND drop_sequence IS NOT NULL AND trip_id IS NOT NULL
        AND (trip_id=%s OR trip_id LIKE %s)""", (base, f"{base}-%"))
    return [r for r in rows if trip_base(r.get("trip_id")) == base]

def trip_group_dropped(base):
    """Every member of a trip that still carries a drop number, whatever its status.
    Used to tell a number that was freed (its request went back to Pending) from one
    that is simply held by a trip member that already finished."""
    if not base:
        return []
    if LOCAL_MODE:
        return [r for r in _store["truck_requests"]
                if r.get("trip_id") and r.get("drop_sequence") is not None
                and trip_base(r["trip_id"]) == base]
    rows = db_q("""SELECT id, status_id, drop_sequence, trip_id FROM truck_requests
        WHERE drop_sequence IS NOT NULL AND trip_id IS NOT NULL
        AND (trip_id=%s OR trip_id LIKE %s)""", (base, f"{base}-%"))
    return [r for r in rows if trip_base(r.get("trip_id")) == base]

def trip_group_is_gapped(rows):
    seqs = sorted(r.get("drop_sequence") or 0 for r in rows)
    return seqs != list(range(1, len(seqs) + 1))

def _trip_estimated_cost(row, seq, primary_dest=None):
    return price_request(row, row.get("vendor_id"), row.get("truck_type_id"), primary_dest, drop_seq=seq)[1]

def apply_trip_order(base, ordered):
    """Write drop numbers 1..n and their trip letters for a trip, in the given order."""
    if not base or not ordered:
        return 0
    changed = 0
    for i, row in enumerate(ordered, start=1):
        seq, tid = i, f"{base}-{_trip_letter(i)}"
        if row.get("drop_sequence") == seq and row.get("trip_id") == tid:
            continue
        changed += 1
        if LOCAL_MODE:
            src = next((x for x in _store["truck_requests"] if x["id"] == row["id"]), None)
            if not src:
                continue
            src["drop_sequence"], src["trip_id"] = seq, tid
            if not src.get("assigned_truck_id"):
                src["estimated_cost"] = _trip_estimated_cost(src, seq, ordered[0].get("destination_port_id"))
        else:
            db_x("UPDATE truck_requests SET drop_sequence=%s, trip_id=%s WHERE id=%s", (seq, tid, row["id"]))
            if not row.get("assigned_truck_id"):
                db_x("UPDATE truck_requests SET estimated_cost=%s WHERE id=%s",
                     (_trip_estimated_cost(row, seq, ordered[0].get("destination_port_id")), row["id"]))
    return changed

def resequence_trip(base, ordered=None):
    """Push a trip's remaining members up so the drop numbers are 1..n again."""
    if not base:
        return 0
    rows = trip_group_rows(base) if ordered is None else list(ordered)
    if ordered is None:
        rows.sort(key=lambda r: (r.get("drop_sequence") or 0, r.get("id") or 0))
    return apply_trip_order(base, rows)

def resequence_trip_if_freed(base):
    """Renumber a trip only when one of its numbers was truly freed — the request holding
    it went back to Pending. A number still held by a Delivered/Cancelled member stays
    put, exactly as it does on a truck trip."""
    if not base:
        return 0
    if not trip_group_is_gapped(trip_group_rows(base)):
        return 0
    if not trip_group_is_gapped(trip_group_dropped(base)):
        return 0
    return resequence_trip(base)

def trip_counts_for(row, cache):
    """(active_trip_count, is_consolidated) for a request that has no truck of its own.
    A trip left short by a revert is repaired the moment it is seen, so drop numbers
    never stay behind on screen."""
    base = trip_base(row.get("trip_id"))
    if not base or row.get("status_id") not in (2, 3, 6):
        return 0, False
    grp = cache.get(base)
    if grp is None:
        grp = trip_group_rows(base)
        if resequence_trip_if_freed(base):
            grp = trip_group_rows(base)
        cache[base] = grp
    # The rows being rendered were read before any repair, so hand them the repaired numbers.
    for g in grp:
        if g.get("id") == row.get("id"):
            if g.get("drop_sequence") is not None:
                row["drop_sequence"] = g.get("drop_sequence")
            row["trip_id"] = g.get("trip_id") or row.get("trip_id")
            break
    active = [x for x in grp if x.get("status_id") in (2, 3)]
    return len(active), row.get("status_id") in (2, 3) and len(active) > 1

def _ensure_trip_id_before_terminal(row, truck_peers):
    if row.get("trip_id") or not row.get("assigned_truck_id"):
        return
    active = [p for p in truck_peers
              if p.get("status_id") in (2, 3) and p.get("drop_sequence") is not None]
    sibling = next((p for p in active if p.get("trip_id")), None)
    if sibling:
        base = sibling["trip_id"].rsplit("-", 1)[0]
        row["trip_id"] = f"{base}-{_trip_letter(row.get('drop_sequence'))}"
        return
    if active:
        row["trip_id"] = compute_trip_id(active + [row], row["id"])
    else:
        row["trip_id"] = compute_trip_id([row], row["id"])

def rate_in_range(rate, ref_date):
    if not rate: return False
    eff = str(rate.get("effective_date") or "")[:10]
    exp = str(rate.get("expiry_date") or "")[:10]
    rd = str(ref_date or "")[:10]
    if not rd: return True
    if eff and rd < eff: return False
    if exp and rd > exp: return False
    return True

RATE_CARD_COLS = """id, vendor_id, truck_type_id, origin_port_id, rate_per_trip, default_rate,
    destination_drops, destination_port_id, effective_date, expiry_date, foul_trip_pct, fuel_surcharge_pct"""

def rate_cards(vendor_id, truck_type_id, origin_port_id, booking_date=None, cache=None):
    """Active rate cards for a vendor / truck type / origin that are valid on booking_date."""
    if not vendor_id or not truck_type_id or not origin_port_id:
        return []
    key = (vendor_id, truck_type_id, origin_port_id)
    if cache is not None and key in cache:
        cards = cache[key]
    else:
        if LOCAL_MODE:
            cards = [vr for vr in _store["vendor_rates"]
                     if vr.get("vendor_id") == vendor_id and vr.get("truck_type_id") == truck_type_id
                     and vr.get("origin_port_id") == origin_port_id and vr.get("is_active", True)]
        else:
            cards = db_q(f"SELECT {RATE_CARD_COLS} FROM vendor_rates WHERE vendor_id=%s AND truck_type_id=%s AND origin_port_id=%s AND is_active=1 ORDER BY id", key)
        if cache is not None:
            cache[key] = cards
    if booking_date is not None:
        cards = [c for c in cards if rate_in_range(c, booking_date)]
    return cards

def trip_primary_dest(row, cache=None):
    """Destination of drop 1 of the request's trip (its own destination when it has no trip)."""
    base = trip_base(row.get("trip_id"))
    if not base:
        return row.get("destination_port_id")
    if cache is not None and base in cache:
        return cache[base] or row.get("destination_port_id")
    if LOCAL_MODE:
        mem = [r for r in _store["truck_requests"] if r.get("trip_id") and trip_base(r["trip_id"]) == base
               and r.get("status_id") != 5]
    else:
        mem = [r for r in db_q("""SELECT trip_id, drop_sequence, destination_port_id, status_id FROM truck_requests
            WHERE trip_id=%s OR trip_id LIKE %s""", (base, f"{base}-%")) if trip_base(r.get("trip_id")) == base
            and r.get("status_id") != 5]
    mem = [r for r in mem if r.get("drop_sequence") is not None] or mem
    first = min(mem, key=lambda r: (r.get("drop_sequence") or 99, r.get("trip_id") or ""), default=None)
    dest = first.get("destination_port_id") if first else None
    if cache is not None:
        cache[base] = dest
    return dest or row.get("destination_port_id")

def price_request(row, vendor_id, truck_type_id, primary_dest=None, cache=None, drop_seq=None):
    """(rate card, amount, basis) pricing one request - see pick_rate for the rules.
    drop_seq overrides the row's own drop number (used while a trip is being built)."""
    seq = drop_seq if drop_seq is not None else row.get("drop_sequence")
    if primary_dest is None and not _is_first_drop(seq):
        primary_dest = trip_primary_dest(row)
    cards = rate_cards(vendor_id, truck_type_id, row.get("origin_port_id"), row.get("booking_date"), cache)
    return pick_rate(cards, row.get("destination_port_id"), primary_dest, seq)

def find_best_rate(vendor_id, truck_type_id, origin_port_id, dest_port_id, booking_date=None):
    cards = rate_cards(vendor_id, truck_type_id, origin_port_id, booking_date)
    return pick_rate(cards, dest_port_id)[0]

def best_rate_for(vendor_id, truck_type_id, origin_port_id, dest_port_id, booking_date=None):
    """Same match as find_best_rate (kept for older callers)."""
    return find_best_rate(vendor_id, truck_type_id, origin_port_id, dest_port_id, booking_date=booking_date)

def backfill_rate_estimated_costs(vendor_id, truck_type_id, origin_port_id):
    """Re-price every allocated / finished request on a rate card's vendor, truck type and
    origin after the card changed. Foul Trips never carry an Actual Cost."""
    if LOCAL_MODE:
        if not rate_cards(vendor_id, truck_type_id, origin_port_id): return
        pcache = {}
        for r in _store["truck_requests"]:
            if not r.get("assigned_truck_id") or r.get("status_id") not in (2, 3, 4, 5, 7): continue
            truck = next((t for t in _store["trucks"] if t["id"] == r["assigned_truck_id"]), None)
            if not truck or truck.get("vendor_id") != vendor_id or truck.get("truck_type_id") != truck_type_id \
                    or r.get("origin_port_id") != origin_port_id:
                continue
            _, est, _ = price_request(r, vendor_id, truck_type_id, trip_primary_dest(r, pcache))
            r["estimated_cost"] = est
            r["actual_cost"] = est if r.get("status_id") == 4 else 0
        return
    if not rate_cards(vendor_id, truck_type_id, origin_port_id): return
    match_reqs = db_q("""SELECT tr.id, tr.trip_id, tr.assigned_truck_id, tr.origin_port_id, tr.destination_port_id,
        tr.drop_sequence, tr.status_id, COALESCE(DATE(tr.booking_date), DATE(tr.created_at)) as booking_date
        FROM truck_requests tr
        JOIN trucks tk ON tr.assigned_truck_id=tk.id
        WHERE tk.vendor_id=%s AND tk.truck_type_id=%s AND tr.origin_port_id=%s AND tr.status_id IN (2,3,4,5,7)""",
        (vendor_id, truck_type_id, origin_port_id))
    pcache, ccache = {}, {}
    for mr in match_reqs:
        _, est, _ = price_request(mr, vendor_id, truck_type_id, trip_primary_dest(mr, pcache), ccache)
        db_x("UPDATE truck_requests SET estimated_cost=%s, actual_cost=%s WHERE id=%s",
             (est, est if mr.get("status_id") == 4 else 0, mr["id"]))

def _rate_groups(active):
    """Split a truck's open requests into their trips; each trip is priced on its own."""
    groups = {}
    for r in active:
        key = trip_base(r.get("trip_id")) or f"req-{r.get('id')}"
        groups.setdefault(key, []).append(r)
    out = []
    for rs in groups.values():
        primary = next((r for r in rs if r.get("drop_sequence") == 1), None)
        if not primary:
            primary = min((r for r in rs if r.get("drop_sequence") is not None),
                          key=lambda x: x["drop_sequence"], default=None)
        if primary:
            out.append((primary, rs))
    return out

def recalculate_trip_rates(truck_id):
    """Recalculate rates for all active requests on a truck, trip by trip. Each request is
    priced by its own destination (see pick_rate); the trip's drop 1 decides which card
    supplies an Additional Destination Drop / Default Rate."""
    if not truck_id: return
    if LOCAL_MODE:
        truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
        if not truck: return
        active = [r for r in _store["truck_requests"]
            if r.get("assigned_truck_id") == truck_id and r.get("status_id") not in (4, 5)]
        for primary, rs in _rate_groups(active):
            primary_dest = primary.get("destination_port_id")
            for r in rs:
                card, est, _ = price_request(r, truck.get("vendor_id"), r.get("truck_type_id") or truck.get("truck_type_id"), primary_dest)
                if not card: continue
                r["estimated_cost"] = est
                if r.get("status_id") not in (4, 5):
                    r["actual_cost"] = 0
        return
    truck = db_1("SELECT vendor_id, truck_type_id FROM trucks WHERE id=%s", (truck_id,))
    if not truck: return
    active = db_q("SELECT id, trip_id, origin_port_id, destination_port_id, drop_sequence, truck_type_id, booking_date, status_id FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5)", (truck_id,))
    ccache = {}
    for primary, rs in _rate_groups(active):
        primary_dest = primary.get("destination_port_id")
        for r in rs:
            card, est, _ = price_request(r, truck["vendor_id"], r.get("truck_type_id") or truck["truck_type_id"], primary_dest, ccache)
            if not card: continue
            db_x("UPDATE truck_requests SET estimated_cost=%s, actual_cost=0 WHERE id=%s", (est, r["id"]))

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
    day = datetime.now().strftime("%Y%m%d")
    return f"REQ-{day}-{next_seq_string(f'req:{day}', width0=3)}"

def geodesic_distance_km(lat1, lon1, lat2, lon2):
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return round(R * 2 * math.asin(math.sqrt(a)), 1)

def get_port_coords_map():
    ports = []
    if LOCAL_MODE:
        ports = [{"id": p["id"], "latitude": p.get("latitude"), "longitude": p.get("longitude")} for p in _store["ports"]]
    else:
        ports = db_q("SELECT id, latitude, longitude FROM ports WHERE is_active=1")
    return {p["id"]: (float(p["latitude"]), float(p["longitude"])) if p.get("latitude") and p.get("longitude") else None for p in ports}

def compute_distance_for_request(req, coords_map, prev_port_id=None):
    if prev_port_id is None:
        origin_coords = coords_map.get(req.get("origin_port_id"))
    else:
        origin_coords = coords_map.get(prev_port_id)
    dest_coords = coords_map.get(req.get("destination_port_id"))
    if origin_coords and dest_coords:
        return geodesic_distance_km(origin_coords[0], origin_coords[1], dest_coords[0], dest_coords[1])
    return None

def add_distances_to_requests(reqs, coords_map):
    trips = {}
    for r in reqs:
        ds = r.get("drop_sequence")
        trip_key = r.get("trip_id")
        if trip_key and ds is not None:
            trips.setdefault(trip_key, []).append(r)
        elif (not trip_key) and r.get("assigned_truck_id") and ds is not None and r.get("status_id") in (2, 3):
            trips.setdefault(("truck", r["assigned_truck_id"]), []).append(r)
        elif r.get("status_id") != 1:
            r["distance_km"] = compute_distance_for_request(r, coords_map)
    for key in trips:
        group = trips[key]
        group.sort(key=lambda x: x.get("drop_sequence") or 0)
        prev_dest = None
        for r in group:
            if r.get("drop_sequence") == 1 or prev_dest is None:
                r["distance_km"] = compute_distance_for_request(r, coords_map)
            else:
                r["distance_km"] = compute_distance_for_request(r, coords_map, prev_port_id=prev_dest)
            prev_dest = r.get("destination_port_id")
    for r in reqs:
        # A Pending request is not on any trip, so it has no distance to travel.
        if r.get("status_id") == 1:
            r["distance_km"] = None
        elif "distance_km" not in r:
            r["distance_km"] = None

def gen_name_from_email(email):
    local = email.split("@")[0]
    parts = local.replace(".", " ").replace("_", " ").replace("-", " ").split()
    return " ".join(p.capitalize() for p in parts) if parts else email

def is_hash_name(name):
    if not name or len(name) < 20: return False
    return all(c in "0123456789abcdef" for c in name)

# The Driver/Fleet role only uses the Scanning App: these are the only app (SSO)
# endpoints it may call. The scanning app itself signs in with a driver / fleet
# account, so its /api/scan/* endpoints never go through get_user().
DRIVER_FLEET_ROLE = "driver_fleet"
DRIVER_FLEET_PATHS = {"/api/me", "/api/local-mode", "/api/role-visibility"}

def get_user(request: Request):
    u = _get_user_row(request)
    if u and u.get("role") == DRIVER_FLEET_ROLE:
        path = request.url.path
        if path not in DRIVER_FLEET_PATHS and not path.startswith("/api/scan/") and _driver_fleet_scan_only():
            raise HTTPException(403, "The Driver/Fleet role can only use the Scanning App")
    return u

def _driver_fleet_scan_only():
    """True while Role Visibility gives Driver/Fleet nothing but the Scanning App
    (the default). Once a master admin grants it more pages it is a normal role."""
    try:
        cfg = _merge_role_visibility(_load_role_visibility_cfg() or DEFAULT_ROLE_VISIBILITY)
    except Exception:
        return True
    return all(p == SCAN_PAGE for p in (cfg.get(DRIVER_FLEET_ROLE) or []))

def _get_user_row(request: Request):
    sync_u = _SYNC_USER.get()
    if sync_u:
        return sync_u
    email = request.headers.get("X-Forwarded-Email") or "nigel.ng@ninjavan.co"
    name = request.headers.get("X-Forwarded-User") or email
    if LOCAL_MODE:
        # Local-only identity override for trying other roles on the dev machine.
        # Inert when a real DATABASE_URL is present (query param is simply ignored).
        email = request.query_params.get("__email") or email
        name = request.query_params.get("__user") or name
    if is_hash_name(name):
        name = gen_name_from_email(email)
    if LOCAL_MODE:
        for u in _store["users"]:
            if u["email"] == email:
                if is_hash_name(u["name"]):
                    u["name"] = name
                return u
        uid = nid("users")
        u = {"id": uid, "email": email, "name": name, "role": "new_user", "is_active": True, "created_at": nows(), "updated_at": nows()}
        _store["users"].append(u)
        return u
    u = db_1("SELECT * FROM users WHERE email=%s", (email,))
    if u:
        if is_hash_name(u["name"]):
            db_x("UPDATE users SET name=%s WHERE id=%s", (name, u["id"]))
            u["name"] = name
        return u
    try:
        db_x("INSERT INTO users (email,name,role) VALUES (%s,%s,'new_user')", (email, name))
    except Exception:
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
# Roles: base roles, "New User" (no access) and dynamic Vendor - "<name>" roles
# ---------------------------------------------------------------------------

VENDOR_ROLE_PREFIX = "Vendor - "
BASE_ROLES = ("viewer", "normal_user", "admin", "master_admin", "new_user", "driver_fleet")
SCAN_PAGE = "scan-app"
DEFAULT_VENDOR_PAGES = ["dashboard", "masterlist", "vendor-trucks", "driver-accounts", "fleet", "scan-app", "user-guide"]
# Simplified step-by-step user guide: shown to every role except New User.
GUIDE_PAGE = "user-guide"
# The Driver / Fleet Accounts page belongs beside Vendor Truck Assignment.
VT_PAGE = "vendor-trucks"
DA_PAGE = "driver-accounts"
ROLE_LABELS_BASE = {
    "viewer": "Viewer", "normal_user": "Normal User", "admin": "Admin",
    "master_admin": "Master Admin", "new_user": "New User (no access)",
    "driver_fleet": "Driver/Fleet",
}
# Master admins may rename roles; the amended names live beside the page grants
# in the role_visibility config under this reserved key (never a role itself).
ROLE_LABELS_KEY = "role_labels"

def clean_role_labels(labels) -> dict:
    """Plain-text only: strip angle brackets, cap length, drop empties."""
    if not isinstance(labels, dict): return {}
    out = {}
    for k, v in labels.items():
        if not isinstance(v, str): continue
        v = v.replace("<", "").replace(">", "").strip()
        if v: out[str(k)] = v[:64]
    return out

def is_vendor_role(role) -> bool:
    return bool(role) and str(role).startswith(VENDOR_ROLE_PREFIX)

def vendor_name_from_role(role):
    return role[len(VENDOR_ROLE_PREFIX):] if is_vendor_role(role) else None

def all_vendors():
    if LOCAL_MODE: return [row2d(v) for v in _store["vendors"]]
    return db_q("SELECT * FROM vendors WHERE is_active=1 ORDER BY name")

def vendor_role_names():
    return [VENDOR_ROLE_PREFIX + (v.get("name") or "") for v in all_vendors()]

def vendor_id_for_role(role):
    vn = vendor_name_from_role(role)
    if not vn: return None
    vn = vn.strip().lower()
    v = next((x for x in all_vendors() if (x.get("name") or "").strip().lower() == vn), None)
    return v.get("id") if v else None

def vendor_scope(request):
    """Vendor id when the caller holds a vendor role, else None (no scope)."""
    u = get_user(request)
    if is_vendor_role(u.get("role", "")):
        vid = vendor_id_for_role(u["role"])
        if vid is None: raise HTTPException(403, "This vendor role is not linked to a vendor")
        return vid, u
    return None, u

def require_vendor(request):
    u = get_user(request)
    if not is_vendor_role(u.get("role", "")):
        raise HTTPException(403, "Vendor access required")
    vid = vendor_id_for_role(u["role"])
    if vid is None: raise HTTPException(403, "This vendor role is not linked to a vendor")
    return u, vid

def require_vendor_or_admin(request):
    """Vendor (scoped) or admin (unscoped). Viewers/others 403."""
    u = get_user(request)
    if is_vendor_role(u.get("role", "")):
        vid = vendor_id_for_role(u["role"])
        if vid is None: raise HTTPException(403, "This vendor role is not linked to a vendor")
        return u, vid
    if u["role"] in ("master_admin", "admin"):
        return u, None
    raise HTTPException(403, "Vendor access required")

def _owned_by_vendor(item, scope_vid):
    """True when a truck request belongs to the scoped vendor."""
    if scope_vid is None: return True
    if not item: return False
    if item.get("vendor_id") == scope_vid: return True
    if item.get("assigned_truck_id"):
        if LOCAL_MODE:
            truck = next((t for t in _store["trucks"] if t["id"] == item["assigned_truck_id"]), None)
        else:
            truck = db_1("SELECT vendor_id FROM trucks WHERE id=%s", (item["assigned_truck_id"],))
        return bool(truck and truck.get("vendor_id") == scope_vid)
    return False

def normalise_trip_drop_numbers():
    """Repair trips whose drop numbers carried on from another trip on the same truck
    (e.g. a 1-drop trip numbered 5/E because the truck already had 4 drops). Every trip
    is renumbered 1..n in its existing order and its letters follow. Idempotent: a trip
    already numbered 1..n is left alone."""
    if LOCAL_MODE:
        rows = [x for x in _store["truck_requests"] if x.get("trip_id") and x.get("drop_sequence") is not None]
    else:
        rows = db_q("""SELECT id, trip_id, drop_sequence, status_id, assigned_truck_id, vendor_id,
            truck_type_id, origin_port_id, destination_port_id, booking_date
            FROM truck_requests WHERE trip_id IS NOT NULL AND drop_sequence IS NOT NULL""")
    groups = {}
    for r in rows:
        b = trip_base(r.get("trip_id"))
        if b and not b.startswith("req-"):
            groups.setdefault(b, []).append(r)
    fixed, trucks = 0, set()
    for base, rs in groups.items():
        rs.sort(key=lambda r: (r.get("drop_sequence") or 0, r.get("id") or 0))
        want = [(i + 1, f"{base}-{_trip_letter(i + 1)}") for i in range(len(rs))]
        if [(r.get("drop_sequence"), r.get("trip_id")) for r in rs] == want:
            continue
        fixed += 1
        for r, (seq, tid) in zip(rs, want):
            if r.get("drop_sequence") == seq and r.get("trip_id") == tid:
                continue
            if LOCAL_MODE:
                r["drop_sequence"], r["trip_id"] = seq, tid
            else:
                db_x("UPDATE truck_requests SET drop_sequence=%s, trip_id=%s WHERE id=%s", (seq, tid, r["id"]))
            if r.get("status_id") in (2, 3, 6, 7):
                if r.get("assigned_truck_id"):
                    trucks.add(r["assigned_truck_id"])
                elif r.get("status_id") in (2, 3, 6):
                    cost = _trip_estimated_cost(r, seq)
                    if LOCAL_MODE:
                        r["estimated_cost"] = cost
                    else:
                        db_x("UPDATE truck_requests SET estimated_cost=%s WHERE id=%s", (cost, r["id"]))
    for tid in trucks:
        recalculate_trip_rates(tid)
    return fixed

@app.on_event("startup")
def _startup_normalise_drops():
    try:
        n = normalise_trip_drop_numbers()
        if n:
            print(f"[startup] renumbered drop # for {n} trip(s) to 1..n per trip")
    except Exception as e:  # never block startup over a repair
        print(f"[startup] drop # repair skipped: {e}")

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

@app.get("/api/roles")
def list_roles(request: Request):
    get_user(request)
    labels = clean_role_labels((_load_role_visibility_cfg() or {}).get(ROLE_LABELS_KEY))
    roles = [{"value": r, "label": labels.get(r) or ROLE_LABELS_BASE[r], "kind": "base"}
             for r in ("viewer", "normal_user", "admin", "master_admin", "driver_fleet", "new_user")]
    for v in all_vendors():
        name = v.get("name") or ""
        if not name: continue
        role = VENDOR_ROLE_PREFIX + name
        if labels.get(role):
            label = labels[role]
        elif labels.get("vendor"):
            label = f"{labels['vendor']} - {name}"
        else:
            label = role
        roles.append({"value": role, "label": label, "kind": "vendor",
                      "vendor_id": v.get("id")})
    return roles

# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

@app.get("/api/users")
def list_users(request: Request):
    require_admin(request)
    if LOCAL_MODE: return [row2d(u) for u in _store["users"] if u.get("is_active")]
    return db_q("SELECT * FROM users WHERE is_active=1 ORDER BY name")

@app.post("/api/users/{uid}/role")
async def set_role(uid: int, request: Request):
    user = require_master(request)
    body = await request.json()
    role = body.get("role")
    if role not in set(BASE_ROLES) | set(vendor_role_names()): raise HTTPException(400, "Invalid role")
    target = next((u for u in _store["users"] if u["id"] == uid), None) if LOCAL_MODE else db_1("SELECT * FROM users WHERE id=%s", (uid,))
    if not target: raise HTTPException(404, "User not found")
    # A master admin may change their own role (self toggle); only *other*
    # master admins are protected from being downgraded.
    if uid != user["id"] and target["role"] == "master_admin" and role != "master_admin":
        raise HTTPException(403, "Cannot downgrade another master admin")
    ROLE_HIERARCHY = {"viewer": 0, "normal_user": 1, "admin": 2, "master_admin": 3}
    if ROLE_HIERARCHY.get(role, 0) < ROLE_HIERARCHY.get(target["role"], 0):
        if role != "master_admin" or target["role"] != "master_admin":
            pass
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
    if role not in (set(BASE_ROLES) - {"master_admin"}) | set(vendor_role_names()): raise HTTPException(400, "Invalid role")
    if uid == user["id"]: raise HTTPException(400, "Cannot change your own role")
    target = next((u for u in _store["users"] if u["id"] == uid), None) if LOCAL_MODE else db_1("SELECT * FROM users WHERE id=%s", (uid,))
    if not target: raise HTTPException(404, "User not found")
    if target["role"] == "master_admin": raise HTTPException(403, "Cannot change master admin role")
    if target["role"] == "admin" and role != "admin": raise HTTPException(403, "Cannot downgrade another admin")
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

@app.delete("/api/users/{uid}")
async def remove_user(uid: int, request: Request):
    caller = get_user(request)
    caller_role = caller.get("role", "")
    ROLE_HIERARCHY = {"viewer": 0, "normal_user": 1, "admin": 2, "master_admin": 3}
    if LOCAL_MODE:
        target = next((u for u in _store["users"] if u["id"] == uid), None)
    else:
        target = db_1("SELECT * FROM users WHERE id=%s", (uid,))
    if not target: raise HTTPException(404, "User not found")
    target_role = target.get("role", "")
    if caller_role == "admin":
        if ROLE_HIERARCHY.get(target_role, 0) >= ROLE_HIERARCHY["admin"]:
            raise HTTPException(403, "Admin cannot remove another admin or master admin")
    elif caller_role != "master_admin":
        raise HTTPException(403, "Only admin or master admin can remove users")
    if target.get("email") == caller.get("email"):
        raise HTTPException(400, "Cannot remove yourself")
    if LOCAL_MODE:
        _store["users"] = [u for u in _store["users"] if u["id"] != uid]
        return {"ok": True}
    db_x("DELETE FROM users WHERE id=%s", (uid,))
    return {"ok": True}

DEFAULT_ROLE_VISIBILITY = {
    "viewer": ["dashboard", "masterlist", "scan-app", "user-guide"],
    "normal_user": ["dashboard", "new-request", "masterlist", "pending", "scan-app", "user-guide"],
    "admin": ["dashboard", "new-request", "masterlist", "pending", "fleet", "rates", "evaluation", "cost", "foul-trip-review", "trip-utilisation", "library", "users", "role-visibility", "vendor-trucks", "driver-accounts", "scan-app", "user-guide"],
    "master_admin": ["dashboard", "new-request", "masterlist", "pending", "fleet", "rates", "evaluation", "cost", "foul-trip-review", "trip-utilisation", "library", "users", "role-visibility", "page-security", "vendor-trucks", "driver-accounts", "scan-app", "user-guide"],
    "driver_fleet": ["scan-app"],
    "new_user": [],
    "_scan_app_v1": True,
}
# Marker stored with the config: once present, Scanning App is a normal page that a
# master admin can switch on or off per role. Configs saved before the page existed
# get it for every role that could already open the scanning app (everyone but New User).
SCAN_APP_MARKER = "_scan_app_v1"
SECURITY_PAGE = "page-security"

def _load_role_visibility_cfg():
    """Stored config dict (pages per role + role_labels) or None when absent."""
    if LOCAL_MODE:
        cfg = _store.get("role_visibility")
    else:
        row = db_1("SELECT config FROM role_visibility WHERE id=1")
        cfg = row.get("config") if row else None
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg)
            except Exception:
                return None
    return cfg if isinstance(cfg, dict) else None

def _merge_role_visibility(cfg):
    """Ensure every known role key exists: new_user = no pages, vendors = vendor defaults.
    Reserved keys (role_labels) are kept but never treated as roles."""
    raw = cfg if isinstance(cfg, dict) else {}
    labels = clean_role_labels(raw.get(ROLE_LABELS_KEY))
    upgraded = bool(raw.get(SCAN_APP_MARKER))
    out = {k: v for k, v in raw.items() if k not in (ROLE_LABELS_KEY, SCAN_APP_MARKER)}
    out.setdefault("new_user", [])
    if not upgraded:
        for k, v in list(out.items()):
            if k != "new_user" and isinstance(v, list) and SCAN_PAGE not in v:
                out[k] = list(v) + [SCAN_PAGE]
    # Driver/Fleet starts on the Scanning App only; a master admin may widen it.
    out.setdefault(DRIVER_FLEET_ROLE, [SCAN_PAGE])
    live_vendors = set(vendor_role_names())
    for k in [k for k in out if k.startswith(VENDOR_ROLE_PREFIX)]:
        if k not in live_vendors:
            out.pop(k)  # vendor deleted or renamed -> drop the stale role key
    for vr in live_vendors:
        out.setdefault(vr, list(DEFAULT_VENDOR_PAGES))
    # The User Guide is available to every role except New User, including
    # vendor keys that were written before it existed.
    for k in list(out):
        if k in ("new_user", DRIVER_FLEET_ROLE) or k == ROLE_LABELS_KEY:
            continue
        v = out.get(k)
        if isinstance(v, list) and GUIDE_PAGE not in v:
            out[k] = list(v) + [GUIDE_PAGE]
    # Driver / Fleet Accounts rides along with Vendor Truck Assignment: a role
    # that can assign a trip needs the page that creates the driver who drives it.
    for k in list(out):
        if k == "new_user" or k == ROLE_LABELS_KEY:
            continue
        v = out.get(k)
        if isinstance(v, list) and VT_PAGE in v and DA_PAGE not in v:
            out[k] = list(v) + [DA_PAGE]
    # Page Password & Access Logs belongs to the master admin only.
    for k in list(out):
        v = out.get(k)
        if not isinstance(v, list):
            continue
        if k == "master_admin":
            if SECURITY_PAGE not in v:
                out[k] = list(v) + [SECURITY_PAGE]
        elif SECURITY_PAGE in v:
            out[k] = [p for p in v if p != SECURITY_PAGE]
    if "master_admin" not in out:
        out["master_admin"] = list(DEFAULT_ROLE_VISIBILITY["master_admin"])
    valid = set(BASE_ROLES) | {"vendor"} | live_vendors
    out[ROLE_LABELS_KEY] = {k: v for k, v in labels.items() if k in valid}
    return out

@app.get("/api/role-visibility")
def get_role_visibility(request: Request):
    get_user(request)
    cfg = _load_role_visibility_cfg()
    return _merge_role_visibility(DEFAULT_ROLE_VISIBILITY if cfg is None else cfg)

@app.put("/api/role-visibility")
async def set_role_visibility(request: Request):
    require_master(request)
    body = await request.json()
    if not isinstance(body, dict): raise HTTPException(400, "Invalid config")
    valid_roles = set(BASE_ROLES) | {"vendor"} | set(vendor_role_names())
    labels_in = body.pop(ROLE_LABELS_KEY, None)
    if labels_in is not None:
        if not isinstance(labels_in, dict): raise HTTPException(400, "Invalid role labels")
        if any(not isinstance(v, str) for v in labels_in.values()): raise HTTPException(400, "Invalid role labels")
        for role in labels_in:
            if role not in valid_roles: raise HTTPException(400, f"Invalid role: {role}")
    for role, pages in body.items():
        if role not in valid_roles: raise HTTPException(400, f"Invalid role: {role}")
        if not isinstance(pages, list): raise HTTPException(400, f"Invalid pages for {role}")
    # labels submitted -> cleaned; omitted -> keep the names already stored
    if labels_in is None:
        prev = _load_role_visibility_cfg() or {}
        labels = clean_role_labels(prev.get(ROLE_LABELS_KEY))
    else:
        labels = clean_role_labels(labels_in)
    expanded = {}
    vendor_keys = [VENDOR_ROLE_PREFIX + (v.get("name") or "") for v in all_vendors()]
    for role, pages in body.items():
        if role == "vendor":
            for vk in vendor_keys: expanded[vk] = list(pages)
        else:
            expanded[role] = list(pages)
    expanded[ROLE_LABELS_KEY] = labels
    expanded.setdefault(DRIVER_FLEET_ROLE, [SCAN_PAGE])
    expanded[SCAN_APP_MARKER] = True
    if LOCAL_MODE:
        _store["role_visibility"] = expanded
        return {"ok": True}
    existing = db_1("SELECT id FROM role_visibility WHERE id=1")
    config_json = json.dumps(expanded)
    if existing:
        db_x("UPDATE role_visibility SET config=%s WHERE id=1", (config_json,))
    else:
        db_x("INSERT INTO role_visibility (id, config) VALUES (1, %s)", (config_json,))
    return {"ok": True}

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
def _rename_role_label(cfg, old_role, new_role):
    """Follow a vendor role rename/delete inside the stored role_labels map."""
    labels = cfg.get(ROLE_LABELS_KEY)
    if not isinstance(labels, dict) or old_role not in labels:
        return False
    if new_role:
        labels[new_role] = labels.pop(old_role)
    else:
        labels.pop(old_role)
    return True

def _sync_vendor_role(old_role, new_role=None):
    """Vendor renamed (new_role set) or deleted (new_role None): keep users and
    the stored role-visibility config in step with the vendor list."""
    if LOCAL_MODE:
        for u in _store.get("users", []):
            if u.get("role") == old_role:
                u["role"] = new_role or "new_user"
        cfg = _store.get("role_visibility")
        if isinstance(cfg, dict):
            if old_role in cfg:
                if new_role:
                    cfg[new_role] = cfg.pop(old_role)
                else:
                    cfg.pop(old_role)
            _rename_role_label(cfg, old_role, new_role)
        return
    if new_role:
        db_x("UPDATE users SET role=%s WHERE role=%s", (new_role, old_role))
    else:
        db_x("UPDATE users SET role=%s WHERE role=%s", ("new_user", old_role))
    row = db_1("SELECT config FROM role_visibility WHERE id=1")
    if row and row.get("config"):
        try:
            cfg = json.loads(row["config"]) if isinstance(row["config"], str) else dict(row["config"])
        except Exception:
            return
        changed = False
        if old_role in cfg:
            if new_role:
                cfg[new_role] = cfg.pop(old_role)
            else:
                cfg.pop(old_role)
            changed = True
        if _rename_role_label(cfg, old_role, new_role):
            changed = True
        if changed:
            db_x("UPDATE role_visibility SET config=%s WHERE id=1", (json.dumps(cfg),))

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
    if "name" in body:
        new_name = (body.get("name") or "").strip()
        if not new_name: raise HTTPException(400, "Name required")
        if LOCAL_MODE:
            if any(v["id"] != vid and (v.get("name") or "").strip().lower() == new_name.lower()
                   for v in _store["vendors"]):
                raise HTTPException(400, "Vendor exists")
        elif db_1("SELECT id FROM vendors WHERE LOWER(name)=LOWER(%s) AND is_active=1 AND id!=%s", (new_name, vid)):
            raise HTTPException(400, "Vendor exists")
    if LOCAL_MODE:
        for v in _store["vendors"]:
            if v["id"] == vid:
                old_name = (v.get("name") or "").strip()
                for f in ("name", "contact_person", "phone", "email", "address"):
                    if f in body: v[f] = body[f]
                new_name = (v.get("name") or "").strip()
                if new_name and new_name != old_name:
                    _sync_vendor_role(VENDOR_ROLE_PREFIX + old_name, VENDOR_ROLE_PREFIX + new_name)
                return row2d(v)
        raise HTTPException(404, "Not found")
    old = db_1("SELECT name FROM vendors WHERE id=%s", (vid,))
    old_name = ((old or {}).get("name") or "").strip() if old else ""
    sets, params = [], []
    for f in ("name", "contact_person", "phone", "email", "address"):
        if f in body: sets.append(f"{f}=%s"); params.append(body[f])
    if sets: params.append(vid); db_x(f"UPDATE vendors SET {','.join(sets)} WHERE id=%s", tuple(params))
    new_name = ((body.get("name") or "").strip() if "name" in body else old_name)
    if old_name and new_name and new_name != old_name:
        _sync_vendor_role(VENDOR_ROLE_PREFIX + old_name, VENDOR_ROLE_PREFIX + new_name)
    return db_1("SELECT * FROM vendors WHERE id=%s", (vid,))

@app.delete("/api/vendors/{vid}")
def delete_vendor(vid: int, request: Request):
    require_admin(request)
    if LOCAL_MODE:
        v = next((x for x in _store["vendors"] if x["id"] == vid), None)
        _store["vendors"] = [x for x in _store["vendors"] if x["id"] != vid]
        if v:
            _sync_vendor_role(VENDOR_ROLE_PREFIX + (v.get("name") or "").strip())
        return {"ok": True}
    old = db_1("SELECT name FROM vendors WHERE id=%s", (vid,))
    db_x("UPDATE vendors SET is_active=0 WHERE id=%s", (vid,))
    if old and (old.get("name") or "").strip():
        _sync_vendor_role(VENDOR_ROLE_PREFIX + old["name"].strip())
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
        tt = {"id": tid, "name": name, "code": code, "max_capacity_kg": body.get("max_capacity_kg", 0), "max_capacity_cbm": body.get("max_capacity_cbm", 0), "max_capacity_units": body.get("max_capacity_units"), "is_active": True, "created_at": nows()}
        _store["truck_types"].append(tt)
        for c in caps:
            cid = nid("truck_type_capacities")
            _store["truck_type_capacities"].append({"id": cid, "truck_type_id": tid, "packaging_type_id": c["packaging_type_id"], "max_quantity": c.get("max_quantity", 0), "created_at": nows()})
        return tt
    existing_tt = db_1("SELECT id FROM truck_types WHERE code=%s AND is_active=1", (code,))
    if existing_tt: raise HTTPException(400, "Code exists")
    db_x("DELETE FROM truck_types WHERE code=%s AND is_active=0", (code,))
    tid = db_i("INSERT INTO truck_types (name,code,max_capacity_kg,max_capacity_cbm,max_capacity_units) VALUES (%s,%s,%s,%s,%s)", (name, code, body.get("max_capacity_kg", 0), body.get("max_capacity_cbm", 0), body.get("max_capacity_units")))
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
                if "max_capacity_units" in body:
                    mu = body["max_capacity_units"]
                    t["max_capacity_units"] = None if mu in ("", None) else mu
                if caps is not None:
                    _store["truck_type_capacities"] = [c for c in _store["truck_type_capacities"] if c["truck_type_id"] != tt_id]
                    for c in caps:
                        cid = nid("truck_type_capacities")
                        _store["truck_type_capacities"].append({"id": cid, "truck_type_id": tt_id, "packaging_type_id": c["packaging_type_id"], "max_quantity": c.get("max_quantity", 0), "created_at": nows()})
                return row2d(t)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for f in ("name", "code", "max_capacity_kg", "max_capacity_cbm", "max_capacity_units"):
        if f in body:
            val = body[f]
            if f == "max_capacity_units" and val in ("", None):
                val = None
            elif isinstance(val, str):
                val = val.strip()
            sets.append(f"{f}=%s")
            params.append(val)
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

TRUCKS_RECONCILE_SQL = """UPDATE trucks SET status='available'
    WHERE is_active=1 AND status='assigned'
    AND NOT EXISTS (SELECT 1 FROM truck_requests r WHERE r.assigned_truck_id=trucks.id AND r.status_id NOT IN (4,5,7))"""

def build_trucks_query(scope_vid=None, status=None, available=None):
    q = """SELECT t.*, tt.name as truck_type_name, v.name as vendor_name,
        (SELECT COUNT(DISTINCT truck_request_id) FROM truck_request_history WHERE truck_id=t.id AND status_id IN (4,5,7)) as history_count
        FROM trucks t LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
        LEFT JOIN vendors v ON t.vendor_id=v.id"""
    w, p = ["WHERE t.is_active=1"], []
    if scope_vid is not None: w.append("AND t.vendor_id=%s"); p.append(scope_vid)
    if status: w.append("AND t.status=%s"); p.append(status)
    if available is not None: w.append("AND t.is_available=%s"); p.append(int(available))
    return f"{q} {' '.join(w)} ORDER BY t.plate_number", tuple(p)

@app.get("/api/trucks")
def list_trucks(request: Request, status: Optional[str] = None, available: Optional[int] = None):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        trucks = [row2d(t) for t in _store["trucks"]]
        for t in trucks:
            t["truck_type_name"] = next((tt["name"] for tt in _store["truck_types"] if tt["id"] == t["truck_type_id"]), "")
            t["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == t.get("vendor_id")), "")
            active_reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5, 7)]
            if t.get("status") == "assigned" and not active_reqs:
                t["status"] = "available"
                for st in _store["trucks"]:
                    if st["id"] == t["id"]:
                        st["status"] = "available"
                        break
            t["current_requests"] = [{"id": r["id"], "request_number": r["request_number"], "status_id": r["status_id"],
                "status_name": next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), ""),
                "origin_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), ""),
                "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")} for r in active_reqs]
            hist = [h for h in _store["truck_request_history"] if h["truck_id"] == t["id"] and h.get("status_id") in (4, 5, 7)]
            t["history_count"] = len({h["truck_request_id"] for h in hist})
        if status: trucks = [t for t in trucks if t["status"] == status]
        if available is not None:
            want = bool(int(available))
            trucks = [t for t in trucks if bool(t.get("is_available", True)) == want]
        if scope_vid is not None: trucks = [t for t in trucks if t.get("vendor_id") == scope_vid]
        return trucks
    try:
        db_x(TRUCKS_RECONCILE_SQL)
    except Exception as e:
        print(f"[fleet] status reconcile skipped: {e}")
    sql, params = build_trucks_query(scope_vid, status, available)
    trucks = db_q(sql, params)
    for t in trucks:
        t["current_requests"] = db_q("""SELECT tr.id, tr.request_number, tr.status_id, ts.name as status_name,
            po.name as origin_port_name, pd.name as destination_port_name
            FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
            LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
            WHERE tr.assigned_truck_id=%s AND tr.status_id NOT IN (4,5,7)""", (t["id"],))
    return trucks

@app.post("/api/trucks")
async def create_truck(request: Request):
    user = get_user(request)
    is_admin = user.get("role") in ("master_admin", "admin")
    forced_vendor = None
    if not is_admin:
        _u, forced_vendor = require_vendor(request)
    body = await request.json()
    plate = body.get("plate_number", "").strip().upper()
    ttid = body.get("truck_type_id")
    vendor_id = forced_vendor if forced_vendor is not None else body.get("vendor_id")
    if not plate or not ttid: raise HTTPException(400, "Plate and type required")
    if LOCAL_MODE:
        for t in _store["trucks"]:
            if t["plate_number"] == plate: raise HTTPException(400, "Plate exists")
        tid = nid("trucks")
        truck = {"id": tid, "plate_number": plate, "truck_type_id": ttid, "vendor_id": vendor_id, "driver_name": body.get("driver_name", ""), "driver_phone": body.get("driver_phone", ""), "status": "available", "is_active": True, "is_available": True, "created_at": nows(), "updated_at": nows()}
        _store["trucks"].append(truck)
        return truck
    if db_1("SELECT id FROM trucks WHERE plate_number=%s", (plate,)): raise HTTPException(400, "Plate exists")
    tid = db_i("INSERT INTO trucks (plate_number,truck_type_id,vendor_id,driver_name,driver_phone) VALUES (%s,%s,%s,%s,%s)", (plate, ttid, vendor_id, body.get("driver_name", ""), body.get("driver_phone", "")))
    return db_1("SELECT * FROM trucks WHERE id=%s", (tid,))

@app.put("/api/trucks/{tid}")
async def update_truck(tid: int, request: Request):
    user = get_user(request)
    is_admin = user.get("role") in ("master_admin", "admin")
    forced_vendor = None
    if not is_admin:
        _u, forced_vendor = require_vendor(request)
        if LOCAL_MODE:
            own = next((t for t in _store["trucks"] if t["id"] == tid), None)
        else:
            own = db_1("SELECT vendor_id FROM trucks WHERE id=%s", (tid,))
        if not own or own.get("vendor_id") != forced_vendor:
            raise HTTPException(403, "Not your vendor's truck")
    body = await request.json()
    if forced_vendor is not None:
        body["vendor_id"] = forced_vendor
    if LOCAL_MODE:
        for t in _store["trucks"]:
            if t["id"] == tid:
                old_status = t.get("status")
                for k in ("plate_number", "truck_type_id", "vendor_id", "driver_name", "driver_phone", "status", "is_available"):
                    if k in body: t[k] = body[k]
                t["updated_at"] = nows()
                if "status" in body and old_status == "assigned" and body.get("status") != "assigned":
                    pending_id = next((s["id"] for s in _store["truck_statuses"] if s["name"] == "Pending"), None)
                    if pending_id:
                        for r in _store["truck_requests"]:
                            if r.get("assigned_truck_id") == tid:
                                r["status_id"] = pending_id
                                r["assigned_truck_id"] = None
                                r["updated_by"] = request.headers.get("X-Forwarded-Email", "")
                                r["updated_at"] = nows()
                                if not any(pa.get("truck_request_id") == r["id"] and pa.get("is_accepted") is None for pa in _store["pending_allocations"]):
                                    _store["pending_allocations"].append({"id": nid("pending_allocations"), "truck_request_id": r["id"], "suggested_truck_id": None, "suggestion_reason": "Reverted to pending", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
                return row2d(t)
        raise HTTPException(404, "Not found")
    if "status" in body:
        cur = db_1("SELECT status FROM trucks WHERE id=%s", (tid,))
        old_status = cur.get("status") if cur else None
    sets, params = [], []
    for k in ("plate_number", "truck_type_id", "vendor_id", "driver_name", "driver_phone", "status", "is_available"):
        if k in body: sets.append(f"{k}=%s"); params.append(body[k])
    if not sets: raise HTTPException(400, "Nothing to update")
    params.append(tid)
    db_x(f"UPDATE trucks SET {','.join(sets)} WHERE id=%s", tuple(params))
    if "status" in body and old_status == "assigned" and body.get("status") != "assigned":
        pending_st = db_1("SELECT id FROM truck_statuses WHERE name='Pending'")
        if pending_st:
            email = request.headers.get("X-Forwarded-Email", "")
            db_x("UPDATE truck_requests SET status_id=%s, assigned_truck_id=NULL, updated_by=%s, updated_at=NOW() WHERE assigned_truck_id=%s",
                 (pending_st["id"], email, tid))
            db_i("""INSERT INTO pending_allocations (truck_request_id, suggestion_reason)
                SELECT tr.id, 'Reverted to pending' FROM truck_requests tr
                WHERE tr.status_id=%s AND NOT EXISTS (
                    SELECT 1 FROM pending_allocations pa WHERE pa.truck_request_id=tr.id AND pa.is_accepted IS NULL)""",
                 (pending_st["id"],))
    return db_1("SELECT * FROM trucks WHERE id=%s", (tid,))

@app.delete("/api/trucks/{tid}")
def delete_truck(tid: int, request: Request):
    user = get_user(request)
    if user.get("role") not in ("master_admin", "admin"):
        _u, vid = require_vendor(request)
        own = next((t for t in _store["trucks"] if t["id"] == tid), None) if LOCAL_MODE else db_1("SELECT vendor_id FROM trucks WHERE id=%s", (tid,))
        if not own or own.get("vendor_id") != vid:
            raise HTTPException(403, "Not your vendor's truck")
    if LOCAL_MODE:
        _store["trucks"] = [t for t in _store["trucks"] if t["id"] != tid]
        return {"ok": True}
    db_x("UPDATE trucks SET is_active=0 WHERE id=%s", (tid,))
    return {"ok": True}

@app.get("/api/trucks/{tid}/history")
def truck_history(tid: int, request: Request):
    get_user(request)
    if LOCAL_MODE:
        rows = [h for h in _store["truck_request_history"] if h["truck_id"] == tid and h.get("status_id") in (4, 5, 7)]
        seen, hist = set(), []
        for h in sorted(rows, key=lambda x: x.get("archived_at", ""), reverse=True):
            if h["truck_request_id"] in seen:
                continue
            seen.add(h["truck_request_id"])
            h = dict(h)
            h["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == h.get("origin_port_id")), "")
            h["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == h.get("destination_port_id")), "")
            h["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == h.get("status_id")), "")
            h["status_color"] = next((s.get("color") for s in _store["truck_statuses"] if s["id"] == h.get("status_id")), "")
            h["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == h.get("account_id")), "")
            h["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == h.get("department_id")), "")
            updater = next((u for u in _store["users"] if u.get("email") == h.get("updated_by")), None)
            h["updated_by_name"] = updater.get("name", "") if updater else (h.get("updated_by") or "")
            hist.append(h)
        return hist
    return db_q("""SELECT h.*, po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        a.name as account_name, d.name as department_name,
        uu.name as updated_by_name, h.updated_by as updated_by_email
        FROM truck_request_history h
        LEFT JOIN ports po ON h.origin_port_id=po.id LEFT JOIN ports pd ON h.destination_port_id=pd.id
        LEFT JOIN truck_statuses ts ON h.status_id=ts.id
        LEFT JOIN accounts a ON h.account_id=a.id
        LEFT JOIN departments d ON h.department_id=d.id
        LEFT JOIN users uu ON h.updated_by=uu.email
        WHERE h.truck_id=%s AND h.status_id IN (4,5,7)
        AND h.archived_at = (SELECT MAX(h2.archived_at) FROM truck_request_history h2
            WHERE h2.truck_id=h.truck_id AND h2.truck_request_id=h.truck_request_id)
        ORDER BY h.archived_at DESC""", (tid,))

def archive_truck_requests(truck_id, email="system"):
    truck_reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == truck_id] if LOCAL_MODE else \
        db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id, account_id,
            assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""", (truck_id,))
    trip_by_id = {}
    for r in truck_reqs:
        tid = resolve_trip_id(r, truck_reqs)
        if tid:
            trip_by_id[r["id"]] = tid
            if LOCAL_MODE and r.get("status_id") in (2, 3, 4, 5, 7) and not r.get("trip_id"):
                r["trip_id"] = tid
            elif not LOCAL_MODE and not r.get("trip_id") and r.get("status_id") in (4, 5, 7):
                db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s AND trip_id IS NULL", (tid, r["id"]))
    if LOCAL_MODE:
        existing = {(h["truck_id"], h["truck_request_id"]) for h in _store["truck_request_history"]}
        for r in _store["truck_requests"]:
            if r.get("assigned_truck_id") == truck_id and r.get("status_id") in (4, 5, 7):
                if (truck_id, r["id"]) in existing:
                    continue
                _store["truck_request_history"].append({
                    "id": nid("truck_request_history"), "truck_id": truck_id,
                    "truck_request_id": r["id"], "request_number": r.get("request_number", ""),
                    "requestor_name": r.get("requestor_name", ""), "requestor_email": r.get("requestor_email", ""),
                    "origin_port_id": r.get("origin_port_id"), "destination_port_id": r.get("destination_port_id"),
                    "truck_type_id": r.get("truck_type_id"), "quantity": r.get("quantity", 0),
                    "weight_kg": r.get("weight_kg", 0), "volume_cbm": r.get("volume_cbm", 0),
                    "status_id": r.get("status_id"), "pickup_datetime": r.get("pickup_datetime"),
                    "call_datetime": r.get("call_datetime"),
                    "final_call_datetime": r.get("final_call_datetime"),
                    "trip_id": trip_by_id.get(r["id"]), "drop_sequence": r.get("drop_sequence"),
                    "account_id": r.get("account_id"), "department_id": r.get("department_id"),
                    "updated_by": r.get("updated_by") or email,
                    "archived_at": nows(), "archived_by": email})
        return
    reqs = db_q("""SELECT id,request_number,requestor_name,requestor_email,origin_port_id,destination_port_id,
        truck_type_id,quantity,weight_kg,volume_cbm,status_id,pickup_datetime,call_datetime,
        final_call_datetime,drop_sequence,trip_id,account_id,department_id,updated_by
        FROM truck_requests WHERE assigned_truck_id=%s AND status_id IN (4,5,7)""", (truck_id,))
    for r in reqs:
        if db_1("SELECT id FROM truck_request_history WHERE truck_id=%s AND truck_request_id=%s", (truck_id, r["id"])):
            continue
        db_i("""INSERT INTO truck_request_history (truck_id,truck_request_id,request_number,requestor_name,requestor_email,
            origin_port_id,destination_port_id,truck_type_id,quantity,weight_kg,volume_cbm,status_id,pickup_datetime,
            call_datetime,final_call_datetime,trip_id,drop_sequence,account_id,department_id,updated_by,archived_by)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
            (truck_id, r["id"], r["request_number"], r["requestor_name"], r["requestor_email"],
             r["origin_port_id"], r["destination_port_id"], r["truck_type_id"], r["quantity"], r["weight_kg"],
             r["volume_cbm"], r["status_id"], r["pickup_datetime"], r.get("call_datetime"),
             r.get("final_call_datetime"),
             trip_by_id.get(r["id"]) or r.get("trip_id"), r.get("drop_sequence"), r.get("account_id"), r.get("department_id"),
             r.get("updated_by") or email, email))

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@app.get("/api/dashboard")
def dashboard(request: Request, final_call_from: Optional[str] = None, final_call_to: Optional[str] = None,
    account_id: Optional[int] = None, department_id: Optional[int] = None,
    status_id: Optional[int] = None, origin_port_id: Optional[int] = None,
    destination_port_id: Optional[int] = None, mawb: Optional[str] = None,
    list_status_id: Optional[int] = None):
    """Summary counts plus the request list. list_status_id (a clicked summary tile)
    narrows only the list - the counts keep showing every status."""
    scope_vid, _ = vendor_scope(request)
    list_limit = 1000 if list_status_id else 50
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        flt = []
        for r in reqs:
            if account_id and r.get("account_id") != account_id: continue
            if department_id and r.get("department_id") != department_id: continue
            if status_id and r.get("status_id") != status_id: continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if destination_port_id and r.get("destination_port_id") != destination_port_id: continue
            if mawb:
                m = mawb.lower()
                if m not in ((r.get("international_mawb") or "") + " " + (r.get("domestic_mawb") or "")).lower(): continue
            fc = str(r.get("final_call_datetime") or "")[:10]
            if final_call_from and (not fc or fc < final_call_from): continue
            if final_call_to and (not fc or fc > final_call_to): continue
            flt.append(r)
        if scope_vid is not None:
            flt = [r for r in flt if _owned_by_vendor(r, scope_vid)]
        trucks = _store["trucks"]
        if scope_vid is not None:
            trucks = [t for t in trucks if t.get("vendor_id") == scope_vid]
        tc = sum(r.get("actual_cost", 0) or 0 for r in flt)
        listed = [r for r in flt if not list_status_id or r.get("status_id") == list_status_id]
        recent = [row2d(r) for r in listed][-list_limit:][::-1]
        for r in recent:
            r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["status_color"] = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == r.get("packaging_type_id")), "")
            r["quantity"] = r.get("quantity") or 0
            r["requestor_name"] = r.get("requestor_name", "")
        return {
            "total_requests": len(flt),
            "pending_allocation": sum(1 for r in flt if r.get("status_id") == 1),
            "allocated": sum(1 for r in flt if r.get("status_id") == 2),
            "in_transit": sum(1 for r in flt if r.get("status_id") == 3),
            "delivered": sum(1 for r in flt if r.get("status_id") == 4),
            "cancelled": sum(1 for r in flt if r.get("status_id") == 5),
            "foul_trip": sum(1 for r in flt if r.get("status_id") == 7),
            "total_cost": tc,
            "total_trucks": len(trucks),
            "available_trucks": sum(1 for t in trucks if t.get("status") == "available"),
            "busy_trucks": sum(1 for t in trucks if t.get("status") == "busy"),
            "recent_requests": recent,
            "list_status_id": list_status_id,
            "list_total": len(listed),
        }
    wh, pa = [], []
    if scope_vid is not None: wh.append("tr.vendor_id=%s"); pa.append(scope_vid)
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if status_id: wh.append("tr.status_id=%s"); pa.append(status_id)
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if mawb: wh.append("(tr.international_mawb LIKE %s OR tr.domestic_mawb LIKE %s)"); pa.extend([f"%{mawb}%", f"%{mawb}%"])
    if final_call_from: wh.append("DATE(tr.final_call_datetime)>=%s"); pa.append(final_call_from)
    if final_call_to: wh.append("DATE(tr.final_call_datetime)<=%s"); pa.append(final_call_to)
    ws = (" WHERE " + " AND ".join(wh)) if wh else ""
    stats = db_1(f"""SELECT COUNT(*) as total_requests,
        SUM(CASE WHEN status_id=1 THEN 1 ELSE 0 END) as pending_allocation,
        SUM(CASE WHEN status_id=2 THEN 1 ELSE 0 END) as allocated,
        SUM(CASE WHEN status_id=3 THEN 1 ELSE 0 END) as in_transit,
        SUM(CASE WHEN status_id=4 THEN 1 ELSE 0 END) as delivered,
        SUM(CASE WHEN status_id=5 THEN 1 ELSE 0 END) as cancelled,
        SUM(CASE WHEN status_id=7 THEN 1 ELSE 0 END) as foul_trip,
        COALESCE(SUM(actual_cost),0) as total_cost FROM truck_requests tr{ws}""", tuple(pa))
    if scope_vid is not None:
        ts = db_1("""SELECT COUNT(*) as total_trucks,
            SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) as available_trucks,
            SUM(CASE WHEN status='busy' THEN 1 ELSE 0 END) as busy_trucks
            FROM trucks WHERE is_active=1 AND vendor_id=%s""", (scope_vid,))
    else:
        ts = db_1("""SELECT COUNT(*) as total_trucks,
            SUM(CASE WHEN status='available' THEN 1 ELSE 0 END) as available_trucks,
            SUM(CASE WHEN status='busy' THEN 1 ELSE 0 END) as busy_trucks FROM trucks WHERE is_active=1""")
    lwh, lpa = list(wh), list(pa)
    if list_status_id:
        lwh.append("tr.status_id=%s"); lpa.append(list_status_id)
    lws = (" WHERE " + " AND ".join(lwh)) if lwh else ""
    lcount = db_1(f"SELECT COUNT(*) as c FROM truck_requests tr{lws}", tuple(lpa)) or {}
    recent = db_q(f"""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        pt.name as packaging_type_name
        FROM truck_requests tr LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        {lws} ORDER BY tr.created_at DESC LIMIT %s""", tuple(lpa) + (list_limit,))
    for r in recent:
        r["quantity"] = r.get("quantity") or 0
        r["requestor_name"] = r.get("requestor_name", "")
    return {**(stats or {}), **(ts or {}), "recent_requests": recent,
            "list_status_id": list_status_id, "list_total": int(lcount.get("c") or 0)}

# ---------------------------------------------------------------------------
# Capacity Conversion: one base packaging unit, per-type factors, utilisation
# ---------------------------------------------------------------------------

CAPACITY_CONVERSION_DEFAULT = {"base_packaging_type_id": None, "factors": {}}

def load_capacity_conversion():
    """Stored conversion config: base packaging unit + factors (base units per 1 unit of that type)."""
    if LOCAL_MODE:
        cfg = _store.get("capacity_conversion")
        if not cfg: return dict(CAPACITY_CONVERSION_DEFAULT)
        return {"base_packaging_type_id": cfg.get("base_packaging_type_id"),
                "factors": dict(cfg.get("factors") or {})}
    row = db_1("SELECT config FROM capacity_conversion WHERE id=1")
    cfg = row.get("config") if row else None
    if not cfg: return dict(CAPACITY_CONVERSION_DEFAULT)
    if isinstance(cfg, str):
        import json as _json
        try: cfg = _json.loads(cfg)
        except Exception: cfg = None
    if not isinstance(cfg, dict): return dict(CAPACITY_CONVERSION_DEFAULT)
    return {"base_packaging_type_id": cfg.get("base_packaging_type_id"),
            "factors": {str(k): v for k, v in (cfg.get("factors") or {}).items()}}

def save_capacity_conversion(cfg):
    import json as _json
    clean = {"base_packaging_type_id": cfg.get("base_packaging_type_id"),
             "factors": {str(k): v for k, v in (cfg.get("factors") or {}).items()}}
    if LOCAL_MODE:
        _store["capacity_conversion"] = clean
        return clean
    db_x("REPLACE INTO capacity_conversion (id, config) VALUES (1, %s)", (_json.dumps(clean),))
    return clean

def conversion_factor(cfg, pkg_id):
    if not pkg_id: return 1.0
    try: return float((cfg.get("factors") or {}).get(str(pkg_id), 1.0))
    except (TypeError, ValueError): return 1.0

def to_base_units(qty, pkg_id, cfg=None):
    """Quantity expressed in the base packaging unit, using the conversion factors."""
    if cfg is None: cfg = load_capacity_conversion()
    try: q = float(qty or 0)
    except (TypeError, ValueError): q = 0.0
    return q * conversion_factor(cfg, pkg_id)

def utilisation_pct(units, capacity):
    try: cap = float(capacity or 0)
    except (TypeError, ValueError): cap = 0.0
    if cap <= 0: return None
    return round(units / cap * 100, 1)

def utilisation_tier(pct):
    if pct is None: return None
    if pct < 70: return "red"
    if pct <= 85: return "yellow"
    return "green"

@app.get("/api/capacity-conversion")
def get_capacity_conversion(request: Request):
    return load_capacity_conversion()

@app.put("/api/capacity-conversion")
async def put_capacity_conversion(request: Request):
    require_admin(request)
    body = await request.json()
    base = body.get("base_packaging_type_id")
    if base in ("", 0, "0"): base = None
    if base is not None:
        try: base = int(base)
        except (TypeError, ValueError): raise HTTPException(400, "base_packaging_type_id must be an integer")
        if LOCAL_MODE:
            if not any(p["id"] == base for p in _store["packaging_types"]): raise HTTPException(400, "Unknown packaging type")
        elif not db_1("SELECT id FROM packaging_types WHERE id=%s", (base,)):
            raise HTTPException(400, "Unknown packaging type")
    raw = body.get("factors") or {}
    if not isinstance(raw, dict): raise HTTPException(400, "factors must be an object")
    factors = {}
    for k, v in raw.items():
        try: fid = int(k)
        except (TypeError, ValueError): raise HTTPException(400, "Factor keys must be packaging type ids")
        try: fv = float(v)
        except (TypeError, ValueError): raise HTTPException(400, "Factor values must be numbers")
        if fv < 0: raise HTTPException(400, "Factors cannot be negative")
        factors[fid] = fv
    if base is not None:
        factors[base] = 1.0
    return save_capacity_conversion({"base_packaging_type_id": base, "factors": factors})

@app.get("/api/trip-utilisation")
def trip_utilisation(request: Request, final_from: Optional[str] = None, final_to: Optional[str] = None,
    department_id: Optional[int] = None, origin_port_id: Optional[int] = None,
    vendor_id: Optional[int] = None, truck_type_id: Optional[int] = None):
    require_page_unlock(request, "trip-utilisation")
    require_admin(request)
    cfg = load_capacity_conversion()
    if LOCAL_MODE:
        rows = []
        for r in _store["truck_requests"]:
            if not r.get("trip_id") or not r.get("final_call_datetime"): continue
            rows.append({**row2d(r)})
    else:
        wh = ["tr.trip_id IS NOT NULL", "tr.final_call_datetime IS NOT NULL"]
        pa = []
        if final_from: wh.append("DATE(tr.final_call_datetime)>=%s"); pa.append(final_from)
        if final_to: wh.append("DATE(tr.final_call_datetime)<=%s"); pa.append(final_to)
        if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
        if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
        if truck_type_id: wh.append("tr.truck_type_id=%s"); pa.append(truck_type_id)
        if vendor_id: wh.append("COALESCE(tr.vendor_id, tk.vendor_id)=%s"); pa.append(vendor_id)
        rows = db_q(f"""SELECT tr.id, tr.request_number, tr.trip_id, tr.quantity, tr.initial_quantity,
            tr.packaging_type_id, tr.truck_type_id, tr.origin_port_id, tr.department_id, tr.status_id,
            COALESCE(tr.vendor_id, tk.vendor_id) as vendor_id, tr.final_call_datetime,
            po.name as origin_port_name, d.name as department_name,
            tt.name as truck_type_name, tt.max_capacity_units, v.name as vendor_name
            FROM truck_requests tr
            LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id
            LEFT JOIN ports po ON tr.origin_port_id=po.id
            LEFT JOIN departments d ON tr.department_id=d.id
            LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
            LEFT JOIN vendors v ON COALESCE(tr.vendor_id, tk.vendor_id)=v.id
            WHERE {' AND '.join(wh)}""", tuple(pa))
    if LOCAL_MODE:
        kept = []
        for r in rows:
            if final_from and (str(r.get("final_call_datetime") or "")[:10]) < final_from: continue
            if final_to and (str(r.get("final_call_datetime") or "")[:10]) > final_to: continue
            if department_id and r.get("department_id") != department_id: continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if truck_type_id and r.get("truck_type_id") != truck_type_id: continue
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            vid = r.get("vendor_id") or (truck.get("vendor_id") if truck else None)
            if vendor_id and vid != vendor_id: continue
            r["vendor_id"] = vid
            r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == vid), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            tt = next((t for t in _store["truck_types"] if t["id"] == r.get("truck_type_id")), None)
            r["truck_type_name"] = tt["name"] if tt else ""
            r["max_capacity_units"] = tt.get("max_capacity_units") if tt else None
            kept.append(r)
        rows = kept
    groups = {}
    for r in rows:
        base = trip_base(r.get("trip_id") or "")
        if not base: continue
        g = groups.setdefault(base, {"base": base, "members": []})
        g["members"].append(r)
    trips = []
    for base, g in groups.items():
        # Trip Utilisation reviews Delivered requests only; drops that are still
        # open (or cancelled / foul) are left out of the figures.
        everyone = [m for m in g["members"] if m.get("status_id") not in (5,)]
        members = [m for m in g["members"] if m.get("status_id") == 4]
        if not members:
            continue
        status_label = ("Delivered" if len(members) == len(everyone)
                        else f"Delivered {len(members)} of {len(everyone)} drops")
        tt_name = next((m.get("truck_type_name") for m in members if m.get("truck_type_name")), "")
        cap = next((m.get("max_capacity_units") for m in members if m.get("max_capacity_units") is not None), None)
        initial_units = sum(to_base_units(m.get("initial_quantity") if m.get("initial_quantity") is not None else m.get("quantity"),
                                          m.get("packaging_type_id"), cfg) for m in members)
        revised_units = sum(to_base_units(m.get("quantity"), m.get("packaging_type_id"), cfg) for m in members)
        init_pct = utilisation_pct(initial_units, cap)
        rev_pct = utilisation_pct(revised_units, cap)
        trips.append({
            "trip_id": base,
            "status_name": status_label,
            "trip_ids": sorted({m.get("trip_id") for m in members if m.get("trip_id")}),
            "final_call_datetime": max((str(m.get("final_call_datetime") or "") for m in members), default=""),
            "request_count": len(members),
            "vendor_name": next((m.get("vendor_name") for m in members if m.get("vendor_name")), ""),
            "origin_port_name": next((m.get("origin_port_name") for m in members if m.get("origin_port_name")), ""),
            "department_name": next((m.get("department_name") for m in members if m.get("department_name")), ""),
            "truck_type_name": tt_name,
            "max_capacity_units": cap,
            "initial_units": round(initial_units, 3),
            "revised_units": round(revised_units, 3),
            "initial_utilisation": init_pct,
            "revised_utilisation": rev_pct,
            "initial_tier": utilisation_tier(init_pct),
            "revised_tier": utilisation_tier(rev_pct),
        })
    trips.sort(key=lambda t: t["final_call_datetime"], reverse=True)
    return trips

# ---------------------------------------------------------------------------
# Truck Requests
# ---------------------------------------------------------------------------

def _revised_qty(r):
    """Manifest count column: what was actually scanned wins over the
    manifest file's own count, which wins over the original quantity."""
    if r.get("unload_scan_closed_at") or (r.get("unload_scan_count") or 0) > 0:
        return int(r.get("unload_scan_count") or 0)
    m = r.get("manifest")
    if m:
        return int(m.get("id_count") or 0)
    return r.get("quantity") or 0

@app.get("/api/requests")
def list_requests(request: Request, status_id: Optional[int] = None, account_id: Optional[int] = None,
    department_id: Optional[int] = None, origin_port_id: Optional[int] = None,
    destination_port_id: Optional[int] = None, truck_type_id: Optional[int] = None,
    vendor_id: Optional[int] = None, search: Optional[str] = None,
    booking_from: Optional[str] = None, booking_to: Optional[str] = None,
    pickup_from: Optional[str] = None, pickup_to: Optional[str] = None,
    call_from: Optional[str] = None, call_to: Optional[str] = None,
    initial_call_from: Optional[str] = None, initial_call_to: Optional[str] = None,
    foul_from: Optional[str] = None, foul_to: Optional[str] = None,
    cancel_from: Optional[str] = None, cancel_to: Optional[str] = None,
    customs_from: Optional[str] = None, customs_to: Optional[str] = None,
    mawb: Optional[str] = None, plate: Optional[str] = None, trip: Optional[str] = None,
    manifest: Optional[str] = None,
    sort_by: str = "created_at", sort_dir: str = "desc", page: int = 1, per_page: int = 50):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        reqs = [row2d(r) for r in _store["truck_requests"]]
        trip_cache = {}
        _ucount = {}
        for s in _store["scan_unload"]:
            _ucount[s.get("request_id")] = _ucount.get(s.get("request_id"), 0) + 1
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
            tv = truck.get("vendor_id") if truck else None
            if tv is None and r.get("vendor_id"): tv = r.get("vendor_id")
            r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == tv), "")
            r["plate_number"] = truck["plate_number"] if truck else ""
            r["updated_by"] = r.get("updated_by", "")
            updater = next((u for u in _store["users"] if u.get("email") == r.get("updated_by")), None)
            r["updated_by_name"] = updater.get("name", "") if updater else r.get("updated_by", "")
            r["updated_by_email"] = r.get("updated_by", "")
            r["foul_trip_approved_by"] = r.get("foul_trip_approved_by", "") or ""
            approver = next((u for u in _store["users"] if u.get("email") == r.get("foul_trip_approved_by")), None)
            r["foul_trip_approved_by_name"] = approver.get("name", "") if approver else r["foul_trip_approved_by"]
            r["foul_trip_approved_by_email"] = r["foul_trip_approved_by"]
            r["updated_at"] = to_gmt8(r.get("updated_at", ""))
            r["attachments"] = [row2d(a) for a in _store["attachments"] if a.get("truck_request_id") == r["id"]]
            _mf = next((m for m in _store["manifests"] if m.get("truck_request_id") == r["id"]), None)
            r["manifest"] = {"id": _mf.get("id"), "original_filename": _mf.get("original_filename"),
                             "file_size": _mf.get("file_size", 0), "id_count": len(_mf.get("ids") or []),
                             "created_at": _mf.get("created_at")} if _mf else None
            r["manifest_status"] = 1 if _mf else 0
            _da = _driver_row(r.get("driver_account_id")) if r.get("driver_account_id") else None
            r["driver_username"] = _da.get("username") if _da else None
            r["driver_name"] = (_da or {}).get("driver_name") or ""
            r["driver_phone"] = (_da or {}).get("driver_phone") or ""
            r["unload_scan_count"] = _ucount.get(r["id"], 0)
            r["unload_scan_closed"] = bool(r.get("unload_scan_closed_at"))
            r["pickup_scan_closed"] = bool(r.get("pickup_scan_closed_at"))
            r["revised_qty"] = _revised_qty(r)
            r["delivered_date"] = (r.get("end_unloading_datetime") or "")[:10]
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                r["trip_id"] = resolve_trip_id(r, truck_reqs)
                active = [x for x in truck_reqs if x.get("status_id") in (2, 3)]
                r["active_trip_count"] = len(active)
                r["is_consolidated"] = r.get("status_id") in (2, 3) and len(active) > 1
            else:
                r["trip_id"] = r.get("trip_id") or None
                cnt, consol = trip_counts_for(r, trip_cache)
                r["active_trip_count"] = cnt
                r["is_consolidated"] = consol
        if scope_vid is not None:
            reqs = [r for r in reqs if _owned_by_vendor(r, scope_vid)]
        if status_id: reqs = [r for r in reqs if r.get("status_id") == status_id]
        if account_id: reqs = [r for r in reqs if r.get("account_id") == account_id]
        if department_id: reqs = [r for r in reqs if r.get("department_id") == department_id]
        if origin_port_id: reqs = [r for r in reqs if r.get("origin_port_id") == origin_port_id]
        if destination_port_id: reqs = [r for r in reqs if r.get("destination_port_id") == destination_port_id]
        if truck_type_id: reqs = [r for r in reqs if r.get("truck_type_id") == truck_type_id]
        if vendor_id:
            def has_vid(r):
                if r.get("vendor_id") == vendor_id: return True
                truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
                return bool(truck and truck.get("vendor_id") == vendor_id)
            reqs = [r for r in reqs if has_vid(r)]
        if booking_from: reqs = [r for r in reqs if (r.get("booking_date") or "") >= booking_from]
        if booking_to: reqs = [r for r in reqs if (r.get("booking_date") or "") <= booking_to]
        if pickup_from: reqs = [r for r in reqs if (r.get("pickup_datetime") or "")[:10] >= pickup_from]
        if pickup_to: reqs = [r for r in reqs if (r.get("pickup_datetime") or "")[:10] <= pickup_to]
        if call_from: reqs = [r for r in reqs if (r.get("final_call_datetime") or "")[:10] >= call_from]
        if call_to: reqs = [r for r in reqs if (r.get("final_call_datetime") or "")[:10] <= call_to]
        if initial_call_from: reqs = [r for r in reqs if (r.get("call_datetime") or "")[:10] >= initial_call_from]
        if initial_call_to: reqs = [r for r in reqs if (r.get("call_datetime") or "")[:10] <= initial_call_to]
        if foul_from: reqs = [r for r in reqs if (r.get("foul_trip_date") or "")[:10] >= foul_from]
        if foul_to: reqs = [r for r in reqs if (r.get("foul_trip_date") or "")[:10] <= foul_to]
        if cancel_from: reqs = [r for r in reqs if (r.get("cancellation_date") or "")[:10] >= cancel_from]
        if cancel_to: reqs = [r for r in reqs if (r.get("cancellation_date") or "")[:10] <= cancel_to]
        if customs_from: reqs = [r for r in reqs if (r.get("customs_cleared_datetime") or "")[:10] >= customs_from]
        if customs_to: reqs = [r for r in reqs if (r.get("customs_cleared_datetime") or "")[:10] <= customs_to]
        if mawb:
            m = mawb.lower()
            reqs = [r for r in reqs if m in ((r.get("international_mawb") or "") + " " + (r.get("domestic_mawb") or "")).lower()]
        if plate:
            pl = plate.lower()
            reqs = [r for r in reqs if pl in (r.get("plate_number") or "").lower()]
        if trip:
            tp = trip.lower()
            reqs = [r for r in reqs if tp in (r.get("trip_id") or "").lower()]
        if manifest == "missing":
            reqs = [r for r in reqs if not r.get("manifest")]
        elif manifest == "uploaded":
            reqs = [r for r in reqs if r.get("manifest")]
        if search:
            s = search.lower()
            reqs = [r for r in reqs if s in (r.get("request_number", "") + r.get("requestor_name", "") + r.get("requestor_email", "") + r.get("vendor_name", "") + r.get("plate_number", "") + (r.get("trip_id") or "")).lower()]
        if sort_by == "trip_id":
            reqs.sort(key=lambda x: x.get("trip_id") or "", reverse=(sort_dir == "desc"))
        elif sort_by in ("quantity", "revised_qty"):
            reqs.sort(key=lambda x: x.get("revised_qty") or 0, reverse=(sort_dir == "desc"))
        else:
            reqs.sort(key=lambda x: ((v := x.get(sort_by, "")) is None, v if v is not None else 0), reverse=(sort_dir == "desc"))
        coords = get_port_coords_map()
        add_distances_to_requests(reqs, coords)
        total = len(reqs)
        start = (page - 1) * per_page
        page_items = reqs[start:start + per_page]
        _mark_trip_drivers(page_items)
        return {"items": page_items, "total": total, "page": page, "per_page": per_page}

    wh, pa = ["1=1"], []
    if scope_vid is not None: wh.append("tr.vendor_id=%s"); pa.append(scope_vid)
    if status_id: wh.append("tr.status_id=%s"); pa.append(status_id)
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if truck_type_id: wh.append("tr.truck_type_id=%s"); pa.append(truck_type_id)
    if vendor_id: wh.append("(COALESCE(tk.vendor_id, tr.vendor_id)=%s)"); pa.append(vendor_id)
    if booking_from: wh.append("tr.booking_date>=%s"); pa.append(booking_from)
    if booking_to: wh.append("tr.booking_date<=%s"); pa.append(booking_to)
    if pickup_from: wh.append("DATE(tr.pickup_datetime)>=%s"); pa.append(pickup_from)
    if pickup_to: wh.append("DATE(tr.pickup_datetime)<=%s"); pa.append(pickup_to)
    if call_from: wh.append("DATE(tr.final_call_datetime)>=%s"); pa.append(call_from)
    if call_to: wh.append("DATE(tr.final_call_datetime)<=%s"); pa.append(call_to)
    if initial_call_from: wh.append("DATE(tr.call_datetime)>=%s"); pa.append(initial_call_from)
    if initial_call_to: wh.append("DATE(tr.call_datetime)<=%s"); pa.append(initial_call_to)
    if foul_from: wh.append("tr.foul_trip_date>=%s"); pa.append(foul_from)
    if foul_to: wh.append("tr.foul_trip_date<=%s"); pa.append(foul_to)
    if cancel_from: wh.append("tr.cancellation_date>=%s"); pa.append(cancel_from)
    if cancel_to: wh.append("tr.cancellation_date<=%s"); pa.append(cancel_to)
    if customs_from: wh.append("DATE(tr.customs_cleared_datetime)>=%s"); pa.append(customs_from)
    if customs_to: wh.append("DATE(tr.customs_cleared_datetime)<=%s"); pa.append(customs_to)
    if mawb: wh.append("(tr.international_mawb LIKE %s OR tr.domestic_mawb LIKE %s)"); pa.extend([f"%{mawb}%", f"%{mawb}%"])
    if plate: wh.append("tk.plate_number LIKE %s"); pa.append(f"%{plate}%")
    if trip: wh.append("tr.trip_id LIKE %s"); pa.append(f"%{trip}%")
    if search: wh.append("(tr.request_number LIKE %s OR tr.requestor_name LIKE %s OR v.name LIKE %s OR tk.plate_number LIKE %s)"); s = f"%{search}%"; pa.extend([s, s, s, s])
    if manifest == "missing":
        wh.append("NOT EXISTS (SELECT 1 FROM request_manifests mf WHERE mf.truck_request_id=tr.id)")
    elif manifest == "uploaded":
        wh.append("EXISTS (SELECT 1 FROM request_manifests mf WHERE mf.truck_request_id=tr.id)")
    ws = " AND ".join(wh)
    if sort_by not in ("created_at", "request_number", "pickup_datetime", "status_id", "account_name", "department_name", "origin_port_name", "destination_port_name", "truck_type_name", "packaging_type_name", "quantity", "initial_quantity", "vendor_name", "plate_number", "booking_date", "trip_id", "status_name", "call_datetime", "customs_cleared_datetime", "special_instructions", "arrived_pickup_datetime", "start_loading_datetime", "end_loading_datetime", "arrived_dest_datetime", "start_unloading_datetime", "end_unloading_datetime",               "foul_trip_reason", "international_mawb", "domestic_mawb", "delivered_date", "foul_trip_date", "cancellation_date", "manifest_status", "updated_at",               "revised_qty", "unload_scan_count", "driver_username", "driver_name", "driver_phone"):
        sort_by = "created_at"
    _MFSQL = "EXISTS (SELECT 1 FROM request_manifests mf WHERE mf.truck_request_id=tr.id)"
    _MFCNT = "(SELECT COALESCE(MAX(mf.id_count),0) FROM request_manifests mf WHERE mf.truck_request_id=tr.id)"
    _UCNT = "(SELECT COUNT(*) FROM scan_unload_items si WHERE si.request_id=tr.id)"
    _REVQTY = (f"(CASE WHEN tr.unload_scan_closed_at IS NOT NULL THEN {_UCNT} "
               f"WHEN {_UCNT} > 0 THEN {_UCNT} WHEN {_MFSQL} THEN {_MFCNT} "
               f"ELSE COALESCE(tr.quantity,0) END)")
    sort_map = {"account_name": "a.name", "department_name": "d.name", "origin_port_name": "po.name", "destination_port_name": "pd.name", "truck_type_name": "tt.name", "packaging_type_name": "pt.name", "quantity": _REVQTY, "revised_qty": _REVQTY, "unload_scan_count": _UCNT, "driver_username": "da.username", "driver_name": "da.driver_name", "driver_phone": "da.driver_phone", "vendor_name": "COALESCE(v.name, vv.name)", "plate_number": "tk.plate_number", "booking_date": "tr.booking_date", "status_name": "ts.name", "delivered_date": "tr.end_unloading_datetime"}
    if sort_by == "trip_id":
        order_col = "tr.created_at"
    elif sort_by == "manifest_status":
        order_col = "(CASE WHEN EXISTS (SELECT 1 FROM request_manifests ms WHERE ms.truck_request_id=tr.id) THEN 1 ELSE 0 END)"
    else:
        order_col = sort_map.get(sort_by, f"tr.{sort_by}")
    sd = "DESC" if sort_dir == "desc" else "ASC"
    joins = """FROM truck_requests tr
        LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN departments d ON tr.department_id=d.id LEFT JOIN ports po ON tr.origin_port_id=po.id
        LEFT JOIN ports pd ON tr.destination_port_id=pd.id LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN vendors vv ON tr.vendor_id=vv.id LEFT JOIN users uu ON tr.updated_by=uu.email
        LEFT JOIN users fa ON tr.foul_trip_approved_by=fa.email
        LEFT JOIN driver_accounts da ON tr.driver_account_id=da.id"""
    total = (db_1(f"SELECT COUNT(*) as c {joins} WHERE {ws}", tuple(pa)) or {}).get("c", 0)
    pa.extend([per_page, (page - 1) * per_page])
    items = db_q(f"""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        tt.name as truck_type_name, pt.name as packaging_type_name,
        tk.plate_number, COALESCE(v.name, vv.name) as vendor_name, tr.updated_by, tr.updated_at,
        uu.name as updated_by_name, tr.updated_by as updated_by_email,
        da.username as driver_username, COALESCE(da.driver_name,'') as driver_name,
        COALESCE(da.driver_phone,'') as driver_phone,
        COALESCE(fa.name, tr.foul_trip_approved_by) as foul_trip_approved_by_name,
        tr.foul_trip_approved_by as foul_trip_approved_by_email
        {joins}
        WHERE {ws} ORDER BY {order_col} {sd} LIMIT %s OFFSET %s""", tuple(pa))
    for i in items: i["attachments"] = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (i["id"],))
    _mids = [i["id"] for i in items]
    _mans = db_q("SELECT * FROM request_manifests WHERE truck_request_id IN (%s)" % ",".join(["%s"] * len(_mids)), tuple(_mids)) if _mids else []
    _mmap = {m["truck_request_id"]: m for m in _mans}
    _ucnt = {}
    if _mids:
        for s in db_q("SELECT request_id, COUNT(*) as c FROM scan_unload_items WHERE request_id IN (%s) GROUP BY request_id" % ",".join(["%s"] * len(_mids)), tuple(_mids)):
            _ucnt[s["request_id"]] = s.get("c") or 0
    for i in items:
        m = _mmap.get(i["id"])
        i["manifest"] = {"id": m["id"], "original_filename": m["original_filename"], "file_size": m["file_size"],
                         "id_count": m.get("id_count") or 0, "created_at": m.get("created_at")} if m else None
        i["manifest_status"] = 1 if m else 0
        i["unload_scan_count"] = _ucnt.get(i["id"], 0)
        i["unload_scan_closed"] = bool(i.get("unload_scan_closed_at"))
        i["pickup_scan_closed"] = bool(i.get("pickup_scan_closed_at"))
        i["revised_qty"] = _revised_qty(i)
        i["updated_at"] = to_gmt8(i.get("updated_at"))
    trip_cache = {}
    for i in items:
        if i.get("assigned_truck_id") and i.get("status_id") in (2, 3, 4, 5, 7):
            truck_reqs = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (i["assigned_truck_id"],))
            i["trip_id"] = resolve_trip_id(i, truck_reqs)
            active = [x for x in truck_reqs if x.get("status_id") in (2, 3)]
            i["active_trip_count"] = len(active)
            i["is_consolidated"] = i.get("status_id") in (2, 3) and len(active) > 1
        else:
            i["trip_id"] = i.get("trip_id") or None
            cnt, consol = trip_counts_for(i, trip_cache)
            i["active_trip_count"] = cnt
            i["is_consolidated"] = consol
        i["delivered_date"] = (i.get("end_unloading_datetime") or "")[:10]
    if sort_by == "trip_id":
        items.sort(key=lambda x: x.get("trip_id") or "", reverse=(sort_dir == "desc"))
    coords = get_port_coords_map()
    add_distances_to_requests(items, coords)
    _mark_trip_drivers(items)
    return {"items": items, "total": total, "page": page, "per_page": per_page}

def _mark_trip_drivers(items):
    """trip_has_driver: an Allocated request whose trip has a driver on any of its
    requests - each of them gets the "remove driver" button, not only the ones that
    carry the driver themselves."""
    bases = {trip_base(i.get("trip_id")) for i in items if i.get("status_id") == 2 and i.get("trip_id")}
    bases.discard(None)
    with_driver = set()
    if bases:
        if LOCAL_MODE:
            rows = [x for x in _store["truck_requests"]
                    if x.get("status_id") == 2 and x.get("driver_account_id") and x.get("trip_id")]
        else:
            rows = db_q("""SELECT trip_id FROM truck_requests
                WHERE status_id=2 AND driver_account_id IS NOT NULL AND trip_id IS NOT NULL""")
        with_driver = {trip_base(x.get("trip_id")) for x in rows} & bases
    for i in items:
        i["trip_has_driver"] = bool(i.get("status_id") == 2 and (
            i.get("driver_account_id") or (i.get("trip_id") and trip_base(i.get("trip_id")) in with_driver)))

# ---------------------------------------------------------------------------
# CSV bulk creation (New Request page)
# ---------------------------------------------------------------------------

BULK_HEADER_MAP = {
    "department": "department", "dept": "department",
    "originport": "origin_port", "origin": "origin_port",
    "account": "account", "accountname": "account",
    "destinationport": "destination_port", "destination": "destination_port", "destport": "destination_port", "dest": "destination_port",
    "packagingtype": "packaging", "packaging": "packaging", "pkg": "packaging",
    "quantity": "quantity", "qty": "quantity",
    "internationalmawb": "international_mawb", "imawb": "international_mawb",
    "domesticmawb": "domestic_mawb", "dmawb": "domestic_mawb",
    "initialcalldatetimetbc": "call_datetime", "initialcalldatetime": "call_datetime", "calltbc": "call_datetime",
    "customscleareddatetime": "customs_cleared_datetime", "customs": "customs_cleared_datetime", "customscleared": "customs_cleared_datetime",
    "weightkg": "weight_kg", "weight": "weight_kg",
    "volumecbm": "volume_cbm", "volume": "volume_cbm",
    "specialinstructions": "special_instructions", "notes": "special_instructions", "remarks": "special_instructions",
}
BULK_REQUIRED = ("department", "origin_port", "account", "destination_port", "packaging", "quantity", "call_datetime")
BULK_LABELS = {
    "department": "Department", "origin_port": "Origin Port", "account": "Account",
    "destination_port": "Destination Port", "packaging": "Packaging Type", "quantity": "Quantity",
    "international_mawb": "International MAWB", "domestic_mawb": "Domestic MAWB",
    "call_datetime": "Initial Call datetime (TBC)", "customs_cleared_datetime": "Customs Cleared Date/Time",
    "weight_kg": "Weight (KG)", "volume_cbm": "Volume (CBM)", "special_instructions": "Special Instructions",
}
BULK_COLUMNS = tuple(BULK_LABELS.keys())

def _norm_hdr(h):
    return re.sub(r"[^a-z0-9]", "", str(h or "").lower())

def _bulk_txt(v):
    return re.sub(r"\s+", " ", str(v or "")).strip()

def _bulk_ctx():
    def lc_map(rows):
        out = {}
        for x in rows:
            k = str(x.get("name") or "").strip().lower()
            if k and k not in out:
                out[k] = x.get("id")
        return out
    if LOCAL_MODE:
        return {"departments": lc_map(_store["departments"]), "ports": lc_map(_store["ports"]),
                "accounts": lc_map(_store["accounts"]), "packaging": lc_map(_store["packaging_types"])}
    return {"departments": lc_map(db_q("SELECT id, name FROM departments")),
            "ports": lc_map(db_q("SELECT id, name FROM ports")),
            "accounts": lc_map(db_q("SELECT id, name FROM accounts")),
            "packaging": lc_map(db_q("SELECT id, name FROM packaging_types"))}

_BULK_MONTHS = {m: i for i, m in enumerate(
    ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], start=1)}
BULK_DT_HELP = ("not a valid date/time - use e.g. 2026-10-15 09:00, 15/10/2026 9:00 "
                "or 15-Oct-2026 9:00")

def _bulk_parse_dt(v):
    """Read a date/time the way people (and Excel) write it.

    Excel re-saves the template's '2026-10-15 09:00' in the computer's own format,
    e.g. '15/10/2026 9:00' or '10/15/2026 9:00 AM', so all of these are accepted:
    YYYY-MM-DD / YYYY/MM/DD, DD/MM/YYYY (MM/DD/YYYY only when the second number
    can only be a day, e.g. 10/15/2026), DD-Mon-YYYY, 2-digit years,
    optional HH:MM[:SS] with AM/PM, and Excel serial numbers.
    Day-first is used when both readings are possible (Philippine format)."""
    s = _bulk_txt(v).replace("T", " ").replace(".", "/") if not re.fullmatch(r"\d+(\.\d+)?", _bulk_txt(v)) else _bulk_txt(v)
    if not s:
        return None, None
    # Excel serial date (days since 1899-12-30), with an optional time fraction.
    if re.fullmatch(r"\d+(\.\d+)?", s):
        try:
            f = float(s)
            if 20000 < f < 80000:
                d = datetime(1899, 12, 30) + timedelta(days=f)
                d = d.replace(second=0, microsecond=0) + timedelta(minutes=1 if d.second >= 30 else 0)
                return (d.strftime("%Y-%m-%dT%H:%M") if f % 1 else d.strftime("%Y-%m-%d")), None
        except (ValueError, OverflowError):
            pass
        return None, BULK_DT_HELP
    m = re.match(r"^(\S+)(?:\s+(\d{1,2}):(\d{2})(?::(\d{2}))?\s*([AaPp][Mm])?)?$", s)
    if not m:
        return None, BULK_DT_HELP
    dpart, hh, mi, ss, ampm = m.groups()
    y = mo = dd = None
    parts = re.split(r"[-/]", dpart)
    if len(parts) != 3:
        return None, BULK_DT_HELP
    a, b, c = parts
    try:
        if re.fullmatch(r"\d{4}", a):                       # YYYY-MM-DD
            y, mo, dd = int(a), int(b), int(c)
        elif b.isalpha():                                    # 15-Oct-2026
            mo = _BULK_MONTHS.get(b[:3].lower())
            dd, y = int(a), int(c)
        else:                                                # DD/MM/YYYY or MM/DD/YYYY
            p1, p2, y = int(a), int(b), int(c)
            if p1 > 12 or p2 <= 12:
                dd, mo = p1, p2                              # day first (default)
            else:
                mo, dd = p1, p2                              # 10/15/2026 can only be month first
        if y is not None and y < 100:
            y += 2000
    except ValueError:
        return None, BULK_DT_HELP
    if not (y and mo and dd):
        return None, BULK_DT_HELP
    h = int(hh) if hh is not None else 0
    if ampm:
        if h < 1 or h > 12:
            return None, BULK_DT_HELP
        h = (h % 12) + (12 if ampm.lower() == "pm" else 0)
    try:
        d = datetime(y, mo, dd, h, int(mi or 0), int(ss or 0))
    except ValueError:
        return None, "not a real calendar date"
    if hh is not None:
        return d.strftime("%Y-%m-%dT%H:%M"), None
    return d.strftime("%Y-%m-%d"), None

def _bulk_validate_row(data, ctx):
    """Validate one CSV row against master data -> (issues, resolved ids/values)."""
    issues = []

    def txt(k):
        return _bulk_txt(data.get(k))

    # name -> id lookups
    dep = None
    if not txt("department"):
        issues.append("Department is required")
    else:
        dep = ctx["departments"].get(txt("department").lower())
        if dep is None:
            issues.append(f'Department "{txt("department")}" not found in Master Library')
    acc = None
    if not txt("account"):
        issues.append("Account is required")
    else:
        acc = ctx["accounts"].get(txt("account").lower())
        if acc is None:
            issues.append(f'Account "{txt("account")}" not found in Master Library')
    org = None
    if not txt("origin_port"):
        issues.append("Origin Port is required")
    else:
        org = ctx["ports"].get(txt("origin_port").lower())
        if org is None:
            issues.append(f'Origin Port "{txt("origin_port")}" not found in Master Library')
    dst = None
    if not txt("destination_port"):
        issues.append("Destination Port is required")
    else:
        dst = ctx["ports"].get(txt("destination_port").lower())
        if dst is None:
            issues.append(f'Destination Port "{txt("destination_port")}" not found in Master Library')
    if org is not None and dst is not None and org == dst:
        issues.append("Destination Port cannot be the same as Origin Port")
    pkg = None
    if not txt("packaging"):
        issues.append("Packaging Type is required")
    else:
        pkg = ctx["packaging"].get(txt("packaging").lower())
        if pkg is None:
            issues.append(f'Packaging Type "{txt("packaging")}" not found in Master Library')
    qty = None
    q = txt("quantity")
    if not q:
        issues.append("Quantity is required")
    else:
        try:
            fq = float(q)
            if fq != int(fq) or int(fq) < 1:
                raise ValueError
            qty = int(fq)
        except Exception:
            issues.append(f'Quantity "{q}" must be a whole number of at least 1')
    wt = 0.0
    if txt("weight_kg"):
        try:
            wt = float(txt("weight_kg"))
            if wt < 0:
                raise ValueError
        except Exception:
            issues.append(f'Weight (KG) "{txt("weight_kg")}" must be a number')
    vol = 0.0
    if txt("volume_cbm"):
        try:
            vol = float(txt("volume_cbm"))
            if vol < 0:
                raise ValueError
        except Exception:
            issues.append(f'Volume (CBM) "{txt("volume_cbm")}" must be a number')
    call_dt, call_err = _bulk_parse_dt(data.get("call_datetime"))
    if call_err:
        issues.append(f'Initial Call datetime (TBC) {call_err}')
    elif not call_dt:
        issues.append("Initial Call datetime (TBC) is required")
    cust_dt, cust_err = _bulk_parse_dt(data.get("customs_cleared_datetime"))
    if cust_err:
        issues.append(f'Customs Cleared Date/Time {cust_err}')
    imawb = txt("international_mawb")
    dmawb = txt("domestic_mawb")
    if len(imawb) > 100:
        issues.append("International MAWB is too long (max 100 characters)")
    if len(dmawb) > 100:
        issues.append("Domestic MAWB is too long (max 100 characters)")
    resolved = {
        "account_id": acc, "department_id": dep, "origin_port_id": org, "destination_port_id": dst,
        "packaging_type_id": pkg, "quantity": qty, "international_mawb": imawb or None,
        "domestic_mawb": dmawb or None, "call_datetime": call_dt, "customs_cleared_datetime": cust_dt,
        "weight_kg": wt, "volume_cbm": vol, "special_instructions": txt("special_instructions"),
    }
    return issues, resolved

def _bulk_parse_csv(content: bytes):
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = content.decode("latin-1", errors="replace")
    try:
        dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t")
    except Exception:
        dialect = csv.excel
    rows = list(csv.reader(io.StringIO(text), dialect))
    if not rows:
        raise HTTPException(400, "The CSV file is empty")
    colmap = {}
    for i, h in enumerate(rows[0]):
        key = BULK_HEADER_MAP.get(_norm_hdr(h))
        if key and key not in colmap:
            colmap[key] = i
    missing = [BULK_LABELS[k] for k in BULK_REQUIRED if k not in colmap]
    if missing:
        raise HTTPException(400, "Missing required column(s): " + ", ".join(missing))
    out = []
    for ln, r in enumerate(rows[1:], start=2):
        if not any(str(c).strip() for c in r):
            continue
        data = {key: (r[i] if i < len(r) else "") for key, i in colmap.items()}
        out.append((ln, data))
    return out

@app.get("/api/requests/bulk-template")
def bulk_template(request: Request):
    get_user(request)
    if LOCAL_MODE:
        depts = [d["name"] for d in _store["departments"]]
        accts = [a["name"] for a in _store["accounts"]]
        pkgs = [p["name"] for p in _store["packaging_types"]]
        pts = [p["name"] for p in _store["ports"]]
    else:
        depts = [r["name"] for r in db_q("SELECT name FROM departments ORDER BY id")]
        accts = [r["name"] for r in db_q("SELECT name FROM accounts ORDER BY id")]
        pkgs = [r["name"] for r in db_q("SELECT name FROM packaging_types ORDER BY id")]
        pts = [r["name"] for r in db_q("SELECT name FROM ports ORDER BY id")]
    ex_dept = depts[0] if depts else "PHCC"
    ex_acct = accts[0] if accts else "Ninja Van PH"
    ex_pkg = pkgs[0] if pkgs else "Pallet"
    ex_org = pts[0] if pts else "Manila Port"
    ex_dst = pts[1] if len(pts) > 1 else ("Cebu Port" if ex_org != "Cebu Port" else "Davao Port")
    ex = [ex_dept, ex_org, ex_acct, ex_dst, ex_pkg, "10", "988-12345678", "DOM-00123",
          "2026-10-15 09:00", "2026-10-15 10:00", "150.5", "1.25", "Handle with care"]
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow([BULK_LABELS[k] for k in BULK_COLUMNS])
    w.writerow(ex)
    return Response("\ufeff" + buf.getvalue(), media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": 'attachment; filename="bulk_requests_template.csv"'})

@app.post("/api/requests/bulk/validate")
async def bulk_validate(request: Request, file: UploadFile = File(...)):
    get_user(request)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(400, "CSV file is too large (max 10MB)")
    ctx = await run_in_threadpool(_bulk_ctx)
    parsed = await run_in_threadpool(_bulk_parse_csv, content)
    out = []
    for ln, data in parsed:
        issues, _resolved = _bulk_validate_row(data, ctx)
        out.append({"row": ln, "data": data, "issues": issues, "valid": not issues})
    ready = sum(1 for r in out if r["valid"])
    return {"total": len(out), "ready_count": ready, "issue_count": len(out) - ready, "rows": out}

@app.post("/api/requests/bulk")
async def bulk_create(request: Request):
    user = get_user(request)
    body = await request.json()
    rows = body.get("rows")
    if not isinstance(rows, list) or not rows:
        raise HTTPException(400, "No rows to create - upload a CSV first")
    ctx = await run_in_threadpool(_bulk_ctx)
    results, created, failed = [], 0, 0
    for i, data in enumerate(rows, start=1):
        row_no = data.get("_row") if isinstance(data, dict) and isinstance(data.get("_row"), int) else i
        if not isinstance(data, dict):
            failed += 1
            results.append({"row": row_no, "ok": False, "issues": ["Invalid row"]})
            continue
        issues, resolved = _bulk_validate_row(data, ctx)
        if issues:
            failed += 1
            results.append({"row": row_no, "ok": False, "issues": issues})
            continue
        try:
            inserted = _insert_request(user, resolved)
            created += 1
            results.append({"row": row_no, "ok": True, "request_number": (inserted or {}).get("request_number", "")})
        except Exception as e:
            failed += 1
            results.append({"row": row_no, "ok": False, "issues": [str(e)[:200] or "Could not create this request"]})
    return {"total": len(rows), "created": created, "failed": failed, "results": results}

@app.get("/api/requests/{rid}")
def get_request(rid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == rid:
                if not _owned_by_vendor(r, scope_vid): raise HTTPException(404, "Not found")
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
                _mfm = next((m for m in _store["manifests"] if m.get("truck_request_id") == rid), None)
                res["manifest"] = {"id": _mfm.get("id"), "original_filename": _mfm.get("original_filename"),
                                   "file_size": _mfm.get("file_size", 0), "id_count": len(_mfm.get("ids") or []),
                                   "created_at": _mfm.get("created_at")} if _mfm else None
                if res.get("assigned_truck_id") and res.get("status_id") in (2, 3, 4, 5, 7):
                    peers = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == res["assigned_truck_id"]]
                    res["trip_id"] = resolve_trip_id(res, peers)
                return _request_view_extras(res)
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
    if not _owned_by_vendor(item, scope_vid): raise HTTPException(404, "Not found")
    item["attachments"] = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (rid,))
    _mrow = db_1("SELECT id, original_filename, file_size, id_count, created_at FROM request_manifests WHERE truck_request_id=%s", (rid,))
    item["manifest"] = _mrow
    if item.get("assigned_truck_id") and item.get("status_id") in (2, 3, 4, 5, 7) and not item.get("trip_id"):
        peers = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
            account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
            (item["assigned_truck_id"],))
        item["trip_id"] = resolve_trip_id(item, peers)
    return _request_view_extras(row2d(item))

def _request_view_extras(r):
    """Fields the request view popup shows beside the stored columns: truck plate,
    vendor, driver, delivered date and the foul-trip approver's name."""
    r["plate_number"] = _truck_plate(r.get("assigned_truck_id")) if r.get("assigned_truck_id") else ""
    vid = r.get("vendor_id")
    if not vid and r.get("assigned_truck_id"):
        t = (next((x for x in _store["trucks"] if x["id"] == r["assigned_truck_id"]), None) if LOCAL_MODE
             else db_1("SELECT vendor_id FROM trucks WHERE id=%s", (r["assigned_truck_id"],)))
        vid = (t or {}).get("vendor_id")
    if vid:
        v = (next((x for x in _store["vendors"] if x["id"] == vid), None) if LOCAL_MODE
             else db_1("SELECT name FROM vendors WHERE id=%s", (vid,)))
        r["vendor_name"] = (v or {}).get("name") or ""
    else:
        r["vendor_name"] = ""
    d = _driver_row(r.get("driver_account_id")) if r.get("driver_account_id") else None
    r["driver_username"] = (d or {}).get("username") or ""
    r["driver_name"] = (d or {}).get("driver_name") or ""
    r["driver_phone"] = (d or {}).get("driver_phone") or ""
    r["delivered_date"] = (str(r.get("end_unloading_datetime") or ""))[:10]
    appr = r.get("foul_trip_approved_by") or ""
    if appr:
        u = (next((x for x in _store["users"] if x.get("email") == appr), None) if LOCAL_MODE
             else db_1("SELECT name FROM users WHERE email=%s", (appr,)))
        r["foul_trip_approved_by_name"] = (u or {}).get("name") or appr
    else:
        r["foul_trip_approved_by_name"] = ""
    upd = r.get("updated_by") or ""
    if upd:
        uu = (next((x for x in _store["users"] if x.get("email") == upd), None) if LOCAL_MODE
              else db_1("SELECT name FROM users WHERE email=%s", (upd,)))
        r["updated_by_name"] = (uu or {}).get("name") or upd
    else:
        r["updated_by_name"] = ""
    r["updated_at"] = to_gmt8(r.get("updated_at")) if r.get("updated_at") else None
    r["pickup_scan_closed"] = bool(r.get("pickup_scan_closed_at"))
    r["unload_scan_closed"] = bool(r.get("unload_scan_closed_at"))
    r["scan_trip_base"] = trip_base(r.get("trip_id")) or f"req-{r.get('id')}"
    for k in ("trip_id", "drop_sequence", "late_reason", "special_instructions", "foul_trip_reason",
              "foul_trip_date", "foul_trip_count", "cancellation_date", "final_call_datetime"):
        r.setdefault(k, None)
    for k in ("final_call_datetime", "call_datetime", "customs_cleared_datetime", "foul_trip_approved_at",
              *MILESTONE_FIELDS):
        if r.get(k):
            r[k] = to_gmt8(r[k])
    return r

def _insert_request(user, body):
    """Insert one validated truck request — shared by single create and CSV bulk."""
    rn = gen_req_no()
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
            "quantity": body.get("quantity", 0), "initial_quantity": body.get("quantity", 0), "weight_kg": body.get("weight_kg", 0), "volume_cbm": body.get("volume_cbm", 0),
            "special_instructions": body.get("special_instructions", ""), "status_id": body.get("status_id", 1),
            "international_mawb": body.get("international_mawb") or "",
            "domestic_mawb": body.get("domestic_mawb") or "",
            "assigned_truck_id": None, "estimated_cost": body.get("estimated_cost", 0), "actual_cost": 0,
            "vendor_id": None, "final_call_datetime": None, "trip_id": None, "drop_sequence": None,
            "trip_date": None, "arrived_pickup_datetime": None, "start_loading_datetime": None,
            "end_loading_datetime": None, "arrived_dest_datetime": None, "start_unloading_datetime": None,
            "end_unloading_datetime": None, "foul_trip_reason": None, "foul_trip_count": None,
            "foul_trip_approved_by": None, "foul_trip_approved_at": None,
            "created_at": nows(), "updated_at": nows()}
        _store["truck_requests"].append(req)
        pid = nid("pending_allocations")
        _store["pending_allocations"].append({"id": pid, "truck_request_id": rid, "suggested_truck_id": None, "suggestion_reason": "New request", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
        return row2d(req)
    rid = db_i("""INSERT INTO truck_requests (request_number,requestor_email,requestor_name,account_id,department_id,
        origin_port_id,destination_port_id,pickup_datetime,delivery_datetime,call_datetime,customs_cleared_datetime,booking_date,
        truck_type_id,packaging_type_id,quantity,initial_quantity,weight_kg,volume_cbm,special_instructions,status_id,estimated_cost,
        international_mawb,domestic_mawb)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (rn, user["email"], user["name"], body["account_id"], body["department_id"],
         body["origin_port_id"], body["destination_port_id"], body.get("pickup_datetime"), body.get("delivery_datetime"),
         body.get("call_datetime"), body.get("customs_cleared_datetime"), booking_date,
         body.get("truck_type_id"), body.get("packaging_type_id"), body.get("quantity", 0), body.get("quantity", 0),
         body.get("weight_kg", 0),
         body.get("volume_cbm", 0), body.get("special_instructions", ""), body.get("status_id", 1), body.get("estimated_cost", 0),
         body.get("international_mawb") or None, body.get("domestic_mawb") or None))
    db_i("INSERT INTO pending_allocations (truck_request_id,suggestion_reason) VALUES (%s,'New request')", (rid,))
    return db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))

@app.post("/api/requests")
async def create_request(request: Request):
    try:
        user = get_user(request)
        body = await request.json()
        for f in ("account_id", "department_id", "origin_port_id", "destination_port_id", "packaging_type_id"):
            if not body.get(f): raise HTTPException(400, f"{f} required")
        if body.get("quantity", 0) <= 0: raise HTTPException(400, "Quantity must be greater than 0")
        if not str(body.get("call_datetime") or "").strip():
            raise HTTPException(400, "Initial Call datetime (TBC) is required")
        if body.get("origin_port_id") == body.get("destination_port_id"):
            raise HTTPException(400, "Origin port cannot be the same as destination port")
        return _insert_request(user, body)

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
    if any(k in body for k in ("actual_cost",) + BULK_COST_FIELDS):
        body["cost_updated_by"] = user.get("email", "")
        body["cost_updated_at"] = nows()
    if is_vendor_role(user.get("role", "")):
        for k in ("account_id", "department_id", "origin_port_id", "destination_port_id",
                  "international_mawb", "domestic_mawb", "call_datetime",
                  "customs_cleared_datetime", "final_call_datetime"):
            body.pop(k, None)
        if body.get("status_id") is not None:
            try:
                want = int(body.get("status_id"))
            except (TypeError, ValueError):
                want = None
            if want == 1:
                cur_row = (next((x for x in _store["truck_requests"] if x["id"] == rid), None) if LOCAL_MODE
                           else db_1("SELECT status_id FROM truck_requests WHERE id=%s", (rid,)))
                if cur_row and cur_row.get("status_id") != 1:
                    raise HTTPException(403, "Vendor roles cannot move a request back to Pending")
    if "actual_cost" in body:
        # A Foul Trip never carries an Actual Cost (it is charged through the Foul Trip Cost).
        tgt = body.get("status_id")
        if tgt is None:
            cr = (next((x for x in _store["truck_requests"] if x["id"] == rid), None) if LOCAL_MODE
                  else db_1("SELECT status_id FROM truck_requests WHERE id=%s", (rid,)))
            tgt = cr.get("status_id") if cr else None
        try: tgt = int(tgt) if tgt is not None else None
        except (TypeError, ValueError): tgt = None
        if tgt == 7:
            body["actual_cost"] = 0
    for k in ("truck_type_id", "assigned_truck_id"):
        if k in body and body[k] in (0, "0", ""):
            body[k] = None
    fields = ("account_id", "department_id", "origin_port_id", "destination_port_id", "pickup_datetime",
              "delivery_datetime", "call_datetime", "customs_cleared_datetime", "booking_date",
              "final_call_datetime", "truck_type_id", "packaging_type_id", "quantity", "weight_kg", "volume_cbm",
              "special_instructions", "international_mawb", "domestic_mawb", "status_id",
              "assigned_truck_id", "estimated_cost", "actual_cost",
              "trip_date", "arrived_pickup_datetime", "start_loading_datetime", "end_loading_datetime",
              "arrived_dest_datetime", "start_unloading_datetime", "end_unloading_datetime", "foul_trip_reason",
              "foul_trip_date", "cancellation_date", "foul_trip_count",
              "toll_fee", "management_fee", "fuel", "parking", "miscellaneous", "manpower", "toll",
              "welfare", "wh_rental", "toll_fee_easytrip", "toll_fee_autosweep",
              "drop_sequence", "updated_by", "cost_updated_by", "cost_updated_at", "updated_at")
    new_status = body.get("status_id")
    if new_status == 4:
        validate_delivered_chronology(body)
    # Foul Trip Count Confirmation: compulsory (1 or 2) the moment a request becomes a
    # Foul Trip, and any count that is supplied at any time must be 1 or 2.
    if "foul_trip_count" in body:
        raw_cnt = body.get("foul_trip_count")
        if raw_cnt is None or str(raw_cnt).strip() == "":
            body["foul_trip_count"] = None
        else:
            try:
                cnt_val = int(str(raw_cnt).strip())
            except ValueError:
                raise HTTPException(400, "Foul Trip Count Confirmation must be 1 or 2")
            if cnt_val not in (1, 2):
                raise HTTPException(400, "Foul Trip Count Confirmation must be 1 or 2")
            body["foul_trip_count"] = cnt_val
    foul_touched = any(k in body for k in ("foul_trip_date", "foul_trip_reason", "foul_trip_count"))
    cur_row = None
    if new_status in (5, 7) or foul_touched:
        if LOCAL_MODE:
            cur_row = next((x for x in _store["truck_requests"] if x["id"] == rid), None)
        else:
            cur_row = db_1("SELECT status_id, foul_trip_date, foul_trip_reason, foul_trip_count FROM truck_requests WHERE id=%s", (rid,))
        cur_status = cur_row.get("status_id") if cur_row else None
        if new_status in (5, 7) and cur_status != new_status:
            if new_status == 7:
                if not (str(body.get("foul_trip_date") or "").strip()):
                    raise HTTPException(400, "Foul Trip Date is required when status is Foul Trip")
                if not (str(body.get("foul_trip_reason") or "").strip()):
                    raise HTTPException(400, "Foul Trip Reason is required when status is Foul Trip")
                if body.get("foul_trip_count") not in (1, 2):
                    raise HTTPException(400, "Foul Trip Count Confirmation (1 or 2) is required when status is Foul Trip")
            if new_status == 5:
                if not (str(body.get("cancellation_date") or "").strip()):
                    raise HTTPException(400, "Cancellation Date is required when status is Cancelled")
    # A green-tick approval only ever covers the foul trip as it stood when it was given:
    # entering Foul Trip, changing its date / reason / count afterwards, or leaving the status
    # withdraws it — so the trip has to be reviewed again before it counts on Cost Analysis.
    reset_approval = False
    if cur_row is not None:
        cur_status = cur_row.get("status_id")
        eff_status = new_status if new_status is not None else cur_status
        if eff_status != cur_status:
            reset_approval = True
        elif eff_status == 7:
            for k in ("foul_trip_date", "foul_trip_reason", "foul_trip_count"):
                if k in body and str(body.get(k) or "").strip() != str(cur_row.get(k) or "").strip():
                    reset_approval = True
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == rid:
                old_status = r.get("status_id")
                if new_status and old_status: validate_status_transition(old_status, new_status)
                for k in fields:
                    if k in body: r[k] = body[k]
                if new_status in (4, 5, 7) and r.get("assigned_truck_id"):
                    peers = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                    _ensure_trip_id_before_terminal(r, peers)
                if new_status == 1:
                    old_tid = r.get("assigned_truck_id")
                    old_base = trip_base(r.get("trip_id"))
                    reverted_seq = r.get("drop_sequence")
                    r["assigned_truck_id"] = None
                    r["drop_sequence"] = None
                    r["trip_id"] = None
                    r["estimated_cost"] = 0
                    r["actual_cost"] = 0
                    r["truck_type_id"] = None
                    r["vendor_id"] = None
                    r["final_call_datetime"] = None
                    has_pa = any(pa["truck_request_id"] == rid and pa.get("is_accepted") is None for pa in _store["pending_allocations"])
                    if not has_pa:
                        pid = nid("pending_allocations")
                        _store["pending_allocations"].append({"id": pid, "truck_request_id": rid, "suggested_truck_id": None, "suggestion_reason": "Reverted to pending", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
                    # Drop numbers belong to the trip, not the truck: only this trip closes up.
                    if old_base:
                        resequence_trip_if_freed(old_base)
                    if old_tid:
                        freeze_trip_ids_on_truck(old_tid)
                        remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == old_tid and x.get("status_id") not in (4, 5, 7)]
                        if not remaining:
                            for t in _store["trucks"]:
                                if t["id"] == old_tid: t["status"] = "available"; break
                        else:
                            recalculate_trip_rates(old_tid)
                if new_status == 4 and r.get("assigned_truck_id"):
                    if r.get("actual_cost", 0) == 0: r["actual_cost"] = r.get("estimated_cost", 0)
                    tid = r["assigned_truck_id"]
                    archive_truck_requests(tid, request.headers.get("X-Forwarded-Email", ""))
                    remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7)]
                    if not remaining:
                        for t in _store["trucks"]:
                            if t["id"] == tid: t["status"] = "available"; break
                        for x in _store["truck_requests"]:
                            if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7): x["assigned_truck_id"] = None
                    else:
                        recalculate_trip_rates(tid)
                if new_status == 5 and r.get("assigned_truck_id"):
                    tid = r["assigned_truck_id"]
                    archive_truck_requests(tid, request.headers.get("X-Forwarded-Email", ""))
                    remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7)]
                    if not remaining:
                        for t in _store["trucks"]:
                            if t["id"] == tid: t["status"] = "available"; break
                    else:
                        recalculate_trip_rates(tid)
                if new_status == 7:
                    if r.get("estimated_cost", 0) == 0 and r.get("assigned_truck_id"):
                        truck = next((t for t in _store["trucks"] if t["id"] == r["assigned_truck_id"]), None)
                        if truck:
                            tt_id = r.get("truck_type_id") or truck.get("truck_type_id")
                            card, est, _ = price_request(r, truck.get("vendor_id"), tt_id, trip_primary_dest(r))
                            if card: r["estimated_cost"] = est
                    # A Foul Trip has no Actual Cost - it is charged through the Foul Trip Cost.
                    r["actual_cost"] = 0
                    _store["pending_allocations"] = [p for p in _store["pending_allocations"] if p.get("truck_request_id") != rid or p.get("is_accepted") is not None]
                    tid = r.get("assigned_truck_id")
                    if tid:
                        archive_truck_requests(tid, request.headers.get("X-Forwarded-Email", ""))
                        remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7)]
                        if not remaining:
                            for t in _store["trucks"]:
                                if t["id"] == tid: t["status"] = "available"; break
                        else:
                            recalculate_trip_rates(tid)
                if reset_approval:
                    r["foul_trip_approved_by"] = None
                    r["foul_trip_approved_at"] = None
                return row2d(r)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for k in fields:
        if k in body: sets.append(f"{k}=%s"); params.append(body[k])
    if reset_approval:
        sets.extend(["foul_trip_approved_by=NULL", "foul_trip_approved_at=NULL"])
    if not sets: raise HTTPException(400, "Nothing to update")
    if new_status:
        cur = db_1("SELECT status_id FROM truck_requests WHERE id=%s", (rid,))
        if cur and cur.get("status_id"): validate_status_transition(cur["status_id"], new_status)
    params.append(rid)
    db_x(f"UPDATE truck_requests SET {','.join(sets)} WHERE id=%s", tuple(params))
    if new_status in (4, 5, 7):
        cur2 = db_1("SELECT id, request_number, status_id, drop_sequence, trip_id, account_id, assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
        if cur2 and cur2.get("assigned_truck_id") and not cur2.get("trip_id"):
            peers = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (cur2["assigned_truck_id"],))
            _ensure_trip_id_before_terminal(cur2, peers)
            if cur2.get("trip_id"):
                db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s AND trip_id IS NULL", (cur2["trip_id"], rid))
    if new_status == 1:
        req = db_1("SELECT assigned_truck_id, drop_sequence, trip_id FROM truck_requests WHERE id=%s", (rid,))
        old_tid = req.get("assigned_truck_id") if req else None
        old_base = trip_base(req.get("trip_id")) if req else None
        reverted_seq = req.get("drop_sequence") if req else None
        db_x("""UPDATE truck_requests SET assigned_truck_id=NULL, drop_sequence=NULL, trip_id=NULL,
            estimated_cost=0, actual_cost=0, truck_type_id=NULL, vendor_id=NULL, final_call_datetime=NULL
            WHERE id=%s""", (rid,))
        # Drop numbers belong to the trip, not the truck: only this trip closes up.
        if old_base:
            resequence_trip_if_freed(old_base)
        if old_tid:
            freeze_trip_ids_on_truck(old_tid)
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (old_tid,))
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
            email = request.headers.get("X-Forwarded-Email", "")
            archive_truck_requests(req["assigned_truck_id"], email)
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (req["assigned_truck_id"],))
            if remaining and remaining.get("c", 0) == 0:
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (req["assigned_truck_id"],))
                db_x("UPDATE truck_requests SET assigned_truck_id=NULL WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (req["assigned_truck_id"],))
            else:
                recalculate_trip_rates(req["assigned_truck_id"])
    if new_status == 5:
        req = db_1("SELECT assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
        if req and req.get("assigned_truck_id"):
            email = request.headers.get("X-Forwarded-Email", "")
            archive_truck_requests(req["assigned_truck_id"], email)
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (req["assigned_truck_id"],))
            if remaining and remaining.get("c", 0) == 0:
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (req["assigned_truck_id"],))
            else:
                recalculate_trip_rates(req["assigned_truck_id"])
    if new_status == 7:
        db_x("DELETE FROM pending_allocations WHERE truck_request_id=%s AND is_accepted IS NULL", (rid,))
        req = db_1("SELECT id, assigned_truck_id, drop_sequence, estimated_cost, actual_cost, origin_port_id, destination_port_id, truck_type_id, booking_date FROM truck_requests WHERE id=%s", (rid,))
        if req and req.get("assigned_truck_id"):
            if not req.get("estimated_cost"):
                truck = db_1("SELECT vendor_id, truck_type_id FROM trucks WHERE id=%s", (req["assigned_truck_id"],))
                if truck:
                    tt_id = req.get("truck_type_id") or truck.get("truck_type_id")
                    full = db_1("SELECT id, trip_id, drop_sequence, origin_port_id, destination_port_id, booking_date FROM truck_requests WHERE id=%s", (rid,))
                    card, est, _ = price_request(full, truck["vendor_id"], tt_id, trip_primary_dest(full))
                    if card and est: db_x("UPDATE truck_requests SET estimated_cost=%s WHERE id=%s", (est, rid))
            # A Foul Trip has no Actual Cost - it is charged through the Foul Trip Cost.
            db_x("UPDATE truck_requests SET actual_cost=0 WHERE id=%s", (rid,))
            email = request.headers.get("X-Forwarded-Email", "")
            archive_truck_requests(req["assigned_truck_id"], email)
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (req["assigned_truck_id"],))
            if remaining and remaining.get("c", 0) == 0:
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (req["assigned_truck_id"],))
            else:
                recalculate_trip_rates(req["assigned_truck_id"])
        else:
            db_x("UPDATE truck_requests SET actual_cost=0 WHERE id=%s", (rid,))
    return db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))

# ---------------------------------------------------------------------------
# Foul Trip Approval: the green tick that lets a foul trip into Cost Analysis
# ---------------------------------------------------------------------------

@app.post("/api/requests/{rid}/approve-foul-trip")
def approve_foul_trip(rid: int, request: Request):
    """Admin green tick: records who reviewed a Foul Trip and when."""
    user = require_admin(request)
    email = user.get("email", "")
    stamp = nows()
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == rid:
                if r.get("status_id") != 7:
                    raise HTTPException(400, "Only Foul Trip requests can be approved")
                if r.get("foul_trip_count") not in (1, 2):
                    raise HTTPException(400, "Foul Trip Count Confirmation (1 or 2) is required before approval")
                r["foul_trip_approved_by"] = email
                r["foul_trip_approved_at"] = stamp
                return row2d(r)
        raise HTTPException(404, "Not found")
    row = db_1("SELECT id, status_id, foul_trip_count FROM truck_requests WHERE id=%s", (rid,))
    if not row: raise HTTPException(404, "Not found")
    if row.get("status_id") != 7:
        raise HTTPException(400, "Only Foul Trip requests can be approved")
    if int(row.get("foul_trip_count") or 0) not in (1, 2):
        raise HTTPException(400, "Foul Trip Count Confirmation (1 or 2) is required before approval")
    db_x("UPDATE truck_requests SET foul_trip_approved_by=%s, foul_trip_approved_at=%s WHERE id=%s",
         (email, stamp, rid))
    return db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))

@app.get("/api/foul-trip-review")
def foul_trip_review(request: Request):
    require_admin(request)
    if LOCAL_MODE:
        rows = [row2d(r) for r in _store["truck_requests"] if r.get("status_id") == 7]
        pcache = {}
        for r in rows:
            r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            r["department_name"] = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            r["status_name"] = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            r["status_color"] = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            tt_id = r.get("truck_type_id") or (truck.get("truck_type_id") if truck else None)
            r["truck_type_name"] = next((t["name"] for t in _store["truck_types"] if t["id"] == tt_id), "")
            r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == (truck.get("vendor_id") if truck else r.get("vendor_id"))), "")
            r["plate_number"] = truck.get("plate_number", "") if truck else ""
            truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r.get("assigned_truck_id")] if r.get("assigned_truck_id") else []
            r["trip_id"] = resolve_trip_id(r, truck_reqs) if truck_reqs else (r.get("trip_id") or None)
            appr = next((u for u in _store["users"] if u.get("email") == r.get("foul_trip_approved_by")), None)
            r["foul_trip_approved_by_name"] = appr.get("name", "") if appr else (r.get("foul_trip_approved_by") or "")
            r["foul_trip_approved_by_email"] = r.get("foul_trip_approved_by") or ""
            # Rate/Trip, Foul Trip % and Foul Trip Cost — same maths as Cost Analysis
            rate, base, basis = price_request(r, (truck or {}).get("vendor_id") or r.get("vendor_id"), tt_id,
                                              trip_primary_dest(r, pcache))
            if not rate:
                base = r.get("estimated_cost") or 0
            r["rate_per_trip"] = base or None
            r["rate_basis"] = basis
            r["foul_trip_pct"] = (rate or {}).get("foul_trip_pct")
            r["foul_trip_cost"] = foul_fuel_costs(rate, base, 7, r.get("foul_trip_count"))[0]
        add_distances_to_requests(rows, get_port_coords_map())
        rows.sort(key=lambda x: (str(x.get("foul_trip_date") or ""), x.get("id") or 0), reverse=True)
        return {"items": rows,
                "pending": sum(1 for r in rows if not r.get("foul_trip_approved_by")),
                "approved": sum(1 for r in rows if r.get("foul_trip_approved_by"))}
    rows = db_q("""SELECT tr.*, a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        ts.name as status_name, ts.color as status_color,
        COALESCE(tt.name, ttt.name) as truck_type_name, COALESCE(v.name, vv.name) as vendor_name,
        tk.plate_number, COALESCE(fa.name, tr.foul_trip_approved_by) as foul_trip_approved_by_name,
        tr.foul_trip_approved_by as foul_trip_approved_by_email,
        tk.vendor_id as rate_vendor_id, tk.truck_type_id as rate_truck_type_id
        FROM truck_requests tr
        LEFT JOIN accounts a ON tr.account_id=a.id LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN truck_statuses ts ON tr.status_id=ts.id LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN vendors vv ON tr.vendor_id=vv.id LEFT JOIN truck_types ttt ON tk.truck_type_id=ttt.id
        LEFT JOIN users fa ON tr.foul_trip_approved_by=fa.email
        WHERE tr.status_id=7 ORDER BY tr.foul_trip_date DESC, tr.id DESC""", ())
    rate_cache, pcache = {}, {}
    for i in rows:
        if i.get("assigned_truck_id"):
            truck_reqs = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (i["assigned_truck_id"],))
            i["trip_id"] = resolve_trip_id(i, truck_reqs)
        else:
            i["trip_id"] = i.get("trip_id") or None
        i["foul_trip_approved_by_email"] = i.get("foul_trip_approved_by") or ""
        # Rate/Trip, Foul Trip % and Foul Trip Cost — same maths as Cost Analysis
        rate, base, basis = price_request(i, i.get("rate_vendor_id") or i.get("vendor_id"),
                                          i.get("truck_type_id") or i.get("rate_truck_type_id"),
                                          trip_primary_dest(i, pcache), rate_cache)
        if not rate:
            base = i.get("estimated_cost") or 0
        i["rate_per_trip"] = base or None
        i["rate_basis"] = basis
        i["foul_trip_pct"] = (rate or {}).get("foul_trip_pct")
        i["foul_trip_cost"] = foul_fuel_costs(rate, base, 7, i.get("foul_trip_count"))[0]
    add_distances_to_requests(rows, get_port_coords_map())
    return {"items": rows,
            "pending": sum(1 for r in rows if not r.get("foul_trip_approved_by")),
            "approved": sum(1 for r in rows if r.get("foul_trip_approved_by"))}

@app.delete("/api/requests/clear-all")
def clear_all_requests(request: Request):
    require_master(request)
    try:
        if LOCAL_MODE:
            for a in _store["attachments"]:
                _delete_att_file(a.get("storage_path", ""))
            _store["truck_requests"] = []
            _store["attachments"] = []
            _store["pending_allocations"] = []
            _store["truck_request_history"] = []
            for t in _store["trucks"]:
                t["status"] = "available"
            _store["_cnt"]["truck_requests"] = 0
            _store["_cnt"]["attachments"] = 0
            _store["_cnt"]["pending_allocations"] = 0
            _store["_cnt"]["truck_request_history"] = 0
            return {"ok": True, "message": "All requests cleared"}
        for a in db_q("SELECT storage_path FROM truck_request_attachments"):
            _delete_att_file(a.get("storage_path", ""))
        for tbl in ["truck_request_history", "pending_allocations", "attachments"]:
            try: db_x(f"DELETE FROM {tbl}")
            except Exception: pass
        db_x("UPDATE trucks SET status='available'")
        db_x("DELETE FROM truck_requests")
        return {"ok": True, "message": "All requests cleared"}
    except Exception as e:
        raise HTTPException(500, str(e))

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
        for a in [a for a in _store["attachments"] if a.get("truck_request_id") == rid]:
            _delete_att_file(a.get("storage_path", ""))
        _store["attachments"] = [a for a in _store["attachments"] if a.get("truck_request_id") != rid]
        _store["pending_allocations"] = [p for p in _store["pending_allocations"] if p.get("truck_request_id") != rid]
        if truck_id:
            if reverted_seq:
                for x in _store["truck_requests"]:
                    if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x["drop_sequence"] > reverted_seq:
                        x["drop_sequence"] -= 1
            remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("status_id") not in (4, 5, 7)]
            if not remaining:
                for t in _store["trucks"]:
                    if t["id"] == truck_id: t["status"] = "available"; break
            else:
                freeze_trip_ids_on_truck(truck_id)
                recalculate_trip_rates(truck_id)
        return {"ok": True}
    req = db_1("SELECT assigned_truck_id, drop_sequence, status_id FROM truck_requests WHERE id=%s", (rid,))
    if not req: raise HTTPException(404, "Not found")
    if req.get("status_id") and req["status_id"] != 1: raise HTTPException(400, "Only pending requests can be deleted")
    truck_id = req.get("assigned_truck_id")
    reverted_seq = req.get("drop_sequence")
    if reverted_seq:
        db_x("UPDATE truck_requests SET drop_sequence=drop_sequence-1 WHERE assigned_truck_id=%s AND drop_sequence>%s", (truck_id, reverted_seq))
    for a in db_q("SELECT storage_path FROM truck_request_attachments WHERE truck_request_id=%s", (rid,)):
        _delete_att_file(a.get("storage_path", ""))
    db_x("DELETE FROM truck_requests WHERE id=%s", (rid,))
    if truck_id:
        remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (truck_id,))
        if remaining and remaining.get("c", 0) == 0:
            db_x("UPDATE trucks SET status='available' WHERE id=%s", (truck_id,))
        else:
            freeze_trip_ids_on_truck(truck_id)
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
        if not req: raise HTTPException(404, "Request not found")
    else:
        req = db_1("SELECT assigned_truck_id, drop_sequence, status_id, trip_id FROM truck_requests WHERE id=%s", (rid,))
        if not req: raise HTTPException(404, "Request not found")
    if req.get("status_id") != 2: raise HTTPException(400, "Drop # can only be rearranged for Allocated requests")
    # Drop numbers run 1..n inside each trip, whether or not a truck is on it yet.
    base = trip_base(req.get("trip_id"))
    if not base: raise HTTPException(400, "Request not allocated to a trip")
    rows = trip_group_rows(base)
    rows.sort(key=lambda r: (r.get("drop_sequence") or 0, r.get("id") or 0))
    if len(rows) > 1:
        others = [r for r in rows if r["id"] != rid]
        pos = max(1, min(int(new_seq), len(rows)))
        ordered = others[:pos - 1] + [r for r in rows if r["id"] == rid] + others[pos - 1:]
        apply_trip_order(base, ordered)
    truck_id = req.get("assigned_truck_id")
    if truck_id:
        freeze_trip_ids_on_truck(truck_id)
        recalculate_trip_rates(truck_id)
    return {"ok": True}

# ---------------------------------------------------------------------------
# Pending Allocations
# ---------------------------------------------------------------------------

@app.get("/api/pending-allocations")
def list_pending(request: Request):
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r.get("status_id") == 1 and not any(pa.get("truck_request_id") == r["id"] and pa.get("is_accepted") is None for pa in _store["pending_allocations"]):
                _store["pending_allocations"].append({"id": nid("pending_allocations"), "truck_request_id": r["id"], "suggested_truck_id": None, "suggestion_reason": "Reverted to pending", "is_accepted": None, "allocated_by": None, "allocated_at": None, "created_at": nows()})
        result = []
        for pa in _store["pending_allocations"]:
            if pa.get("is_accepted") is not None: continue
            req = next((r for r in _store["truck_requests"] if r["id"] == pa["truck_request_id"]), None)
            if not req: continue
            if req.get("status_id") != 1: continue
            item = {**row2d(pa)}
            item.update({"request_number": req.get("request_number", ""), "requestor_name": req.get("requestor_name", ""),
                "pickup_datetime": req.get("pickup_datetime", ""), "call_datetime": req.get("call_datetime", ""),
                "international_mawb": req.get("international_mawb", "") or "",
                "domestic_mawb": req.get("domestic_mawb", "") or "",
                "origin_port_id": req.get("origin_port_id"),
                "destination_port_id": req.get("destination_port_id"), "truck_type_id": req.get("truck_type_id"),
                "account_id": req.get("account_id"), "department_id": req.get("department_id"),
                "packaging_type_id": req.get("packaging_type_id"), "quantity": req.get("quantity", 0),
                "weight_kg": req.get("weight_kg", 0), "volume_cbm": req.get("volume_cbm", 0),
                "origin_port_name": next((p["name"] for p in _store["ports"] if p["id"] == req.get("origin_port_id")), ""),
                "origin_lat": next((p.get("latitude") for p in _store["ports"] if p["id"] == req.get("origin_port_id")), None),
                "origin_lon": next((p.get("longitude") for p in _store["ports"] if p["id"] == req.get("origin_port_id")), None),
                "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == req.get("destination_port_id")), ""),
                "dest_lat": next((p.get("latitude") for p in _store["ports"] if p["id"] == req.get("destination_port_id")), None),
                "dest_lon": next((p.get("longitude") for p in _store["ports"] if p["id"] == req.get("destination_port_id")), None),
                "department_name": next((d["name"] for d in _store["departments"] if d["id"] == req.get("department_id")), ""),
                "packaging_type_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == req.get("packaging_type_id")), ""),
                "truck_type_name": next((t["name"] for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), ""),
                "max_capacity_kg": next((t.get("max_capacity_kg", 0) for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), 0),
                "max_capacity_cbm": next((t.get("max_capacity_cbm", 0) for t in _store["truck_types"] if t["id"] == req.get("truck_type_id")), 0)})
            same = [r for r in _store["truck_requests"] if r["id"] != req["id"] and r.get("origin_port_id") == req.get("origin_port_id") and r.get("status_id") == 1]
            sug = []
            for sr in same:
                try:
                    if not req.get("call_datetime") or not sr.get("call_datetime"): continue
                    dt1 = datetime.fromisoformat(str(req.get("call_datetime")).replace(" ", "T").replace("Z", "+00:00"))
                    dt2 = datetime.fromisoformat(str(sr.get("call_datetime")).replace(" ", "T").replace("Z", "+00:00"))
                    if abs((dt1 - dt2).total_seconds()) <= 14400:
                        sug.append({"request_id": sr["id"], "request_number": sr.get("request_number", ""), "requestor_name": sr.get("requestor_name", ""), "call_datetime": str(sr.get("call_datetime", "")),
                            "packaging_type_name": next((p["name"] for p in _store["packaging_types"] if p["id"] == sr.get("packaging_type_id")), ""),
                            "quantity": sr.get("quantity", 0), "weight_kg": sr.get("weight_kg", 0), "volume_cbm": sr.get("volume_cbm", 0),
                            "reason": f"Same origin, similar initial call time"})
                except: pass
            item["consolidation_suggestions"] = sug
            avail = [t for t in _store["trucks"] if t.get("status") in ("available", "assigned") and t.get("is_available", True)]
            in_transit_truck_ids = set(r.get("assigned_truck_id") for r in _store["truck_requests"] if r.get("status_id") == 3 and r.get("assigned_truck_id"))
            avail = [t for t in avail if t["id"] not in in_transit_truck_ids]
            truck_list = []
            for t in avail:
                cur_reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5, 7)]
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
    db_x("""INSERT INTO pending_allocations (truck_request_id, suggestion_reason)
        SELECT tr.id, 'Reverted to pending' FROM truck_requests tr
        WHERE tr.status_id=1 AND NOT EXISTS (
            SELECT 1 FROM pending_allocations pa WHERE pa.truck_request_id=tr.id AND pa.is_accepted IS NULL)""")
    rows = db_q("""SELECT pa.*, tr.request_number, tr.requestor_name, tr.pickup_datetime, tr.call_datetime,
        tr.international_mawb, tr.domestic_mawb,
        tr.origin_port_id, tr.destination_port_id, tr.truck_type_id, tr.account_id, tr.department_id,
        tr.packaging_type_id, tr.quantity, tr.weight_kg, tr.volume_cbm,
        po.name as origin_port_name, po.latitude as origin_lat, po.longitude as origin_lon,
        pd.name as destination_port_name, pd.latitude as dest_lat, pd.longitude as dest_lon,
        d.name as department_name,
        pt.name as packaging_type_name, tt.name as truck_type_name,
        tt.max_capacity_kg, tt.max_capacity_cbm
        FROM pending_allocations pa JOIN truck_requests tr ON pa.truck_request_id=tr.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        WHERE pa.is_accepted IS NULL AND tr.status_id=1 ORDER BY pa.created_at DESC""")
    for item in rows:
        same = db_q("""SELECT id, request_number, requestor_name, call_datetime, quantity, weight_kg, volume_cbm, packaging_type_id
            FROM truck_requests WHERE id!=%s AND origin_port_id=%s AND status_id=1
            AND call_datetime IS NOT NULL AND %s IS NOT NULL
            AND ABS(TIMESTAMPDIFF(HOUR, call_datetime, %s))<=4""", (item["truck_request_id"], item["origin_port_id"], item.get("call_datetime"), item.get("call_datetime")))
        for s in same:
            s["packaging_type_name"] = next((p["name"] for p in db_q("SELECT name FROM packaging_types WHERE id=%s", (s["packaging_type_id"],))), "")
        item["consolidation_suggestions"] = [{"request_id": s["id"], "request_number": s["request_number"], "requestor_name": s["requestor_name"], "call_datetime": str(s["call_datetime"]), "packaging_type_name": s.get("packaging_type_name", ""), "quantity": s.get("quantity", 0), "weight_kg": s.get("weight_kg", 0), "volume_cbm": s.get("volume_cbm", 0), "reason": f"Same origin, similar initial call time"} for s in same]
        avail_trucks = db_q("""SELECT t.id,t.plate_number,t.truck_type_id,t.status,v.name as vendor_name,tt.name as truck_type_name,t.driver_name,t.driver_phone
            FROM trucks t LEFT JOIN vendors v ON t.vendor_id=v.id LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
            WHERE t.status IN ('available','assigned') AND t.is_active=1 AND t.is_available=1
            AND t.id NOT IN (SELECT assigned_truck_id FROM truck_requests WHERE status_id=3 AND assigned_truck_id IS NOT NULL)""")
        for at in avail_trucks:
            at_ttcaps = db_q("SELECT packaging_type_id, max_quantity FROM truck_type_capacities WHERE truck_type_id=%s", (at["truck_type_id"],))
            pkg_rows = db_q("SELECT packaging_type_id, SUM(quantity) as total FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7) GROUP BY packaging_type_id", (at["id"],))
            pkg_counts = {r["packaging_type_id"]: r["total"] for r in pkg_rows}
            majority_pkg = max(pkg_counts, key=pkg_counts.get) if pkg_counts else item.get("packaging_type_id")
            cur_qty = pkg_counts.get(majority_pkg, 0)
            cap = next((c["max_quantity"] for c in at_ttcaps if c["packaging_type_id"] == majority_pkg), 0)
            at["current_qty"] = cur_qty
            at["max_qty"] = cap
            at["remaining_qty"] = (cap - cur_qty) if cap > 0 else 999
            at["majority_pkg_name"] = next((p["name"] for p in db_q("SELECT name FROM packaging_types WHERE id=%s", (majority_pkg,))), "")
            at["pkg_capacities"] = {str(c["packaging_type_id"]): {"max": c["max_quantity"], "current": pkg_counts.get(c["packaging_type_id"], 0)} for c in at_ttcaps}
            origins = db_q("SELECT DISTINCT origin_port_id FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (at["id"],))
            at["assigned_origins"] = [o["origin_port_id"] for o in origins if o.get("origin_port_id")]
            rate_row = db_1("""SELECT rate_per_trip, default_rate FROM vendor_rates
                WHERE vendor_id=(SELECT vendor_id FROM trucks WHERE id=%s) AND truck_type_id=%s AND origin_port_id=%s AND is_active=1 LIMIT 1""",
                (at["id"], at["truck_type_id"], item["origin_port_id"]))
            at["rate_per_trip"] = rate_row.get("rate_per_trip", 0) if rate_row else 0
            at["default_rate"] = rate_row.get("default_rate", 0) if rate_row else 0
            at["current_drops"] = db_q("""SELECT tr.id as request_id, tr.request_number, tr.drop_sequence, pd.name as destination_port_name
                FROM truck_requests tr LEFT JOIN ports pd ON tr.destination_port_id=pd.id
                WHERE tr.assigned_truck_id=%s AND tr.status_id NOT IN (4,5,7) AND tr.drop_sequence IS NOT NULL ORDER BY tr.drop_sequence""", (at["id"],))
        avail_trucks.sort(key=lambda x: x["rate_per_trip"] if x.get("rate_per_trip", 0) > 0 else 999999)
        item["available_trucks"] = avail_trucks
    return rows

def _allocate_vendor(pid, user, body, vendor_id, consolidate_pa_ids):
    final_call = body.get("final_call_datetime")
    if not final_call:
        raise HTTPException(400, "final_call_datetime is required")
    if LOCAL_MODE:
        vendor = next((v for v in _store["vendors"] if v["id"] == vendor_id), None)
        if not vendor: raise HTTPException(400, "Vendor not found")
        pa = next((p for p in _store["pending_allocations"] if p["id"] == pid), None)
        if not pa or pa.get("is_accepted") is not None:
            raise HTTPException(404, "Not found")
        batch = [pa]
        for cpid in consolidate_pa_ids:
            cpa = next((p for p in _store["pending_allocations"] if p["id"] == cpid and p.get("is_accepted") is None), None)
            if cpa: batch.append(cpa)
        seen = set()
        batch = [p for p in batch if not (p["id"] in seen or seen.add(p["id"]))]
        reqs = []
        for p in batch:
            r = next((x for x in _store["truck_requests"] if x["id"] == p["truck_request_id"]), None)
            if not r or r.get("status_id") != 1:
                raise HTTPException(400, "Only pending requests can be allocated")
            reqs.append((p, r))
        consol_seqs = body.get("consolidate_drop_sequences", {}) or {}
        base = f"{trip_prefix_for_vendor(vendor_id)}-{next_seq_string('trip', width0=5)}"
        explicit, used = [], set()
        for i, (p, r) in enumerate(reqs):
            s = body.get("drop_sequence") if i == 0 else (consol_seqs.get(str(p["id"])) or consol_seqs.get(p["id"]))
            explicit.append(int(s) if s else None)
            if s: used.add(int(s))
        nxt = 1
        for i in range(len(explicit)):
            if explicit[i] is None:
                while nxt in used: nxt += 1
                explicit[i] = nxt
                used.add(nxt)
        email = user.get("email", "")
        tt_override = int(body["truck_type_id"]) if body.get("truck_type_id") else None
        _first = min(range(len(reqs)), key=lambda k: explicit[k]) if reqs else None
        batch_primary = reqs[_first][1].get("destination_port_id") if _first is not None else None
        for i, (p, r) in enumerate(reqs):
            seq = explicit[i]
            if tt_override: r["truck_type_id"] = tt_override
            r["vendor_id"] = vendor_id
            r["final_call_datetime"] = final_call
            r["status_id"] = 2
            r["drop_sequence"] = seq
            r["trip_id"] = f"{base}-{_trip_letter(seq)}"
            r["estimated_cost"] = price_request(r, vendor_id, r.get("truck_type_id"), batch_primary)[1]
            r["updated_by"] = email
            r["updated_at"] = nows()
            p["suggested_truck_id"] = None
            p["is_accepted"] = True
            p["allocated_by"] = email
            p["allocated_at"] = nows()
        return {"ok": True, "trip_id": base}
    vendor = db_1("SELECT id FROM vendors WHERE id=%s AND is_active=1", (vendor_id,))
    if not vendor: raise HTTPException(400, "Vendor not found")
    pa = db_1("""SELECT pa.id, pa.truck_request_id, tr.status_id, tr.origin_port_id, tr.destination_port_id,
        tr.truck_type_id, tr.booking_date
        FROM pending_allocations pa JOIN truck_requests tr ON pa.truck_request_id=tr.id
        WHERE pa.id=%s AND pa.is_accepted IS NULL AND tr.status_id=1""", (pid,))
    if not pa: raise HTTPException(404, "Not found")
    batch = [pa]
    for cpid in consolidate_pa_ids:
        cpa = db_1("""SELECT pa.id, pa.truck_request_id, tr.status_id, tr.origin_port_id, tr.destination_port_id,
            tr.truck_type_id, tr.booking_date
            FROM pending_allocations pa JOIN truck_requests tr ON pa.truck_request_id=tr.id
            WHERE pa.id=%s AND pa.is_accepted IS NULL AND tr.status_id=1""", (cpid,))
        if cpa: batch.append(cpa)
    seen = set()
    batch = [p for p in batch if not (p["id"] in seen or seen.add(p["id"]))]
    base = f"{trip_prefix_for_vendor(vendor_id)}-{next_seq_string('trip', width0=5)}"
    consol_seqs = body.get("consolidate_drop_sequences", {}) or {}
    explicit, used = [], set()
    for i, p in enumerate(batch):
        s = body.get("drop_sequence") if i == 0 else (consol_seqs.get(str(p["id"])) or consol_seqs.get(p["id"]))
        explicit.append(int(s) if s else None)
        if s: used.add(int(s))
    nxt = 1
    for i in range(len(explicit)):
        if explicit[i] is None:
            while nxt in used: nxt += 1
            explicit[i] = nxt
            used.add(nxt)
    email = user.get("email", "")
    tt_override = int(body["truck_type_id"]) if body.get("truck_type_id") else None
    _first = min(range(len(batch)), key=lambda k: explicit[k]) if batch else None
    batch_primary = batch[_first].get("destination_port_id") if _first is not None else None
    for i, p in enumerate(batch):
        seq = explicit[i]
        eff_tt = tt_override if tt_override else p.get("truck_type_id")
        est = price_request(p, vendor_id, eff_tt, batch_primary, drop_seq=seq)[1]
        db_x("""UPDATE truck_requests SET vendor_id=%s, final_call_datetime=%s, status_id=2,
            truck_type_id=%s, drop_sequence=%s, trip_id=%s, estimated_cost=%s, updated_by=%s, updated_at=NOW()
            WHERE id=%s""", (vendor_id, final_call, eff_tt, seq, f"{base}-{_trip_letter(seq)}", est, email, p["truck_request_id"]))
        db_x("UPDATE pending_allocations SET suggested_truck_id=NULL, is_accepted=1, allocated_by=%s, allocated_at=NOW() WHERE id=%s", (email, p["id"]))
    return {"ok": True, "trip_id": base}

@app.post("/api/pending-allocations/{pid}/allocate")
async def allocate(pid: int, request: Request):
    user = get_user(request)
    body = await request.json()
    truck_id = body.get("truck_id")
    vendor_id = body.get("vendor_id")
    consolidate_pa_ids = body.get("consolidate_request_ids", [])
    if vendor_id:
        return _allocate_vendor(pid, user, body, int(vendor_id), consolidate_pa_ids)
    if not truck_id: raise HTTPException(400, "truck_id or vendor_id required")
    final_call = body.get("final_call_datetime")
    if LOCAL_MODE:
        truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
        if not truck: raise HTTPException(400, "Truck not found")
        for pa in _store["pending_allocations"]:
            if pa["id"] == pid:
                pa["suggested_truck_id"] = truck_id; pa["is_accepted"] = True; pa["allocated_by"] = user["email"]; pa["allocated_at"] = nows()
                for t in _store["trucks"]:
                    if t["id"] == truck_id: t["status"] = "assigned"; break
                for r in _store["truck_requests"]:
                    if r["id"] == pa["truck_request_id"]:
                        r["assigned_truck_id"] = truck_id; r["status_id"] = 2; r["updated_by"] = user["email"]; r["updated_at"] = nows(); r["truck_type_id"] = truck.get("truck_type_id")
                        r["vendor_id"] = truck.get("vendor_id")
                        if final_call is not None: r["final_call_datetime"] = final_call
                        req_drop_seq = body.get("drop_sequence")
                        if not req_drop_seq:
                            existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x.get("status_id") in (2, 3) and x["id"] != r["id"]]
                            req_drop_seq = (max(existing_seqs) + 1) if existing_seqs else 1
                        if req_drop_seq:
                            existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x.get("status_id") in (2, 3) and x["id"] != r["id"]]
                            if req_drop_seq in existing_seqs:
                                for x in _store["truck_requests"]:
                                    if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x.get("status_id") in (2, 3) and x["drop_sequence"] >= req_drop_seq and x["id"] != r["id"]:
                                        x["drop_sequence"] += 1
                            r["drop_sequence"] = req_drop_seq
                        rate_match = find_best_rate(truck.get("vendor_id"), truck.get("truck_type_id"), r.get("origin_port_id"), r.get("destination_port_id"), booking_date=r.get("booking_date"))
                        if rate_match: r["estimated_cost"] = compute_rate(rate_match, r.get("destination_port_id"), r.get("drop_sequence"))
                        primary_dest_id = r.get("destination_port_id")
                        break
                for cpid in consolidate_pa_ids:
                    cpa = next((p for p in _store["pending_allocations"] if p["id"] == cpid), None)
                    if not cpa: continue
                    crid = cpa["truck_request_id"]
                    for r2 in _store["truck_requests"]:
                        if r2["id"] == crid:
                            r2["assigned_truck_id"] = truck_id; r2["status_id"] = 2; r2["updated_by"] = user["email"]; r2["updated_at"] = nows(); r2["truck_type_id"] = truck.get("truck_type_id")
                            r2["vendor_id"] = truck.get("vendor_id")
                            if final_call is not None: r2["final_call_datetime"] = final_call
                            consol_seqs = body.get("consolidate_drop_sequences", {})
                            consol_drop_seq = consol_seqs.get(str(cpid)) or consol_seqs.get(cpid)
                            if consol_drop_seq:
                                existing_seqs = [x.get("drop_sequence") for x in _store["truck_requests"] if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x.get("status_id") in (2, 3) and x["id"] != r2["id"]]
                                if consol_drop_seq in existing_seqs:
                                    for x in _store["truck_requests"]:
                                        if x.get("assigned_truck_id") == truck_id and x.get("drop_sequence") is not None and x.get("status_id") in (2, 3) and x["drop_sequence"] >= consol_drop_seq and x["id"] != r2["id"]:
                                            x["drop_sequence"] += 1
                                r2["drop_sequence"] = consol_drop_seq
                            rate_match2, est2, _ = price_request(r2, truck.get("vendor_id"), truck.get("truck_type_id"), primary_dest_id)
                            if rate_match2: r2["estimated_cost"] = est2
                            break
                    cpa["suggested_truck_id"] = truck_id; cpa["is_accepted"] = True; cpa["allocated_by"] = user["email"]; cpa["allocated_at"] = nows()
                freeze_trip_ids_on_truck(truck_id)
                recalculate_trip_rates(truck_id)
                return {"ok": True}
        raise HTTPException(404, "Not found")
    pa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (pid,))
    if not pa: raise HTTPException(404, "Pending allocation not found")
    truck = db_1("SELECT vendor_id, truck_type_id FROM trucks WHERE id=%s", (truck_id,))
    if not truck: raise HTTPException(400, "Truck not found")
    db_x("UPDATE pending_allocations SET suggested_truck_id=%s,is_accepted=1,allocated_by=%s,allocated_at=NOW() WHERE id=%s", (truck_id, user["email"], pid))
    db_x("UPDATE trucks SET status='assigned' WHERE id=%s", (truck_id,))
    if pa:
        tr = db_1("SELECT origin_port_id, destination_port_id, truck_type_id, booking_date FROM truck_requests WHERE id=%s", (pa["truck_request_id"],))
        rate = None
        if tr and truck:
            rate = price_request(tr, truck["vendor_id"], truck["truck_type_id"])[0]
        primary_dest_id = tr.get("destination_port_id") if tr else None
        req_drop_seq = body.get("drop_sequence")
        if not req_drop_seq:
            max_seq = db_1("SELECT MAX(drop_sequence) as max_seq FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence IS NOT NULL AND status_id IN (2,3)", (truck_id,))
            req_drop_seq = (max_seq["max_seq"] + 1) if max_seq and max_seq.get("max_seq") else 1
        est = price_request(tr, truck["vendor_id"], truck["truck_type_id"], drop_seq=req_drop_seq or 1)[1] if rate and tr else 0
        drop_seq_sql = ""
        drop_seq_params = []
        if req_drop_seq:
            existing = db_1("SELECT drop_sequence FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence=%s AND status_id IN (2,3)", (truck_id, req_drop_seq))
            if existing:
                db_x("UPDATE truck_requests SET drop_sequence=drop_sequence+1 WHERE assigned_truck_id=%s AND drop_sequence>=%s AND status_id IN (2,3)", (truck_id, req_drop_seq))
            drop_seq_sql = ", drop_sequence=%s"
            drop_seq_params = [req_drop_seq]
        db_x(f"UPDATE truck_requests SET assigned_truck_id=%s,status_id=2,updated_by=%s,estimated_cost=%s,truck_type_id=%s,vendor_id=%s,final_call_datetime=%s,updated_at=NOW(){drop_seq_sql} WHERE id=%s",
             (truck_id, user["email"], est, truck["truck_type_id"], truck.get("vendor_id"), final_call)+tuple(drop_seq_params)+(pa["truck_request_id"],))
    for cpid in consolidate_pa_ids:
        cpa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (cpid,))
        if not cpa: continue
        crid = cpa["truck_request_id"]
        ctr = db_1("SELECT origin_port_id, destination_port_id, truck_type_id, booking_date FROM truck_requests WHERE id=%s", (crid,))
        rate2, est2_p = None, 0
        if ctr and truck:
            rate2, est2_p, _ = price_request(ctr, truck["vendor_id"], truck["truck_type_id"], primary_dest_id,
                                             drop_seq=(body.get("consolidate_drop_sequences", {}) or {}).get(str(cpid)) or (body.get("consolidate_drop_sequences", {}) or {}).get(cpid) or 2)
        consol_seqs = body.get("consolidate_drop_sequences", {})
        consol_drop_seq = consol_seqs.get(str(cpid)) or consol_seqs.get(cpid)
        est2 = est2_p if rate2 and ctr else 0
        c_drop_seq_sql = ""
        c_drop_seq_params = []
        if consol_drop_seq:
            c_existing = db_1("SELECT drop_sequence FROM truck_requests WHERE assigned_truck_id=%s AND drop_sequence=%s AND status_id IN (2,3)", (truck_id, consol_drop_seq))
            if c_existing:
                db_x("UPDATE truck_requests SET drop_sequence=drop_sequence+1 WHERE assigned_truck_id=%s AND drop_sequence>=%s AND status_id IN (2,3)", (truck_id, consol_drop_seq))
            c_drop_seq_sql = ", drop_sequence=%s"
            c_drop_seq_params = [consol_drop_seq]
        db_x(f"UPDATE truck_requests SET assigned_truck_id=%s,status_id=2,updated_by=%s,estimated_cost=%s,truck_type_id=%s,vendor_id=%s,final_call_datetime=%s,updated_at=NOW(){c_drop_seq_sql} WHERE id=%s",
             (truck_id, user["email"], est2, truck["truck_type_id"], truck.get("vendor_id"), final_call)+tuple(c_drop_seq_params)+(crid,))
        db_x("UPDATE pending_allocations SET suggested_truck_id=%s,is_accepted=1,allocated_by=%s,allocated_at=NOW() WHERE id=%s", (truck_id, user["email"], cpid))
    freeze_trip_ids_on_truck(truck_id)
    recalculate_trip_rates(truck_id)
    return {"ok": True}

def _trip_payload(key, rs, truck, available_trucks, drivers=None, assigned_driver=None):
    first = rs[0]
    status = 3 if any(x.get("status_id") == 3 for x in rs) else 2
    trucks = available_trucks
    want_tt = first.get("truck_type_id")
    if trucks is not None and want_tt is not None:
        trucks = [t for t in trucks if t.get("truck_type_id") == want_tt]
    if drivers is not None and want_tt is not None:
        # Only accounts whose truck is the trip's truck type can take the trip.
        drivers = [d for d in drivers if d.get("truck_type_id") == want_tt]
    return {
        "trip_id": key,
        "status_id": status,
        "vendor_id": first.get("vendor_id"),
        "vendor_name": first.get("vendor_name") or "",
        "truck_type_id": first.get("truck_type_id"),
        "truck_type_name": first.get("truck_type_name"),
        "origin_port_id": first.get("origin_port_id"),
        "origin_port_name": first.get("origin_port_name"),
        "destination_port_name": first.get("destination_port_name"),
        "final_call_datetime": first.get("final_call_datetime"),
        "assigned_truck": truck,
        "assigned_driver": assigned_driver,
        "requests": rs,
        "available_trucks": trucks,
        "drivers": drivers,
    }

@app.get("/api/trip-assignments")
def trip_assignments(request: Request):
    vid, _user = vendor_scope(request)
    if LOCAL_MODE:
        rows = [row2d(r) for r in _store["truck_requests"] if r.get("status_id") == 2 and not r.get("assigned_truck_id")]
        if vid is not None:
            rows = [r for r in rows if _owned_by_vendor(r, vid)]
        truck_ids = {r.get("assigned_truck_id") for r in rows if r.get("assigned_truck_id")}
        for tid in truck_ids:
            peers = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid]
            for r in peers:
                if r.get("status_id") in (2, 3) and not r.get("trip_id"):
                    resolve_trip_id(r, peers)
        store_trip = {x["id"]: x.get("trip_id") for x in _store["truck_requests"]}
        for r in rows:
            r["trip_id"] = r.get("trip_id") or store_trip.get(r["id"])
        avail_trucks = None
        if vid is not None:
            avail_trucks = []
            for t in _store["trucks"]:
                if t.get("vendor_id") != vid: continue
                if not t.get("is_available", True): continue
                if t.get("status") not in ("available", "assigned"): continue
                active = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") in (2, 3)]
                avail_trucks.append({"id": t["id"], "plate_number": t["plate_number"], "vendor_id": t.get("vendor_id"),
                    "truck_type_id": t.get("truck_type_id"),
                    "truck_type_name": next((tt["name"] for tt in _store["truck_types"] if tt["id"] == t.get("truck_type_id")), ""),
                    "driver_name": t.get("driver_name", ""), "driver_phone": t.get("driver_phone", ""),
                    "status": t.get("status"), "active_requests": len(active)})
            avail_trucks.sort(key=lambda x: x["plate_number"])
        drivers = None
        if vid is not None:
            drivers = [_driver_public(d) for d in _driver_rows(vid, active_only=True)]
        groups = {}
        for r in rows:
            key = trip_base(r.get("trip_id")) or f"req-{r['id']}"
            groups.setdefault(key, []).append(r)
        out = []
        for key, rs in groups.items():
            rs.sort(key=lambda x: (x.get("drop_sequence") is None, x.get("drop_sequence") or 0, x["id"]))
            first = rs[0]
            truck = None
            if first.get("assigned_truck_id"):
                t = next((x for x in _store["trucks"] if x["id"] == first["assigned_truck_id"]), None)
                if t:
                    truck = {"id": t["id"], "plate_number": t["plate_number"], "driver_name": t.get("driver_name", ""),
                             "driver_phone": t.get("driver_phone", ""), "status": t.get("status")}
            for r in rs:
                r["truck_type_name"] = r.get("truck_type_name") or next((tt["name"] for tt in _store["truck_types"] if tt["id"] == r.get("truck_type_id")), "")
                r["origin_port_name"] = r.get("origin_port_name") or next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
                r["destination_port_name"] = r.get("destination_port_name") or next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
                r["packaging_type_name"] = next((p["name"] for p in _store["packaging_types"] if p["id"] == r.get("packaging_type_id")), "")
                r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
                tv = r.get("vendor_id")
                if not tv and r.get("assigned_truck_id"):
                    trow = next((x for x in _store["trucks"] if x["id"] == r.get("assigned_truck_id")), None)
                    tv = trow.get("vendor_id") if trow else None
                r["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == tv), "")
                r["requestor_name"] = r.get("requestor_name", "")
            out.append(_trip_payload(key, rs, truck, avail_trucks, drivers,
                                     _driver_public(_driver_row(first.get("driver_account_id")))
                                     if first.get("driver_account_id") else None))
        out.sort(key=lambda x: str(x.get("final_call_datetime") or "9999-12-31"))
        return out
    rows = db_q("""SELECT tr.id, tr.request_number, tr.requestor_name, tr.status_id, tr.drop_sequence, tr.trip_id,
        tr.assigned_truck_id, tr.vendor_id, tr.final_call_datetime, tr.quantity, tr.weight_kg, tr.volume_cbm,
        tr.packaging_type_id, tr.destination_port_id, tr.origin_port_id, tr.truck_type_id, tr.account_id,
        tr.driver_account_id, tr.international_mawb, tr.domestic_mawb,
        tt.name as truck_type_name, po.name as origin_port_name, pd.name as destination_port_name,
        pt.name as packaging_type_name, a.name as account_name, COALESCE(vv.name, v.name) as vendor_name
        FROM truck_requests tr
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id
        LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN packaging_types pt ON tr.packaging_type_id=pt.id
        LEFT JOIN accounts a ON tr.account_id=a.id
        LEFT JOIN vendors vv ON tr.vendor_id=vv.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id
        LEFT JOIN vendors v ON tk.vendor_id=v.id
        WHERE tr.status_id=2 AND tr.assigned_truck_id IS NULL ORDER BY tr.id""")
    trucks_by_id = {}
    if rows:
        tid_set = {r.get("assigned_truck_id") for r in rows if r.get("assigned_truck_id")}
        for tid in tid_set:
            trucks_by_id[tid] = db_1("SELECT id, plate_number, driver_name, driver_phone, vendor_id, status FROM trucks WHERE id=%s", (tid,))
    if vid is not None:
        rows = [r for r in rows if r.get("vendor_id") == vid
                or (r.get("assigned_truck_id") and (trucks_by_id.get(r["assigned_truck_id"]) or {}).get("vendor_id") == vid)]
    resolved = {}
    for tid in {r.get("assigned_truck_id") for r in rows if r.get("assigned_truck_id")}:
        peers = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
            assigned_truck_id, account_id FROM truck_requests WHERE assigned_truck_id=%s""", (tid,))
        for p in peers:
            if p.get("status_id") in (2, 3) and not p.get("trip_id"):
                resolve_trip_id(p, peers)
            if p.get("trip_id"):
                resolved[p["id"]] = p["trip_id"]
    for r in rows:
        r["trip_id"] = r.get("trip_id") or resolved.get(r["id"])
    avail_trucks = None
    if vid is not None:
        avail_trucks = db_q("""SELECT t.id, t.plate_number, t.vendor_id, t.driver_name, t.driver_phone, t.status, t.truck_type_id,
            tt.name as truck_type_name FROM trucks t LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
            WHERE t.is_active=1 AND t.is_available=1 AND t.vendor_id=%s AND t.status IN ('available','assigned')
            ORDER BY t.plate_number""", (vid,))
        for t in avail_trucks:
            cnt = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id IN (2,3)", (t["id"],))
            t["active_requests"] = cnt.get("c", 0) if cnt else 0
    drivers = None
    if vid is not None:
        drivers = [_driver_public(d) for d in _driver_rows(vid, active_only=True)]
    groups = {}
    for r in rows:
        key = trip_base(r.get("trip_id")) or f"req-{r['id']}"
        groups.setdefault(key, []).append(r)
    out = []
    for key, rs in groups.items():
        rs.sort(key=lambda x: (x.get("drop_sequence") is None, x.get("drop_sequence") or 0, x["id"]))
        first = rs[0]
        truck = None
        trow = trucks_by_id.get(first.get("assigned_truck_id")) if first.get("assigned_truck_id") else None
        if trow:
            truck = {"id": trow["id"], "plate_number": trow["plate_number"], "driver_name": trow.get("driver_name", ""),
                     "driver_phone": trow.get("driver_phone", ""), "status": trow.get("status")}
        out.append(_trip_payload(key, rs, truck, avail_trucks, drivers,
                                 _driver_public(_driver_row(first.get("driver_account_id")))
                                 if first.get("driver_account_id") else None))
    out.sort(key=lambda x: str(x.get("final_call_datetime") or "9999-12-31"))
    return out

@app.post("/api/trips/{trip_id}/assign-truck")
async def assign_trip_truck(trip_id: str, request: Request):
    u, vid = require_vendor_or_admin(request)
    body = await request.json()
    truck_id = body.get("truck_id")
    if not truck_id: raise HTTPException(400, "truck_id required")
    return _assign_truck_core(u, vid, trip_id, truck_id)

def _assign_truck_core(u, vid, trip_id, truck_id, keep_status=False):
    """Put a truck on a trip: drop sequence, rates and truck status.
    keep_status leaves the rows at Allocated (2) - that is what the driver
    assignment does; the plain truck assignment moves them to In Transit (3)."""
    try:
        truck_id = int(truck_id)
    except (TypeError, ValueError):
        raise HTTPException(400, "truck_id must be a number")
    email = u.get("email", "")
    if LOCAL_MODE:
        truck = next((t for t in _store["trucks"] if t["id"] == truck_id), None)
        if not truck:
            raise HTTPException(404, "Truck not found")
        if vid is not None and truck.get("vendor_id") != vid:
            raise HTTPException(403, "Not your vendor's truck")
        if not truck.get("is_available", True):
            raise HTTPException(400, "Truck is not available")
        reqs = [r for r in _store["truck_requests"]
                if r.get("status_id") in (2, 3) and trip_base(r.get("trip_id")) == trip_base(trip_id)
                and _owned_by_vendor(r, vid)]
        if not reqs and trip_id.startswith("req-"):
            try: single_id = int(trip_id[4:])
            except ValueError: single_id = None
            if single_id:
                single = next((r for r in _store["truck_requests"] if r["id"] == single_id and r.get("status_id") in (2, 3)), None)
                if single and _owned_by_vendor(single, vid): reqs = [single]
        if not reqs: raise HTTPException(404, "No active requests for this trip")
        trip_vid = next((r.get("vendor_id") for r in reqs if r.get("vendor_id")), None)
        if trip_vid is not None and truck.get("vendor_id") != trip_vid:
            raise HTTPException(403, "Trip belongs to a different vendor")
        old_tids = {r.get("assigned_truck_id") for r in reqs
                    if r.get("assigned_truck_id") and r["assigned_truck_id"] != truck_id}
        # Drop numbers are per trip (1..n), even when the truck already carries another trip.
        start = 1
        ordered = sorted(reqs, key=lambda x: (x.get("drop_sequence") is None, x.get("drop_sequence") or 0, x["id"]))
        want_tt = next((r.get("truck_type_id") for r in ordered if r.get("truck_type_id") is not None), None)
        if want_tt is not None and truck.get("truck_type_id") != want_tt:
            tt_name = next((x["name"] for x in _store["truck_types"] if x["id"] == want_tt), str(want_tt))
            raise HTTPException(400, f"Truck type does not match this trip ({tt_name} required)")
        for i, r in enumerate(ordered):
            r["assigned_truck_id"] = truck_id
            r["drop_sequence"] = start + i
            if not keep_status and r.get("status_id") == 2: r["status_id"] = 3
            r["updated_by"] = email
            r["updated_at"] = nows()
        truck["status"] = "assigned"
        for ot in old_tids:
            freeze_trip_ids_on_truck(ot)
            remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == ot and x.get("status_id") in (2, 3)]
            if remaining:
                recalculate_trip_rates(ot)
            else:
                for t in _store["trucks"]:
                    if t["id"] == ot: t["status"] = "available"; break
        freeze_trip_ids_on_truck(truck_id)
        recalculate_trip_rates(truck_id)
        return {"ok": True, "truck_id": truck_id, "assigned": len(ordered),
                "status_id": 2 if keep_status else 3}

    truck = db_1("SELECT id, vendor_id, is_available, truck_type_id FROM trucks WHERE id=%s AND is_active=1", (truck_id,))
    if not truck:
        raise HTTPException(404, "Truck not found")
    if vid is not None and truck.get("vendor_id") != vid:
        raise HTTPException(403, "Not your vendor's truck")
    if not truck.get("is_available", True):
        raise HTTPException(400, "Truck is not available")
    if trip_id.startswith("req-"):
        try: single_id = int(trip_id[4:])
        except ValueError: single_id = None
        if not single_id: raise HTTPException(404, "No active requests for this trip")
        rows = db_q("SELECT id, drop_sequence, assigned_truck_id, vendor_id, status_id, truck_type_id FROM truck_requests WHERE id=%s AND status_id IN (2,3)", (single_id,))
    else:
        want = trip_base(trip_id)
        active_rows = db_q("SELECT id, drop_sequence, assigned_truck_id, vendor_id, status_id, trip_id, truck_type_id FROM truck_requests WHERE status_id IN (2,3) AND trip_id IS NOT NULL", ())
        rows = [r for r in active_rows if trip_base(r.get("trip_id")) == want]
    if vid is not None:
        reqs = [r for r in rows if r.get("vendor_id") == vid
                or (r.get("assigned_truck_id") and (db_1("SELECT vendor_id FROM trucks WHERE id=%s", (r["assigned_truck_id"],)) or {}).get("vendor_id") == vid)]
    else:
        reqs = rows
    if not reqs: raise HTTPException(404, "No active requests for this trip")
    trip_vid = next((r.get("vendor_id") for r in reqs if r.get("vendor_id")), None)
    if trip_vid is not None and truck.get("vendor_id") != trip_vid:
        raise HTTPException(403, "Trip belongs to a different vendor")
    old_tids = {r.get("assigned_truck_id") for r in reqs
                if r.get("assigned_truck_id") and r["assigned_truck_id"] != truck_id}
    # Drop numbers are per trip (1..n), even when the truck already carries another trip.
    start = 1
    ordered = sorted(reqs, key=lambda x: (x.get("drop_sequence") is None, x.get("drop_sequence") or 0, x["id"]))
    want_tt = next((r.get("truck_type_id") for r in ordered if r.get("truck_type_id") is not None), None)
    if want_tt is not None and truck.get("truck_type_id") != want_tt:
        tt_row = db_1("SELECT name FROM truck_types WHERE id=%s", (want_tt,))
        tt_name = (tt_row or {}).get("name") or str(want_tt)
        raise HTTPException(400, f"Truck type does not match this trip ({tt_name} required)")
    for i, r in enumerate(ordered):
        if keep_status:
            db_x("""UPDATE truck_requests SET assigned_truck_id=%s, drop_sequence=%s,
                updated_by=%s, updated_at=NOW() WHERE id=%s""",
                 (truck_id, start + i, email, r["id"]))
        else:
            db_x("""UPDATE truck_requests SET assigned_truck_id=%s, drop_sequence=%s,
                status_id=IF(status_id=2,3,status_id), updated_by=%s, updated_at=NOW() WHERE id=%s""",
                 (truck_id, start + i, email, r["id"]))
    db_x("UPDATE trucks SET status='assigned' WHERE id=%s", (truck_id,))
    for ot in old_tids:
        freeze_trip_ids_on_truck(ot)
        cnt = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id IN (2,3)", (ot,))
        if cnt and cnt.get("c"):
            recalculate_trip_rates(ot)
        else:
            db_x("UPDATE trucks SET status='available' WHERE id=%s", (ot,))
    freeze_trip_ids_on_truck(truck_id)
    recalculate_trip_rates(truck_id)
    return {"ok": True, "truck_id": truck_id, "assigned": len(ordered),
            "status_id": 2 if keep_status else 3}

def _free_truck_assignment(rids, email):
    """Take the truck back off the given requests so the trip can be assigned
    again, and put the truck's own bookkeeping straight."""
    if not rids:
        return []
    marks = ",".join(["%s"] * len(rids))
    if LOCAL_MODE:
        gone = {}
        for x in _store["truck_requests"]:
            if x["id"] in rids:
                tid = x.get("assigned_truck_id")
                if tid:
                    gone.setdefault(tid, []).append(x.get("drop_sequence"))
                x["assigned_truck_id"] = None
                x["drop_sequence"] = None
                x["updated_by"] = email
                x["updated_at"] = nows()
        for tid, seqs in gone.items():
            rem = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid]
            actives = [x for x in rem if x.get("status_id") in (2, 3)]
            if not actives:
                for t in _store["trucks"]:
                    if t["id"] == tid:
                        t["status"] = "available"
                        break
            else:
                recalculate_trip_rates(tid)
        return list(gone)
    found = db_q(f"SELECT id, assigned_truck_id, drop_sequence FROM truck_requests WHERE id IN ({marks})",
                 tuple(rids))
    gone = {}
    for r in found:
        tid = r.get("assigned_truck_id")
        if tid:
            gone.setdefault(tid, []).append(r.get("drop_sequence"))
    db_x(f"""UPDATE truck_requests SET assigned_truck_id=NULL, drop_sequence=NULL,
        updated_by=%s, updated_at=NOW() WHERE id IN ({marks})""",
         (email,) + tuple(rids))
    for tid, seqs in gone.items():
        cnt = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id IN (2,3)", (tid,))
        if not (cnt and cnt.get("c")):
            db_x("UPDATE trucks SET status='available' WHERE id=%s", (tid,))
        else:
            recalculate_trip_rates(tid)
    return list(gone)

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
                    if r["id"] == pa["truck_request_id"]:
                        r["status_id"] = 5
                        r["cancellation_date"] = date.today().isoformat()
                        tid = r.get("assigned_truck_id")
                        if tid:
                            peers = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid]
                            _ensure_trip_id_before_terminal(r, peers)
                            archive_truck_requests(tid, user["email"])
                            remaining = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7)]
                            if not remaining:
                                for t in _store["trucks"]:
                                    if t["id"] == tid: t["status"] = "available"; break
                        break
                return {"ok": True}
        raise HTTPException(404, "Not found")
    db_x("UPDATE pending_allocations SET is_accepted=0,allocated_by=%s,allocated_at=NOW(),suggestion_reason=%s WHERE id=%s", (user["email"], reason, pid))
    pa = db_1("SELECT truck_request_id FROM pending_allocations WHERE id=%s", (pid,))
    if not pa: raise HTTPException(404, "Pending allocation not found")
    if pa:
        db_x("UPDATE truck_requests SET status_id=5, cancellation_date=COALESCE(cancellation_date, CURDATE()) WHERE id=%s", (pa["truck_request_id"],))
        req = db_1("""SELECT id, request_number, status_id, drop_sequence, trip_id,
            account_id, assigned_truck_id FROM truck_requests WHERE id=%s""", (pa["truck_request_id"],))
        if req and req.get("assigned_truck_id") and not req.get("trip_id"):
            peers = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (req["assigned_truck_id"],))
            _ensure_trip_id_before_terminal(req, peers)
            if req.get("trip_id"):
                db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s AND trip_id IS NULL", (req["trip_id"], pa["truck_request_id"]))
        if req and req.get("assigned_truck_id"):
            archive_truck_requests(req["assigned_truck_id"], user["email"])
            remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (req["assigned_truck_id"],))
            if remaining and remaining.get("c", 0) == 0:
                db_x("UPDATE trucks SET status='available' WHERE id=%s", (req["assigned_truck_id"],))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Attachments
# ---------------------------------------------------------------------------

def _obj_storage_on() -> bool:
    return bool(os.environ.get("OBJECT_STORAGE_BUCKET", ""))

def _att_content_type(raw: str) -> str:
    ctype = (raw or "").split(";")[0].strip().lower()
    if ctype in ("text/html", "image/svg+xml", "application/xhtml+xml", "text/xml"):
        return "application/octet-stream"
    return ctype or "application/octet-stream"

def _is_object_key(path: str) -> bool:
    return bool(path) and not os.path.isabs(path) and _obj_storage_on()

def _delete_att_file(path: str) -> None:
    if not path:
        return
    if _is_object_key(path):
        try:
            obj_storage.delete(path)
        except Exception:
            pass
        return
    try:
        if os.path.exists(path):
            os.remove(path)
    except OSError:
        pass

async def _save_att_bytes(rid: int, fn: str, content: bytes, ctype: str) -> str:
    if _obj_storage_on():
        try:
            key = obj_storage.safe_key("attachments", str(rid), fn)
        except ValueError:
            raise HTTPException(400, "Invalid filename")
        await run_in_threadpool(obj_storage.put_bytes, key, content, content_type=ctype)
        return key
    fp = os.path.join(_store["_upload"], fn)
    with open(fp, "wb") as f:
        f.write(content)
    return fp

@app.post("/api/requests/{rid}/attachments")
async def upload_att(rid: int, request: Request, file: UploadFile = File(...)):
    scope_vid, user = vendor_scope(request)
    if scope_vid is not None:
        req_row = next((r for r in _store["truck_requests"] if r["id"] == rid), None) if LOCAL_MODE \
            else db_1("SELECT vendor_id, assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
        if not req_row or not _owned_by_vendor(req_row, scope_vid): raise HTTPException(404, "Not found")
    if LOCAL_MODE:
        existing = [a for a in _store["attachments"] if a.get("truck_request_id") == rid]
        if len(existing) >= 8: raise HTTPException(400, "Max 8 attachments")
        content = await file.read()
        if sum(a.get("file_size", 0) for a in existing) + len(content) > 25 * 1024 * 1024:
            raise HTTPException(400, "Max 25MB total")
        fid = uuid.uuid4().hex
        raw_ext = os.path.splitext(file.filename or "")[1].lower()
        ext = raw_ext if (len(raw_ext) <= 9 and raw_ext.startswith(".") and raw_ext[1:].isalnum()) else ""
        fn = f"{fid}{ext}"
        ctype = _att_content_type(file.content_type)
        fp = await _save_att_bytes(rid, fn, content, ctype)
        aid = nid("attachments")
        att = {"id": aid, "truck_request_id": rid, "filename": fn, "original_filename": file.filename or "unknown", "file_size": len(content), "file_type": ctype, "storage_path": fp, "uploaded_by": user["email"], "created_at": nows()}
        _store["attachments"].append(att)
        return row2d(att)
    existing = db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (rid,))
    if len(existing) >= 8: raise HTTPException(400, "Max 8 attachments")
    content = await file.read()
    if sum(a.get("file_size", 0) for a in existing) + len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "Max 25MB total")
    fid = uuid.uuid4().hex
    raw_ext = os.path.splitext(file.filename or "")[1].lower()
    ext = raw_ext if (len(raw_ext) <= 9 and raw_ext.startswith(".") and raw_ext[1:].isalnum()) else ""
    fn = f"{fid}{ext}"
    ctype = _att_content_type(file.content_type)
    fp = await _save_att_bytes(rid, fn, content, ctype)
    aid = db_i("""INSERT INTO truck_request_attachments (truck_request_id,filename,original_filename,file_size,file_type,storage_path,uploaded_by)
        VALUES (%s,%s,%s,%s,%s,%s,%s)""", (rid, fn, file.filename or "unknown", len(content), ctype, fp, user["email"]))
    return db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))

@app.get("/api/attachments/{aid}/download")
def download_att(aid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        att = next((a for a in _store["attachments"] if a["id"] == aid), None)
    else:
        att = db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))
    if not att:
        raise HTTPException(404, "Not found")
    if scope_vid is not None:
        rid = att.get("truck_request_id")
        req_row = next((r for r in _store["truck_requests"] if r["id"] == rid), None) if LOCAL_MODE \
            else db_1("SELECT vendor_id, assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
        if not req_row or not _owned_by_vendor(req_row, scope_vid): raise HTTPException(404, "Not found")
    path = att.get("storage_path", "")
    filename = att.get("original_filename") or att.get("filename") or "download"
    media = att.get("file_type") or "application/octet-stream"
    if _is_object_key(path):
        try:
            if not obj_storage.exists(path):
                raise HTTPException(404, "File missing")
            data = obj_storage.get_bytes(path)
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(404, "File missing")
        safe_name = filename.replace('"', "")
        return Response(
            data,
            media_type=media,
            headers={"Content-Disposition": f'attachment; filename="{safe_name}"'},
        )
    if not path or not os.path.exists(path):
        raise HTTPException(404, "File missing")
    return FileResponse(path, filename=filename, media_type=media)

@app.delete("/api/attachments/{aid}")
def delete_att(aid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        att = next((a for a in _store["attachments"] if a["id"] == aid), None)
        if att and scope_vid is not None:
            req_row = next((r for r in _store["truck_requests"] if r["id"] == att.get("truck_request_id")), None)
            if not req_row or not _owned_by_vendor(req_row, scope_vid):
                raise HTTPException(404, "Not found")
        if att:
            _delete_att_file(att.get("storage_path", ""))
        _store["attachments"] = [a for a in _store["attachments"] if a["id"] != aid]
        return {"ok": True}
    att = db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))
    if att and scope_vid is not None:
        req_row = db_1("SELECT vendor_id, assigned_truck_id FROM truck_requests WHERE id=%s", (att.get("truck_request_id"),))
        if not req_row or not _owned_by_vendor(req_row, scope_vid):
            raise HTTPException(404, "Not found")
    if att:
        _delete_att_file(att.get("storage_path", ""))
    db_x("DELETE FROM truck_request_attachments WHERE id=%s", (aid,))
    return {"ok": True}

# ---------------------------------------------------------------------------
# Manifest files — one Excel per truck request, IDs taken from its key column
# ---------------------------------------------------------------------------

MANIFEST_KEYWORDS = ("bag", "carton", "gunny", "sack", "箱号", "箱號", "袋号", "袋號")
MANIFEST_ID_WORDS = ("no", "number", "id", "code", "barcode", "label", "#", "号", "號")
# Columns that mention a bag/carton but hold a measurement or a count, not the ID.
MANIFEST_NOT_ID = ("size", "weight", "volume", "qty", "quantity", "count", "total", "sum",
                   "dimension", "type", "pcs", "计数", "數", "数", "尺寸", "重量", "体积", "體積")
MANIFEST_ID_HEADERS = {"id", "code", "referenceno", "reference", "trackingno", "trackingnumber",
                       "barcode", "manifestid", "itemno", "slipno"}
# Labels pivot tables and totals rows put in the key column.
MANIFEST_JUNK = {"(blank)", "(空白)", "blank", "总计", "總計", "合计", "合計", "grand total", "total", "sum"}
MANIFEST_MAX = 10 * 1024 * 1024
# A full 10MB packing list can hold well over 100k rows; keep every unique ID it has.
MANIFEST_MAX_IDS = 300000
MANIFEST_HEADER_SCAN = 30          # rows searched for the header on every sheet
MANIFEST_GAP_STOP = 2000           # stop reading after this many empty rows in a row
MANIFEST_MAX_ROWS = 500000

def _manifest_header_score(h):
    """How sure we are that a header cell names the bag/carton/gunny/sack ID column."""
    t = str(h or "").strip().lower()
    if not t:
        return 0
    has_kw = any(k in t for k in MANIFEST_KEYWORDS)
    if has_kw:
        if any(x in t for x in MANIFEST_NOT_ID):
            return 0
        words = re.findall(r"[a-z]+|#|[号號]", t)
        return 3 if any(w in MANIFEST_ID_WORDS for w in words) else 2
    return 1 if _norm_hdr(h) in MANIFEST_ID_HEADERS else 0

def _manifest_sheet_candidate(ws):
    """(score, rows read, header text, ids) for the best key column on one sheet, or None.

    The header does not have to be on row 1: titles, blank rows and pivot-table
    headers above it are skipped."""
    best = None
    for r_idx, row in enumerate(ws.iter_rows(min_row=1, max_row=MANIFEST_HEADER_SCAN, values_only=True), start=1):
        for c_idx, h in enumerate(row or (), start=1):
            sc = _manifest_header_score(h)
            if sc and (best is None or sc > best[0]):
                best = (sc, r_idx, c_idx, str(h).strip())
        if best and best[0] >= 3:
            break
    if not best:
        return None
    sc, hr, col, htxt = best
    ids, seen, gap, n = [], set(), 0, 0
    for (v,) in ws.iter_rows(min_row=hr + 1, min_col=col, max_col=col, values_only=True):
        n += 1
        if n > MANIFEST_MAX_ROWS:
            break
        if v is None or (isinstance(v, str) and not v.strip()):
            gap += 1
            if gap >= MANIFEST_GAP_STOP:
                break
            continue
        gap = 0
        if isinstance(v, float) and v.is_integer():
            v = int(v)
        sv = str(v).strip()
        k = sv.lower()
        if k in MANIFEST_JUNK or k == htxt.lower():
            continue
        if k in seen:
            continue
        seen.add(k)
        ids.append(sv)
        if len(ids) > MANIFEST_MAX_IDS:
            raise HTTPException(400, f"Too many IDs in the file (max {MANIFEST_MAX_IDS:,})")
    if not ids:
        return None
    return (sc, n, htxt, ids)

def _parse_manifest(content: bytes):
    """Read an Excel manifest and return the unique IDs from its key column.

    Every sheet is checked (not only the one open when the file was saved), and the
    header may sit below title or blank rows. When several sheets have a key column
    the one with the clearest header and the most rows wins - so a raw packing list
    beats a pivot-table summary of it."""
    try:
        from openpyxl import load_workbook
    except ImportError:
        raise HTTPException(500, "Excel support (openpyxl) is not installed on this server")
    try:
        wb = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except Exception:
        raise HTTPException(400, "Cannot read this file - please upload a valid Excel workbook (.xlsx)")
    try:
        sheets = list(wb.worksheets)
        if not sheets:
            raise HTTPException(400, "The Excel file has no worksheet")
        found = []
        for ws in sheets:
            cand = _manifest_sheet_candidate(ws)
            if cand:
                found.append(cand)
    finally:
        try:
            wb.close()
        except Exception:
            pass
    if not found:
        names = ", ".join(str(ws.title) for ws in sheets)
        raise HTTPException(400, "Could not find a bag / carton / gunny / sack ID column in any sheet "
                                 f"({names}) - the header should be e.g. 'Carton No', 'Bag ID' or 'Sack No'")
    found.sort(key=lambda c: (c[0], c[1]), reverse=True)
    return found[0][3]

def _manifest_scope_check(rid, scope_vid):
    if scope_vid is None:
        return
    req_row = next((r for r in _store["truck_requests"] if r["id"] == rid), None) if LOCAL_MODE \
        else db_1("SELECT vendor_id, assigned_truck_id FROM truck_requests WHERE id=%s", (rid,))
    if not req_row or not _owned_by_vendor(req_row, scope_vid):
        raise HTTPException(404, "Not found")

def _manifest_meta(m):
    if not m:
        return None
    if m.get("ids") is not None:
        cnt = len(m.get("ids") or [])
    else:
        cnt = int(m.get("id_count") or 0)
    return {"id": m.get("id"), "original_filename": m.get("original_filename"),
            "file_size": m.get("file_size", 0), "id_count": cnt, "created_at": m.get("created_at")}

def _manifest_request_row(rid):
    if LOCAL_MODE:
        return next((r for r in _store["truck_requests"] if r["id"] == rid), None)
    return db_1("SELECT id, request_number, international_mawb, domestic_mawb FROM truck_requests WHERE id=%s", (rid,))

def _manifest_csv_bytes(req_row, ids) -> bytes:
    """The manifest CSV: the request's MAWBs beside every unique bag/carton/gunny/sack ID."""
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["International MAWB", "Domestic MAWB", "Bag/Carton/Gunny/Sack ID"])
    imawb = str((req_row or {}).get("international_mawb") or "")
    dmawb = str((req_row or {}).get("domestic_mawb") or "")
    for x in ids:
        w.writerow([imawb, dmawb, x])
    return buf.getvalue().encode("utf-8")

def _csv_has_current_mawbs(data: bytes, req_row) -> bool:
    try:
        rows = csv.reader(io.StringIO(data.decode("utf-8", "replace")))
        next(rows, None)
        first = next(rows, None)
        if not first:
            return False
        got = [str(first[0]), str(first[1]) if len(first) > 1 else ""]
        want = [str((req_row or {}).get("international_mawb") or ""),
                str((req_row or {}).get("domestic_mawb") or "")]
        return got == want
    except Exception:
        return False

def _read_att_file(path):
    if not path:
        return None
    try:
        if _is_object_key(path):
            return obj_storage.get_bytes(path)
        if os.path.exists(path):
            with open(path, "rb") as f:
                return f.read()
    except Exception:
        return None
    return None

def _store_manifest_csv(rid, req_row, ids, prev_path=""):
    """Convert the extracted IDs into the manifest CSV and store that file.

    The Excel file that was uploaded is never persisted: only this CSV (MAWBs +
    unique IDs) is written to storage, and any previously stored file for the
    request is removed once the new one is safely in place."""
    csv_bytes = _manifest_csv_bytes(req_row, ids)
    cfn = uuid.uuid4().hex + ".csv"
    if _obj_storage_on():
        try:
            key = obj_storage.safe_key("attachments", str(rid), cfn)
        except ValueError:
            raise HTTPException(400, "Invalid filename")
        obj_storage.put_bytes(key, csv_bytes, content_type="text/csv")
        path = key
    else:
        path = os.path.join(_store["_upload"], cfn)
        with open(path, "wb") as f:
            f.write(csv_bytes)
    if prev_path and prev_path != path:
        _delete_att_file(prev_path)
    name = str((req_row or {}).get("request_number") or f"request-{rid}") + "-manifest.csv"
    return {"filename": cfn, "original_filename": name,
            "file_size": len(csv_bytes), "storage_path": path}

@app.post("/api/requests/{rid}/manifest")
async def upload_manifest(rid: int, request: Request, file: UploadFile = File(...)):
    scope_vid, user = vendor_scope(request)
    _manifest_scope_check(rid, scope_vid)
    if LOCAL_MODE:
        if not any(r["id"] == rid for r in _store["truck_requests"]):
            raise HTTPException(404, "Not found")
        existing = next((m for m in _store["manifests"] if m.get("truck_request_id") == rid), None)
    else:
        if not db_1("SELECT id FROM truck_requests WHERE id=%s", (rid,)):
            raise HTTPException(404, "Not found")
        existing = db_1("SELECT id FROM request_manifests WHERE truck_request_id=%s", (rid,))
    if existing:
        raise HTTPException(400, "A manifest file is already uploaded for this request - delete it first")
    ext = os.path.splitext(file.filename or "")[1].lower()
    if ext not in (".xlsx", ".xlsm"):
        raise HTTPException(400, "Manifest must be an Excel file (.xlsx or .xlsm)")
    content = await file.read()
    if not content:
        raise HTTPException(400, "The uploaded file is empty")
    if len(content) > MANIFEST_MAX:
        raise HTTPException(400, "Manifest file must be 10MB or smaller")
    ids = await run_in_threadpool(_parse_manifest, content)
    req_row = await run_in_threadpool(_manifest_request_row, rid)
    st = await run_in_threadpool(_store_manifest_csv, rid, req_row, ids)
    if LOCAL_MODE:
        m = {"id": nid("manifests"), "truck_request_id": rid,
             "id_count": len(ids), "ids": ids, "uploaded_by": user["email"],
             "created_at": nows(), **st}
        _store["manifests"].append(m)
        return _manifest_meta(m)
    mid = db_i("""INSERT INTO request_manifests (truck_request_id,filename,original_filename,file_size,
        storage_path,id_count,ids_json,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s,%s,%s)""",
        (rid, st["filename"], st["original_filename"], st["file_size"], st["storage_path"],
         len(ids), json.dumps(ids), user["email"]))
    return _manifest_meta(db_1("SELECT * FROM request_manifests WHERE id=%s", (mid,)))

@app.delete("/api/requests/{rid}/manifest")
def delete_manifest(rid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    _manifest_scope_check(rid, scope_vid)
    if LOCAL_MODE:
        m = next((x for x in _store["manifests"] if x.get("truck_request_id") == rid), None)
        if m:
            _delete_att_file(m.get("storage_path", ""))
            _store["manifests"] = [x for x in _store["manifests"] if x.get("truck_request_id") != rid]
        return {"ok": True}
    m = db_1("SELECT storage_path FROM request_manifests WHERE truck_request_id=%s", (rid,))
    if m:
        _delete_att_file(m.get("storage_path", ""))
        db_x("DELETE FROM request_manifests WHERE truck_request_id=%s", (rid,))
    return {"ok": True}

@app.get("/api/requests/{rid}/manifest/download")
def download_manifest(rid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    _manifest_scope_check(rid, scope_vid)
    if LOCAL_MODE:
        req_row = next((r for r in _store["truck_requests"] if r["id"] == rid), None)
        m = next((x for x in _store["manifests"] if x.get("truck_request_id") == rid), None)
        ids = list(m.get("ids") or []) if m else []
    else:
        req_row = db_1("SELECT id, request_number, international_mawb, domestic_mawb FROM truck_requests WHERE id=%s", (rid,))
        m = db_1("SELECT id, filename, storage_path, id_count, ids_json FROM request_manifests WHERE truck_request_id=%s", (rid,))
        try:
            ids = json.loads(m.get("ids_json") or "[]") if m else []
        except Exception:
            ids = []
    if not req_row:
        raise HTTPException(404, "Not found")
    if not m:
        raise HTTPException(404, "No manifest file uploaded for this request")
    # The stored file is the manifest CSV itself — serve it as it is. Anything
    # else (an Excel stored by an older release, a missing object, or a CSV whose
    # MAWBs no longer match the request) is rebuilt from the extracted IDs and
    # written back as the CSV, so storage only ever holds the small CSV.
    data = None
    if str(m.get("filename") or "").lower().endswith(".csv"):
        data = _read_att_file(m.get("storage_path") or "")
        if data is not None and not _csv_has_current_mawbs(data, req_row):
            data = None
    if data is None:
        if not ids:
            raw = _read_att_file(m.get("storage_path") or "")
            if raw:
                try:
                    ids = _parse_manifest(raw)
                except HTTPException:
                    ids = []
        if not ids:
            raise HTTPException(404, "The stored manifest file is missing - delete the manifest and upload it again")
        data = _manifest_csv_bytes(req_row, ids)
        st = _store_manifest_csv(rid, req_row, ids, m.get("storage_path") or "")
        if LOCAL_MODE:
            m.update(st)
            m["ids"] = ids
        else:
            db_x("""UPDATE request_manifests SET filename=%s, original_filename=%s, file_size=%s,
                storage_path=%s, id_count=%s, ids_json=%s WHERE id=%s""",
                (st["filename"], st["original_filename"], st["file_size"], st["storage_path"],
                 len(ids), json.dumps(ids), m["id"]))
    fname = str(req_row.get("request_number") or f"request-{rid}") + "-manifest.csv"
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{fname}"'})

# ---------------------------------------------------------------------------
# Driver / Fleet accounts and the scanning app (pickup sort + unloading)
# ---------------------------------------------------------------------------

SCAN_SESSION_DAYS = 30
LATE_REASON_MAX = 1000
MILESTONES = (("arrived_pickup_datetime", "Arrived Pickup"),
              ("start_loading_datetime", "Start Loading"),
              ("end_loading_datetime", "End Loading"),
              ("arrived_dest_datetime", "Arrived Destination"),
              ("start_unloading_datetime", "Start Unloading"),
              ("end_unloading_datetime", "End Unloading"))
MILESTONE_FIELDS = [m[0] for m in MILESTONES]
MILESTONE_LABEL = dict(MILESTONES)
SCAN_WRITABLE = set(MILESTONE_FIELDS) | {"late_reason", "driver_account_id", "pickup_scan_key",
                                         "pickup_scan_closed_at", "unload_scan_key",
                                         "unload_scan_closed_at", "status_id"}
_SCAN_FROM = """FROM truck_requests tr
    LEFT JOIN accounts a ON tr.account_id=a.id
    LEFT JOIN ports po ON tr.origin_port_id=po.id
    LEFT JOIN ports pd ON tr.destination_port_id=pd.id"""
_SCAN_SELECT = ("SELECT tr.*, a.name as account_name, po.name as origin_port_name, "
                "pd.name as destination_port_name " + _SCAN_FROM)

def _pw_hash(password, salt):
    return hashlib.pbkdf2_hmac("sha256", str(password).encode("utf-8"),
                               bytes.fromhex(salt), 120000).hex()

def _pw_new(password):
    salt = secrets.token_hex(16)
    return _pw_hash(password, salt), salt

def _pw_ok(password, hashed, salt):
    if not hashed or not salt:
        return False
    try:
        return secrets.compare_digest(_pw_hash(password, salt), hashed)
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Protected pages: one common password (set / changed / reset by the master admin) in
# front of Driver / Fleet Accounts (non-vendor roles), Rate Management, Cost Analysis,
# Trip Utilisation Review and Vendor Speed Performance. Every password change and every
# unlock is written to page_lock_logs, which the app can only add to - never edit or delete.
# ---------------------------------------------------------------------------

PROTECTED_PAGES = {
    "driver-accounts": "Driver / Fleet Accounts",
    "rates": "Rate Management",
    "cost": "Cost Analysis",
    "trip-utilisation": "Trip Utilisation Review",
    "evaluation": "Vendor Speed Performance",
}
PAGE_TOKEN_HOURS = 12
PAGE_LOCK_MAX_FAILS = 5
PAGE_LOCK_WINDOW = 15 * 60
PAGE_PW_MIN = 6
_page_lock_fails = {}

def _page_lock_row():
    if LOCAL_MODE:
        return _store.get("page_lock")
    try:
        return db_1("SELECT * FROM page_lock WHERE id=1")
    except Exception:
        return None

def page_lock_enabled(row=None):
    row = row if row is not None else _page_lock_row()
    return bool(row and row.get("password_hash") and row.get("password_salt"))

def page_lock_applies(user, page, row=None):
    if page not in PROTECTED_PAGES or not page_lock_enabled(row):
        return False
    if page == "driver-accounts" and is_vendor_role(user.get("role", "")):
        return False
    return True

def _client_ip(request):
    fwd = (request.headers.get("X-Forwarded-For") or "").split(",")[0].strip() if request else ""
    return fwd or (request.client.host if request and request.client else "")

def _page_log(event, user, page=None, detail="", request=None):
    rec = {"event_type": event, "page": page or None,
           "page_name": PROTECTED_PAGES.get(page or "", "") or None,
           "user_email": user.get("email", ""), "user_name": user.get("name", ""),
           "user_role": user.get("role", ""), "detail": (detail or "")[:500],
           "ip_address": _client_ip(request)[:64], "created_at": nows()}
    if LOCAL_MODE:
        _store.setdefault("page_lock_logs", [])
        rec["id"] = len(_store["page_lock_logs"]) + 1
        _store["page_lock_logs"].append(rec)
        return
    db_i("""INSERT INTO page_lock_logs (event_type,page,page_name,user_email,user_name,user_role,detail,ip_address,created_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (rec["event_type"], rec["page"], rec["page_name"], rec["user_email"], rec["user_name"],
         rec["user_role"], rec["detail"], rec["ip_address"], rec["created_at"]))

def _page_token_sig(msg, row):
    key = (str(row.get("password_hash") or "") + ":" + str(row.get("password_salt") or "")).encode()
    return hmac.new(key, msg.encode(), hashlib.sha256).hexdigest()

def _page_token(email, page, row):
    exp = int(time.time()) + PAGE_TOKEN_HOURS * 3600
    msg = f"{email}|{page}|{exp}"
    return base64.urlsafe_b64encode(msg.encode()).decode().rstrip("=") + "." + _page_token_sig(msg, row)

def _page_token_ok(token, email, page, row):
    try:
        b, sig = str(token or "").rsplit(".", 1)
        msg = base64.urlsafe_b64decode(b + "=" * (-len(b) % 4)).decode()
        t_email, t_page, t_exp = msg.rsplit("|", 2)
    except Exception:
        return False
    if t_email != email or t_page != page or int(t_exp) < time.time():
        return False
    return secrets.compare_digest(sig, _page_token_sig(msg, row))

def require_page_unlock(request, page):
    """423 unless the caller unlocked this protected page (when a password is set)."""
    user = get_user(request)
    if _SYNC_USER.get():
        return user
    row = _page_lock_row()
    if page_lock_applies(user, page, row):
        if not _page_token_ok(request.headers.get("X-Page-Token"), user.get("email", ""), page, row):
            raise HTTPException(423, "This page is password protected - enter the page password to open it")
    return user

@app.get("/api/page-lock")
def page_lock_status(request: Request):
    user = get_user(request)
    row = _page_lock_row()
    on = page_lock_enabled(row)
    out = {"enabled": on, "pages": PROTECTED_PAGES,
           "applies": [p for p in PROTECTED_PAGES if page_lock_applies(user, p, row)]}
    if user.get("role") == "master_admin" and row:
        out["updated_at"] = to_gmt8(row.get("updated_at")) if row.get("updated_at") else None
        out["updated_by"] = row.get("updated_by") or ""
    return out

@app.post("/api/page-lock/unlock")
async def page_lock_unlock(request: Request):
    user = get_user(request)
    body = await request.json()
    page = str(body.get("page") or "")
    if page not in PROTECTED_PAGES:
        raise HTTPException(400, "Unknown page")
    row = _page_lock_row()
    if not page_lock_applies(user, page, row):
        return {"ok": True, "token": None}
    key = user.get("email", "")
    now = time.time()
    fails = [t for t in _page_lock_fails.get(key, []) if now - t < PAGE_LOCK_WINDOW]
    if len(fails) >= PAGE_LOCK_MAX_FAILS:
        _page_lock_fails[key] = fails
        _page_log("ACCESS_BLOCKED", user, page, "Too many wrong passwords - locked for 15 minutes", request)
        raise HTTPException(429, "Too many wrong passwords - try again in 15 minutes")
    if not _pw_ok(str(body.get("password") or ""), row.get("password_hash"), row.get("password_salt")):
        fails.append(now)
        _page_lock_fails[key] = fails
        _page_log("ACCESS_DENIED", user, page, f"Wrong password (attempt {len(fails)} of {PAGE_LOCK_MAX_FAILS})", request)
        raise HTTPException(403, "Wrong password")
    _page_lock_fails.pop(key, None)
    _page_log("ACCESS_GRANTED", user, page, "Opened after entering the page password", request)
    return {"ok": True, "token": _page_token(key, page, row), "expires_in": PAGE_TOKEN_HOURS * 3600}

@app.post("/api/page-lock/password")
async def page_lock_set_password(request: Request):
    user = require_master(request)
    body = await request.json()
    action = str(body.get("action") or "").lower()
    new_pw = str(body.get("new_password") or "")
    row = _page_lock_row()
    on = page_lock_enabled(row)
    if action not in ("set", "change", "reset"):
        raise HTTPException(400, "Unknown action")
    if action == "set" and on:
        raise HTTPException(400, "A page password is already set - use Change or Reset")
    if action in ("change", "reset") and not on:
        raise HTTPException(400, "No page password is set yet - use Set password")
    if action == "change" and not _pw_ok(str(body.get("current_password") or ""), row.get("password_hash"), row.get("password_salt")):
        _page_log("PASSWORD_CHANGE_FAILED", user, None, "Current password was wrong", request)
        raise HTTPException(403, "Current password is wrong")
    if len(new_pw) < PAGE_PW_MIN:
        raise HTTPException(400, f"The new password must be at least {PAGE_PW_MIN} characters")
    if new_pw != str(body.get("confirm_password") or ""):
        raise HTTPException(400, "The new password and its confirmation do not match")
    if on and _pw_ok(new_pw, row.get("password_hash"), row.get("password_salt")):
        raise HTTPException(400, "The new password must be different from the current one")
    h, salt = _pw_new(new_pw)
    stamp = nows()
    if LOCAL_MODE:
        _store["page_lock"] = {"id": 1, "password_hash": h, "password_salt": salt,
                               "updated_by": user.get("email", ""), "updated_at": stamp}
    elif row:
        db_x("UPDATE page_lock SET password_hash=%s, password_salt=%s, updated_by=%s, updated_at=%s WHERE id=1",
             (h, salt, user.get("email", ""), stamp))
    else:
        db_x("INSERT INTO page_lock (id,password_hash,password_salt,updated_by,updated_at) VALUES (1,%s,%s,%s,%s)",
             (h, salt, user.get("email", ""), stamp))
    ev = {"set": "PASSWORD_SET", "change": "PASSWORD_CHANGED", "reset": "PASSWORD_RESET"}[action]
    _page_log(ev, user, None, {"set": "Page password set", "change": "Page password changed (current password confirmed)",
                               "reset": "Page password reset by master admin"}[action], request)
    return {"ok": True, "updated_at": stamp}

@app.get("/api/page-lock/logs")
def page_lock_logs(request: Request, event_type: Optional[str] = None, page: Optional[str] = None,
                   q: Optional[str] = None, date_from: Optional[str] = None, date_to: Optional[str] = None,
                   limit: int = 2000):
    require_master(request)
    limit = max(1, min(int(limit or 2000), 10000))
    if LOCAL_MODE:
        rows = [dict(r) for r in _store.get("page_lock_logs", [])]
    else:
        wh, pa = [], []
        if event_type: wh.append("event_type=%s"); pa.append(event_type)
        if page: wh.append("page=%s"); pa.append(page)
        if date_from: wh.append("DATE(created_at)>=%s"); pa.append(date_from)
        if date_to: wh.append("DATE(created_at)<=%s"); pa.append(date_to)
        if q: wh.append("(user_email LIKE %s OR user_name LIKE %s)"); pa.extend([f"%{q}%", f"%{q}%"])
        rows = db_q(f"SELECT * FROM page_lock_logs {('WHERE ' + ' AND '.join(wh)) if wh else ''} ORDER BY id DESC LIMIT {limit}", tuple(pa))
    if LOCAL_MODE:
        if event_type: rows = [r for r in rows if r.get("event_type") == event_type]
        if page: rows = [r for r in rows if r.get("page") == page]
        if date_from: rows = [r for r in rows if str(r.get("created_at") or "")[:10] >= date_from]
        if date_to: rows = [r for r in rows if str(r.get("created_at") or "")[:10] <= date_to]
        if q:
            ql = q.lower()
            rows = [r for r in rows if ql in (r.get("user_email") or "").lower() or ql in (r.get("user_name") or "").lower()]
        rows = sorted(rows, key=lambda r: r.get("id") or 0, reverse=True)[:limit]
    for r in rows:
        r["created_at"] = to_gmt8(r.get("created_at")) if r.get("created_at") else None
    return {"items": rows}

def _truck_plate(tid):
    if not tid:
        return ""
    if LOCAL_MODE:
        t = next((x for x in _store["trucks"] if x["id"] == tid), None)
        return (t or {}).get("plate_number") or ""
    t = db_1("SELECT plate_number FROM trucks WHERE id=%s", (tid,))
    return (t or {}).get("plate_number") or ""

def _local_truck_type(d):
    t = next((x for x in _store["trucks"] if x["id"] == d.get("truck_id")), None) if d.get("truck_id") else None
    d["truck_type_id"] = (t or {}).get("truck_type_id")
    d["truck_type_name"] = next((tt["name"] for tt in _store["truck_types"] if tt["id"] == d["truck_type_id"]), "") if t else ""

def _driver_public(d):
    if not d:
        return None
    plate = d.get("plate_number")
    if plate is None:
        plate = _truck_plate(d.get("truck_id"))
    return {"id": d.get("id"), "vendor_id": d.get("vendor_id"),
            "username": d.get("username") or "", "driver_name": d.get("driver_name") or "",
            "driver_phone": d.get("driver_phone") or "", "vendor_name": d.get("vendor_name") or "",
            "truck_id": d.get("truck_id"), "plate_number": plate or "",
            "truck_type_id": d.get("truck_type_id"), "truck_type_name": d.get("truck_type_name") or "",
            "has_override_code": bool(d.get("override_hash")),
            "is_active": bool(d.get("is_active", 1))}

OVERRIDE_CODE_RE = re.compile(r"[A-Za-z0-9]{4,32}")

def _clean_override_code(raw):
    code = str(raw or "").strip()
    if not OVERRIDE_CODE_RE.fullmatch(code):
        raise HTTPException(400, "Override code must be 4-32 letters or numbers")
    return code

def _driver_rows(vid=None, active_only=False):
    if LOCAL_MODE:
        rows = [row2d(d) for d in _store["driver_accounts"]]
        if vid is not None:
            rows = [d for d in rows if d.get("vendor_id") == vid]
        if active_only:
            rows = [d for d in rows if d.get("is_active", 1)]
        for d in rows:
            d["plate_number"] = _truck_plate(d.get("truck_id"))
            _local_truck_type(d)
            d["vendor_name"] = next((v["name"] for v in _store["vendors"] if v["id"] == d.get("vendor_id")), "")
        rows.sort(key=lambda d: str(d.get("username") or "").lower())
        return rows
    sql = """SELECT da.*, v.name as vendor_name, tk2.plate_number as plate_number,
        tk2.truck_type_id as truck_type_id, ttd.name as truck_type_name
        FROM driver_accounts da
        LEFT JOIN vendors v ON da.vendor_id=v.id
        LEFT JOIN trucks tk2 ON da.truck_id=tk2.id
        LEFT JOIN truck_types ttd ON tk2.truck_type_id=ttd.id"""
    wh, pa = [], []
    if vid is not None:
        wh.append("da.vendor_id=%s"); pa.append(vid)
    if active_only:
        wh.append("da.is_active=1")
    if wh:
        sql += " WHERE " + " AND ".join(wh)
    sql += " ORDER BY da.username"
    return db_q(sql, tuple(pa))

def _driver_row(did):
    if LOCAL_MODE:
        row = row2d(next((x for x in _store["driver_accounts"] if x["id"] == did), None))
        if row:
            row["plate_number"] = _truck_plate(row.get("truck_id"))
            _local_truck_type(row)
        return row
    return db_1("""SELECT da.*, v.name as vendor_name, tk2.plate_number as plate_number,
        tk2.truck_type_id as truck_type_id, ttd.name as truck_type_name
        FROM driver_accounts da
        LEFT JOIN vendors v ON da.vendor_id=v.id
        LEFT JOIN trucks tk2 ON da.truck_id=tk2.id
        LEFT JOIN truck_types ttd ON tk2.truck_type_id=ttd.id WHERE da.id=%s""", (did,))

def _driver_by_username(u):
    u = str(u or "").strip().lower()
    if not u:
        return None
    if LOCAL_MODE:
        row = row2d(next((x for x in _store["driver_accounts"]
                          if str(x.get("username") or "").lower() == u), None))
        if row:
            row["plate_number"] = _truck_plate(row.get("truck_id"))
            _local_truck_type(row)
        return row
    return db_1("""SELECT da.*, v.name as vendor_name, tk2.plate_number as plate_number,
        tk2.truck_type_id as truck_type_id, ttd.name as truck_type_name
        FROM driver_accounts da
        LEFT JOIN vendors v ON da.vendor_id=v.id
        LEFT JOIN trucks tk2 ON da.truck_id=tk2.id
        LEFT JOIN truck_types ttd ON tk2.truck_type_id=ttd.id WHERE LOWER(da.username)=%s""", (u,))

def _clean_username(raw):
    u = str(raw or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9._@-]{3,100}", u):
        raise HTTPException(400, "Username must be 3-100 characters: letters, numbers, dot, underscore, dash or @")
    return u

def _driver_vendor_ok(vid, want_vid):
    """A vendor caller may only touch its own vendor's driver accounts."""
    if vid is not None and vid != want_vid:
        raise HTTPException(403, "That driver account belongs to another vendor")

def _clean_truck(want_vid, raw):
    """Validate the truck carried by a driver/fleet account."""
    if raw in (0, "0", "", None):
        return None
    try:
        tid = int(raw)
    except (TypeError, ValueError):
        raise HTTPException(400, "truck_id must be a number")
    if LOCAL_MODE:
        t = next((x for x in _store["trucks"] if x["id"] == tid), None)
    else:
        t = db_1("SELECT id, vendor_id, is_active FROM trucks WHERE id=%s", (tid,))
    if not t or not t.get("is_active", 1):
        raise HTTPException(400, "Truck not found")
    if want_vid is not None and t.get("vendor_id") != want_vid:
        raise HTTPException(400, "That truck belongs to a different vendor")
    return tid

def get_driver(request):
    tok = (request.headers.get("X-Scan-Token") or "").strip()
    if not tok:
        raise HTTPException(401, "Sign in to the scanning app first")
    if LOCAL_MODE:
        s = _store["driver_sessions"].get(tok)
        if not s or str(s.get("expires_at") or "") <= nows():
            _store["driver_sessions"].pop(tok, None)
            raise HTTPException(401, "Your scanning session has expired - sign in again")
        d = next((x for x in _store["driver_accounts"] if x["id"] == s.get("driver_account_id")), None)
        d = row2d(d)
    else:
        s = db_1("SELECT * FROM driver_sessions WHERE token=%s", (tok,))
        if not s or str(s.get("expires_at") or "") <= nows():
            raise HTTPException(401, "Your scanning session has expired - sign in again")
        d = _driver_row(s.get("driver_account_id"))
    if not d or not d.get("is_active", 1):
        raise HTTPException(401, "This driver account is not active")
    return d

def _scan_actor(request):
    """Who performed a scan: the signed-in driver when there is one, else 'scanner'."""
    tok = (request.headers.get("X-Scan-Token") or "").strip()
    if tok:
        try:
            return get_driver(request).get("username") or "scanner"
        except HTTPException:
            pass
    return "scanner"

def _scan_row_names(r):
    if not LOCAL_MODE:
        return r
    r["account_name"] = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
    r["origin_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
    r["destination_port_name"] = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
    return r

def _write_fields(row, values, email=None):
    """Persist given truck_requests columns for one row, local + database."""
    for k in values:
        if k not in SCAN_WRITABLE:
            raise HTTPException(500, "Unsupported field")
        row[k] = values[k]
    if LOCAL_MODE:
        for x in _store["truck_requests"]:
            if x["id"] == row["id"]:
                x.update(values)
                x["updated_at"] = nows()
                if email:
                    x["updated_by"] = email
                break
        return
    sets = [f"{k}=%s" for k in values]
    params = list(values.values())
    sets.append("updated_at=NOW()")
    if email:
        sets.append("updated_by=%s"); params.append(email)
    params.append(row["id"])
    db_x(f"UPDATE truck_requests SET {','.join(sets)} WHERE id=%s", tuple(params))

def _set_milestones(rows, field, email=None):
    """Record `field` (auto-filling any earlier empty milestone with now).

    Refuses to run when a later milestone is already recorded on the row, so a
    out-of-order tap can never produce a backwards timeline.
    """
    idx = MILESTONE_FIELDS.index(field)
    earlier = MILESTONE_FIELDS[:idx]
    later = MILESTONE_FIELDS[idx + 1:]
    now = nows()
    for r in rows:
        hit = next((MILESTONE_LABEL[x] for x in later if r.get(x)), None)
        if hit:
            raise HTTPException(400, f"Cannot record {MILESTONE_LABEL[field]} - "
                                     f"{hit} is already recorded for {r.get('request_number') or r.get('id')}")
    applied = 0
    for r in rows:
        vals = {}
        for f in earlier + [field]:
            if not r.get(f):
                vals[f] = now
        if vals:
            _write_fields(r, vals, email)
            applied += 1
    return applied

def _manifest_ids_for(rid):
    if LOCAL_MODE:
        m = next((x for x in _store["manifests"] if x.get("truck_request_id") == rid), None)
        return list(m.get("ids") or []) if m else []
    m = db_1("SELECT ids_json FROM request_manifests WHERE truck_request_id=%s", (rid,))
    if not m:
        return []
    try:
        return json.loads(m.get("ids_json") or "[]")
    except Exception:
        return []

def _expected_pickup_ids(rows):
    out, seen = [], set()
    for r in rows:
        for x in _manifest_ids_for(r.get("id")):
            k = str(x).lower()
            if k in seen:
                continue
            seen.add(k)
            out.append(x)
    return out

def _trip_key_of(row):
    return trip_base(row.get("trip_id")) or f"req-{row.get('id')}"

def _scan_base(rows):
    for r in rows:
        b = trip_base(r.get("trip_id"))
        if b:
            return b
    return f"req-{rows[0].get('id')}"

def _rows_by_pickup_key(key):
    if not key:
        return []
    if LOCAL_MODE:
        return [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("pickup_scan_key") == key]
    return db_q(_SCAN_SELECT + " WHERE tr.pickup_scan_key=%s", (key,))

def _rows_by_unload_key(key):
    if not key:
        return []
    if LOCAL_MODE:
        return [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("unload_scan_key") == key]
    return db_q(_SCAN_SELECT + " WHERE tr.unload_scan_key=%s", (key,))

def _rows_for_base(base):
    """Every request that belongs to a trip, whatever its status."""
    if not base:
        return []
    if LOCAL_MODE:
        if base.startswith("req-"):
            try:
                rid = int(base[4:])
            except ValueError:
                return []
            return [_scan_row_names(row2d(r)) for r in _store["truck_requests"] if r["id"] == rid]
        return [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("trip_id") and trip_base(r["trip_id"]) == base]
    if base.startswith("req-"):
        try:
            rid = int(base[4:])
        except ValueError:
            return []
        return db_q(_SCAN_SELECT + " WHERE tr.id=%s", (rid,))
    rows = db_q(_SCAN_SELECT + " WHERE tr.trip_id=%s OR tr.trip_id LIKE %s", (base, base + "-_"))
    return [r for r in rows if trip_base(r.get("trip_id")) == base]

def _pickup_scans(base):
    if not base:
        return []
    if LOCAL_MODE:
        return [row2d(s) for s in _store["scan_pickup"] if s.get("trip_base") == base]
    return db_q("SELECT * FROM scan_pickup_items WHERE trip_base=%s ORDER BY id", (base,))

def _unload_scans(rid):
    if LOCAL_MODE:
        return [row2d(s) for s in _store["scan_unload"] if s.get("request_id") == rid]
    return db_q("SELECT * FROM scan_unload_items WHERE request_id=%s ORDER BY id", (rid,))

def _scan_kind_of(scans, bag):
    k = str(bag).lower()
    for s in scans:
        if str(s.get("bag_id") or "").lower() == k:
            return s.get("scan_kind") or "original"
    return None

def _record_scan(table, values, trip_base_val=None, rid=None, bag=None):
    """Insert one scan row; returns False when that bag is already recorded."""
    if LOCAL_MODE:
        rows = _store[table]
        for s in rows:
            same_bag = str(s.get("bag_id") or "").lower() == str(bag).lower()
            if table == "scan_pickup":
                if s.get("trip_base") == trip_base_val and same_bag:
                    return False
            elif s.get("request_id") == rid and same_bag:
                return False
        values = dict(values, id=nid(table))
        # The reader filters on these keys, so they must live on the row itself.
        if table == "scan_pickup":
            values["trip_base"] = trip_base_val
        values["request_id"] = rid
        values.setdefault("scanned_at", nows())
        rows.append(values)
        return True
    try:
        if table == "scan_pickup":
            db_i("""INSERT INTO scan_pickup_items (trip_base,request_id,bag_id,scan_kind,scanned_by)
                VALUES (%s,%s,%s,%s,%s)""", (trip_base_val, rid, values["bag_id"],
                                             values.get("scan_kind") or "original",
                                             values.get("scanned_by")))
        else:
            db_i("""INSERT INTO scan_unload_items (request_id,bag_id,scan_kind,scanned_by)
                VALUES (%s,%s,%s,%s)""", (rid, values["bag_id"],
                                          values.get("scan_kind") or "original",
                                          values.get("scanned_by")))
        return True
    except Exception:
        return False

def _unload_reference(row, trip_rows):
    """Bag ids an unloading scan at `row` accepts: the bags picked up for that drop.

    A pickup scan is tied to the drop whose manifest lists the bag. On a
    single-drop trip every pickup-scanned bag belongs to that one drop."""
    trip_rows = trip_rows or [row]
    base = _scan_base(trip_rows)
    single = len({r.get("id") for r in trip_rows}) <= 1
    out, seen = [], set()
    for s in _pickup_scans(base):
        rid = s.get("request_id")
        if rid == row.get("id") or (single and not rid):
            b = str(s.get("bag_id") or "")
            if b.lower() not in seen:
                seen.add(b.lower())
                out.append(b)
    return out

def _drop_no(row, trip_rows):
    """Drop # of a request inside its own trip (1..n, in drop order).

    drop_sequence counts across the whole truck, so a truck carrying two trips
    numbers the second trip 4, 5... The driver needs the number within the trip."""
    ordered = _ordered(trip_rows or [row])
    for i, r in enumerate(ordered):
        if r.get("id") == row.get("id"):
            return i + 1
    return row.get("drop_sequence")

def _drop_info(r, trip_rows=None):
    return {"request_id": r.get("id"), "request_number": r.get("request_number") or "",
            "account_name": r.get("account_name") or "",
            "destination_port_name": r.get("destination_port_name") or "",
            "drop_sequence": _drop_no(r, trip_rows) if trip_rows else r.get("drop_sequence")}

def _pickup_owner(bag, trip_rows):
    """The drop a bag was picked up for (None when not pickup-scanned or unattributed)."""
    base = _scan_base(trip_rows)
    k = str(bag).lower()
    hit = next((s for s in _pickup_scans(base) if str(s.get("bag_id") or "").lower() == k), None)
    if not hit:
        return None, False
    rid = hit.get("request_id")
    if not rid and len(trip_rows) == 1:
        rid = trip_rows[0].get("id")
    owner = next((r for r in trip_rows if r.get("id") == rid), None)
    return owner, True

def _scan_summary(kind, rows, key, trip_rows=None):
    base = _scan_base(rows)
    closed_field = "pickup_scan_closed_at" if kind == "pickup" else "unload_scan_closed_at"
    closed = next((r.get(closed_field) for r in rows if r.get(closed_field)), None)
    if kind == "pickup":
        scans = _pickup_scans(base)
        expected = _expected_pickup_ids(rows)
    else:
        scans = _unload_scans(rows[0]["id"])
        if trip_rows is None:
            trip_rows = _rows_for_base(base) or rows
        expected = _unload_reference(rows[0], trip_rows)
    exp_set = {str(x).lower() for x in expected}
    scanned = []
    for s in scans:
        b = str(s.get("bag_id") or "")
        scanned.append({"bag_id": b, "scan_kind": s.get("scan_kind") or "original",
                        "request_id": s.get("request_id"),
                        "scanned_at": to_gmt8(s.get("scanned_at")),
                        "known": (b.lower() in exp_set) if exp_set else None})
    scanned_keys = {x["bag_id"].lower() for x in scanned}
    original = sum(1 for x in scanned if x["scan_kind"] != "override")
    override = sum(1 for x in scanned if x["scan_kind"] == "override")
    remaining = len(exp_set - scanned_keys)
    if kind == "pickup":
        started = any(r.get("arrived_pickup_datetime") for r in rows)
        mode = "manifest" if exp_set else "free"
    else:
        started = bool(rows[0].get("arrived_dest_datetime"))
        mode = "pickup"
    return {"kind": kind, "trip_id": base, "key": key,
            "mode": mode,
            "expected_count": (len(exp_set) if (exp_set or kind == "unload") else None),
            "scanned_count": len(scans),
            "original_count": original,
            "override_count": override,
            "remaining_count": remaining,
            "scanned": scanned,
            "started": started,
            "closed": bool(closed), "closed_at": to_gmt8(closed),
            "requests": [{"id": r.get("id"), "request_number": r.get("request_number"),
                          "drop_sequence": _drop_no(r, trip_rows or rows),
                          "account_name": r.get("account_name") or "",
                          "destination_port_name": r.get("destination_port_name") or "",
                          "status_id": r.get("status_id")} for r in rows]}

SCAN_CSV_HEADER = ["Bag ID", "Trip ID", "International MAWB", "Domestic MAWB", "Account",
                   "Origin", "Destination", "Drop #", "Remark"]

def _scan_csv(rows, scans, expected, label):
    """One line per bag of a scan session: the bag, its trip, the MAWBs, account,
    origin, destination and drop of the request it belongs to, and how it was scanned
    (original / override / missing)."""
    by_id = {r.get("id"): r for r in rows}
    base = _scan_base(rows) if rows else ""

    def line(bag, owner, remark):
        o = owner or {}
        return [bag, o.get("trip_id") or base, o.get("international_mawb") or "", o.get("domestic_mawb") or "",
                o.get("account_name") or "", o.get("origin_port_name") or "",
                o.get("destination_port_name") or "", o.get("drop_sequence") or "", remark]

    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(SCAN_CSV_HEADER)
    seen = set()
    for x in expected:
        k = str(x).lower()
        if k in seen:
            continue
        seen.add(k)
        owner = None
        for r in rows:
            if k in {str(m).lower() for m in _manifest_ids_for(r.get("id"))}:
                owner = r
                break
        if owner is None and len(rows) == 1:
            owner = rows[0]
        kind = _scan_kind_of(scans, x)
        w.writerow(line(x, owner, kind if kind else "missing"))
    for s in scans:
        b = str(s.get("bag_id") or "")
        if b.lower() in seen:
            continue
        seen.add(b.lower())
        owner = by_id.get(s.get("request_id")) or (rows[0] if len(rows) == 1 else None)
        w.writerow(line(b, owner, s.get("scan_kind") or "original"))
    data = ("\ufeff" + buf.getvalue()).encode("utf-8")
    name = f"{label}-scan.csv"
    return Response(data, media_type="text/csv; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="{name}"'})

# --- Driver / Fleet account management ------------------------------------

def _trip_stage(rows):
    """Plain-language progress of one trip, from its requests' milestones."""
    rows = _ordered(rows)
    total = len(rows)
    done = sum(1 for r in rows if r.get("status_id") == 4)
    active = [r for r in rows if r.get("status_id") in (2, 3)]
    if not active:
        return "Completed", "done"
    if any(r.get("status_id") == 3 for r in active):
        cur = active[0]
        d = rows.index(cur) + 1
        if cur.get("unload_scan_closed_at"):
            return f"Drop {d}: unloading scan ended ({done}/{total} delivered)", "transit"
        if cur.get("start_unloading_datetime"):
            return f"Drop {d}: unloading ({done}/{total} delivered)", "transit"
        if cur.get("arrived_dest_datetime"):
            return f"Drop {d}: arrived at destination ({done}/{total} delivered)", "transit"
        return f"In Transit to drop {d} ({done}/{total} delivered)", "transit"
    if any(r.get("end_loading_datetime") for r in active):
        return "Loaded - waiting to depart", "loading"
    if any(r.get("pickup_scan_closed_at") for r in active):
        return "Pickup scan ended - waiting for End Loading", "loading"
    if any(r.get("start_loading_datetime") for r in active):
        return "Loading (pickup scan in progress)", "loading"
    if any(r.get("arrived_pickup_datetime") for r in active):
        return "Arrived at pickup", "loading"
    return "Allocated - not started", "allocated"

def _driver_trip_map(driver_ids):
    """driver id -> [{trip_id, status, stage, drops}] for trips still open."""
    if not driver_ids:
        return {}
    if LOCAL_MODE:
        mine = [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("driver_account_id") in driver_ids and r.get("status_id") in (2, 3)]
    else:
        marks = ",".join(["%s"] * len(driver_ids))
        mine = db_q(_SCAN_SELECT + f" WHERE tr.driver_account_id IN ({marks}) AND tr.status_id IN (2,3)",
                    tuple(driver_ids))
    by = {}
    for r in mine:
        by.setdefault(r.get("driver_account_id"), {}).setdefault(_trip_key_of(r), []).append(r)
    out = {}
    for did, trips in by.items():
        lst = []
        for base, rs in trips.items():
            full = _rows_for_base(base) or rs
            label, tone = _trip_stage(full)
            fcs = [to_gmt8(r.get("final_call_datetime")) for r in rs if r.get("final_call_datetime")]
            lst.append({"trip_id": base,
                        "status_id": 3 if any(r.get("status_id") == 3 for r in rs) else 2,
                        "status_name": "In Transit" if any(r.get("status_id") == 3 for r in rs) else "Allocated",
                        "stage": label, "tone": tone, "drops": len(full),
                        "final_call_datetime": min(fcs) if fcs else None})
        lst.sort(key=lambda t: str(t.get("final_call_datetime") or "9999-12-31"))
        out[did] = lst
    return out

@app.get("/api/driver-accounts")
def list_driver_accounts(request: Request):
    require_page_unlock(request, "driver-accounts")
    u, vid = require_vendor_or_admin(request)
    rows = _driver_rows(vid)
    trips = _driver_trip_map([d.get("id") for d in rows])
    out = []
    for d in rows:
        p = _driver_public(d)
        p["trips"] = trips.get(d.get("id"), [])
        out.append(p)
    return out

@app.post("/api/driver-accounts")
async def create_driver_account(request: Request):
    require_page_unlock(request, "driver-accounts")
    u, vid = require_vendor_or_admin(request)
    body = await request.json()
    username = _clean_username(body.get("username"))
    password = str(body.get("password") or "")
    if len(password) < 4:
        raise HTTPException(400, "Password must be at least 4 characters")
    want_vid = vid if vid is not None else body.get("vendor_id")
    if not want_vid:
        raise HTTPException(400, "Vendor is required")
    if vid is not None:
        _driver_vendor_ok(vid, want_vid)
    elif not LOCAL_MODE and not db_1("SELECT id FROM vendors WHERE id=%s", (want_vid,)):
        raise HTTPException(400, "Vendor not found")
    elif LOCAL_MODE and not any(v["id"] == want_vid for v in _store["vendors"]):
        raise HTTPException(400, "Vendor not found")
    if _driver_by_username(username):
        raise HTTPException(400, "That username is already in use")
    tid = _clean_truck(want_vid, body.get("truck_id"))
    ov_hash = ov_salt = None
    if str(body.get("override_code") or "").strip():
        ov_hash, ov_salt = _pw_new(_clean_override_code(body.get("override_code")))
    hashed, salt = _pw_new(password)
    vals = (want_vid, username, hashed, salt,
            str(body.get("driver_name") or "").strip() or None,
            str(body.get("driver_phone") or "").strip() or None,
            1 if body.get("is_active", True) else 0, tid)
    if LOCAL_MODE:
        d = {"id": nid("driver_accounts"), "vendor_id": vals[0], "username": vals[1],
             "password_hash": vals[2], "password_salt": vals[3], "driver_name": vals[4],
             "driver_phone": vals[5], "is_active": bool(vals[6]), "truck_id": vals[7],
             "override_hash": ov_hash, "override_salt": ov_salt,
             "active_trip_id": None, "created_at": nows(), "updated_at": nows()}
        _store["driver_accounts"].append(d)
        return _driver_public(_driver_row(d["id"]))
    did = db_i("""INSERT INTO driver_accounts (vendor_id,username,password_hash,password_salt,
        driver_name,driver_phone,is_active,truck_id,override_hash,override_salt)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""", vals + (ov_hash, ov_salt))
    return _driver_public(_driver_row(did))

@app.put("/api/driver-accounts/{did}")
async def update_driver_account(did: int, request: Request):
    require_page_unlock(request, "driver-accounts")
    u, vid = require_vendor_or_admin(request)
    d = _driver_row(did)
    if not d:
        raise HTTPException(404, "Driver account not found")
    _driver_vendor_ok(vid, d.get("vendor_id"))
    body = await request.json()
    sets, params = [], []
    if "username" in body:
        username = _clean_username(body.get("username"))
        other = _driver_by_username(username)
        if other and other.get("id") != did:
            raise HTTPException(400, "That username is already in use")
        sets.append("username=%s"); params.append(username)
    if str(body.get("password") or ""):
        password = str(body.get("password"))
        if len(password) < 4:
            raise HTTPException(400, "Password must be at least 4 characters")
        hashed, salt = _pw_new(password)
        sets.extend(["password_hash=%s", "password_salt=%s"]); params.extend([hashed, salt])
    if body.get("clear_override_code"):
        sets.extend(["override_hash=%s", "override_salt=%s"]); params.extend([None, None])
    elif str(body.get("override_code") or "").strip():
        oh, osalt = _pw_new(_clean_override_code(body.get("override_code")))
        sets.extend(["override_hash=%s", "override_salt=%s"]); params.extend([oh, osalt])
    if "driver_name" in body:
        sets.append("driver_name=%s"); params.append(str(body.get("driver_name") or "").strip() or None)
    if "driver_phone" in body:
        sets.append("driver_phone=%s"); params.append(str(body.get("driver_phone") or "").strip() or None)
    if "is_active" in body:
        active = 1 if body.get("is_active") else 0
        sets.append("is_active=%s"); params.append(active)
        if not active and LOCAL_MODE:
            for t, s in list(_store["driver_sessions"].items()):
                if s.get("driver_account_id") == did:
                    _store["driver_sessions"].pop(t, None)
    if vid is not None and "vendor_id" in body:
        raise HTTPException(403, "Vendors cannot move a driver account to another vendor")
    if "vendor_id" in body and vid is None:
        sets.append("vendor_id=%s"); params.append(body.get("vendor_id"))
    if "truck_id" in body:
        eff_vid = body.get("vendor_id") if (vid is None and "vendor_id" in body) else d.get("vendor_id")
        sets.append("truck_id=%s"); params.append(_clean_truck(eff_vid, body.get("truck_id")))
    if not sets:
        raise HTTPException(400, "Nothing to update")
    if LOCAL_MODE:
        for x in _store["driver_accounts"]:
            if x["id"] == did:
                for i, k in enumerate([s.split("=")[0] for s in sets]):
                    x[k] = params[i]
                if not x.get("is_active", 1):
                    for t, s in list(_store["driver_sessions"].items()):
                        if s.get("driver_account_id") == did:
                            _store["driver_sessions"].pop(t, None)
                x["updated_at"] = nows()
                return _driver_public(_driver_row(did))
        raise HTTPException(404, "Driver account not found")
    params.append(did)
    db_x(f"UPDATE driver_accounts SET {','.join(sets)},updated_at=NOW() WHERE id=%s", tuple(params))
    return _driver_public(_driver_row(did))

@app.delete("/api/driver-accounts/{did}")
async def delete_driver_account(did: int, request: Request):
    require_page_unlock(request, "driver-accounts")
    u, vid = require_vendor_or_admin(request)
    d = _driver_row(did)
    if not d:
        raise HTTPException(404, "Driver account not found")
    _driver_vendor_ok(vid, d.get("vendor_id"))
    if LOCAL_MODE:
        _store["driver_accounts"] = [x for x in _store["driver_accounts"] if x["id"] != did]
        for t, s in list(_store["driver_sessions"].items()):
            if s.get("driver_account_id") == did:
                _store["driver_sessions"].pop(t, None)
        for r in _store["truck_requests"]:
            if r.get("driver_account_id") == did:
                r["driver_account_id"] = None
        return {"ok": True}
    db_x("UPDATE truck_requests SET driver_account_id=NULL WHERE driver_account_id=%s", (did,))
    db_x("DELETE FROM driver_sessions WHERE driver_account_id=%s", (did,))
    db_x("DELETE FROM driver_accounts WHERE id=%s", (did,))
    return {"ok": True}

# --- Scanning app authentication ------------------------------------------

@app.post("/api/scan/login")
async def scan_login(request: Request):
    body = await request.json()
    username = str(body.get("username") or "").strip()
    password = str(body.get("password") or "")
    if not username or not password:
        raise HTTPException(400, "Username and password are required")
    d = _driver_by_username(username)
    if not d or not _pw_ok(password, d.get("password_hash"), d.get("password_salt")):
        raise HTTPException(401, "Wrong username or password")
    if not d.get("is_active", 1):
        raise HTTPException(403, "This driver account is not active")
    tok = secrets.token_hex(32)
    exp = (datetime.now(_GMT8) + timedelta(days=SCAN_SESSION_DAYS)).strftime("%Y-%m-%d %H:%M:%S")
    if LOCAL_MODE:
        _store["driver_sessions"][tok] = {"driver_account_id": d["id"],
                                          "created_at": nows(), "expires_at": exp}
    else:
        db_x("INSERT INTO driver_sessions (token,driver_account_id,expires_at) VALUES (%s,%s,%s)",
             (tok, d["id"], exp))
    return {"token": tok, "driver": _driver_public(d)}

@app.post("/api/scan/logout")
async def scan_logout(request: Request):
    tok = (request.headers.get("X-Scan-Token") or "").strip()
    if tok:
        if LOCAL_MODE:
            _store["driver_sessions"].pop(tok, None)
        else:
            db_x("DELETE FROM driver_sessions WHERE token=%s", (tok,))
    return {"ok": True}

@app.get("/api/scan/me")
def scan_me(request: Request):
    return _driver_public(get_driver(request))

# --- Driver trip flow ------------------------------------------------------

def _driver_trip_rows(driver, base):
    if LOCAL_MODE:
        rows = [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("driver_account_id") == driver.get("id")
                and r.get("status_id") in (2, 3) and _trip_key_of(r) == base]
    else:
        rows = db_q(_SCAN_SELECT + " WHERE tr.driver_account_id=%s AND tr.status_id IN (2,3)",
                    (driver.get("id"),))
        rows = [r for r in rows if _trip_key_of(r) == base]
    if not rows:
        raise HTTPException(404, "This trip is not assigned to your account")
    for r in rows:
        if not _owned_by_vendor(r, driver.get("vendor_id")):
            raise HTTPException(403, "This trip belongs to another vendor")
    return rows

def _ordered(rows):
    return sorted(rows, key=lambda x: (x.get("drop_sequence") is None,
                                       x.get("drop_sequence") or 0, x.get("id")))

def _trip_started(rows):
    """A trip is in progress once the driver has tapped Arrived at pickup."""
    return any(r.get("arrived_pickup_datetime") for r in rows)

def _trip_detail(driver, rows):
    base = _scan_base(rows)
    all_rows = _rows_for_base(base) or rows
    expected = _expected_pickup_ids(all_rows)
    scans = _pickup_scans(base)
    pk = next((r.get("pickup_scan_key") for r in rows if r.get("pickup_scan_key")), None)
    closed = next((r.get("pickup_scan_closed_at") for r in rows if r.get("pickup_scan_closed_at")), None)
    reqs = []
    for i, r in enumerate(_ordered(rows)):
        usc = _unload_scans(r.get("id"))
        uref = _unload_reference(r, all_rows)
        uk = r.get("unload_scan_key")
        reqs.append({
            "id": r.get("id"), "request_number": r.get("request_number"),
            "drop_sequence": r.get("drop_sequence"), "drop_no": _drop_no(r, all_rows),
            "status_id": r.get("status_id"),
            "account_name": r.get("account_name") or "",
            "origin_port_name": r.get("origin_port_name") or "",
            "destination_port_name": r.get("destination_port_name") or "",
            "quantity": r.get("quantity"), "weight_kg": r.get("weight_kg"),
            "volume_cbm": r.get("volume_cbm"),
            "manifest_id_count": len(_manifest_ids_for(r.get("id"))),
            "arrived_pickup_datetime": to_gmt8(r.get("arrived_pickup_datetime")),
            "start_loading_datetime": to_gmt8(r.get("start_loading_datetime")),
            "end_loading_datetime": to_gmt8(r.get("end_loading_datetime")),
            "arrived_dest_datetime": to_gmt8(r.get("arrived_dest_datetime")),
            "start_unloading_datetime": to_gmt8(r.get("start_unloading_datetime")),
            "end_unloading_datetime": to_gmt8(r.get("end_unloading_datetime")),
            "late_reason": r.get("late_reason"),
            "pickup_scan_key": r.get("pickup_scan_key"),
            "unload_scan_key": uk,
            "unload_scan_closed": bool(r.get("unload_scan_closed_at")),
            "unload_scan_count": len(usc),
            "unload_expected_count": len(uref),
            "is_next_drop": i == 0,
            "attachments": db_q("SELECT id, original_filename, file_size FROM truck_request_attachments WHERE truck_request_id=%s",
                                (r.get("id"),)) if not LOCAL_MODE else
                           [row2d(a) for a in _store["attachments"] if a.get("truck_request_id") == r.get("id")],
        })
    fcs = [to_gmt8(r.get("final_call_datetime")) for r in rows if r.get("final_call_datetime")]
    return {"trip_id": base, "status_id": 3 if any(r.get("status_id") == 3 for r in rows) else 2,
            "final_call_datetime": min(fcs) if fcs else None,
            "driver": _driver_public(driver),
            "in_progress": _trip_started(rows),
            "total_drops": len(all_rows),
            "delivered_drops": sum(1 for r in all_rows if r.get("status_id") == 4),
            "pickup": {"key": pk,
                       "mode": "manifest" if expected else "free",
                       "expected_count": (len(expected) if expected else None),
                       "scanned_count": len(scans),
                       "closed": bool(closed), "closed_at": to_gmt8(closed)},
            "requests": reqs}

def _driver_active_rows(driver):
    if LOCAL_MODE:
        return [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                if r.get("driver_account_id") == driver.get("id")
                and r.get("status_id") in (2, 3)]
    return db_q(_SCAN_SELECT + " WHERE tr.driver_account_id=%s AND tr.status_id IN (2,3)",
                (driver.get("id"),))

def _busy_trip(driver, except_base=None):
    """The trip this driver has started but not finished, other than except_base."""
    groups = {}
    for r in _driver_active_rows(driver):
        groups.setdefault(_trip_key_of(r), []).append(r)
    for b, rs in groups.items():
        if b != except_base and _trip_started(rs):
            return b
    return None

def _set_active_trip(driver, base):
    if LOCAL_MODE:
        for d in _store["driver_accounts"]:
            if d["id"] == driver.get("id"):
                d["active_trip_id"] = base
        return
    db_x("UPDATE driver_accounts SET active_trip_id=%s,updated_at=NOW() WHERE id=%s",
         (base, driver.get("id")))

@app.get("/api/scan/trips")
def scan_trips(request: Request):
    driver = get_driver(request)
    rows = _driver_active_rows(driver)
    groups = {}
    for r in rows:
        groups.setdefault(_trip_key_of(r), []).append(r)
    out = [_trip_detail(driver, rs) for rs in groups.values()]
    out.sort(key=lambda g: (not g.get("in_progress"), str(g.get("final_call_datetime") or "9999-12-31")))
    busy = next((g["trip_id"] for g in out if g.get("in_progress")), None)
    for g in out:
        g["locked"] = bool(busy) and g["trip_id"] != busy
        g["locked_by"] = busy if g["locked"] else None
    return out

@app.post("/api/scan/trips/{base}/pickup-arrival")
async def scan_pickup_arrival(base: str, request: Request):
    driver = get_driver(request)
    body = await request.json() or {}
    rows = _driver_trip_rows(driver, base)
    if all(r.get("status_id") != 2 for r in rows):
        raise HTTPException(400, "This trip has already left")
    if _trip_started(rows):
        raise HTTPException(409, "Arrived at pickup is already recorded for this trip")
    busy = _busy_trip(driver, except_base=_scan_base(rows))
    if busy:
        raise HTTPException(409, f"Finish trip {busy} (every step up to the last drop) before starting another trip")
    fcs = [to_gmt8(r.get("final_call_datetime")) for r in rows if r.get("final_call_datetime")]
    fc = min(fcs) if fcs else None
    late = str(body.get("late_reason") or "").strip()
    if late:
        late = late[:LATE_REASON_MAX]
    if fc and nows() > fc and not late:
        raise HTTPException(409, {"code": "late_required",
                                  "detail": "This trip is past its Final Call time - record why the arrival is late",
                                  "final_call": fc})
    _set_milestones([r for r in rows if r.get("status_id") == 2], "arrived_pickup_datetime",
                    driver.get("username"))
    if late:
        for r in rows:
            _write_fields(r, {"late_reason": late}, driver.get("username"))
    _set_active_trip(driver, _scan_base(rows))
    return _trip_detail(driver, [r for r in _driver_trip_rows(driver, base)])

@app.post("/api/scan/trips/{base}/end-loading")
async def scan_end_loading(base: str, request: Request):
    driver = get_driver(request)
    rows = [r for r in _driver_trip_rows(driver, base) if r.get("status_id") == 2]
    if not rows:
        raise HTTPException(400, "This trip has already left")
    if not _trip_started(rows):
        raise HTTPException(400, "Complete Step 1 (Arrived at pickup) first")
    if not any(r.get("pickup_scan_closed_at") for r in rows):
        raise HTTPException(400, "Complete Step 2 (end the pickup scan) before End Loading")
    if all(r.get("end_loading_datetime") for r in rows):
        raise HTTPException(409, "End Loading is already recorded for this trip")
    _set_milestones(rows, "end_loading_datetime", driver.get("username"))
    return _trip_detail(driver, _driver_trip_rows(driver, base))

@app.post("/api/scan/trips/{base}/depart")
async def scan_depart(base: str, request: Request):
    driver = get_driver(request)
    rows = [r for r in _driver_trip_rows(driver, base) if r.get("status_id") == 2]
    if not rows:
        raise HTTPException(400, "This trip has already left")
    missing = [r for r in rows if not r.get("end_loading_datetime")]
    if missing:
        raise HTTPException(400, "Complete Step 3 (End Loading) before setting off")
    for r in rows:
        _write_fields(r, {"status_id": 3}, driver.get("username"))
    return _trip_detail(driver, _driver_trip_rows(driver, base))

@app.post("/api/scan/requests/{rid}/drop-arrival")
async def scan_drop_arrival(rid: int, request: Request):
    driver = get_driver(request)
    rows = _driver_trip_rows(driver, _trip_key_of(_scan_request_or_404(rid, driver)))
    target = next((r for r in rows if r.get("id") == rid), None)
    if not target:
        raise HTTPException(404, "This request is not on your trip")
    if target.get("status_id") not in (2, 3):
        raise HTTPException(400, "This drop is already finished")
    _check_drop_turn(rows, target)
    if target.get("arrived_dest_datetime"):
        raise HTTPException(409, "Arrived at destination is already recorded for this drop")
    _set_milestones([target], "arrived_dest_datetime", driver.get("username"))
    return _trip_detail(driver, _driver_trip_rows(driver, _trip_key_of(target)))

@app.post("/api/scan/requests/{rid}/start-unload")
async def scan_start_unload(rid: int, request: Request):
    driver = get_driver(request)
    rows = _driver_trip_rows(driver, _trip_key_of(_scan_request_or_404(rid, driver)))
    target = next((r for r in rows if r.get("id") == rid), None)
    if not target:
        raise HTTPException(404, "This request is not on your trip")
    if target.get("status_id") not in (2, 3):
        raise HTTPException(400, "This drop is already finished")
    if target.get("unload_scan_closed_at"):
        raise HTTPException(409, "Unloading has already been completed for this drop")
    _check_drop_turn(rows, target)
    if not target.get("arrived_dest_datetime"):
        raise HTTPException(400, "Tap Arrived at destination for this drop first")
    # Start Unloading is no longer stamped here: the first bag accepted by the
    # unloading scan records it. This only makes sure the scan link exists.
    if not target.get("unload_scan_key"):
        _write_fields(target, {"unload_scan_key": secrets.token_hex(16)},
                      driver.get("username"))
    return _trip_detail(driver, _driver_trip_rows(driver, _trip_key_of(target)))

@app.post("/api/scan/requests/{rid}/finish")
async def scan_finish(rid: int, request: Request):
    driver = get_driver(request)
    base_row = _scan_request_or_404(rid, driver)
    rows = _driver_trip_rows(driver, _trip_key_of(base_row))
    target = next((r for r in rows if r.get("id") == rid), None)
    if not target:
        raise HTTPException(404, "This request is not on your trip")
    if target.get("status_id") == 4:
        return {"ok": True, "status_id": 4}
    if target.get("status_id") not in (2, 3):
        raise HTTPException(400, "This drop is already finished")
    if target.get("end_unloading_datetime"):
        return {"ok": True, "status_id": target.get("status_id")}
    _check_drop_turn(rows, target)
    if not target.get("arrived_dest_datetime"):
        raise HTTPException(400, "Tap Arrived at destination for this drop first")
    if not target.get("unload_scan_closed_at"):
        raise HTTPException(400, "End the unloading scan for this drop before finishing it")
    now = nows()
    vals = {"end_unloading_datetime": now, "status_id": 4}
    if not target.get("start_unloading_datetime"):
        # Nothing was scanned at this drop, so no bag stamped Start Unloading.
        vals["start_unloading_datetime"] = now
    body = {f: target.get(f) for f in MILESTONE_FIELDS}
    body.update({k: v for k, v in vals.items() if k in MILESTONE_FIELDS})
    validate_delivered_chronology(body)
    _write_fields(target, vals, driver.get("username"))
    _finalize_delivered(target, driver.get("username"))
    left = [r for r in rows if r.get("id") != rid]
    if not left:
        _set_active_trip(driver, None)
    return {"ok": True, "status_id": 4, "trip_complete": not left}

def _check_drop_turn(rows, target):
    """Drops are worked strictly in drop # order, and only after Depart."""
    if target.get("status_id") != 3:
        raise HTTPException(400, "Complete Step 4 (Depart) before working on the drops")
    first = _ordered(rows)[0] if rows else None
    if first and first.get("id") != target.get("id"):
        full = _rows_for_base(_scan_base(rows)) or rows
        raise HTTPException(400, f"Finish drop {_drop_no(first, full)} ({first.get('request_number') or ''}) first - drops are done in order")

def _scan_request_or_404(rid, driver):
    if LOCAL_MODE:
        row = next((x for x in _store["truck_requests"] if x["id"] == rid), None)
        row = row2d(row)
    else:
        row = db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))
    if not row:
        raise HTTPException(404, "Request not found")
    if row.get("driver_account_id") != driver.get("id"):
        raise HTTPException(404, "This request is not assigned to your account")
    if not _owned_by_vendor(row, driver.get("vendor_id")):
        raise HTTPException(404, "Request not found")
    return row

def _finalize_delivered(row, email):
    """The bookkeeping update_request does when a request becomes Delivered."""
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] == row["id"]:
                if not r.get("actual_cost"):
                    r["actual_cost"] = r.get("estimated_cost", 0)
                tid = r.get("assigned_truck_id")
                if tid:
                    peers = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == tid]
                    _ensure_trip_id_before_terminal(r, peers)
                    archive_truck_requests(tid, email)
                    remaining = [x for x in _store["truck_requests"]
                                 if x.get("assigned_truck_id") == tid and x.get("status_id") not in (4, 5, 7)]
                    if not remaining:
                        for t in _store["trucks"]:
                            if t["id"] == tid:
                                t["status"] = "available"; break
                    else:
                        recalculate_trip_rates(tid)
                break
        return
    db_x("UPDATE truck_requests SET actual_cost=estimated_cost WHERE id=%s AND actual_cost=0", (row["id"],))
    tid = row.get("assigned_truck_id")
    if not tid:
        return
    cur = db_1("""SELECT id, request_number, status_id, drop_sequence, trip_id,
        account_id, assigned_truck_id FROM truck_requests WHERE id=%s""", (row["id"],))
    if cur and not cur.get("trip_id"):
        peers = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
            account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""", (tid,))
        _ensure_trip_id_before_terminal(cur, peers)
        if cur.get("trip_id"):
            db_x("UPDATE truck_requests SET trip_id=%s WHERE id=%s AND trip_id IS NULL",
                 (cur["trip_id"], row["id"]))
    archive_truck_requests(tid, email)
    remaining = db_1("SELECT COUNT(*) as c FROM truck_requests WHERE assigned_truck_id=%s AND status_id NOT IN (4,5,7)", (tid,))
    if remaining and remaining.get("c", 0) == 0:
        db_x("UPDATE trucks SET status='available' WHERE id=%s", (tid,))
    else:
        recalculate_trip_rates(tid)

# --- The public scan links (QR / barcode) ---------------------------------

@app.get("/api/scan/pickup/{key}")
def scan_pickup_get(key: str, ov: Optional[str] = None):
    rows = _rows_by_pickup_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    s = _scan_summary("pickup", rows, key)
    drv = _trip_driver(rows)
    s["override_available"] = bool(drv and drv.get("override_hash"))
    return s

@app.post("/api/scan/pickup/{key}")
async def scan_pickup_post(key: str, request: Request):
    body = await request.json() or {}
    rows = _rows_by_pickup_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    bag = str(body.get("bag_id") or "").strip()
    if not bag:
        raise HTTPException(400, "No bag ID was read")
    if len(bag) > 255:
        raise HTTPException(400, "Bag ID is too long")
    if any(r.get("pickup_scan_closed_at") for r in rows):
        raise HTTPException(409, "Pickup scanning has been closed for this trip")
    if not any(r.get("arrived_pickup_datetime") for r in rows):
        raise HTTPException(409, "Step 1 first: the driver must tap Arrived at pickup before bags can be scanned")
    base = _scan_base(rows)
    expected = _expected_pickup_ids(rows)
    exp_set = {str(x).lower() for x in expected}
    actor = _scan_actor(request)
    kind = "original"
    if exp_set and bag.lower() not in exp_set:
        # Already scanned (e.g. forced through earlier)? That is a duplicate, not unknown.
        if _scan_kind_of(_pickup_scans(base), bag):
            return {"result": "duplicate", "bag_id": bag,
                    "detail": "Bag ID already scanned on this trip",
                    **_scan_summary("pickup", rows, key)}
        code = str(body.get("ov") or "").strip()
        if not code:
            return {"result": "unknown", "bag_id": bag, "needs_override": True,
                    "detail": "Bag ID is not on this trip manifest",
                    **_scan_summary("pickup", rows, key)}
        err = _check_override(rows, key, code)
        if err:
            return {"result": "unknown", "bag_id": bag, "needs_override": True, "override_error": err,
                    "detail": err, **_scan_summary("pickup", rows, key)}
        kind = "override"
    owner = next((r for r in rows
                  if str(bag).lower() in {str(m).lower() for m in _manifest_ids_for(r.get("id"))}), None)
    if owner is None and len(rows) == 1:
        owner = rows[0]
    ok = _record_scan("scan_pickup",
                      {"bag_id": bag, "scan_kind": kind, "scanned_by": actor},
                      trip_base_val=base, rid=(owner or {}).get("id"), bag=bag)
    if not ok:
        return {"result": "duplicate", "bag_id": bag,
                "detail": "Bag ID already scanned on this trip",
                **_scan_summary("pickup", rows, key)}
    for r in rows:
        if not r.get("start_loading_datetime"):
            _set_milestones([r], "start_loading_datetime", actor)
    return {"result": "success", "bag_id": bag, "scan_kind": kind,
            "request_id": (owner or {}).get("id"),
            "drop": _drop_info(owner, rows) if owner else None,
            **_scan_summary("pickup", rows, key)}

@app.post("/api/scan/pickup/{key}/end")
async def scan_pickup_end(key: str, request: Request):
    body = await request.json() or {}
    rows = _rows_by_pickup_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    if not _may_close(request, body, key):
        raise HTTPException(403, "Ending the pickup scan needs the driver's override code (or the driver signed in on this phone)")
    if any(r.get("pickup_scan_closed_at") for r in rows):
        return _scan_summary("pickup", rows, key)
    now = nows()
    for r in rows:
        _write_fields(r, {"pickup_scan_closed_at": now})
    return _scan_summary("pickup", rows, key)

@app.get("/api/scan/unload/{key}")
def scan_unload_get(key: str, ov: Optional[str] = None):
    rows = _rows_by_unload_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    return _scan_summary("unload", rows, key)

@app.post("/api/scan/unload/{key}")
async def scan_unload_post(key: str, request: Request):
    body = await request.json() or {}
    rows = _rows_by_unload_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    row = rows[0]
    rid = row.get("id")
    bag = str(body.get("bag_id") or "").strip()
    if not bag:
        raise HTTPException(400, "No bag ID was read")
    if len(bag) > 255:
        raise HTTPException(400, "Bag ID is too long")
    if row.get("unload_scan_closed_at"):
        raise HTTPException(409, "Unloading has already been completed for this drop")
    if not row.get("arrived_dest_datetime"):
        raise HTTPException(409, "The driver must tap Arrived at destination for this drop before unloading")
    trip_rows = _rows_for_base(_scan_base(rows)) or rows
    here = _drop_info(row, trip_rows)
    actor = _scan_actor(request)
    # A bag already unloaded here is a duplicate: reported, never recorded again.
    if _scan_kind_of(_unload_scans(rid), bag):
        return {"result": "duplicate", "bag_id": bag, "drop": here,
                "detail": "Bag ID already scanned at this drop",
                **_scan_summary("unload", rows, key, trip_rows)}
    ref_list = _unload_reference(row, trip_rows)
    ref = {str(x).lower() for x in ref_list}
    kind = "original"
    # Record the bag exactly as it was picked up (same letters/case).
    bag = next((str(x) for x in ref_list if str(x).lower() == bag.lower()), bag)
    if bag.lower() not in ref:
        pick = _pickup_scan_row(bag, _scan_base(trip_rows))
        if pick and (pick.get("scan_kind") or "") == "override" and not pick.get("request_id"):
            # A bag forced through at pickup belongs to no drop: it may be unloaded at
            # whichever drop it turns up at - but only once on the whole trip.
            where = next((r for r in _ordered(trip_rows)
                          if r.get("id") != rid and _scan_kind_of(_unload_scans(r.get("id")), bag)), None)
            if where:
                return {"result": "duplicate", "bag_id": bag, "drop": _drop_info(where, trip_rows),
                        "detail": f"Override bag already unloaded at drop {_drop_no(where, trip_rows)}",
                        **_scan_summary("unload", rows, key, trip_rows)}
            kind = "override"
            bag = str(pick.get("bag_id") or bag)
    if bag.lower() not in ref and kind != "override":
        owner, picked = _pickup_owner(bag, trip_rows)
        if owner and owner.get("id") != rid:
            why = (f"Bag ID belongs to drop {_drop_no(owner, trip_rows)} "
                   f"({owner.get('account_name') or ''} - {owner.get('destination_port_name') or ''}), not this drop")
        elif picked:
            why = "Bag ID was pickup-scanned but is not tied to this drop"
        else:
            why = "Bag ID was not pickup-scanned on this trip"
        return {"result": "failed", "bag_id": bag, "drop": None,
                "other_drop": _drop_info(owner, trip_rows) if owner and owner.get("id") != rid else None,
                "detail": why, **_scan_summary("unload", rows, key, trip_rows)}
    ok = _record_scan("scan_unload",
                      {"bag_id": bag, "scan_kind": kind, "scanned_by": actor},
                      rid=rid, bag=bag)
    if not ok:
        return {"result": "duplicate", "bag_id": bag, "drop": here,
                "detail": "Bag ID already scanned at this drop",
                **_scan_summary("unload", rows, key, trip_rows)}
    if not row.get("start_unloading_datetime"):
        # The first accepted bag is what records Start Unloading.
        _set_milestones([row], "start_unloading_datetime", actor)
    return {"result": "success", "bag_id": bag, "scan_kind": kind, "drop": here,
            **_scan_summary("unload", rows, key, trip_rows)}

@app.post("/api/scan/unload/{key}/end")
async def scan_unload_end(key: str, request: Request):
    rows = _rows_by_unload_key(key)
    if not rows:
        raise HTTPException(404, "This scan link is not valid any more")
    if rows[0].get("unload_scan_closed_at"):
        return _scan_summary("unload", rows, key)
    if not rows[0].get("arrived_dest_datetime"):
        raise HTTPException(409, "The driver must tap Arrived at destination for this drop first")
    # Anyone on the unloading screen may end it: the scan link is the permission.
    _write_fields(rows[0], {"unload_scan_closed_at": nows()})
    return _scan_summary("unload", _rows_by_unload_key(key), key)

OVERRIDE_MAX_FAILS = 8          # wrong codes allowed per scan session...
OVERRIDE_LOCK_SECONDS = 900     # ...within this window before overrides are paused
_OV_FAILS = {}

def _trip_driver(rows):
    did = next((r.get("driver_account_id") for r in rows if r.get("driver_account_id")), None)
    return _driver_row(did) if did else None

def _pickup_scan_row(bag, base):
    k = str(bag).lower()
    return next((x for x in _pickup_scans(base) if str(x.get("bag_id") or "").lower() == k), None)

def _check_override(rows, key, code):
    """None when `code` is the trip driver's override code, else a message."""
    now = time.time()
    fails = [t for t in _OV_FAILS.get(key, []) if now - t < OVERRIDE_LOCK_SECONDS]
    _OV_FAILS[key] = fails
    if len(fails) >= OVERRIDE_MAX_FAILS:
        return "Too many wrong override codes - try again in 15 minutes"
    drv = _trip_driver(rows)
    if not drv or not drv.get("override_hash"):
        return ("No override code is set for this trip's driver / fleet account - "
                "set one on the Driver / Fleet Accounts page")
    if _pw_ok(code, drv.get("override_hash"), drv.get("override_salt")):
        _OV_FAILS.pop(key, None)
        return None
    fails.append(now)
    _OV_FAILS[key] = fails
    return "Wrong override code"

def _ov_ok(body, key, rows=None):
    code = str(body.get("ov") or "").strip()
    if not code:
        return False
    rows = rows if rows is not None else _rows_by_pickup_key(key)
    return bool(rows) and _check_override(rows, key, code) is None

def _may_close(request, body, key):
    if _ov_ok(body, key):
        return True
    tok = (request.headers.get("X-Scan-Token") or "").strip()
    if not tok:
        return False
    try:
        get_driver(request)
        return True
    except HTTPException:
        return False

@app.post("/api/scan/requests/{rid}/photo")
async def scan_photo(rid: int, request: Request, file: UploadFile = File(...)):
    driver = get_driver(request)
    row = _scan_request_or_404(rid, driver)
    existing = ([a for a in _store["attachments"] if a.get("truck_request_id") == rid] if LOCAL_MODE
                else db_q("SELECT * FROM truck_request_attachments WHERE truck_request_id=%s", (rid,)))
    if len(existing) >= 8:
        raise HTTPException(400, "Max 8 attachments")
    content = await file.read()
    if sum(a.get("file_size", 0) for a in existing) + len(content) > 25 * 1024 * 1024:
        raise HTTPException(400, "Max 25MB total")
    if not content:
        raise HTTPException(400, "The uploaded file is empty")
    fid = uuid.uuid4().hex
    raw_ext = os.path.splitext(file.filename or "")[1].lower()
    ext = raw_ext if (len(raw_ext) <= 9 and raw_ext.startswith(".") and raw_ext[1:].isalnum()) else ".jpg"
    fn = f"{fid}{ext}"
    ctype = _att_content_type(file.content_type)
    fp = await _save_att_bytes(rid, fn, content, ctype)
    if LOCAL_MODE:
        att = {"id": nid("attachments"), "truck_request_id": rid, "filename": fn,
               "original_filename": file.filename or "photo.jpg", "file_size": len(content),
               "file_type": ctype, "storage_path": fp, "uploaded_by": driver.get("username") or "driver",
               "created_at": nows()}
        _store["attachments"].append(att)
        return row2d(att)
    aid = db_i("""INSERT INTO truck_request_attachments (truck_request_id,filename,original_filename,
        file_size,file_type,storage_path,uploaded_by) VALUES (%s,%s,%s,%s,%s,%s,%s)""",
        (rid, fn, file.filename or "photo.jpg", len(content), ctype, fp, driver.get("username") or "driver"))
    return db_1("SELECT * FROM truck_request_attachments WHERE id=%s", (aid,))

# --- Assigning a driver to a trip -----------------------------------------

def _trip_assign_rows(trip_id, vid=None):
    if trip_id.startswith("req-"):
        try:
            rid = int(trip_id[4:])
        except ValueError:
            raise HTTPException(404, "No active requests for this trip")
        rows = ([_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                 if r["id"] == rid and r.get("status_id") == 2] if LOCAL_MODE
                else db_q(_SCAN_SELECT + " WHERE tr.id=%s AND tr.status_id=2", (rid,)))
    else:
        want = trip_base(trip_id)
        if LOCAL_MODE:
            rows = [_scan_row_names(row2d(r)) for r in _store["truck_requests"]
                    if r.get("status_id") == 2 and r.get("trip_id")
                    and trip_base(r["trip_id"]) == want]
        else:
            allr = db_q(_SCAN_SELECT + " WHERE tr.status_id=2 AND tr.trip_id IS NOT NULL", ())
            rows = [r for r in allr if trip_base(r.get("trip_id")) == want]
    if vid is not None:
        rows = [r for r in rows if _owned_by_vendor(r, vid)]
    if not rows:
        raise HTTPException(404, "No active requests for this trip")
    return rows

@app.post("/api/trips/{trip_id}/assign-driver")
async def assign_trip_driver(trip_id: str, request: Request):
    u, vid = require_vendor_or_admin(request)
    body = await request.json()
    did = body.get("driver_account_id")
    if not did:
        raise HTTPException(400, "driver_account_id required")
    try:
        did = int(did)
    except (TypeError, ValueError):
        raise HTTPException(400, "driver_account_id must be a number")
    d = _driver_row(did)
    if not d or not d.get("is_active", 1):
        raise HTTPException(404, "Driver account not found or not active")
    if vid is not None and d.get("vendor_id") != vid:
        raise HTTPException(403, "That driver account belongs to another vendor")
    rows = _trip_assign_rows(trip_id, vid)
    for r in rows:
        if not _owned_by_vendor(r, d.get("vendor_id")):
            raise HTTPException(403, "That driver account belongs to a different vendor than this trip")
    tid = d.get("truck_id")
    if not tid:
        raise HTTPException(400, "This driver / fleet account has no truck - set one on the Driver / Fleet Accounts page first")
    base = _scan_base(rows)
    _assign_truck_core(u, vid, trip_id, tid, keep_status=True)
    rows = _trip_assign_rows(trip_id, vid)
    pk = next((r.get("pickup_scan_key") for r in rows if r.get("pickup_scan_key")), None) \
        or secrets.token_hex(16)
    for r in rows:
        vals = {"driver_account_id": did}
        if not r.get("pickup_scan_key"):
            vals["pickup_scan_key"] = pk
        if not r.get("unload_scan_key"):
            vals["unload_scan_key"] = secrets.token_hex(16)
        _write_fields(r, vals, u.get("email", ""))
    return {"ok": True, "trip_id": base, "assigned": len(rows),
            "driver_account_id": did, "truck_id": tid,
            "plate_number": _truck_plate(tid), "status_id": 2,
            "pickup_scan_key": pk}

def _restore_drop_order(ordered_ids):
    """Number a freed trip's requests 1..n in their previous order."""
    def _relettered(tid, seq):
        # Keep the trip letter in step with the drop number ('X-00086-D' -> 'X-00086-A').
        if not tid:
            return tid
        base = trip_base(tid)
        return f"{base}-{_trip_letter(seq)}" if base and base != tid else tid
    for i, rid in enumerate(ordered_ids):
        if LOCAL_MODE:
            for x in _store["truck_requests"]:
                if x["id"] == rid:
                    x["drop_sequence"] = i + 1
                    x["trip_id"] = _relettered(x.get("trip_id"), i + 1)
                    break
        else:
            cur = db_1("SELECT trip_id FROM truck_requests WHERE id=%s", (rid,)) or {}
            db_x("UPDATE truck_requests SET drop_sequence=%s, trip_id=%s WHERE id=%s",
                 (i + 1, _relettered(cur.get("trip_id"), i + 1), rid))

@app.post("/api/requests/{rid}/unassign-driver")
async def unassign_driver(rid: int, request: Request):
    vid, u = vendor_scope(request)
    if vid is None and u.get("role") != "master_admin":
        raise HTTPException(403, "Only Master Admin or a vendor can remove a driver")
    if LOCAL_MODE:
        row = row2d(next((x for x in _store["truck_requests"] if x["id"] == rid), None))
    else:
        row = db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))
    if not row:
        raise HTTPException(404, "Request not found")
    if vid is not None and not _owned_by_vendor(row, vid):
        raise HTTPException(404, "That request is not on your vendor")
    if row.get("status_id") != 2:
        raise HTTPException(400, "A driver can only be removed while the trip is Allocated")
    base = _trip_key_of(row)
    rows = [r for r in _rows_for_base(base) if r.get("status_id") == 2] or [row]
    clears = {k: None for k in ("driver_account_id", "late_reason", "pickup_scan_key",
                                "pickup_scan_closed_at", "unload_scan_key",
                                "unload_scan_closed_at") + tuple(MILESTONE_FIELDS)}
    for r in rows:
        _write_fields(r, clears, u.get("email", ""))
    rids = [r.get("id") for r in rows]
    # Remember the trip's own drop order before the truck comes off: freeing the
    # truck blanks drop_sequence, but the trip keeps its drops (1, 2, 3...) so it
    # goes back on the assignment list exactly as it was.
    order = [r.get("id") for r in sorted(rows, key=lambda x: (x.get("drop_sequence") is None,
                                                              x.get("drop_sequence") or 0,
                                                              x.get("id")))]
    freed = _free_truck_assignment(rids, u.get("email", ""))
    _restore_drop_order(order)
    if LOCAL_MODE:
        _store["scan_pickup"] = [s for s in _store["scan_pickup"] if s.get("trip_base") != base]
        _store["scan_unload"] = [s for s in _store["scan_unload"] if s.get("request_id") not in rids]
        for d in _store["driver_accounts"]:
            if d.get("active_trip_id") == base:
                d["active_trip_id"] = None
    else:
        db_x("DELETE FROM scan_pickup_items WHERE trip_base=%s", (base,))
        if rids:
            db_x("DELETE FROM scan_unload_items WHERE request_id IN (%s)" % ",".join(["%s"] * len(rids)),
                 tuple(rids))
        db_x("UPDATE driver_accounts SET active_trip_id=NULL,updated_at=NOW() WHERE active_trip_id=%s",
             (base,))
    return {"ok": True, "trip_id": base, "cleared": len(rows),
            "trucks_freed": len(freed)}

# --- Scan CSV downloads ----------------------------------------------------

@app.get("/api/trips/{base}/pickup-scan/download")
def download_pickup_scan(base: str, request: Request):
    scope_vid, _ = vendor_scope(request)
    rows = _rows_for_base(base)
    if not rows:
        raise HTTPException(404, "Not found")
    if scope_vid is not None:
        rows = [r for r in rows if _owned_by_vendor(r, scope_vid)]
        if not rows:
            raise HTTPException(404, "Not found")
    if not any(r.get("pickup_scan_closed_at") for r in rows):
        raise HTTPException(409, "Pickup scanning is still open for this trip - end scanning first")
    scans = _pickup_scans(_scan_base(rows))
    expected = _expected_pickup_ids(rows)
    label = str(base)
    return _scan_csv(rows, scans, expected, f"{label}-pickup")

@app.get("/api/requests/{rid}/unload-scan/download")
def download_unload_scan(rid: int, request: Request):
    scope_vid, _ = vendor_scope(request)
    if LOCAL_MODE:
        row = row2d(next((x for x in _store["truck_requests"] if x["id"] == rid), None))
    else:
        row = db_1("SELECT * FROM truck_requests WHERE id=%s", (rid,))
    if not row:
        raise HTTPException(404, "Not found")
    if scope_vid is not None and not _owned_by_vendor(row, scope_vid):
        raise HTTPException(404, "Not found")
    if not row.get("unload_scan_closed_at"):
        raise HTTPException(409, "Unloading is still open for this drop - end scanning first")
    trip_rows = _rows_for_base(_scan_base([row])) or [row]
    scans = _unload_scans(rid)
    ref = _unload_reference(row, trip_rows)
    label = str(row.get("request_number") or f"request-{rid}")
    return _scan_csv([_scan_row_names(row) if LOCAL_MODE else
                      (db_1(_SCAN_SELECT + " WHERE tr.id=%s", (rid,)) or row)],
                     scans, ref, f"{label}-unloading")

# ---------------------------------------------------------------------------
# Vendor Rates
# ---------------------------------------------------------------------------

@app.get("/api/vendor-rates")
def list_rates(request: Request, vendor_name: Optional[str] = None, origin_port_id: Optional[int] = None, destination_port_id: Optional[int] = None):
    require_page_unlock(request, "rates")
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

def _clean_pct(body, key):
    if key not in body:
        return
    v = body.get(key)
    if v is None or str(v).strip() == "":
        body[key] = None
        return
    try:
        f = float(v)
    except (TypeError, ValueError):
        raise HTTPException(400, f"{key} must be a number")
    if f < 0 or f > 100:
        raise HTTPException(400, f"{key} must be between 0 and 100")
    body[key] = round(f, 2)

def _check_rate_drops(main_dest, drops):
    """Additional Destination Drops must differ from the Main Destination and from each other."""
    if isinstance(drops, str):
        try: drops = json.loads(drops)
        except Exception: drops = []
    seen = set()
    for d in drops or []:
        pid = d.get("port_id") if isinstance(d, dict) else None
        if pid in (None, ""):
            continue
        try: pid = int(pid)
        except (TypeError, ValueError): raise HTTPException(400, "Invalid Additional Destination Drop location")
        if main_dest not in (None, "") and pid == int(main_dest):
            raise HTTPException(400, "An Additional Destination Drop location cannot be the same as the Main Destination")
        if pid in seen:
            raise HTTPException(400, "The same Additional Destination Drop location is listed twice")
        seen.add(pid)

@app.post("/api/vendor-rates")
async def create_rate(request: Request):
    require_page_unlock(request, "rates")
    require_admin(request)
    body = await request.json()
    for f in ("vendor_name", "truck_type_id", "origin_port_id", "destination_port_id", "effective_date"):
        if not body.get(f): raise HTTPException(400, f"{f} required")
    _check_rate_drops(body.get("destination_port_id"), body.get("destination_drops"))
    _clean_pct(body, "foul_trip_pct")
    _clean_pct(body, "fuel_surcharge_pct")
    if LOCAL_MODE:
        rid = nid("vendor_rates")
        rate = {"id": rid, "vendor_name": body["vendor_name"], "vendor_id": body.get("vendor_id"),
            "truck_type_id": body["truck_type_id"],
            "origin_port_id": body["origin_port_id"], "destination_port_id": body["destination_port_id"],
            "rate_per_trip": body.get("rate_per_trip", 0),
            "destination_drops": body.get("destination_drops", []),
            "default_rate": body.get("default_rate", 0),
            "foul_trip_pct": body.get("foul_trip_pct"),
            "fuel_surcharge_pct": body.get("fuel_surcharge_pct"),
            "effective_date": body["effective_date"],
            "expiry_date": body.get("expiry_date"), "is_active": True, "created_at": nows(), "updated_at": nows()}
        _store["vendor_rates"].append(rate)
        backfill_rate_estimated_costs(body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"])
        return row2d(rate)
    rid = db_i("""INSERT INTO vendor_rates (vendor_name,vendor_id,truck_type_id,origin_port_id,destination_port_id,
        rate_per_trip,default_rate,destination_drops,foul_trip_pct,fuel_surcharge_pct,effective_date,expiry_date)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)""",
        (body["vendor_name"], body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"], body["destination_port_id"],
         body.get("rate_per_trip", 0), body.get("default_rate", 0),
         json.dumps(body.get("destination_drops", [])) if body.get("destination_drops") else None,
         body.get("foul_trip_pct"), body.get("fuel_surcharge_pct"),
         body["effective_date"], body.get("expiry_date")))
    backfill_rate_estimated_costs(body.get("vendor_id"), body["truck_type_id"], body["origin_port_id"])
    return db_1("SELECT * FROM vendor_rates WHERE id=%s", (rid,))

@app.put("/api/vendor-rates/{rid}")
async def update_rate(rid: int, request: Request):
    require_page_unlock(request, "rates")
    require_admin(request)
    body = await request.json()
    if "destination_drops" in body or "destination_port_id" in body:
        cur = (next((r for r in _store["vendor_rates"] if r["id"] == rid), None) if LOCAL_MODE
               else db_1("SELECT destination_port_id, destination_drops FROM vendor_rates WHERE id=%s", (rid,)))
        if not cur: raise HTTPException(404, "Not found")
        _check_rate_drops(body.get("destination_port_id", cur.get("destination_port_id")),
                          body.get("destination_drops", cur.get("destination_drops")))
    _clean_pct(body, "foul_trip_pct")
    _clean_pct(body, "fuel_surcharge_pct")
    if LOCAL_MODE:
        for r in _store["vendor_rates"]:
            if r["id"] == rid:
                for k in ("vendor_name", "vendor_id", "truck_type_id", "origin_port_id", "destination_port_id", "rate_per_trip", "destination_drops", "default_rate", "foul_trip_pct", "fuel_surcharge_pct", "effective_date", "expiry_date", "is_active"):
                    if k in body: r[k] = body[k]
                r["updated_at"] = nows()
                backfill_rate_estimated_costs(r.get("vendor_id"), r.get("truck_type_id"), r.get("origin_port_id"))
                return row2d(r)
        raise HTTPException(404, "Not found")
    sets, params = [], []
    for k in ("vendor_name", "vendor_id", "truck_type_id", "origin_port_id", "destination_port_id", "rate_per_trip", "destination_drops", "default_rate", "foul_trip_pct", "fuel_surcharge_pct", "effective_date", "expiry_date", "is_active"):
        if k in body:
            val = body[k]
            if k == "destination_drops" and isinstance(val, list):
                val = json.dumps(val)
            sets.append(f"{k}=%s")
            params.append(val)
    if not sets: raise HTTPException(400, "Nothing to update")
    params.append(rid)
    db_x(f"UPDATE vendor_rates SET {','.join(sets)} WHERE id=%s", tuple(params))
    updated_rate = db_1("SELECT * FROM vendor_rates WHERE id=%s", (rid,))
    if updated_rate:
        backfill_rate_estimated_costs(updated_rate.get("vendor_id"), updated_rate.get("truck_type_id"), updated_rate.get("origin_port_id"))
    return updated_rate

@app.delete("/api/vendor-rates/{rid}")
def delete_rate(rid: int, request: Request):
    require_page_unlock(request, "rates")
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
    account_id: Optional[int] = None, department_id: Optional[int] = None,
    mawb: Optional[str] = None, plate: Optional[str] = None):
    require_page_unlock(request, "evaluation")
    get_user(request)
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        results = []
        for r in reqs:
            if r.get("status_id") != 4: continue
            if not r.get("assigned_truck_id"): continue
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            if not truck: continue
            if mawb:
                m = mawb.lower()
                if m not in ((r.get("international_mawb") or "") + " " + (r.get("domestic_mawb") or "")).lower(): continue
            if vendor_id and truck.get("vendor_id") != vendor_id: continue
            if plate and plate.lower() not in (truck.get("plate_number") or "").lower(): continue
            if truck_type_id and truck.get("truck_type_id") != truck_type_id and r.get("truck_type_id") != truck_type_id: continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if destination_port_id and r.get("destination_port_id") != destination_port_id: continue
            if account_id and r.get("account_id") != account_id: continue
            if department_id and r.get("department_id") != department_id: continue
            fc = str(r.get("final_call_datetime") or "")[:10]
            if date_from and fc < date_from: continue
            if date_to and fc > date_to: continue
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
                trip_id = resolve_trip_id(r, truck_reqs)
            sn = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            sc = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")
            results.append({"id": r["id"], "request_number": r.get("request_number", ""),
                "trip_id": trip_id, "drop_sequence": r.get("drop_sequence"),
                "international_mawb": r.get("international_mawb") or "",
                "domestic_mawb": r.get("domestic_mawb") or "",
                "account_name": acct_name, "department_name": dept_name,
                "origin_port_name": oname, "destination_port_name": dname,
                "truck_type_name": ttn, "plate_number": truck.get("plate_number") or "", "vendor_name": vname,
                "booking_date": r.get("booking_date"), "status_name": sn, "status_color": sc,
                "pickup_datetime": r.get("pickup_datetime"),
                "call_datetime": r.get("call_datetime"),
                "final_call_datetime": r.get("final_call_datetime"),
                "end_unloading_datetime": r.get("end_unloading_datetime"),
                "delivered_date": (r.get("end_unloading_datetime") or "")[:10],
                "lt_customs_to_arrival": _fmt_duration(r.get("customs_cleared_datetime"), r.get("arrived_pickup_datetime")),
                "lt_pickup_to_arrival": _fmt_duration(r.get("call_datetime"), r.get("arrived_pickup_datetime")),
                "lt_arrival_to_start_load": _fmt_duration(r.get("arrived_pickup_datetime"), r.get("start_loading_datetime")),
                "lt_start_load_to_end_load": _fmt_duration(r.get("start_loading_datetime"), r.get("end_loading_datetime")),
                "lt_end_load_to_arrived_dest": _fmt_duration(r.get("end_loading_datetime"), r.get("arrived_dest_datetime")),
                "lt_arrived_dest_to_start_unload": _fmt_duration(r.get("arrived_dest_datetime"), r.get("start_unloading_datetime")),
                "lt_start_unload_to_end_unload": _fmt_duration(r.get("start_unloading_datetime"), r.get("end_unloading_datetime")),
                "lt_full_leg": _fmt_duration(r.get("arrived_pickup_datetime"), r.get("end_unloading_datetime")),
            })
        coords = get_port_coords_map()
        add_distances_to_requests(results, coords)
        return results
    wh = ["tr.assigned_truck_id IS NOT NULL", "tr.status_id = 4"]
    pa = []
    if vendor_id: wh.append("tk.vendor_id=%s"); pa.append(vendor_id)
    if truck_type_id: wh.append("(tr.truck_type_id=%s OR tk.truck_type_id=%s)"); pa.extend([truck_type_id, truck_type_id])
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if mawb: wh.append("(tr.international_mawb LIKE %s OR tr.domestic_mawb LIKE %s)"); pa.extend([f"%{mawb}%", f"%{mawb}%"])
    if plate: wh.append("tk.plate_number LIKE %s"); pa.append(f"%{plate}%")
    if search: wh.append("tr.request_number LIKE %s"); pa.append(f"%{search}%")
    if date_from: wh.append("DATE(tr.final_call_datetime)>=%s"); pa.append(date_from)
    if date_to: wh.append("DATE(tr.final_call_datetime)<=%s"); pa.append(date_to)
    ws = " AND ".join(wh)
    rows = db_q(f"""SELECT tr.id, tr.request_number, tr.drop_sequence, tr.booking_date, tr.pickup_datetime, tr.call_datetime,
        tr.final_call_datetime, tr.trip_id,
        tr.international_mawb, tr.domestic_mawb,
        tr.status_id, ts.name as status_name, ts.color as status_color,
        a.name as account_name, d.name as department_name,
        po.name as origin_port_name, pd.name as destination_port_name,
        COALESCE(tt.name, ttt.name) as truck_type_name, tk.plate_number, v.name as vendor_name,
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
            truck_reqs = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (row["assigned_truck_id"],))
            row["trip_id"] = resolve_trip_id(row, truck_reqs)
        else:
            row["trip_id"] = row.get("trip_id") or None
        row["lt_customs_to_arrival"] = _fmt_duration(row.get("customs_cleared_datetime"), row.get("arrived_pickup_datetime"))
        row["lt_pickup_to_arrival"] = _fmt_duration(row.get("call_datetime"), row.get("arrived_pickup_datetime"))
        row["lt_arrival_to_start_load"] = _fmt_duration(row.get("arrived_pickup_datetime"), row.get("start_loading_datetime"))
        row["lt_start_load_to_end_load"] = _fmt_duration(row.get("start_loading_datetime"), row.get("end_loading_datetime"))
        row["lt_end_load_to_arrived_dest"] = _fmt_duration(row.get("end_loading_datetime"), row.get("arrived_dest_datetime"))
        row["lt_arrived_dest_to_start_unload"] = _fmt_duration(row.get("arrived_dest_datetime"), row.get("start_unloading_datetime"))
        row["lt_start_unload_to_end_unload"] = _fmt_duration(row.get("start_unloading_datetime"), row.get("end_unloading_datetime"))
        row["lt_full_leg"] = _fmt_duration(row.get("arrived_pickup_datetime"), row.get("end_unloading_datetime"))
        row["delivered_date"] = (row.get("end_unloading_datetime") or "")[:10]
    coords = get_port_coords_map()
    add_distances_to_requests(rows, coords)
    return rows

@app.post("/api/vendor-evaluations")
async def create_eval(request: Request):
    require_page_unlock(request, "evaluation")
    return {"ok": True}

@app.delete("/api/vendor-evaluations/{eid}")
def delete_eval(eid: int, request: Request):
    require_page_unlock(request, "evaluation")
    return {"ok": True}

# ---------------------------------------------------------------------------
# Cost Summary
# ---------------------------------------------------------------------------

def sync_request_price(r, vendor_id, truck_type_id, pcache=None, ccache=None):
    """Price a Delivered / Foul Trip request from its rate card and keep the stored figures
    in line with it. Returns (card, amount, basis).

    - Estimated Cost always follows the rate card.
    - Delivered: Actual Cost follows the rate card while it is still the automatic figure
      (blank or equal to the old Estimated Cost); a hand-entered Actual Cost is kept.
    - Foul Trip: no Actual Cost - it is charged through the Foul Trip Cost instead."""
    card, price, basis = price_request(r, vendor_id, truck_type_id, trip_primary_dest(r, pcache), ccache)
    est = float(r.get("estimated_cost") or 0)
    act = float(r.get("actual_cost") or 0)
    st = r.get("status_id")
    new_est, new_act = est, act
    if card:
        new_est = price
        if st == 4 and (not act or abs(act - est) < 0.005):
            new_act = price
    if st == 7:
        new_act = 0
    if (new_est, new_act) != (est, act):
        r["estimated_cost"], r["actual_cost"] = new_est, new_act
        if not LOCAL_MODE and r.get("id"):
            db_x("UPDATE truck_requests SET estimated_cost=%s, actual_cost=%s WHERE id=%s", (new_est, new_act, r["id"]))
    return card, (price if card else est), basis

def total_cost_of(row, foul_cost=None, fuel_cost=None):
    """Total Cost on Cost Analysis.

    Actual Cost + Toll Fee + Management Fee + Fuel + Parking + Miscellaneous + Manpower
    + Toll + Welfare + WH Rental + Toll Fee (Easytrip) + Toll Fee (Autosweep)
    + Foul Trip Cost + Fuel Surcharge Cost.
    """
    if foul_cost is None:
        foul_cost = row.get("foul_trip_cost") or 0
    if fuel_cost is None:
        fuel_cost = row.get("fuel_surcharge_cost") or 0
    base = (row.get("actual_cost") or 0) + sum(row.get(f) or 0 for f in BULK_COST_FIELDS)
    return round(base + foul_cost + fuel_cost, 2)

def foul_fuel_costs(rate_match, base, status_id, foul_trip_count):
    """Rate-based additions shown on Cost Analysis. `base` is the request's own rate from
    its rate card (see pick_rate): Rate/Trip when its origin + destination match the card's
    Main Destination, otherwise its Additional Destination Drop rate or the Default Rate.

    Foul Trip Cost  = base x foul_trip_pct% x foul_trip_count (Foul Trip only)
    Fuel Surcharge  = base x fuel_surcharge_pct%            (Delivered + Foul Trip)
    """
    base = base or 0
    foul_pct = float(rate_match.get("foul_trip_pct") or 0) if rate_match else 0
    fuel_pct = float(rate_match.get("fuel_surcharge_pct") or 0) if rate_match else 0
    try:
        cnt = int(foul_trip_count or 0)
    except (TypeError, ValueError):
        cnt = 0
    if cnt not in (1, 2):
        cnt = 1
    foul_cost = round(base * foul_pct / 100 * cnt, 2) if status_id == 7 and foul_pct else 0
    fuel_cost = round(base * fuel_pct / 100, 2) if status_id in (4, 7) and fuel_pct else 0
    return foul_cost, fuel_cost

def cost_summary_stats(rows):
    """Expanded Cost Analysis headline numbers (rows are the filtered requests)."""
    est = round(sum(r.get("estimated_cost") or 0 for r in rows), 2)
    act = round(sum(r.get("actual_cost") or 0 for r in rows), 2)
    foul = round(sum(r.get("foul_trip_cost") or 0 for r in rows), 2)
    fuel = round(sum(r.get("fuel_surcharge_cost") or 0 for r in rows), 2)
    vend = {}
    for r in rows:
        name = (r.get("vendor_name") or "").strip() or "Unassigned"
        d = vend.setdefault(name, {"vendor_name": name, "requests": 0, "delivered": 0, "foul_trip": 0})
        d["requests"] += 1
        if r.get("status_id") == 4: d["delivered"] += 1
        if r.get("status_id") == 7: d["foul_trip"] += 1
    total = len(rows)
    vendor_summary = [dict(d, pct=(round(100.0 * d["requests"] / total, 1) if total else 0.0))
                      for d in vend.values()]
    vendor_summary.sort(key=lambda d: (-d["requests"], d["vendor_name"]))
    return {
        "total_requests": len(rows),
        "total_estimated_cost": est,
        "total_actual_cost": act,
        "delivered": sum(1 for r in rows if r.get("status_id") == 4),
        "foul_trip": sum(1 for r in rows if r.get("status_id") == 7),
        "total_foul_trip_cost": foul,
        "total_fuel_surcharge_cost": fuel,
        "total_cost": round(sum(total_cost_of(r) for r in rows), 2),
        "vendor_summary": vendor_summary,
    }

@app.get("/api/cost-summary")
def cost_summary(request: Request, date_from: str = Query(...), date_to: str = Query(...),
    account_id: Optional[int] = None, department_id: Optional[int] = None,
    origin_port_id: Optional[int] = None, destination_port_id: Optional[int] = None,
    vendor_id: Optional[int] = None, status_id: Optional[int] = None,
    mawb: Optional[str] = None):
    require_page_unlock(request, "cost")
    get_user(request)
    if LOCAL_MODE:
        reqs = _store["truck_requests"]
        flt = []
        for r in reqs:
            if account_id and r.get("account_id") != account_id: continue
            if department_id and r.get("department_id") != department_id: continue
            fc = str(r.get("final_call_datetime") or "")[:10]
            if not fc or fc < date_from or fc > date_to: continue
            if origin_port_id and r.get("origin_port_id") != origin_port_id: continue
            if destination_port_id and r.get("destination_port_id") != destination_port_id: continue
            # Cost Analysis covers Delivered + Foul Trip, and a Foul Trip only counts
            # once an admin has green-ticked it on the Foul Trip Approval page.
            if r.get("status_id") not in (4, 7): continue
            if r.get("status_id") == 7 and not (r.get("foul_trip_approved_by") or ""): continue
            if status_id and r.get("status_id") != status_id: continue
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            if vendor_id and (not truck or truck.get("vendor_id") != vendor_id): continue
            if mawb:
                m = mawb.lower()
                if m not in ((r.get("international_mawb") or "") + " " + (r.get("domestic_mawb") or "")).lower(): continue
            flt.append(r)
        req_list = []
        pcache, ccache = {}, {}
        for r in flt:
            sn = next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "Unknown")
            sc = next((s["color"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "#6B7280")
            truck = next((t for t in _store["trucks"] if t["id"] == r.get("assigned_truck_id")), None)
            tt_id = r.get("truck_type_id") or (truck.get("truck_type_id") if truck else None)
            ttn = next((t["name"] for t in _store["truck_types"] if t["id"] == tt_id), "")
            origin_name = next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), "")
            dest_name = next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")
            v_id = (truck.get("vendor_id") if truck else None) or r.get("vendor_id")
            vname = next((v["name"] for v in _store["vendors"] if v["id"] == v_id), "") if v_id else ""
            acct_name = next((a["name"] for a in _store["accounts"] if a["id"] == r.get("account_id")), "")
            dept_name = next((d["name"] for d in _store["departments"] if d["id"] == r.get("department_id")), "")
            v_rate = (truck.get("vendor_id") if truck else None) or r.get("vendor_id")
            rate_match, est, basis = sync_request_price(r, v_rate, tt_id, pcache, ccache)
            foul_cost, fuel_cost = foul_fuel_costs(rate_match, est, r.get("status_id"), r.get("foul_trip_count"))
            rd = {k: r.get(k) for k in ("id", "trip_id", "request_number", "quantity", "weight_kg", "volume_cbm",
                "pickup_datetime", "call_datetime", "final_call_datetime", "estimated_cost", "actual_cost", "assigned_truck_id", "status_id",
                "foul_trip_reason", "foul_trip_date", "foul_trip_count", "cancellation_date", "booking_date", "international_mawb", "domestic_mawb",
                "end_unloading_datetime", "toll_fee", "management_fee", "fuel", "parking", "miscellaneous", "manpower",
                "toll", "welfare", "wh_rental", "toll_fee_easytrip", "toll_fee_autosweep", "cost_updated_by",
                "cost_updated_at")}
            rd["cost_updated_at"] = to_gmt8(rd.get("cost_updated_at")) if rd.get("cost_updated_at") else None
            rd["delivered_date"] = (r.get("end_unloading_datetime") or "")[:10]
            rd["rate_basis"] = basis
            rd["rate_amount"] = est
            rd["foul_trip_cost"] = foul_cost
            rd["fuel_surcharge_cost"] = fuel_cost
            rd["total_cost"] = total_cost_of(rd, foul_cost, fuel_cost)
            cu = next((u for u in _store["users"] if u.get("email") == rd.get("cost_updated_by")), None)
            rd["cost_updated_by_name"] = cu.get("name", "") if cu else ""
            rd["cost_updated_by_email"] = rd.get("cost_updated_by") or ""
            rd["status_name"] = sn
            rd["status_color"] = sc
            rd["truck_type_name"] = ttn
            rd["origin_port_name"] = origin_name
            rd["destination_port_name"] = dest_name
            rd["vendor_name"] = vname
            rd["account_name"] = acct_name
            rd["department_name"] = dept_name
            if r.get("assigned_truck_id") and r.get("status_id") in (2, 3, 4, 5, 7):
                truck_reqs = [x for x in _store["truck_requests"] if x.get("assigned_truck_id") == r["assigned_truck_id"]]
                rd["trip_id"] = resolve_trip_id(r, truck_reqs)
            else:
                rd["trip_id"] = r.get("trip_id") or None
            req_list.append(rd)
        coords = get_port_coords_map()
        add_distances_to_requests(req_list, coords)
        return {**cost_summary_stats(req_list), "requests": req_list}
    wh = ["DATE(tr.final_call_datetime)>=%s", "DATE(tr.final_call_datetime)<=%s"]
    pa = [date_from, date_to]
    if account_id: wh.append("tr.account_id=%s"); pa.append(account_id)
    if department_id: wh.append("tr.department_id=%s"); pa.append(department_id)
    if origin_port_id: wh.append("tr.origin_port_id=%s"); pa.append(origin_port_id)
    if destination_port_id: wh.append("tr.destination_port_id=%s"); pa.append(destination_port_id)
    if vendor_id: wh.append("(tk.vendor_id=%s OR tr.vendor_id=%s)"); pa.extend([vendor_id, vendor_id])
    # Cost Analysis covers Delivered + Foul Trip, and a Foul Trip only counts
    # once an admin has green-ticked it on the Foul Trip Approval page.
    wh.append("tr.status_id IN (4,7)")
    wh.append("(tr.status_id<>7 OR (tr.foul_trip_approved_by IS NOT NULL AND tr.foul_trip_approved_by<>''))")
    if status_id: wh.append("tr.status_id=%s"); pa.append(status_id)
    if mawb: wh.append("(tr.international_mawb LIKE %s OR tr.domestic_mawb LIKE %s)"); pa.extend([f"%{mawb}%", f"%{mawb}%"])
    ws = " AND ".join(wh)
    reqs = db_q(f"""SELECT tr.*, ts.name as status_name, ts.color as status_color,
        COALESCE(tt.name, ttt.name) as truck_type_name, po.name as origin_port_name, pd.name as destination_port_name,
        COALESCE(v.name, vv.name) as vendor_name, a.name as account_name, d.name as department_name,
        cu.name as cost_updated_by_name, tr.cost_updated_by as cost_updated_by_email,
        tk.vendor_id as rate_vendor_id, tk.truck_type_id as rate_truck_type_id
        FROM truck_requests tr LEFT JOIN truck_statuses ts ON tr.status_id=ts.id
        LEFT JOIN truck_types tt ON tr.truck_type_id=tt.id
        LEFT JOIN ports po ON tr.origin_port_id=po.id LEFT JOIN ports pd ON tr.destination_port_id=pd.id
        LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id LEFT JOIN vendors v ON tk.vendor_id=v.id
        LEFT JOIN vendors vv ON tr.vendor_id=vv.id
        LEFT JOIN truck_types ttt ON tk.truck_type_id=ttt.id
        LEFT JOIN accounts a ON tr.account_id=a.id LEFT JOIN departments d ON tr.department_id=d.id
        LEFT JOIN users cu ON tr.cost_updated_by=cu.email
        WHERE {ws} ORDER BY tr.created_at DESC""", tuple(pa))
    pcache, ccache = {}, {}
    for i in reqs:
        rate, base, basis = sync_request_price(i, i.get("rate_vendor_id") or i.get("vendor_id"),
                                               i.get("truck_type_id") or i.get("rate_truck_type_id"), pcache, ccache)
        foul_cost, fuel_cost = foul_fuel_costs(rate, base, i.get("status_id"), i.get("foul_trip_count"))
        i["rate_basis"] = basis
        i["rate_amount"] = base
        i["foul_trip_cost"] = foul_cost
        i["fuel_surcharge_cost"] = fuel_cost
        i["total_cost"] = total_cost_of(i, foul_cost, fuel_cost)
        if i.get("assigned_truck_id") and i.get("status_id") in (2, 3, 4, 5, 7):
            truck_reqs = db_q("""SELECT id, request_number, status_id, drop_sequence, trip_id,
                account_id, assigned_truck_id FROM truck_requests WHERE assigned_truck_id=%s""",
                (i["assigned_truck_id"],))
            i["trip_id"] = resolve_trip_id(i, truck_reqs)
        else:
            i["trip_id"] = i.get("trip_id") or None
        i["delivered_date"] = (i.get("end_unloading_datetime") or "")[:10]
        i["cost_updated_at"] = to_gmt8(i.get("cost_updated_at")) if i.get("cost_updated_at") else None
    coords = get_port_coords_map()
    add_distances_to_requests(reqs, coords)
    return {**cost_summary_stats(reqs), "requests": reqs}

BULK_COST_FIELDS = ("toll_fee", "management_fee", "fuel", "parking", "miscellaneous", "manpower",
                    "toll", "welfare", "wh_rental", "toll_fee_easytrip", "toll_fee_autosweep")

def _bulk_cost_targets(date_from, date_to, vendor_id=None, truck_type_id=None):
    """Delivered + approved Foul Trip requests a bulk cost update can apply to: matched by
    Delivered Date (End Unloading) or Foul Trip Date, vendor and truck type."""
    if LOCAL_MODE:
        out = []
        for r in _store["truck_requests"]:
            if r.get("status_id") not in (4, 7):
                continue
            if r.get("status_id") == 7 and not (r.get("foul_trip_approved_by") or ""):
                continue
            d = (r.get("foul_trip_date") or str(r.get("end_unloading_datetime") or "")[:10])[:10]
            if not d or d < date_from or d > date_to:
                continue
            trow = next((x for x in _store["trucks"] if x["id"] == r.get("assigned_truck_id")), None) if r.get("assigned_truck_id") else None
            tv = (trow or {}).get("vendor_id") or r.get("vendor_id")
            tt = r.get("truck_type_id") or (trow or {}).get("truck_type_id")
            if vendor_id and tv != vendor_id:
                continue
            if truck_type_id and tt != truck_type_id:
                continue
            out.append({"id": r["id"], "request_number": r.get("request_number"), "trip_id": r.get("trip_id"),
                        "status_id": r.get("status_id"), "match_date": d,
                        "vendor_name": next((v["name"] for v in _store["vendors"] if v["id"] == tv), ""),
                        "truck_type_name": next((t["name"] for t in _store["truck_types"] if t["id"] == tt), ""),
                        "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), "")})
    else:
        wh = ["tr.status_id IN (4,7)", "(tr.status_id<>7 OR (tr.foul_trip_approved_by IS NOT NULL AND tr.foul_trip_approved_by<>''))",
              "COALESCE(tr.foul_trip_date, DATE(tr.end_unloading_datetime)) BETWEEN %s AND %s"]
        pa = [date_from, date_to]
        if vendor_id:
            wh.append("COALESCE(tk.vendor_id, tr.vendor_id)=%s"); pa.append(vendor_id)
        if truck_type_id:
            wh.append("COALESCE(tr.truck_type_id, tk.truck_type_id)=%s"); pa.append(truck_type_id)
        out = db_q(f"""SELECT tr.id, tr.request_number, tr.trip_id, tr.status_id,
            COALESCE(tr.foul_trip_date, DATE(tr.end_unloading_datetime)) AS match_date,
            v.name AS vendor_name, tt.name AS truck_type_name, pd.name AS destination_port_name
            FROM truck_requests tr
            LEFT JOIN trucks tk ON tr.assigned_truck_id=tk.id
            LEFT JOIN vendors v ON v.id=COALESCE(tk.vendor_id, tr.vendor_id)
            LEFT JOIN truck_types tt ON tt.id=COALESCE(tr.truck_type_id, tk.truck_type_id)
            LEFT JOIN ports pd ON pd.id=tr.destination_port_id
            WHERE {' AND '.join(wh)}""", tuple(pa))
    for r in out:
        r["status_name"] = "Foul Trip" if r.get("status_id") == 7 else "Delivered"
        r["match_date"] = str(r.get("match_date") or "")[:10]
    out.sort(key=lambda r: (r["match_date"], r.get("trip_id") or "", r.get("request_number") or ""))
    return out

def _bulk_filters(body):
    date_from = (body.get("date_from") or "").strip()
    date_to = (body.get("date_to") or "").strip()
    if not date_from or not date_to:
        raise HTTPException(400, "Date From and Date To are required")
    try:
        vendor_id = int(body.get("vendor_id")) if body.get("vendor_id") else None
        truck_type_id = int(body.get("truck_type_id")) if body.get("truck_type_id") else None
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid vendor or truck type")
    return date_from, date_to, vendor_id, truck_type_id

@app.post("/api/cost-summary/bulk-matches")
async def bulk_cost_matches(request: Request):
    require_page_unlock(request, "cost")
    """Requests a bulk cost update could apply to, for the user to pick from."""
    require_admin(request)
    body = await request.json()
    return {"items": _bulk_cost_targets(*_bulk_filters(body))}

@app.post("/api/cost-summary/bulk-update")
async def bulk_cost_update(request: Request):
    require_page_unlock(request, "cost")
    bulk_user = require_admin(request)
    body = await request.json()
    date_from, date_to, vendor_id, truck_type_id = _bulk_filters(body)
    split = bool(body.get("split"))
    amounts = {}
    for k, v in (body.get("amounts") or {}).items():
        if k not in BULK_COST_FIELDS:
            raise HTTPException(400, f"Unknown field: {k}")
        if v is None or str(v).strip() == "":
            continue
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise HTTPException(400, f"Invalid amount for {k}")
        if f < 0:
            raise HTTPException(400, "Amounts cannot be negative")
        if f:
            amounts[k] = f
    if not amounts:
        raise HTTPException(400, "Enter at least one amount")
    matches = _bulk_cost_targets(date_from, date_to, vendor_id, truck_type_id)
    ids = [m["id"] for m in matches]
    if "request_ids" in body:
        try:
            chosen = {int(x) for x in (body.get("request_ids") or [])}
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid request selection")
        if not chosen:
            raise HTTPException(400, "Select at least one truck request")
        if chosen - set(ids):
            raise HTTPException(400, "Some selected requests no longer match the date range, vendor and truck type - refresh the list")
        ids = [i for i in ids if i in chosen]
    n = len(ids)
    if not n:
        raise HTTPException(400, "No matching requests found")
    out_fields = {}
    stamp, who = nows(), bulk_user.get("email", "")
    for k, v in amounts.items():
        add = round((v / n) if split else v, 2)
        out_fields[k] = add
        if LOCAL_MODE:
            for r in _store["truck_requests"]:
                if r["id"] in ids:
                    r[k] = round((r.get(k) or 0) + add, 2)
        else:
            marks = ",".join(["%s"] * n)
            db_x(f"UPDATE truck_requests SET {k}=COALESCE({k},0)+%s WHERE id IN ({marks})", tuple([add] + ids))
    if LOCAL_MODE:
        for r in _store["truck_requests"]:
            if r["id"] in ids:
                r["cost_updated_by"], r["cost_updated_at"] = who, stamp
    else:
        marks = ",".join(["%s"] * n)
        db_x(f"UPDATE truck_requests SET cost_updated_by=%s, cost_updated_at=%s WHERE id IN ({marks})",
             tuple([who, stamp] + ids))
    return {"ok": True, "updated": n, "field_amount": out_fields}

# ---------------------------------------------------------------------------
# Google Sheets Sync Endpoints (public, no auth — for Apps Script)
# ---------------------------------------------------------------------------

# The sync endpoints return exactly what the matching app pages show, by calling the
# page's own API function as a read-only "Google Sheets Sync" master admin (no page
# password needed - the sheet is a scheduled export, not a person opening the page).
_SYNC_USER = contextvars.ContextVar("sync_user", default=None)
SYNC_IDENTITY = {"id": 0, "email": "google-sheets-sync", "name": "Google Sheets Sync", "role": "master_admin"}

def _sync_call(fn, **kw):
    from starlette.requests import Request as _Req
    req = _Req({"type": "http", "method": "GET", "scheme": "http", "server": ("sync", 80), "root_path": "",
                "path": "/api/sync", "headers": [], "query_string": b""})
    tok = _SYNC_USER.set(dict(SYNC_IDENTITY))
    try:
        return fn(req, **kw)
    finally:
        _SYNC_USER.reset(tok)

def _sync_attachments(rid):
    if LOCAL_MODE:
        atts = [a for a in _store["attachments"] if a.get("truck_request_id") == rid]
    else:
        atts = db_q("SELECT id, original_filename FROM attachments WHERE truck_request_id=%s", (rid,))
    return [{"original_filename": a.get("original_filename", ""), "download_url": f"/api/attachments/{a.get('id')}/download"} for a in atts]

@app.get("/api/sync/masterlist")
def sync_masterlist():
    items = _sync_call(list_requests, per_page=1000000).get("items", [])
    for r in items:
        if not isinstance(r.get("attachments"), list):
            r["attachments"] = _sync_attachments(r["id"])
        m = r.get("manifest") or None
        r["manifest_status"] = (f"Uploaded ({m.get('id_count', 0)} IDs)" if isinstance(m, dict) else "Missing")
        r["consolidated"] = "Yes" if r.get("is_consolidated") else ""
        r["initial_qty"] = r.get("initial_quantity") if r.get("initial_quantity") is not None else r.get("quantity")
        r["revised_qty_out"] = r.get("revised_qty") if r.get("revised_qty") is not None else r.get("quantity")
        r["foul_trip_approved"] = r.get("foul_trip_approved_by_email") or r.get("foul_trip_approved_by") or ""
    return items

@app.get("/api/sync/rates")
def sync_rates():
    rows = _sync_call(list_rates)
    pname = {p["id"]: p["name"] for p in (_store["ports"] if LOCAL_MODE else db_q("SELECT id, name FROM ports"))}
    for r in rows:
        drops = _rate_drops(r)
        r["additional_drops"] = "; ".join(f"{pname.get(d.get('port_id'), d.get('port_id'))}: {d.get('rate_per_trip', 0)}"
                                          for d in drops if isinstance(d, dict))
    return rows

@app.get("/api/sync/evaluation")
def sync_evaluation():
    return _sync_call(list_evals)

@app.get("/api/sync/cost")
def sync_cost():
    return _sync_call(cost_summary, date_from="1900-01-01", date_to="2999-12-31").get("requests", [])

@app.get("/api/sync/foul-trips")
def sync_foul_trips():
    items = _sync_call(foul_trip_review).get("items", [])
    for r in items:
        r["approval_status"] = "Approved" if r.get("foul_trip_approved_by") else "Awaiting Approval"
    return items

@app.get("/api/sync/trip-utilisation")
def sync_trip_utilisation():
    rows = _sync_call(trip_utilisation)
    for r in rows:
        r["initial_tier"] = (utilisation_tier(r.get("initial_utilisation")) or "").upper()
        r["revised_tier"] = (utilisation_tier(r.get("revised_utilisation")) or "").upper()
    return rows

@app.get("/api/sync/capacity-conversion")
def sync_capacity_conversion():
    cfg = load_capacity_conversion()
    pkgs = [row2d(x) for x in _store["packaging_types"]] if LOCAL_MODE else db_q("SELECT id, name, code FROM packaging_types WHERE is_active=1 ORDER BY name")
    base_id = cfg.get("base_packaging_type_id")
    base_name = next((p["name"] for p in pkgs if p["id"] == base_id), "")
    out = []
    for p in pkgs:
        f = 1.0 if p["id"] == base_id else conversion_factor(cfg, p["id"])
        out.append({"packaging_type": p.get("name", ""), "code": p.get("code", ""), "base_unit": base_name,
                    "is_base": "Yes" if p["id"] == base_id else "",
                    "factor": round(f, 6), "inverse": round(1 / f, 6) if f else ""})
    return out

@app.get("/api/sync/fleet")
def sync_fleet():
    if LOCAL_MODE:
        result = []
        for t in _store["trucks"]:
            tt = next((x for x in _store["truck_types"] if x["id"] == t.get("truck_type_id")), None)
            v = next((x for x in _store["vendors"] if x["id"] == t.get("vendor_id")), None)
            reqs = [r for r in _store["truck_requests"] if r.get("assigned_truck_id") == t["id"] and r.get("status_id") not in (4, 5, 7)]
            hist = [h for h in _store["truck_request_history"] if h.get("truck_id") == t["id"] and h.get("status_id") in (4, 5, 7)]
            caps = next((c for c in _store["truck_type_capacities"] if c.get("truck_type_id") == t.get("truck_type_id")), None)
            result.append({**t, "truck_type_name": tt["name"] if tt else "", "vendor_name": v["name"] if v else "",
                "active_requests": [{"id": r["id"], "request_number": r.get("request_number",""),
                    "origin_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("origin_port_id")), ""),
                    "destination_port_name": next((p["name"] for p in _store["ports"] if p["id"] == r.get("destination_port_id")), ""),
                    "status_name": next((s["name"] for s in _store["truck_statuses"] if s["id"] == r.get("status_id")), "")}
                    for r in reqs],
                "history_count": len({h["truck_request_id"] for h in hist}), "capacity": caps.get("max_quantity") if caps else None})
        return result
    return db_q("""SELECT t.*, tt.name as truck_type_name, v.name as vendor_name,
        (SELECT COUNT(*) FROM truck_requests WHERE assigned_truck_id=t.id AND status_id NOT IN (4,5,7)) as active_requests,
        (SELECT COUNT(DISTINCT truck_request_id) FROM truck_request_history WHERE truck_id=t.id AND status_id IN (4,5,7)) as history_count,
        (SELECT max_quantity FROM truck_type_capacities WHERE truck_type_id=t.truck_type_id LIMIT 1) as capacity
        FROM trucks t LEFT JOIN truck_types tt ON t.truck_type_id=tt.id
        LEFT JOIN vendors v ON t.vendor_id=v.id ORDER BY t.plate_number""")

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
