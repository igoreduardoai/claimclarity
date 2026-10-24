"""Tiny stdlib web UI: python -m billpilot.web  -> http://localhost:8000"""
import json, html
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs
from .agent import run
CLAIMS = sorted((Path(__file__).parent.parent / "data").glob("*.json"))

def page(body):
    return f"""<!doctype html><meta charset=utf-8><title>BillPilot</title>
<style>body{{font-family:system-ui;max-width:860px;margin:2rem auto;padding:0 1rem}}table{{border-collapse:collapse;width:100%}}
td,th{{border-bottom:1px solid #ddd;padding:6px;text-align:left}}.box{{background:#f5f7fb;padding:1rem;border-radius:8px}}
button{{background:#0070ba;color:#fff;border:0;padding:.6rem 1rem;border-radius:6px}}</style>
<h1>BillPilot <small style="color:#888">patient billing agent · PayPal sandbox</small></h1>{body}"""

class H(BaseHTTPRequestHandler):
    def _send(self, s):
        self.send_response(200); self.send_header("Content-Type", "text/html"); self.end_headers(); self.wfile.write(s.encode())
    def do_GET(self):
        opts = "".join(f"<option>{c.name}</option>" for c in CLAIMS)
        self._send(page(f"""<form method=post><label>Claim <select name=claim>{opts}</select></label>
<label> Payments <input name=months type=number value=1 min=1 max=24></label>
<label><input type=checkbox name=approve> I (billing staff) approve sending</label> <button>Run agent</button></form>"""))
    def do_POST(self):
        q = parse_qs(self.rfile.read(int(self.headers["Content-Length"])).decode())
        claim = json.load(open(Path(__file__).parent.parent / "data" / Path(q["claim"][0]).name))
        r = run(claim, int(q.get("months", ["1"])[0]), "approve" in q)
        rows = "".join(f"<tr><td>{html.escape(l['description'])}</td><td>${l['billed']:,.2f}</td><td>${l['allowed']:,.2f}</td><td><b>${l['patient_owes']:,.2f}</b></td></tr>" for l in r["calc"]["lines"])
        self._send(page(f"""<a href=/>← back</a><h2>Total you owe: ${r['calc']['total']:,.2f}</h2>
<table><tr><th>Service</th><th>Billed</th><th>Insurance allowed</th><th>You owe</th></tr>{rows}</table>
<h3>Plain-English explanation <small>({html.escape(r['llm_backend'])})</small></h3><div class=box>{html.escape(r['explanation'])}</div>
<p>Installments: {', '.join(f'${x:,.2f}' for x in r['installments'])}</p>
<p>Guardrail violations caught: {html.escape(str(r['violations_caught']) or 'none')}</p>
<h3>Status: {r['status']}</h3><pre>{html.escape(json.dumps(r.get('paypal_create', r['invoice_draft']), indent=2))}</pre>"""))

if __name__ == "__main__":
    print("http://localhost:8000"); HTTPServer(("0.0.0.0", 8000), H).serve_forever()
