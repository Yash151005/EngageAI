"""
LLM engine — calls HuggingFace Mistral-7B-Instruct for personalised messages and chat.
Falls back to rule-based templates when API is unavailable or HF_TOKEN is unset.
"""

import os
import json
import requests as http_requests
from datetime import datetime
from dotenv import load_dotenv
from backend.database import get_db, get_rules

load_dotenv()

HF_API_URL = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"

PRODUCT_MAP = {
    "salary_increase":    ["SBI Step-Up SIP", "SBI Credit Card Upgrade"],
    "emi_closure":        ["SBI Mutual Fund SIP", "SBI Personal Loan Top-up"],
    "fd_maturity":        ["SBI FD Reinvestment", "SBI Debt Mutual Fund"],
    "large_expense":      ["SBI Personal Loan", "SBI EMI Conversion"],
    "travel_spike":       ["SBI Global Travel Card", "SBI Forex Service"],
    "education_payment":  ["SBI Education Loan", "SBI Scholar Card"],
}

FALLBACK_TEMPLATES = {
    "salary_increase": "Hi {name}! Congrats on the raise 🎉 Grow your wealth with {product}. Apply on YONO today!",
    "emi_closure": "Great news {name}! EMI completed ✅ Redirect savings to {product}. Start on YONO!",
    "fd_maturity": "Hi {name}, your FD matured 💰 Reinvest smartly with {product}. Check YONO now!",
    "large_expense": "Hi {name}, big expense? 💳 Make it easy with {product}. Apply instantly on YONO!",
    "travel_spike": "Bon voyage {name}! ✈️ Save on forex with {product}. Activate via YONO!",
    "education_payment": "Investing in education {name}? 📚 Fund it with {product}. Apply on YONO!",
}

def _call_mistral(prompt):
    token = os.getenv("HF_TOKEN")
    if not token: return None
    headers = {"Authorization": f"Bearer {token}"}
    payload = {"inputs": prompt, "parameters": {"max_new_tokens": 80, "temperature": 0.7, "return_full_text": False}}
    try:
        resp = http_requests.post(HF_API_URL, headers=headers, json=payload, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list) and data:
            return data[0].get("generated_text", "").strip()
    except Exception:
        pass
    return None

def generate_message(customer_name, event_type, event_data):
    if event_data is None: event_data = {}
    products = PRODUCT_MAP.get(event_type, ["SBI Product"])
    product = products[0]
    first_name = customer_name.split()[0]
    rls = get_rules()

    # Dynamic LLM Prompt
    tmpl = rls.get("llm_prompt_template", "")
    prompt = tmpl.format(first_name=first_name, event_type=event_type.replace('_', ' '), event_data=json.dumps(event_data), product=product)
    
    llm_text = _call_mistral(prompt)
    if llm_text and 20 < len(llm_text) <= 160:
        return product, llm_text

    # Fallback
    template = FALLBACK_TEMPLATES.get(event_type, "Hi {name}, explore {product} on SBI YONO!")
    message = template.format(name=first_name, product=product)
    if len(message) > 160: message = message[:157] + "..."
    return product, message

def generate_all_messages():
    db = get_db()
    existing = {m["event_id"] for m in db.messages.find({}, {"event_id": 1}) if m.get("event_id")}

    pipeline = [
        {"$lookup": {"from": "customers", "localField": "customer_id", "foreignField": "_id", "as": "customer"}},
        {"$unwind": "$customer"},
    ]
    events = list(db.detected_events.aggregate(pipeline))

    inserts = []
    for ev in events:
        if ev["_id"] in existing: continue
        product, message = generate_message(ev["customer"]["name"], ev["event_type"], ev.get("event_data"))
        inserts.append({
            "customer_id": ev["customer_id"],
            "event_id": ev["_id"],
            "event_type": ev["event_type"],
            "product": product,
            "message": message,
            "channel": "YONO",
            "sent": True,  # Auto-mark as sent for dashboard
            "status": "sent",
            "chat_history": [],
            "created_at": datetime.utcnow(),
        })

    if inserts:
        db.messages.insert_many(inserts)
    return len(inserts)

def chat_with_advisor(customer_name, product, event_type, user_msg, chat_history):
    """Generate advisor response using Mistral or smart rule fallback."""
    name = customer_name.split()[0]
    
    # Try LLM first
    hist_str = "\n".join([f"{'Customer' if h['role']=='user' else 'Advisor'}: {h['text']}" for h in chat_history[-4:]])
    prompt = (
        f"<s>[INST] You are an SBI bank conversational AI advisor helper. "
        f"You are helping customer '{name}' with their personalized recommendation of '{product}' "
        f"(offered because of a recent '{event_type.replace('_', ' ')}'). "
        f"Conversation History:\n{hist_str}\n"
        f"Customer: {user_msg}\n"
        f"Write a friendly response under 180 characters, and end with a question or CTA. "
        f"Reply ONLY with the text of the message. [/INST]"
    )
    
    llm_resp = _call_mistral(prompt)
    if llm_resp and len(llm_resp) > 10:
        return llm_resp

    # Fallback smart rules
    msg_lower = user_msg.lower()
    if any(k in msg_lower for k in ["interest", "rate", "benefit", "why", "return", "cost", "charge"]):
        if "sip" in product.lower() or "fund" in product.lower():
            return f"Our {product} offers compounding returns (historical avg 12-15% p.a.). Setup is fully automated. Would you like to start a monthly contribution?"
        elif "upgrade" in product.lower() or "card" in product.lower():
            return f"The upgraded card gives you 5x reward points on travel/dining, airport lounge access, and zero joining fees this month. Shall we proceed?"
        elif "loan" in product.lower():
            return f"Interest rates start at an attractive 9.5% p.a. with zero documentation needed since you are pre-approved. Ready to check the terms?"
        elif "forex" in product.lower():
            return f"It offers zero markup rates and instantaneous multi-currency loading. Very handy for travel. Shall I activate it?"
        else:
            return f"It offers exclusive SBI pricing, zero processing fees, and fits your financial profile. Would you like me to initiate the application?"

    if any(k in msg_lower for k in ["apply", "yes", "sure", "ok", "okay", "do it", "confirm", "start", "proceed", "setup"]):
        return f"Great choice! I have initiated the setup for your {product}. You'll see it active on your YONO home screen shortly. Thank you!"

    if any(k in msg_lower for k in ["detail", "more", "info", "what is"]):
        return f"This {product} is specifically curated based on your recent transactions to maximize your financial health. Setting it up takes 2 minutes. Shall we proceed?"

    return f"I can definitely help you with {product}! Would you like to know more about the interest rates, key benefits, or apply directly?"
