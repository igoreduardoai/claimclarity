"""PayPal REST **sandbox only** client (Invoicing v2). Without credentials it runs in
dry-run mode and returns the exact payload it would send."""
import base64, json, os, urllib.request, uuid

BASE = "https://api-m.sandbox.paypal.com"   # hard-coded sandbox; never live

class PayPal:
    def __init__(self):
        self.cid, self.secret = os.getenv("PAYPAL_CLIENT_ID"), os.getenv("PAYPAL_CLIENT_SECRET")
        self.dry = not (self.cid and self.secret)
        self._tok = None

    def _token(self):
        if not self._tok:
            auth = base64.b64encode(f"{self.cid}:{self.secret}".encode()).decode()
            req = urllib.request.Request(BASE + "/v1/oauth2/token", b"grant_type=client_credentials",
                                         {"Authorization": f"Basic {auth}"})
            with urllib.request.urlopen(req, timeout=30) as r:
                self._tok = json.loads(r.read())["access_token"]
        return self._tok

    def _call(self, method, path, body=None):
        if self.dry:
            return {"dry_run": True, "method": method, "path": path, "body": body}
        req = urllib.request.Request(BASE + path, json.dumps(body).encode() if body else None, method=method,
                                     headers={"Authorization": f"Bearer {self._token()}", "Content-Type": "application/json",
                                              "PayPal-Request-Id": str(uuid.uuid4())})
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read()
            return json.loads(txt) if txt else {"status": r.status}

    def invoice_body(self, patient_email, items, note, due_days=30, installment=None):
        body = {
            "detail": {"currency_code": "USD", "note": note[:4000],
                       "payment_term": {"term_type": f"NET_{due_days}" if due_days in (10, 15, 30, 45, 60, 90) else "NET_30"}},
            "primary_recipients": [{"billing_info": {"email_address": patient_email}}],
            "items": [{"name": i["description"][:200], "quantity": "1",
                       "unit_amount": {"currency_code": "USD", "value": f"{i['patient_owes']:.2f}"}} for i in items
                      if i["patient_owes"] > 0],
        }
        if installment:
            body["detail"]["reference"] = f"Installment {installment[0]} of {installment[1]}"
        return body

    def create_invoice(self, body):
        return self._call("POST", "/v2/invoicing/invoices", body)

    def send_invoice(self, invoice_id):
        # Sandbox send: no real email/money. Still requires human approval in the agent.
        return self._call("POST", f"/v2/invoicing/invoices/{invoice_id}/send", {"send_to_recipient": True})
