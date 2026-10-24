"""Build a static replay page (index.html) from a recorded journey run. No model calls happen in the page."""
import json, html, os, statistics as st, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN = sys.argv[1] if len(sys.argv) > 1 else "results/journey-20261024-121125.json"
d = json.load(open(os.path.join(ROOT, RUN)))
runs = d["runs"]
pick = {}
for r in runs: pick.setdefault(r["document"], r)
cases = []
for key, doc, title in [("match", "eob_er_complete.txt", "1 · Amounts match"), ("mismatch", "eob_er_mismatch.txt", "2 · Mismatch flagged"), ("missing", "eob_primary_missing.txt", "3 · Missing information")]:
    r = pick[doc]
    r = {k: v for k, v in r.items() if k != "raw_extraction"}
    r["doc_text"] = open(os.path.join(ROOT, "docs", doc)).read()
    cases.append({"key": key, "title": title, "run": r})
lat = [r["latency_s"] for r in runs]; cost = [r["cost_usd"] for r in runs]
ok = sum(1 for r in runs if r["score"]["status_ok"] and r["score"].get("cross_ok", r["score"].get("missing_ok")))
summary = {"runs": len(runs), "ok": ok, "median_latency": round(st.median(lat), 1), "mean_cost": round(st.mean(cost), 5),
           "total_cost": round(sum(cost), 4), "run_file": os.path.basename(RUN)}
tpl = open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "template.html")).read()
out = tpl.replace("/*DATA*/null", json.dumps({"cases": cases, "summary": summary}))
open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), "w").write(out)
print("wrote index.html", summary)
