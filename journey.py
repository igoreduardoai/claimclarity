"""One end-to-end journey: EOB document -> Nemotron Nano extracts fields WITH verbatim evidence quotes ->
code verifies every quote exists in the document (char span + line) and contains the value -> BillPilot ledger
recomputes patient responsibility -> cross-check against the amount the document states -> Nano writes,
Super audits, guardrails gate. Every conclusion carries its evidence span; missing inputs are listed by name.
Not autonomous: it explains and flags; a person decides what to do with a mismatch."""
import json, os, re, sys, time
from nemotron import chat, WRITER, CALLS
from pipeline import run
REQ = ["deductible_remaining", "coinsurance", "copay", "oop_remaining"]
EXTRACT_SYS = ("Extract fields from this Explanation of Benefits. Reply with JSON only, no prose. Schema: "
  '{"deductible_remaining": F, "coinsurance": F, "copay": F, "oop_remaining": F, "stated_patient_responsibility": F, '
  '"lines": [{"code": str, "description": str, "billed": number, "allowed": number, "evidence": str}]} where '
  'F = {"value": number|null, "evidence": str|null}. coinsurance is a fraction (20% -> 0.2). "evidence" must be copied '
  "VERBATIM from the document (exact characters). If a field is not explicitly stated, use value null and evidence null. "
  "Never guess or infer a missing value.")

def span(doc, quote):
    """Locate the quote in the document. Exact characters, except runs of whitespace may differ (tables)."""
    if not quote or not quote.strip(): return None
    m = re.search(r"\s+".join(map(re.escape, quote.split())), doc)
    if not m: return None
    return {"start": m.start(), "end": m.end(), "line": doc.count("\n", 0, m.start()) + 1, "text": m.group(0)}

def money_in(x, q):
    return q is not None and (f"{x:,.2f}" in q or (float(x).is_integer() and f"${int(x):,}" in q))

def verify(doc, ex):
    fields, missing, rejected = {}, [], []
    for k in REQ + ["stated_patient_responsibility"]:
        f = ex.get(k) or {}; v, q = f.get("value"), f.get("evidence")
        if v is None:
            (missing if k in REQ else rejected).append({"field": k, "why": "not stated in the document"}); continue
        sp = span(doc, q)
        ok = sp and (f"{round(v*100):g}%" in q if k == "coinsurance" else money_in(v, q))
        if ok: fields[k] = {"value": v, "evidence": sp}
        else: (missing if k in REQ else rejected).append({"field": k, "why": "model value/quote not found verbatim in document", "model_value": v})
    lines = []
    for l in ex.get("lines") or []:
        sp = span(doc, l.get("evidence"))
        if sp and l.get("code", "") in sp["text"] and money_in(l["billed"], sp["text"]) and money_in(l["allowed"], sp["text"]):
            lines.append({**{k: l[k] for k in ("code", "description", "billed", "allowed")}, "evidence": sp})
        else: rejected.append({"field": f"line {l.get('code')}", "why": "line quote/amounts not found verbatim in document"})
    if not lines: missing.append({"field": "service lines", "why": "no verifiable service line"})
    return fields, lines, missing, rejected

def journey(path, llm=chat):
    doc = open(path).read(); t0 = time.time(); n0 = len(CALLS)
    raw = (llm(WRITER, EXTRACT_SYS, doc, max_tokens=6144) if llm is chat else llm(WRITER, EXTRACT_SYS, doc)) or "{}"
    try: ex = json.loads(raw[raw.find("{"): raw.rfind("}") + 1])
    except Exception: ex = {"_error": "extractor returned malformed or truncated JSON (fail closed, no retry)"}
    fields, lines, missing, rejected = verify(doc, ex)
    res = {"document": os.path.basename(path), "extractor_error": ex.get("_error"), "raw_extraction": raw, "extracted_fields": fields, "extracted_lines": lines, "rejected": rejected}
    if ex.get("_error"):
        res.update(status="extraction_failed", conclusion="Could not read this document reliably; no conclusion shown. Please retry or review manually.")
    elif missing:
        res.update(status="incomplete", conclusion="Cannot compute what you owe from this document. Missing: " +
                   ", ".join(m["field"] for m in missing) + ".", missing=missing)
    else:
        claim = {"plan": {k: fields[k]["value"] for k in REQ}, "lines": [{k: l[k] for k in ("code", "description", "billed", "allowed")} for l in lines]}
        r = run(claim, llm); stated = fields.get("stated_patient_responsibility")
        if stated is None: check = {"result": "no_stated_amount", "detail": "Document does not state a patient responsibility to cross-check."}
        elif abs(stated["value"] - r["total"]) < 0.005: check = {"result": "match", "stated": stated, "recomputed": r["total"]}
        else: check = {"result": "mismatch", "stated": stated, "recomputed": r["total"], "difference": round(stated["value"] - r["total"], 2)}
        res.update(status="complete", recomputed_total=r["total"], cross_check=check, explanation=r["explanation"],
                   explanation_source=r["source"], auditor=r["auditor"], guardrail_violations=r["guardrail_violations"],
                   conclusion={"match": f"The document's ${r['total']:,.2f} matches the recomputed amount.",
                               "mismatch": f"The document states ${stated['value']:,.2f} (line {stated['evidence']['line']}) but the plan terms and lines in the same document give ${r['total']:,.2f}. Ask the insurer to explain the ${abs(check.get('difference',0)):,.2f} difference." if stated else "",
                               "no_stated_amount": f"Recomputed amount: ${r['total']:,.2f}; the document states none to compare."}[check["result"]])
    res["calls"] = CALLS[n0:]; res["latency_s"] = round(time.time() - t0, 3); res["cost_usd"] = sum(c["cost_usd"] for c in res["calls"])
    return res

if __name__ == "__main__":
    print(json.dumps(journey(sys.argv[1] if len(sys.argv) > 1 else "docs/eob_er_complete.txt"), indent=1))
