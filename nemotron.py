"""Two-model Nemotron pipeline on Nebius Token Factory (OpenAI-compatible).
Nano writes the patient explanation fast; Super audits it against the ledger.
Deterministic guardrails still run last. Without NEBIUS_API_KEY no model is called (tests/offline -> safe template)."""
import json, os, time, urllib.request
BASE = os.getenv("NEBIUS_BASE_URL", "https://api.tokenfactory.nebius.com/v1")
WRITER = os.getenv("NEMOTRON_WRITER", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B")   # id verified via /v1/models 2026-10-24
AUDITOR = os.getenv("NEMOTRON_AUDITOR", "nvidia/nemotron-3-super-120b-a12b")     # id verified via /v1/models 2026-10-24
# USD per 1M tokens (input, output), from Token Factory /v1/models?verbose=true on 2026-10-24
PRICES = {"nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B": (0.06, 0.24), "nvidia/nemotron-3-super-120b-a12b": (0.30, 0.90)}
MAX_TOKENS = int(os.getenv("NEMOTRON_MAX_TOKENS", "2048"))
CALLS = []   # per-call telemetry: model, latency_s, prompt/completion tokens, cost_usd

def chat(model, system, user, max_tokens=None):
    key = os.getenv("NEBIUS_API_KEY")
    if not key: return None
    body = {"model": model, "temperature": 0, "max_tokens": max_tokens or MAX_TOKENS,
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    t = time.time()
    r = urllib.request.urlopen(urllib.request.Request(BASE + "/chat/completions", json.dumps(body).encode(),
                               {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}), timeout=120)
    d = json.loads(r.read())
    u = d.get("usage") or {}
    pi, po = PRICES.get(model, (0, 0))
    pt, ct = u.get("prompt_tokens", 0), u.get("completion_tokens", 0)
    CALLS.append({"model": model, "latency_s": round(time.time() - t, 3), "prompt_tokens": pt, "completion_tokens": ct,
                  "cost_usd": (pt * pi + ct * po) / 1e6, "finish_reason": d["choices"][0].get("finish_reason")})
    # Nemotron 3 returns its reasoning in a separate field; only the final answer (content) is used.
    return (d["choices"][0]["message"].get("content") or "").strip() or None

WRITER_SYS = ("Explain this medical bill to the patient in plain English (<=120 words). Use ONLY the dollar amounts given, "
              "formatted like $1,234.56. No medical advice, no IDs. End with the total and that payment plans exist.")
AUDITOR_SYS = ("You audit a patient bill explanation against a ledger. Reply with JSON only: "
               '{"ok": true|false, "problems": ["..."]}. Flag any amount not in the ledger, wrong total, medical advice, or confusing claims.')

def audit(ledger_text, draft, llm=chat):
    raw = llm(AUDITOR, AUDITOR_SYS, f"LEDGER:\n{ledger_text}\n\nEXPLANATION:\n{draft}") or "{}"
    try:
        a = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
        if not isinstance(a, dict) or not isinstance(a.get("ok"), bool): raise ValueError
        return a
    except Exception: return {"ok": False, "problems": ["auditor returned non-JSON"]}

def explain_and_audit(ledger_text, writer=chat):
    draft = writer(WRITER, WRITER_SYS, ledger_text)
    if not draft: return None, {"ok": None, "problems": ["no NEBIUS_API_KEY: offline mode"]}
    return draft, audit(ledger_text, draft, writer)
