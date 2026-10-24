"""ClaimClarity: deterministic ledger -> Nemotron Nano writer -> Nemotron Super auditor -> regex guardrails."""
import json, sys
from billpilot.billing import Plan, Line, compute
from billpilot.guardrails import check
from billpilot.agent import template_explanation
from nemotron import explain_and_audit, chat

def ledger_of(claim):
    calc = compute([Line(**l) for l in claim["lines"]], Plan(**claim["plan"]))
    ledger = "\n".join(f"{l['description']}: billed ${l['billed']:,.2f}, allowed ${l['allowed']:,.2f}, patient owes ${l['patient_owes']:,.2f}" for l in calc["lines"]) + f"\nTOTAL patient owes ${calc['total']:,.2f}"
    return calc, ledger

def run(claim, writer=chat):
    calc, ledger = ledger_of(claim)
    draft, audit = explain_and_audit(ledger, writer)
    amounts = [calc["total"]] + [l[k] for l in calc["lines"] for k in ("patient_owes", "allowed", "billed")]
    v = check(draft, {"amounts": amounts, "total": calc["total"], "must_mention_total": True}) if draft else ["no_draft"]
    final, source = (draft, "nemotron") if draft and not v and audit.get("ok") else (template_explanation(calc), "safe-template")
    return {"total": calc["total"], "explanation": final, "source": source, "auditor": audit, "guardrail_violations": v}

if __name__ == "__main__":
    print(json.dumps(run(json.load(open(sys.argv[1] if len(sys.argv) > 1 else "data/claim_er_visit.json"))), indent=1))
