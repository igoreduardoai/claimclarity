"""Deterministic patient-responsibility calculator. The LLM never does the math."""
from dataclasses import dataclass, asdict

@dataclass
class Plan:
    deductible_remaining: float
    coinsurance: float          # patient share after deductible, e.g. 0.2
    copay: float                # flat per-visit copay
    oop_remaining: float        # out-of-pocket max remaining

@dataclass
class Line:
    code: str
    description: str
    billed: float
    allowed: float
    covered: bool = True

def compute(lines, plan: Plan):
    """Return per-line breakdown and total patient responsibility (USD, cents-rounded)."""
    ded = plan.deductible_remaining
    oop = plan.oop_remaining
    out, total = [], 0.0
    copay_applied = False
    for ln in lines:
        if not ln.covered:
            owe = ln.allowed
            reason = "not covered by plan"
        else:
            owe = 0.0
            if not copay_applied and plan.copay:
                owe += min(plan.copay, ln.allowed); copay_applied = True
            remaining = ln.allowed - owe
            d = min(ded, remaining); ded -= d; owe += d; remaining -= d
            owe += remaining * plan.coinsurance
            owe = min(owe, oop); oop -= owe
            reason = "copay/deductible/coinsurance"
        owe = round(owe, 2)
        total += owe
        out.append({**asdict(ln), "patient_owes": owe, "insurer_pays": round(ln.allowed - owe, 2) if ln.covered else 0.0,
                    "writeoff": round(ln.billed - ln.allowed, 2), "reason": reason})
    return {"lines": out, "total": round(total, 2)}

def payment_plan(total: float, months: int):
    """Split into equal monthly installments; last one absorbs rounding. No interest."""
    if months < 1 or months > 24:
        raise ValueError("months must be 1-24")
    base = round(total / months, 2)
    parts = [base] * (months - 1) + [round(total - base * (months - 1), 2)]
    return parts
