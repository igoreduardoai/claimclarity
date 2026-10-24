"""Live run of journey.py on the 3 synthetic EOB documents, scored against hand-written ground truth."""
import json, os, sys, time
from journey import journey
from nemotron import CALLS
if not os.getenv("NEBIUS_API_KEY"): sys.exit("NEBIUS_API_KEY not set")
L = {"99284": (1450, 620), "71046": (380, 95), "93005": (210, 40)}
TRUTH = {
 "docs/eob_er_complete.txt": {"status": "complete", "cross": "match", "total": 551.0, "fields": {"deductible_remaining": 500, "coinsurance": 0.2, "copay": 0, "oop_remaining": 3000, "stated_patient_responsibility": 551}, "lines": L},
 "docs/eob_er_mismatch.txt": {"status": "complete", "cross": "mismatch", "total": 551.0, "fields": {"deductible_remaining": 500, "coinsurance": 0.2, "copay": 0, "oop_remaining": 3000, "stated_patient_responsibility": 601}, "lines": L},
 "docs/eob_primary_missing.txt": {"status": "incomplete", "missing": {"coinsurance", "oop_remaining"}, "fields": {"deductible_remaining": 0, "copay": 30}, "lines": {"99213": (220, 110), "80053": (150, 18.5)}}}
out = []
REPS = int(os.getenv('REPS', '1'))
for p, t in [x for x in TRUTH.items() for _ in range(REPS)]:
    r = journey(p); f = r["extracted_fields"]
    fok = sum(1 for k, v in t["fields"].items() if k in f and abs(f[k]["value"] - v) < 1e-6)
    lok = sum(1 for l in r["extracted_lines"] if l["code"] in t["lines"] and (l["billed"], l["allowed"]) == t["lines"][l["code"]])
    score = {"status_ok": r["status"] == t["status"], "fields_correct": f"{fok}/{len(t['fields'])}", "lines_correct": f"{lok}/{len(t['lines'])}",
             "spans_verified": len(f) + len(r["extracted_lines"]), "unverified_rejected": len([x for x in r["rejected"] if "verbatim" in x["why"]])}
    if t["status"] == "complete": score.update(cross_ok=r.get("cross_check", {}).get("result") == t["cross"], total_ok=r.get("recomputed_total") == t["total"])
    else: score["missing_ok"] = {m["field"] for m in r.get("missing", [])} >= t["missing"]
    r["score"] = score; out.append(r)
    print(p, r["status"], score, "|", r["conclusion"], f"| {r['latency_s']}s ${r['cost_usd']:.5f}", flush=True)
os.makedirs("results", exist_ok=True); fn = f"results/journey-{time.strftime('%Y%m%d-%H%M%S')}.json"
json.dump({"runs": out, "total_cost_usd": sum(c["cost_usd"] for c in CALLS)}, open(fn, "w"), indent=1)
print("saved", fn, "total", sum(c["cost_usd"] for c in CALLS))
