"""Safety checks applied to every LLM output before a patient sees it."""
import re

MEDICAL_ADVICE = re.compile(r"\b(you should (stop|start|take)|dosage|diagnos(e|is) you|skip (your )?(treatment|medication))\b", re.I)
PHI = [re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),          # SSN
       re.compile(r"\b\d{9,}\b"),                     # long member/account ids
       re.compile(r"\b(DOB|date of birth)\b", re.I)]
MONEY = re.compile(r"\$\s?([\d,]+\.\d{2})")
# Role checks: an amount attributed to the insurer must be an insurer payment, not the allowed amount.
ROLES = {
    "insurer_pays": re.compile(r"\b(?:insurance|insurer|your plan|the plan)\s+(?:paid|pays|will pay|covered|covers|picked up)\s+(?:about\s+)?\$\s?([\d,]+\.\d{2})", re.I),
    "allowed": re.compile(r"\b(?:allowed|approved)\s+(?:amount\s+)?(?:of\s+|was\s+|is\s+)?\$\s?([\d,]+\.\d{2})", re.I),
    "patient": re.compile(r"\byou\s+(?:owe|pay|will pay)\s+(?:about\s+)?\$\s?([\d,]+\.\d{2})", re.I),
}

def check(text: str, facts: dict):
    """Return list of violations. facts = numbers the text is allowed to cite."""
    v = []
    if MEDICAL_ADVICE.search(text): v.append("medical_advice")
    if any(p.search(text) for p in PHI): v.append("phi_leak")
    allowed = {f"{x:,.2f}" for x in facts.get("amounts", [])}
    for m in MONEY.findall(text):
        if m not in allowed: v.append(f"unsupported_amount:{m}")
    for role, rx in ROLES.items():
        ok = facts.get("roles", {}).get(role)
        if ok is None: continue
        okset = {f"{x:,.2f}" for x in ok}
        for m in rx.findall(text):
            if m not in okset: v.append(f"wrong_role:{role}:{m}")
    if facts.get("must_mention_total") and f"{facts['total']:,.2f}" not in text:
        v.append("missing_total")
    return v
