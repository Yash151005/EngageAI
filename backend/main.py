"""
FastAPI backend for EngageAI (MongoDB version).
Exposes REST endpoints for event detection, chat advisor, rules config, and simulation.
"""

import sys
from pathlib import Path
from typing import Optional
from datetime import datetime
from bson import ObjectId

from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.database import get_db, init_db, serialize_doc, get_rules
from backend.event_detector import run_all_detections
from backend.llm_engine import generate_all_messages, chat_with_advisor
from backend.models import (
    DetectionResponse, EventsResponse, DetectedEvent,
    MessagesResponse, Message, RulesConfig, ChatRequest, Transaction
)

app = FastAPI(
    title="EngageAI — SBI Life Event Detection",
    description="Agentic AI that detects financial life events and generates personalised nudges",
    version="1.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/yono", StaticFiles(directory="yono-mock", html=True), name="yono")


@app.on_event("startup")
def on_startup():
    init_db()

@app.post("/run-detection", response_model=DetectionResponse)
def run_detection():
    result = run_all_detections()
    msg_count = generate_all_messages()
    return DetectionResponse(
        events_detected=result["events_detected"],
        messages_generated=msg_count,
        customers_affected=result["customers_affected"],
    )

@app.get("/events", response_model=EventsResponse)
def get_events(event_type: Optional[str] = Query(None)):
    db = get_db()
    match = {"event_type": event_type} if event_type else {}

    pipeline = [
        {"$match": match},
        {"$lookup": {
            "from": "customers", "localField": "customer_id",
            "foreignField": "_id", "as": "cust",
        }},
        {"$unwind": {"path": "$cust", "preserveNullAndEmptyArrays": True}},
        {"$lookup": {
            "from": "messages", "localField": "_id",
            "foreignField": "event_id", "as": "msg",
        }},
        {"$unwind": {"path": "$msg", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {
            "customer_name": "$cust.name",
            "product": "$msg.product",
            "message": "$msg.message",
            "status": "$msg.status",
            "message_id": "$msg._id",
            "chat_history": "$msg.chat_history"
        }},
        {"$project": {"cust": 0, "msg": 0}},
        {"$sort": {"detected_at": -1}},
    ]

    rows = list(db.detected_events.aggregate(pipeline))
    events = [DetectedEvent(**serialize_doc(r)) for r in rows]
    return EventsResponse(total=len(events), events=events)

@app.get("/messages/{customer_id}", response_model=MessagesResponse)
def get_messages(customer_id: int):
    db = get_db()
    cust = db.customers.find_one({"_id": customer_id})
    if not cust:
        raise HTTPException(404, detail="Customer not found")

    pipeline = [
        {"$match": {"customer_id": customer_id}},
        {"$lookup": {
            "from": "detected_events", "localField": "event_id",
            "foreignField": "_id", "as": "evt",
        }},
        {"$unwind": {"path": "$evt", "preserveNullAndEmptyArrays": True}},
        {"$addFields": {"event_type": "$evt.event_type"}},
        {"$project": {"evt": 0}},
        {"$sort": {"created_at": -1}},
    ]

    rows = list(db.messages.aggregate(pipeline))
    name = cust["name"]
    msgs = [Message(**{**serialize_doc(r), "customer_name": name}) for r in rows]
    return MessagesResponse(
        customer_id=customer_id, customer_name=name, total=len(msgs), messages=msgs
    )

@app.get("/customers")
def list_customers():
    db = get_db()
    return list(db.customers.find({}, {"_id": 0, "id": "$_id", "name": 1, "monthly_income": 1}).sort("_id", 1).limit(200))

# ── New Premium Endpoints ────────────────────────────────────

@app.get("/admin/rules")
def get_admin_rules():
    return serialize_doc(get_rules())

@app.post("/admin/rules")
def update_admin_rules(rules: RulesConfig):
    db = get_db()
    db.rules_config.drop()
    db.rules_config.insert_one(rules.dict())
    return {"status": "success", "message": "Rules updated successfully"}

@app.post("/transactions")
def create_transaction(txn: Transaction):
    db = get_db()
    t_dict = txn.dict()
    if "id" in t_dict: t_dict.pop("id")
    
    # Save transaction
    db.transactions.insert_one(t_dict)
    
    # Trigger pipeline
    res = run_all_detections(customer_id=txn.customer_id)
    msg_count = generate_all_messages()
    return {
        "status": "success", 
        "events_detected": res["events_detected"], 
        "messages_generated": msg_count
    }

@app.post("/messages/{message_id}/status")
def update_message_status(message_id: str, status: str = Query(...)):
    db = get_db()
    try:
        oid = ObjectId(message_id)
    except Exception:
        oid = message_id
        
    res = db.messages.update_one({"_id": oid}, {"$set": {"status": status}})
    if res.matched_count == 0:
        raise HTTPException(404, detail="Message campaign not found")
    return {"status": "success", "updated_status": status}

@app.post("/chat")
def chat_advisor(req: ChatRequest):
    db = get_db()
    try:
        oid = ObjectId(req.message_id)
    except Exception:
        oid = req.message_id

    msg_doc = db.messages.find_one({"_id": oid})
    if not msg_doc:
        raise HTTPException(404, detail="Campaign message not found")

    cust = db.customers.find_one({"_id": req.customer_id})
    cust_name = cust["name"] if cust else "Customer"
    product = msg_doc.get("product", "SBI Product")
    event_type = msg_doc.get("event_type", "financial event")

    history = msg_doc.get("chat_history", []) or []
    history.append({"role": "user", "text": req.user_message, "timestamp": datetime.utcnow().isoformat()})

    bot_text = chat_with_advisor(cust_name, product, event_type, req.user_message, history)
    
    # Dynamic status update if conversion is verbal/indicated
    new_status = msg_doc.get("status", "clicked")
    lower_bot = bot_text.lower()
    if any(k in lower_bot for k in ["initiated", "active", "confirm", "setup"]):
        new_status = "converted"

    history.append({"role": "assistant", "text": bot_text, "timestamp": datetime.utcnow().isoformat()})
    
    db.messages.update_one(
        {"_id": oid},
        {"$set": {"chat_history": history, "status": new_status}}
    )
    return {"response": bot_text, "status": new_status, "chat_history": history}

@app.get("/campaign-stats")
def get_campaign_stats():
    db = get_db()
    total_events = db.detected_events.count_documents({})
    
    sent_count = db.messages.count_documents({"status": {"$in": ["sent", "clicked", "converted"]}})
    click_count = db.messages.count_documents({"status": {"$in": ["clicked", "converted"]}})
    conv_count = db.messages.count_documents({"status": "converted"})

    pipeline = [
        {"$lookup": {
            "from": "detected_events", "localField": "event_id",
            "foreignField": "_id", "as": "evt"
        }},
        {"$unwind": {"path": "$evt", "preserveNullAndEmptyArrays": True}},
        {"$group": {
            "_id": "$evt.event_type",
            "sent": {"$sum": {"$cond": [{"$in": ["$status", ["sent", "clicked", "converted"]]}, 1, 0]}},
            "clicked": {"$sum": {"$cond": [{"$in": ["$status", ["clicked", "converted"]]}, 1, 0]}},
            "converted": {"$sum": {"$cond": [{"$eq": ["$status", "converted"]}, 1, 0]}}
        }}
    ]

    by_type = {}
    rows = list(db.messages.aggregate(pipeline))
    for r in rows:
        if r["_id"]:
            by_type[r["_id"]] = {
                "sent": r["sent"], "clicked": r["clicked"], "converted": r["converted"]
            }
            
    return {
        "total_events": total_events,
        "sent": sent_count,
        "clicked": click_count,
        "converted": conv_count,
        "by_event": by_type
    }
