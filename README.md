# 🏦 EngageAI — Agentic AI for SBI Life Event Detection

> Detects customer financial life events from transaction data and sends
> personalised product nudges via AI-generated messages.

---

## Architecture

```mermaid
graph LR
    A[MongoDB<br>500 Customers] --> B[Event Detector<br>6 Rules]
    B --> C[LLM Engine<br>Mistral-7B]
    C --> D[FastAPI<br>REST API]
    D --> E[Streamlit<br>Dashboard]
    D --> F[React<br>YONO Mock]
```

## 🎯 Detected Events

| # | Event | Detection Logic |
|---|-------|-----------------|
| 1 | **Salary Increase** | Latest credit > 20% above 3-month average |
| 2 | **EMI Closure** | Regular monthly debit stops for 45+ days |
| 3 | **FD Maturity** | Large credit matching a prior FD deposit |
| 4 | **Large Expense** | Single debit > 40% of monthly income |
| 5 | **Travel Spike** | International transaction after 60-day gap |
| 6 | **Education Payment** | Debit to education-category merchant |

---

## 🚀 Setup

### Prerequisites

- **Python 3.10+**
- **MongoDB** — either:
  - [Install locally](https://www.mongodb.com/docs/manual/installation/) (Community Edition, free)
  - [MongoDB Atlas](https://www.mongodb.com/atlas) free-tier cluster (M0)
- (Optional) A free [HuggingFace API token](https://huggingface.co/settings/tokens)

### 1. Clone & Install

```bash
cd EngageAI
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 2. Configure Environment

```bash
copy .env.example .env
# Edit .env:
#   MONGO_URI=mongodb://localhost:27017          (local)
#   MONGO_URI=mongodb+srv://user:pass@cluster... (Atlas)
#   HF_TOKEN=hf_...  (optional, falls back to templates)
```

### 3. Generate Synthetic Data

```bash
python -m backend.data_generator
# Inserts 500 customers + ~20k transactions into MongoDB
```

### 4. Start FastAPI Backend

```bash
uvicorn backend.main:app --reload --port 8000
# API docs at http://localhost:8000/docs
```

### 5. Run Streamlit Dashboard

```bash
streamlit run dashboard/app.py
# Opens at http://localhost:8501
```

### 6. Open YONO Mock

Open `yono-mock/index.html` in your browser.
(Fetches from `http://localhost:8000` — backend must be running.)

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/run-detection` | Run event detection + generate messages |
| `GET`  | `/events?event_type=salary_increase` | Get detected events (optional filter) |
| `GET`  | `/messages/{customer_id}` | Get messages for a customer |
| `GET`  | `/customers` | List customers |

---

## 🔧 How It Works

1. **Data Generation** — 500 fake Indian customers with 6 months of realistic
   transaction history, seeded with event-triggering patterns.

2. **Event Detection** — Six rule-based detectors scan the `transactions`
   collection and flag matching customers into `detected_events`.

3. **LLM Engine** — For each event, the system calls HuggingFace Mistral-7B
   to generate a personalised SMS (< 160 chars). Falls back to curated
   templates when the API is unavailable.

4. **Dashboard** — Streamlit UI shows all flagged customers with their events,
   recommended products, and generated messages. A "Send via YONO" button
   simulates notification delivery.

5. **YONO Mock** — A React single-page app renders a mobile notification card
   with the personalised message, mimicking the SBI YONO interface.

---

## 📁 Project Structure

```
EngageAI/
├── backend/
│   ├── __init__.py
│   ├── database.py          # MongoDB connection + helpers
│   ├── models.py            # Pydantic schemas
│   ├── data_generator.py    # Synthetic data (500 customers)
│   ├── event_detector.py    # 6 rule-based detectors
│   ├── llm_engine.py        # Mistral-7B + fallback
│   └── main.py              # FastAPI endpoints
├── dashboard/
│   └── app.py               # Streamlit dashboard
├── yono-mock/
│   ├── index.html           # React SPA shell
│   ├── styles.css           # Premium mobile CSS
│   └── app.js               # React components
├── requirements.txt
├── .env.example
└── README.md
```

---

## ⚠️ Notes

- **No paid APIs** — Everything runs on free tiers.
- **HF_TOKEN is optional** — The system uses rule-based fallback if unset.
- **MongoDB** — Local Community Edition or Atlas M0 (free).
- Each source file is under 200 lines.
