import argparse, json
from .agent import run
p = argparse.ArgumentParser(description="BillPilot demo")
p.add_argument("claim"); p.add_argument("--months", type=int, default=1)
p.add_argument("--approve", action="store_true", help="human approves: create+send PayPal SANDBOX invoice")
a = p.parse_args()
print(json.dumps(run(json.load(open(a.claim)), a.months, a.approve), indent=2))
