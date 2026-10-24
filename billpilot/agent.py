"""BillPilot agent: claim -> deterministic math -> LLM explanation -> guardrails ->
PayPal sandbox invoice draft -> human approval -> send."""
from .billing import Plan, Line, compute, payment_plan
from .guardrails import check
from . import llm
from .paypal import PayPal

def template_explanation(calc, months=None):
    owed = [l for l in calc["lines"] if l["patient_owes"] > 0]
    parts = [f"{l['description']}: you owe ${l['patient_owes']:,.2f}" for l in owed]
    s = "Here is what your visit costs you after insurance. " + "; ".join(parts) + ". "
    s += f"Your total is ${calc['total']:,.2f}. Payment plans are available"
    if months: s += f" ({months} monthly payments)"
    return s + "."

def run(claim: dict, months: int = 1, approve: bool = False, pp: PayPal | None = None):
    plan = Plan(**claim["plan"])
    lines = [Line(**l) for l in claim["lines"]]
    calc = compute(lines, plan)
    inst = payment_plan(calc["total"], months) if calc["total"] > 0 else []
    amounts = [calc["total"], *[l["patient_owes"] for l in calc["lines"]], *[l["allowed"] for l in calc["lines"]],
               *[l["billed"] for l in calc["lines"]], *inst]
    amounts += [l["insurer_pays"] for l in calc["lines"]]
    roles = {"insurer_pays": [l["insurer_pays"] for l in calc["lines"]],
             "allowed": [l["allowed"] for l in calc["lines"]],
             "patient": [calc["total"], *[l["patient_owes"] for l in calc["lines"]], *inst]}
    facts = {"amounts": amounts, "total": calc["total"], "must_mention_total": True, "roles": roles}
    prompt = ("Explain this bill. 'Allowed' is the price the insurer agreed to, NOT what it paid. Line items: " +
              "; ".join(f"{l['description']}: billed ${l['billed']:,.2f}, allowed ${l['allowed']:,.2f}, insurance paid ${l['insurer_pays']:,.2f}, you owe ${l['patient_owes']:,.2f}" for l in calc["lines"]) +
              f". Total patient owes ${calc['total']:,.2f}." + (f" Plan: {months} payments of about ${inst[0]:,.2f}." if months > 1 and inst else ""))
    text, backend, violations = None, "template", []
    try:
        text, backend = llm.complete(prompt)
    except Exception as e:
        backend = f"error:{type(e).__name__}"
    if text:
        violations = check(text, facts)
    if not text or violations:
        text = template_explanation(calc, months if months > 1 else None)  # safe fallback
        backend += "+fallback" if violations else ""
    pp = pp or PayPal()
    first = [{"description": f"Patient responsibility (payment 1 of {months})" if months > 1 else l["description"],
              "patient_owes": inst[0] if months > 1 else l["patient_owes"]} for l in (calc["lines"][:1] if months > 1 else calc["lines"])]
    body = pp.invoice_body(claim["patient_email"], first, text, installment=(1, months) if months > 1 else None)
    result = {"calc": calc, "installments": inst, "explanation": text, "llm_backend": backend,
              "violations_caught": violations, "invoice_draft": body, "status": "awaiting_human_approval"}
    if approve and calc["total"] > 0:
        created = pp.create_invoice(body)
        result["paypal_create"] = created
        inv_id = created.get("id") or (created.get("href", "").rsplit("/", 1)[-1] if created.get("href") else None)
        result["paypal_send"] = pp.send_invoice(inv_id) if inv_id else created
        result["status"] = "sent_sandbox" if not pp.dry else "dry_run"
    return result
