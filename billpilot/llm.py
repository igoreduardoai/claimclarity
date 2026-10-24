"""Free LLM backends only: OpenRouter (:free models), Groq free tier, Google Gemini free tier, or local Ollama.
Falls back to a deterministic template when no backend is configured, so the demo
always runs at $0."""
import json, os, urllib.request

SYSTEM = ("You explain medical bills to patients in plain English (6th-grade level). "
          "Only use the dollar amounts given to you, formatted like $1,234.56. Never give medical advice. "
          "Never include IDs, SSNs or dates of birth. Be kind and brief (<=120 words). "
          "End by stating the total the patient owes and that payment plans are available.")

def _post(url, body, headers):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", **headers})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())

def complete(prompt: str) -> tuple[str, str]:
    if os.getenv("OPENROUTER_API_KEY"):
        models = os.getenv("OPENROUTER_MODELS", "google/gemma-4-31b-it:free,nvidia/nemotron-3-super-120b-a12b:free,google/gemma-4-26b-a4b-it:free").split(",")
        for m in models:
            if not m.endswith(":free"): continue  # free models only, by policy
            try:
                r = _post("https://openrouter.ai/api/v1/chat/completions",
                          {"model": m, "temperature": 0,
                           "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]},
                          {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
                txt = r["choices"][0]["message"]["content"]
                if txt: return txt, f"openrouter:{m}"
            except Exception:
                continue
    if os.getenv("GROQ_API_KEY"):
        r = _post("https://api.groq.com/openai/v1/chat/completions",
                  {"model": os.getenv("GROQ_MODEL", "llama-3.1-8b-instant"), "temperature": 0,
                   "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]},
                  {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"})
        return r["choices"][0]["message"]["content"], "groq"
    if os.getenv("GEMINI_API_KEY"):
        m = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        r = _post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={os.environ['GEMINI_API_KEY']}",
                  {"systemInstruction": {"parts": [{"text": SYSTEM}]}, "contents": [{"parts": [{"text": prompt}]}],
                   "generationConfig": {"temperature": 0}}, {})
        return r["candidates"][0]["content"]["parts"][0]["text"], "gemini"
    if os.getenv("OLLAMA_MODEL"):
        r = _post(os.getenv("OLLAMA_URL", "http://localhost:11434") + "/api/chat",
                  {"model": os.environ["OLLAMA_MODEL"], "stream": False,
                   "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": prompt}]}, {})
        return r["message"]["content"], "ollama"
    return None, "template"
