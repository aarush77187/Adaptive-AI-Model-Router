# AI Model Router

An intelligent routing layer that automatically picks the best AI model
for each request based on complexity, cost, latency, and what the user
wants to optimize for — instead of sending every request to the most
expensive model available.

## How it works

```
User (Streamlit UI)
       ↓
   POST /route  (FastAPI)
       ↓
     Router
       ↓
  Simple / Medium / Complex
       ↓
  Model A / Model B / Model C  (Groq)
       ↓
    Response + cost/latency metrics
```

The router classifies each prompt as **simple**, **medium**, or
**complex** (word count + code/reasoning keyword detection) and routes
it to a matching model — unless you override it by choosing a priority:

- ⚡ **Speed** — always the fastest model
- 💰 **Cost** — always the cheapest model
- 🎯 **Quality** — always the most powerful model
- ⚖️ **Balanced** — let the router decide (default)

Every request is logged to `router_history.db` (SQLite) with its
features, chosen model, latency, tokens, and cost — this becomes the
training data for a future version that learns routing from real usage
instead of hand-written rules.

## Setup

```bash
pip install -r requirements.txt
cp .env.example .env   # then add your Groq API key
```

## Run

Two terminals:

```bash
uvicorn api:app --reload
```

```bash
streamlit run app.py
```

Open the Streamlit URL it prints, type a prompt, pick a priority, hit
Route.

## Files

| File | Purpose |
|---|---|
| `router_core.py` | Model registry, classification rules, routing logic, SQLite logging |
| `api.py` | FastAPI wrapper — `POST /route`, `GET /health` |
| `app.py` | Streamlit demo UI |
| `router_v0.py`, `router_v1.py` | Earlier standalone-script versions, kept for reference |

## What's next

This is the hackathon MVP (rule-based routing). The planned next phase
replaces the hand-written classification rules with a model trained on
the logged request history, plus multi-objective cost/latency/quality
scoring.
