"""
Pydantic models for EngageAI API request/response schemas.
Updated for MongoDB — event_data is a native dict, IDs may be str (ObjectId).
"""

from pydantic import BaseModel
from typing import Optional, List, Any, Union


# ── Core Entities ──────────────────────────────────────────────

class Customer(BaseModel):
    id: int
    name: str
    age: Optional[int] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    monthly_income: Optional[float] = None
    account_number: Optional[str] = None


class Transaction(BaseModel):
    id: Optional[str] = None
    customer_id: int
    amount: float
    type: str
    category: Optional[str] = None
    description: Optional[str] = None
    merchant: Optional[str] = None
    date: str
    is_international: bool = False


class DetectedEvent(BaseModel):
    id: Optional[Any] = None
    customer_id: int
    customer_name: Optional[str] = None
    event_type: str
    event_data: Optional[dict] = None
    detected_at: Optional[str] = None


class Message(BaseModel):
    id: Optional[Any] = None
    customer_id: int
    customer_name: Optional[str] = None
    event_id: Optional[Any] = None
    event_type: Optional[str] = None
    product: Optional[str] = None
    message: Optional[str] = None
    channel: str = "YONO"
    sent: bool = False
    status: str = "detected"  # detected, sent, clicked, converted
    chat_history: Optional[List[dict]] = []
    created_at: Optional[str] = None


class RulesConfig(BaseModel):
    salary_increase_pct: float = 20.0
    emi_closure_days: int = 45
    fd_maturity_range: float = 0.10
    large_expense_pct: float = 40.0
    travel_spike_days: int = 60
    education_payment_days: int = 30
    llm_prompt_template: str = (
        "<s>[INST] You are an SBI bank product advisor. "
        "Customer '{first_name}' triggered a '{event_type}' event. "
        "Details: {event_data}. "
        "Recommend '{product}'. Write a friendly SMS under 160 characters "
        "with 1 emoji. Reply ONLY with the message text. [/INST]"
    )


class ChatRequest(BaseModel):
    customer_id: int
    message_id: str
    user_message: str



# ── API Response Schemas ───────────────────────────────────────

class DetectionResponse(BaseModel):
    events_detected: int
    messages_generated: int
    customers_affected: int


class EventsResponse(BaseModel):
    total: int
    events: List[DetectedEvent]


class MessagesResponse(BaseModel):
    customer_id: int
    customer_name: Optional[str] = None
    total: int
    messages: List[Message]
