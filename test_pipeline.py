"""Offline tests with mocked Nemotron responses."""
import json
from pipeline import run
C = json.load(open("data/claim_er_visit.json"))
def mock(good_draft, audit):
    def f(model, sys_, user): return good_draft if "Explain" in sys_ else json.dumps(audit)
    return f
R = []
r = run(C, mock("Your ER visit total is $551.00. Payment plans are available.", {"ok": True, "problems": []})); R.append(r["source"] == "nemotron")
r = run(C, mock("You owe $551.00 but get a $50.00 refund.", {"ok": True, "problems": []})); R.append(r["source"] == "safe-template" and r["guardrail_violations"])
r = run(C, mock("Your total is $551.00. Payment plans are available.", {"ok": False, "problems": ["confusing"]})); R.append(r["source"] == "safe-template")
r = run(C, mock("Total $551.00.", "notjson")); R.append(r["source"] == "safe-template")
r = run(C, lambda *a: None); R.append(r["source"] == "safe-template" and r["total"] == 551.0)
print(R, f"{sum(map(bool,R))}/{len(R)} passed")
