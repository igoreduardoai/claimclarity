"""Offline tests for journey.py with a mocked extractor (no network)."""
import json
from journey import journey
def mk(ex, draft="Your total is $551.00. Payment plans are available."):
    def f(model, sys_, user):
        if sys_.startswith("Extract"): return json.dumps(ex)
        return draft if "Explain" in sys_ else json.dumps({"ok": True, "problems": []})
    return f
F = lambda v, q: {"value": v, "evidence": q}
base = {"deductible_remaining": F(500, "deductible remaining before this claim: $500.00"), "coinsurance": F(0.2, "Coinsurance after deductible: 20%"),
        "copay": F(0, "Copay: $0.00"), "oop_remaining": F(3000, "Out-of-pocket maximum remaining: $3,000.00"),
        "stated_patient_responsibility": F(601, "Patient responsibility (amount you may owe the provider): $601.00"),
        "lines": [{"code": "99284", "description": "ER", "billed": 1450, "allowed": 620, "evidence": "Emergency room visit (moderate) 99284 $1,450.00 $620.00"},
                  {"code": "71046", "description": "X-ray", "billed": 380, "allowed": 95, "evidence": "Chest X-ray, 2 views 71046 $380.00 $95.00"},
                  {"code": "93005", "description": "ECG", "billed": 210, "allowed": 40, "evidence": "ECG tracing 93005 $210.00 $40.00"}]}
R = []
r = journey("docs/eob_er_mismatch.txt", mk(base)); R.append(r["cross_check"]["result"] == "mismatch" and r["cross_check"]["stated"]["evidence"]["line"] == 10)
bad = json.loads(json.dumps(base)); bad["coinsurance"] = F(0.1, "Coinsurance after deductible: 10%")   # quote not in doc
r = journey("docs/eob_er_mismatch.txt", mk(bad)); R.append(r["status"] == "incomplete" and any(m["field"] == "coinsurance" for m in r["missing"]))
r = journey("docs/eob_er_mismatch.txt", lambda *a: "not json"); R.append(r["status"] == "extraction_failed")
print(R, f"{sum(R)}/{len(R)} passed")
