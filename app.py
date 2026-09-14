"""
app.py — Streamlit UI for the AI Model Router
-----------------------------------------------
Talks to the FastAPI app (api.py) over HTTP. This is the "demo screen"
for the hackathon: type a prompt, pick a priority, watch which model
gets picked and what it costs/how long it takes.

Setup:
    pip install streamlit requests

Run (in two terminals):
    Terminal 1:  uvicorn api:app --reload
    Terminal 2:  streamlit run app.py
"""

import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/route"

st.set_page_config(page_title="AI Model Router", page_icon="🔀")

st.title("🔀 AI Model Router")
st.caption("Same prompt, different model — depending on what you optimize for.")

prompt = st.text_area("Prompt", placeholder="Ask anything...", height=120)

priority = st.radio(
    "Optimize for",
    options=["balanced", "speed", "cost", "quality"],
    format_func=lambda p: {
        "balanced": "⚖️ Balanced",
        "speed": "⚡ Speed",
        "cost": "💰 Cost",
        "quality": "🎯 Quality",
    }[p],
    horizontal=True,
)

if st.button("Route", type="primary", disabled=not prompt.strip()):
    with st.spinner("Routing..."):
        try:
            response = requests.post(
                API_URL,
                json={"prompt": prompt, "priority": priority},
                timeout=60,
            )
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.ConnectionError:
            st.error("Can't reach the API. Is `uvicorn api:app --reload` running?")
            st.stop()
        except requests.exceptions.HTTPError as e:
            st.error(f"API error: {e.response.json().get('detail', str(e))}")
            st.stop()

    st.success(f"Routed to **{data['model_label']}** ({data['model_name']})")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tier", data["tier"])
    col2.metric("Latency", f"{data['latency_ms']:.0f} ms")
    col3.metric("Cost", f"${data['cost_usd']:.6f}")
    col4.metric("Tokens", f"{data['input_tokens']}/{data['output_tokens']}")

    st.markdown("**Response:**")
    st.write(data["output_text"])
