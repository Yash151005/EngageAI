"""
Streamlit dashboard for EngageAI — SBI Life Event Detection & Control Room.
Provides transaction simulation, configuration of active rules, and analytics tracking.
"""

import streamlit as st
import requests
import pandas as pd
from datetime import datetime

API = "http://127.0.0.1:8000"

st.set_page_config(page_title="EngageAI — SBI Dashboard", page_icon="🏦", layout="wide")

# ── Styling ──────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }
.metric-card {
    background: linear-gradient(135deg, #101b2b 0%, #08101a 100%);
    border: 1px solid rgba(0, 180, 216, 0.2);
    border-radius: 12px; padding: 20px; text-align: center;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
.metric-card h3 { color: #00b4d8; font-size: 2rem; margin: 0; }
.metric-card p { color: #94a3b8; font-size: 0.85rem; margin: 5px 0 0 0; }
.status-badge {
    display: inline-block; padding: 2px 8px; border-radius: 12px;
    font-size: 0.75rem; font-weight: 600; text-transform: uppercase;
}
.badge-detected { background: #64748b; color: white; }
.badge-sent { background: #3b82f6; color: white; }
.badge-clicked { background: #f59e0b; color: white; }
.badge-converted { background: #10b981; color: white; }
</style>
""", unsafe_allow_html=True)

st.title("🏦 EngageAI — SBI Agentic Campaign Center")

# Fetch configuration rules
try:
    rules = requests.get(f"{API}/admin/rules", timeout=5).json()
except Exception:
    rules = {}

tabs = st.tabs(["🔍 Life Event Hub & Simulator", "⚙️ Control Room", "📊 Campaign Analytics"])

# ── TAB 1: LIFE EVENT HUB & SIMULATOR ────────────────────────
with tabs[0]:
    col_ctrl, col_sim = st.columns([2, 1])
    
    with col_ctrl:
        st.subheader("Active Customer Alerts")
        
        col_act, col_filter = st.columns([1, 1])
        with col_act:
            if st.button("🚀 Run Detection Pipeline", use_container_width=True):
                with st.spinner("Analyzing transactions..."):
                    try:
                        r = requests.post(f"{API}/run-detection", timeout=30).json()
                        st.success(f"Pipeline executed: {r['events_detected']} events, {r['messages_generated']} nudges.")
                    except Exception as e:
                        st.error(f"Error running pipeline: {e}")
        
        with col_filter:
            event_filter = st.selectbox("Filter by Event", [
                "All", "salary_increase", "emi_closure", "fd_maturity", "large_expense", "travel_spike", "education_payment"
            ], label_visibility="collapsed")

        limit = st.slider("Alert Display Limit", 5, 100, 15)
        # Fetch Events
        try:
            url = f"{API}/events?limit={limit}" + ("" if event_filter == "All" else f"&event_type={event_filter}")
            events = requests.get(url, timeout=5).json().get("events", [])
        except Exception:
            events = []

        if not events:
            st.info("No active events. Try running the detection pipeline or injecting transactions.")
        else:
            st.caption(f"Showing up to {limit} active alerts. Adjust slider to view more.")
            for ev in events:
                status = ev.get("status") or "detected"
                product = ev.get("product") or "—"
                nudge = ev.get("message") or "—"
                msg_id = ev.get("message_id")

                badge_html = f'<span class="status-badge badge-{status}">{status}</span>'
                
                with st.expander(f"👤 {ev['customer_name']}  ·  {ev['event_type'].replace('_',' ').title()}"):
                    c1, c2, c3 = st.columns([1, 1, 1])
                    c1.markdown(f"**Customer ID:** `{ev['customer_id']}`")
                    c1.markdown(f"**Target Product:** {product}")
                    c2.markdown(f"**Campaign Status:** {badge_html}", unsafe_allow_html=True)
                    c2.markdown(f"**Detected At:** {ev.get('detected_at')[:16].replace('T', ' ')}")
                    c3.json(ev.get("event_data", {}))
                    
                    st.info(f"💬 **SMS Nudge:** {nudge}")
                    
                    if status in ["detected", "sent"] and msg_id:
                        if st.button("📲 Push to YONO", key=f"snd_{ev['id']}"):
                            requests.post(f"{API}/messages/{msg_id}/status?status=sent")
                            st.success("Nudge dispatched to YONO.")
                            st.rerun()

    with col_sim:
        st.subheader("Transaction Simulator")
        try:
            cust_list = requests.get(f"{API}/customers", timeout=5).json()
            cust_opts = {f"{c['name']} (ID: {c['id']})": c for c in cust_list}
        except Exception:
            cust_opts = {}

        if not cust_opts:
            st.warning("No customers loaded.")
        else:
            selected_cust_str = st.selectbox("Select Target Customer", list(cust_opts.keys()))
            cust_obj = cust_opts[selected_cust_str]
            
            sim_cat = st.selectbox("Category", ["salary", "emi", "fd_deposit", "fd_maturity", "purchase", "travel", "education"])
            sim_type = "credit" if sim_cat in ["salary", "fd_maturity"] else "debit"
            sim_amt = st.number_input("Amount (INR)", min_value=1.0, value=50000.0, step=1000.0)
            sim_merchant = st.text_input("Merchant", value="SBI Financials" if "fd" in sim_cat else "Amazon India")
            sim_intl = st.checkbox("International Transaction", value=(sim_cat == "travel"))
            
            if st.button("📥 Inject and Run Agent Pipeline", use_container_width=True):
                payload = {
                    "customer_id": cust_obj["id"],
                    "amount": sim_amt,
                    "type": sim_type,
                    "category": sim_cat,
                    "merchant": sim_merchant,
                    "date": datetime.today().strftime("%Y-%m-%d"),
                    "is_international": sim_intl
                }
                try:
                    res = requests.post(f"{API}/transactions", json=payload, timeout=10).json()
                    if res.get("events_detected", 0) > 0:
                        st.success(f"🎉 New Event Triggered & Nudge Created!")
                    else:
                        st.warning("Transaction injected, but no rules were triggered.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Simulator error: {e}")

# ── TAB 2: CONTROL ROOM ──────────────────────────────────────
with tabs[1]:
    st.subheader("Configure Agent Campaign Rules")
    if not rules:
        st.error("Could not retrieve rules configuration.")
    else:
        with st.form("rules_form"):
            r_sal = st.slider("Salary Increase Trigger Threshold (%)", 5.0, 100.0, float(rules.get("salary_increase_pct", 20.0)))
            r_emi = st.slider("EMI Closure Absence Threshold (Days)", 10, 90, int(rules.get("emi_closure_days", 45)))
            r_fd = st.slider("FD Maturity Matching Range (+/- %)", 1, 30, int(rules.get("fd_maturity_range", 0.10) * 100)) / 100.0
            r_exp = st.slider("Large Expense Trigger Ratio (% of monthly income)", 5.0, 100.0, float(rules.get("large_expense_pct", 40.0)))
            r_trv = st.slider("International Travel Spike Gap (Days)", 10, 180, int(rules.get("travel_spike_days", 60)))
            r_edu = st.slider("Recent Education Payment Window (Days)", 10, 90, int(rules.get("education_payment_days", 30)))
            r_prompt = st.text_area("HuggingFace Mistral-7B Campaign Prompt Template", rules.get("llm_prompt_template", ""), height=150)
            
            if st.form_submit_button("💾 Apply Configuration & Save"):
                payload = {
                    "salary_increase_pct": r_sal, "emi_closure_days": r_emi, "fd_maturity_range": r_fd,
                    "large_expense_pct": r_exp, "travel_spike_days": r_trv, "education_payment_days": r_edu,
                    "llm_prompt_template": r_prompt
                }
                try:
                    requests.post(f"{API}/admin/rules", json=payload, timeout=5)
                    st.success("Configuration updated successfully.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Failed to update configurations: {e}")

# ── TAB 3: CAMPAIGN ANALYTICS ────────────────────────────────
with tabs[2]:
    st.subheader("Dynamic Conversion Analytics")
    try:
        stats = requests.get(f"{API}/campaign-stats", timeout=5).json()
    except Exception:
        stats = {"total_events": 0, "sent": 0, "clicked": 0, "converted": 0, "by_event": {}}

    c1, c2, c3, c4 = st.columns(4)
    ctr = round((stats["clicked"] / stats["sent"] * 100), 1) if stats["sent"] > 0 else 0.0
    cvr = round((stats["converted"] / stats["clicked"] * 100), 1) if stats["clicked"] > 0 else 0.0
    pipeline_val = f"₹{stats['converted'] * 125000:,.0f}"  # Est average value of SBI products is 1.25L

    c1.markdown(f'<div class="metric-card"><h3>{stats["total_events"]}</h3><p>Total Flagged Events</p></div>', unsafe_allow_html=True)
    c2.markdown(f'<div class="metric-card"><h3>{ctr}%</h3><p>Click-Through Rate (CTR)</p></div>', unsafe_allow_html=True)
    c3.markdown(f'<div class="metric-card"><h3>{cvr}%</h3><p>Conversion Rate (CVR)</p></div>', unsafe_allow_html=True)
    c4.markdown(f'<div class="metric-card"><h3>{pipeline_val}</h3><p>Est. Business Impact Value</p></div>', unsafe_allow_html=True)
    
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_funnel, col_breakdown = st.columns([1, 1])
    
    with col_funnel:
        st.write("Campaign Funnel Conversion Flow")
        funnel_df = pd.DataFrame({
            "Stage": ["1. Sent", "2. Clicked", "3. Converted"],
            "Campaign Count": [stats["sent"], stats["clicked"], stats["converted"]]
        })
        st.bar_chart(funnel_df.set_index("Stage"))

    with col_breakdown:
        st.write("Conversions Breakdown by Event Category")
        ev_types = list(stats["by_event"].keys())
        if not ev_types:
            st.info("No conversion data by type available yet.")
        else:
            breakdown_data = []
            for etype, data in stats["by_event"].items():
                breakdown_data.append({
                    "Event Type": etype.replace("_", " ").title(),
                    "Sent": data["sent"],
                    "Clicked": data["clicked"],
                    "Converted": data["converted"]
                })
            df_breakdown = pd.DataFrame(breakdown_data)
            st.dataframe(df_breakdown, use_container_width=True, hide_index=True)
