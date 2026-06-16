"""
Event detection engine — scans MongoDB transactions and flags 6 life events.
Loads rules dynamically and supports targeted customer detection.
"""

from datetime import datetime, timedelta
from collections import defaultdict
from backend.database import get_db, get_rules

def _group_by(docs, key="customer_id"):
    groups = defaultdict(list)
    for d in docs:
        groups[d[key]].append(d)
    return groups

def detect_salary_increase(db, rls, cid=None):
    query = {"category": "salary", "type": "credit"}
    if cid: query["customer_id"] = cid
    rows = list(db.transactions.find(query, {"customer_id": 1, "amount": 1, "date": 1}).sort([("customer_id", 1), ("date", -1)]))
    
    events = []
    threshold = 1.0 + (rls.get("salary_increase_pct", 20.0) / 100.0)
    for cust_id, sals in _group_by(rows).items():
        if len(sals) < 4: continue
        latest = sals[0]["amount"]
        avg3 = sum(s["amount"] for s in sals[1:4]) / 3
        if latest > avg3 * threshold:
            pct = round((latest - avg3) / avg3 * 100, 1)
            events.append({
                "customer_id": cust_id, "event_type": "salary_increase",
                "event_data": {"latest_salary": latest, "prior_avg": round(avg3, 2), "increase_pct": pct},
            })
    return events

def detect_emi_closure(db, rls, cid=None):
    query = {"category": "emi", "type": "debit"}
    if cid: query["customer_id"] = cid
    rows = list(db.transactions.find(query, {"customer_id": 1, "amount": 1, "date": 1}).sort([("customer_id", 1), ("date", -1)]))
    
    events, today = [], datetime.now()
    cutoff_days = rls.get("emi_closure_days", 45)
    for cust_id, emi_list in _group_by(rows).items():
        if len(emi_list) < 3: continue
        last_dt = datetime.strptime(emi_list[0]["date"], "%Y-%m-%d")
        gap = (today - last_dt).days
        if gap > cutoff_days:
            events.append({
                "customer_id": cust_id, "event_type": "emi_closure",
                "event_data": {"last_emi_date": emi_list[0]["date"], "emi_amount": emi_list[0]["amount"], "gap_days": gap},
            })
    return events

def detect_fd_maturity(db, rls, cid=None):
    dep_query = {"category": "fd_deposit", "type": "debit"}
    mat_query = {"category": "fd_maturity", "type": "credit"}
    if cid:
        dep_query["customer_id"] = cid
        mat_query["customer_id"] = cid
        
    deps = list(db.transactions.find(dep_query))
    dep_map = defaultdict(list)
    for d in deps:
        dep_map[d["customer_id"]].append(d["amount"])

    mats = list(db.transactions.find(mat_query))
    events = []
    tolerance = rls.get("fd_maturity_range", 0.10)
    for m in mats:
        cust_id = m["customer_id"]
        for dep_amt in dep_map.get(cust_id, []):
            if abs(m["amount"] - dep_amt) / dep_amt <= tolerance:
                events.append({
                    "customer_id": cust_id, "event_type": "fd_maturity",
                    "event_data": {"maturity_amount": m["amount"], "original_deposit": dep_amt, "maturity_date": m["date"]},
                })
                break
    return events

def detect_large_expense(db, rls, cid=None):
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    cust_query = {} if not cid else {"_id": cid}
    income_map = {c["_id"]: c["monthly_income"] for c in db.customers.find(cust_query, {"_id": 1, "monthly_income": 1})}
    
    tx_query = {"type": "debit", "category": "purchase", "date": {"$gte": cutoff}}
    if cid: tx_query["customer_id"] = cid
    rows = list(db.transactions.find(tx_query))

    events, seen = [], set()
    threshold = rls.get("large_expense_pct", 40.0) / 100.0
    for r in rows:
        cust_id = r["customer_id"]
        if cust_id in seen: continue
        income = income_map.get(cust_id, 0)
        if income and r["amount"] > income * threshold:
            seen.add(cust_id)
            pct = round(r["amount"] / income * 100, 1)
            events.append({
                "customer_id": cust_id, "event_type": "large_expense",
                "event_data": {"amount": r["amount"], "merchant": r.get("merchant"), "income_pct": pct, "date": r["date"]},
            })
    return events

def detect_travel_spike(db, rls, cid=None):
    query = {"is_international": True, "type": "debit"}
    if cid: query["customer_id"] = cid
    rows = list(db.transactions.find(query).sort([("customer_id", 1), ("date", -1)]))

    events = []
    gap_threshold = rls.get("travel_spike_days", 60)
    for cust_id, txns in _group_by(rows).items():
        if len(txns) == 1:
            events.append({
                "customer_id": cust_id, "event_type": "travel_spike",
                "event_data": {"amount": txns[0]["amount"], "merchant": txns[0].get("merchant"), "date": txns[0]["date"]},
            })
        elif len(txns) >= 2:
            d1 = datetime.strptime(txns[0]["date"], "%Y-%m-%d")
            d2 = datetime.strptime(txns[1]["date"], "%Y-%m-%d")
            gap = (d1 - d2).days
            if gap >= gap_threshold:
                events.append({
                    "customer_id": cust_id, "event_type": "travel_spike",
                    "event_data": {"amount": txns[0]["amount"], "date": txns[0]["date"], "gap_days": gap},
                })
    return events

def detect_education_payment(db, rls, cid=None):
    days = rls.get("education_payment_days", 30)
    cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
    query = {"category": "education", "type": "debit", "date": {"$gte": cutoff}}
    if cid: query["customer_id"] = cid
    rows = list(db.transactions.find(query))

    events, seen = [], set()
    for r in rows:
        cust_id = r["customer_id"]
        if cust_id in seen: continue
        seen.add(cust_id)
        events.append({
            "customer_id": cust_id, "event_type": "education_payment",
            "event_data": {"amount": r["amount"], "merchant": r.get("merchant"), "date": r["date"]},
        })
    return events

def run_all_detections(customer_id=None):
    """Execute detectors with dynamic rules. Retains clicked/converted campaigns."""
    db = get_db()
    rls = get_rules()
    
    # Retain events that are associated with active customer interactions
    active_msg_events = list(db.messages.find(
        {"status": {"$in": ["clicked", "converted"]}}, {"event_id": 1}
    ))
    active_event_ids = {m["event_id"] for m in active_msg_events if "event_id" in m}

    # Clean up non-active events and messages
    if customer_id:
        # Only cleanup for this specific customer
        db.messages.delete_many({"customer_id": customer_id, "status": {"$in": ["detected", "sent"]}})
        db.detected_events.delete_many({"customer_id": customer_id, "_id": {"$nin": list(active_event_ids)}})
    else:
        # General cleanup
        db.messages.delete_many({"status": {"$in": ["detected", "sent"]}})
        db.detected_events.delete_many({"_id": {"$nin": list(active_event_ids)}})

    detectors = [
        detect_salary_increase, detect_emi_closure, detect_fd_maturity,
        detect_large_expense, detect_travel_spike, detect_education_payment,
    ]

    all_events = []
    for fn in detectors:
        results = fn(db, rls, customer_id)
        for evt in results:
            evt["detected_at"] = datetime.utcnow()
        all_events.extend(results)

    # Filter out events that match kept active event types for this customer to avoid duplicate alerts
    existing_events = list(db.detected_events.find(
        {"customer_id": {"$in": [e["customer_id"] for e in all_events]}}
    ))
    existing_set = {(e["customer_id"], e["event_type"]) for e in existing_events}

    filtered_events = [
        e for e in all_events if (e["customer_id"], e["event_type"]) not in existing_set
    ]

    if filtered_events:
        db.detected_events.insert_many(filtered_events)

    return {
        "events_detected": len(filtered_events),
        "customers_affected": len({e["customer_id"] for e in filtered_events}),
    }
