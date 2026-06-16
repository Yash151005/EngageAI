"""
Generate 500 fake SBI customers with 6 months of transaction history.
Inserts into MongoDB. Seeds patterns so all 6 event types trigger reliably.
"""

import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from backend.database import get_db, init_db, drop_all

# ── Realistic Indian Name Pools ────────────────────────────────

FIRST_NAMES = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh",
    "Ayaan", "Krishna", "Ishaan", "Priya", "Ananya", "Aadhya", "Diya",
    "Saanvi", "Myra", "Isha", "Kavya", "Riya", "Neha", "Amit", "Rahul",
    "Suresh", "Rajesh", "Pooja", "Sneha", "Meera", "Rohan", "Vikram",
    "Deepak", "Sunita", "Geeta", "Lakshmi", "Sanjay", "Manish", "Kiran",
    "Nisha", "Tanvi", "Harshita", "Gaurav", "Preeti", "Ankur", "Swati",
    "Mohit", "Divya", "Nikhil", "Shruti", "Varun", "Pallavi", "Tushar",
]

LAST_NAMES = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Reddy",
    "Nair", "Iyer", "Joshi", "Mehta", "Shah", "Rao", "Das", "Pillai",
    "Chatterjee", "Banerjee", "Deshmukh", "Kulkarni", "Patil", "Saxena",
    "Malhotra", "Kapoor", "Agarwal", "Bhat", "Menon", "Pandey", "Dubey",
]

EDU_MERCHANTS = [
    "IIT Delhi", "BITS Pilani", "Coursera", "UpGrad", "Amity University",
    "Manipal Academy", "Allen Coaching", "FIITJEE", "Byju's", "Unacademy",
]

MERCHANTS = [
    "Amazon", "Flipkart", "BigBasket", "Swiggy", "Zomato",
    "DMart", "Reliance Fresh", "Croma", "Myntra", "Airtel",
]

INCOMES = [25000, 35000, 50000, 65000, 80000, 100000, 150000, 200000]

EVENT_TYPES = [
    "salary_increase", "emi_closure", "fd_maturity",
    "large_expense", "travel_spike", "education",
]


def _gen_transactions(cid, income, flags):
    """Generate 6 months of transactions for one customer."""
    txns = []
    ref = datetime(2026, 6, 15)

    for m in range(6, 0, -1):
        dt = (ref - timedelta(days=m * 30)).strftime("%Y-%m-%d")
        if flags.get("salary_increase") and m == 1:
            amt = income * random.uniform(1.25, 1.45)
        else:
            amt = income * random.uniform(0.95, 1.05)
        txns.append({"customer_id": cid, "amount": round(amt, 2), "type": "credit",
                      "category": "salary", "description": "Monthly Salary",
                      "merchant": "Employer", "date": dt, "is_international": False})

    emi = round(income * random.uniform(0.10, 0.25), 2)
    for m in range(6, 0, -1):
        if flags.get("emi_closure") and m <= 2:
            continue
        dt = (ref - timedelta(days=m * 30 - 5)).strftime("%Y-%m-%d")
        txns.append({"customer_id": cid, "amount": emi, "type": "debit",
                      "category": "emi", "description": "Home Loan EMI",
                      "merchant": "SBI Home Loan", "date": dt, "is_international": False})

    if flags.get("fd_maturity"):
        fd = round(income * random.uniform(8, 15), 2)
        txns.append({"customer_id": cid, "amount": fd, "type": "debit",
                      "category": "fd_deposit", "description": "Fixed Deposit",
                      "merchant": "SBI FD",
                      "date": (ref - timedelta(days=150)).strftime("%Y-%m-%d"),
                      "is_international": False})
        txns.append({"customer_id": cid, "amount": round(fd * random.uniform(1.02, 1.05), 2),
                      "type": "credit", "category": "fd_maturity",
                      "description": "FD Maturity Credit", "merchant": "SBI FD",
                      "date": (ref - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
                      "is_international": False})

    if flags.get("large_expense"):
        txns.append({"customer_id": cid, "amount": round(income * random.uniform(0.45, 0.70), 2),
                      "type": "debit", "category": "purchase",
                      "description": "Large Purchase", "merchant": random.choice(MERCHANTS),
                      "date": (ref - timedelta(days=random.randint(1, 15))).strftime("%Y-%m-%d"),
                      "is_international": False})

    if flags.get("travel_spike"):
        txns.append({"customer_id": cid, "amount": round(income * random.uniform(0.15, 0.35), 2),
                      "type": "debit", "category": "travel",
                      "description": "International Purchase", "merchant": "Booking.com",
                      "date": (ref - timedelta(days=random.randint(1, 10))).strftime("%Y-%m-%d"),
                      "is_international": True})

    if flags.get("education"):
        txns.append({"customer_id": cid, "amount": round(income * random.uniform(0.5, 2.0), 2),
                      "type": "debit", "category": "education",
                      "description": "Education Fee", "merchant": random.choice(EDU_MERCHANTS),
                      "date": (ref - timedelta(days=random.randint(1, 20))).strftime("%Y-%m-%d"),
                      "is_international": False})

    for m in range(6, 0, -1):
        for _ in range(random.randint(3, 7)):
            dt = (ref - timedelta(days=m * 30 - random.randint(0, 29))).strftime("%Y-%m-%d")
            txns.append({"customer_id": cid, "amount": round(random.uniform(200, income * 0.12), 2),
                          "type": "debit", "category": "purchase",
                          "description": "Regular Purchase", "merchant": random.choice(MERCHANTS),
                          "date": dt, "is_international": False})
    return txns


def main():
    """Populate MongoDB with synthetic data."""
    print("[*] Dropping old collections...")
    drop_all()
    init_db()
    db = get_db()

    print("[*] Generating 500 customers...")
    customers = []
    for i in range(1, 501):
        first = random.choice(FIRST_NAMES)
        last = random.choice(LAST_NAMES)
        customers.append({
            "_id": i, "id": i,
            "name": f"{first} {last}", "age": random.randint(22, 65),
            "email": f"{first.lower()}.{last.lower()}{i}@email.com",
            "phone": f"+91{random.randint(7000000000, 9999999999)}",
            "monthly_income": random.choice(INCOMES),
            "account_number": f"SBI{random.randint(10000000000, 99999999999)}",
        })
    db.customers.insert_many(customers)

    print("[*] Generating transactions...")
    all_txns = []
    for c in customers:
        flags = {e: True for e in EVENT_TYPES if random.random() < 0.18}
        if c["_id"] <= 100 and not flags:
            flags[random.choice(EVENT_TYPES)] = True
        all_txns.extend(_gen_transactions(c["_id"], c["monthly_income"], flags))

    # Bulk insert in 5000-doc chunks for performance
    for i in range(0, len(all_txns), 5000):
        db.transactions.insert_many(all_txns[i:i + 5000])

    print(f"[OK] {len(customers)} customers, {len(all_txns)} transactions -> MongoDB")


if __name__ == "__main__":
    main()
