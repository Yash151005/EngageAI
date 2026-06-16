"""
MongoDB connection and helpers for EngageAI.
Supports local MongoDB and MongoDB Atlas via MONGO_URI env variable.
"""

import os
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient, ASCENDING, DESCENDING
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
DB_NAME = "engageai"

_client = None


def get_client():
    """Lazy-init and return the MongoClient singleton."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return _client


def get_db():
    """Return the engageai database handle."""
    return get_client()[DB_NAME]


def init_db():
    """Create indexes for optimal query performance and init rules."""
    db = get_db()
    db.customers.create_index("id", unique=True)
    db.transactions.create_index([("customer_id", ASCENDING), ("date", DESCENDING)])
    db.transactions.create_index("category")
    db.transactions.create_index([("category", ASCENDING), ("type", ASCENDING)])
    db.transactions.create_index("is_international")
    db.detected_events.create_index("customer_id")
    db.messages.create_index("customer_id")
    db.messages.create_index("event_id")

    # Seed default configuration rules if none exist
    if db.rules_config.count_documents({}) == 0:
        db.rules_config.insert_one({
            "salary_increase_pct": 20.0,
            "emi_closure_days": 45,
            "fd_maturity_range": 0.10,
            "large_expense_pct": 40.0,
            "travel_spike_days": 60,
            "education_payment_days": 30,
            "llm_prompt_template": (
                "<s>[INST] You are an SBI bank product advisor. "
                "Customer '{first_name}' triggered a '{event_type}' event. "
                "Details: {event_data}. "
                "Recommend '{product}'. Write a friendly SMS under 160 characters "
                "with 1 emoji. Reply ONLY with the message text. [/INST]"
            )
        })


def get_rules():
    """Retrieve dynamic rules config. Falls back to default if unavailable."""
    db = get_db()
    rules = db.rules_config.find_one()
    if not rules:
        return {
            "salary_increase_pct": 20.0,
            "emi_closure_days": 45,
            "fd_maturity_range": 0.10,
            "large_expense_pct": 40.0,
            "travel_spike_days": 60,
            "education_payment_days": 30,
            "llm_prompt_template": (
                "<s>[INST] You are an SBI bank product advisor. "
                "Customer '{first_name}' triggered a '{event_type}' event. "
                "Details: {event_data}. "
                "Recommend '{product}'. Write a friendly SMS under 160 characters "
                "with 1 emoji. Reply ONLY with the message text. [/INST]"
            )
        }
    return rules


def drop_all():
    """Drop all collections — used before re-generating data."""
    db = get_db()
    for col in ["customers", "transactions", "detected_events", "messages", "rules_config"]:
        db[col].drop()


def serialize_doc(doc):
    """Convert a MongoDB document to a JSON-serialisable dict.

    - ObjectId  → str
    - int _id   → kept as int  (customers use integer _id)
    - datetime  → ISO-8601 string
    """
    if not doc:
        return None
    result = {}
    for key, value in doc.items():
        if key == "_id":
            result["id"] = value if isinstance(value, int) else str(value)
        elif isinstance(value, ObjectId):
            result[key] = str(value)
        elif isinstance(value, datetime):
            result[key] = value.isoformat()
        else:
            result[key] = value
    return result
