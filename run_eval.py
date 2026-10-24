"""Live eval on Nebius Token Factory. Part A: full pipeline (Nano writer -> Super auditor -> guardrails) on every
synthetic claim. Part B: auditor-only test with a known-correct explanation and two injected errors per claim
(inflated total; invented $50.00 refund). Writes results/live-<ts>.json. Hard budget stop via BUDGET_USD."""
import glob, json, os, statistics, sys, time
import nemotron
from nemotron import CALLS, AUDITOR, audit
from pipeline import run, ledger_of
from billpilot.agent import template_explanation
from billpilot.guardrails import check
BUDGET = float(os.getenv("BUDGET_USD", "0.50"))
spent = lambda: sum(c["cost_usd"] for c in CALLS)
def guard():
    if spent() > BUDGET: sys.exit(f"BUDGET STOP at ${spent():.4f}")
if not os.getenv("NEBIUS_API_KEY"): sys.exit("NEBIUS_API_KEY not set")
claims = sorted(glob.glob("data/*.json")); out = {"writer": nemotron.WRITER, "auditor": AUDITOR, "base": nemotron.BASE, "A": [], "B": []}
for f in claims:
    guard(); n0 = len(CALLS); t = time.time()
    r = run(json.load(open(f)))
    out["A"].append({"claim": os.path.basename(f), **r, "latency_s": round(time.time() - t, 3), "calls": CALLS[n0:]})
    print("A", os.path.basename(f), r["source"], r["auditor"].get("ok"), r["guardrail_violations"], f"${spent():.4f}", flush=True)
for f in claims:
    calc, ledger = ledger_of(json.load(open(f))); good = template_explanation(calc)
    T = calc["total"]; wrong = T + 50
    cases = [("correct", good, True),
             ("inflated_total", good.replace(f"Your total is ${T:,.2f}", f"Your total is ${wrong:,.2f}"), False),
             ("invented_refund", good + " You will also get a $50.00 refund from your plan.", False)]
    amounts = [T] + [l[k] for l in calc["lines"] for k in ("patient_owes", "allowed", "billed")]
    for name, text, expect_ok in cases:
        guard(); n0 = len(CALLS)
        a = audit(ledger, text)
        g = check(text, {"amounts": amounts, "total": T, "must_mention_total": True})
        out["B"].append({"claim": os.path.basename(f), "case": name, "expect_ok": expect_ok, "auditor_ok": a.get("ok"),
                         "problems": a.get("problems"), "guardrails": g, "calls": CALLS[n0:]})
        print("B", os.path.basename(f), name, "auditor_ok=", a.get("ok"), "guard=", g, f"${spent():.4f}", flush=True)
out["calls"] = CALLS; out["total_cost_usd"] = spent()
os.makedirs("results", exist_ok=True); p = f"results/live-{time.strftime('%Y%m%d-%H%M%S')}.json"
json.dump(out, open(p, "w"), indent=1); print("saved", p, f"total ${spent():.4f}")
