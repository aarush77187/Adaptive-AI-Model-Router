"""
cloud_app.py — Streamlit Cloud deployment entrypoint
------------------------------------------------------
Same UI and behavior as app.py, but calls the routing logic directly
(router_core.route()) instead of over HTTP to a separate FastAPI
service. This is deliberate: Streamlit Community Cloud only runs one
process, so there's no separate place to host api.py alongside it.

For local development, keep using app.py + api.py (the real two-service
architecture this project is built around) — this file exists only so
there's a single public URL for hackathon judges to try live.

Deploy on share.streamlit.io:
    1. Push this repo to GitHub (already done).
    2. New app -> pick this repo -> main file path: cloud_app.py
    3. In the app's Settings -> Secrets, add:
           GROQ_API_KEY = "your_real_key_here"
    4. Deploy. You'll get a URL like https://<something>.streamlit.app
"""

import os

import streamlit as st

# Must happen BEFORE importing router_core, since router_core reads
# GROQ_API_KEY from the environment at import time.
if "GROQ_API_KEY" in st.secrets:
    os.environ["GROQ_API_KEY"] = st.secrets["GROQ_API_KEY"]

import router_core as core

core.init_db()

st.set_page_config(page_title="AI Model Router", page_icon="🔀")

st.title("🔀 AI Model Router")
st.caption("Same prompt, different model — depending on what you optimize for.")

if not os.environ.get("GROQ_API_KEY"):
    st.error("GROQ_API_KEY is not set. Add it under Settings → Secrets in Streamlit Cloud.")
    st.stop()

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
            result = core.route(prompt, priority=priority)
        except Exception as e:
            st.error(f"Model call failed: {e}")
            st.stop()

    st.success(f"Routed to **{result.label}** ({result.model_name})")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Tier", result.tier)
    col2.metric("Latency", f"{result.latency_ms:.0f} ms")
    col3.metric("Cost", f"${result.cost_usd:.6f}")
    col4.metric("Tokens", f"{result.input_tokens}/{result.output_tokens}")

    st.markdown("**Response:**")
    st.write(result.output_text)
