# ClaimClarity: every conclusion shows where it came from

**Live demo (replay of a recorded run):** https://igoreduardoai.github.io/claimclarity/
Nebius × NVIDIA Global AI Hackathon · MIT license · synthetic data only

A synthetic Explanation of Benefits (EOB) goes in. NVIDIA Nemotron extracts each field **with a verbatim quote**; code checks that every quote really is in the document (line + character span), recomputes what the patient owes with a deterministic ledger, and cross-checks the amount the EOB states. The result is a conclusion plus the evidence behind it, or an exact list of what's missing. It explains and flags; a person decides what to do.

## Where Nemotron and Nebius Token Factory are used
All model calls go to **Nebius Token Factory** (`https://api.tokenfactory.nebius.com/v1`, OpenAI-compatible; `nemotron.py`):
| Step | Model | File |
|---|---|---|
| Extract EOB fields + verbatim evidence quotes | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | `journey.py` |
| Write the plain-English patient explanation | `nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B` | `nemotron.py` |
| Audit the explanation against the ledger (JSON verdict) | `nvidia/nemotron-3-super-120b-a12b` | `nemotron.py` |

Code (not a model) does the math (`billpilot/billing.py`), verifies quotes (`journey.py`), and runs regex guardrails (`billpilot/guardrails.py`). If any check fails, the patient gets a safe template built from the ledger.

## Recorded results (2026-10-24, Nebius Token Factory)
- Document journey (`results/journey-20261024-121125.json`): **9/9** correct outcomes over 3 EOBs × 3 runs: a match ($551.00), a mismatch flagged (EOB states $601.00 on line 10; its own terms give $551.00), and an incomplete EOB that names the missing fields (coinsurance, out-of-pocket max). Median 16.0 s, mean $0.00087 per document.
- An earlier run (`results/journey-20261024-120852.json`) got 6/9 before two fixes (larger extraction token budget; whitespace-tolerant quote matching). It's kept for transparency.
- Pipeline eval (`results/live-20261024-120400.json`), 10 claims: 10/10 Nemotron explanations passed audit + guardrails; 9.8 s and $0.00050 per explanation. Auditor stress test: Nemotron Super flagged 20/20 injected errors with 1 false alarm in 10 correct texts; the regex guardrails alone missed 1/20.

## Run it
```bash
python3 test_pipeline.py && python3 test_journey.py               # 8 offline tests (mocked models)
export NEBIUS_API_KEY=...                                         # your Token Factory key
python3 journey.py docs/eob_er_mismatch.txt                       # document -> evidence -> cross-check
python3 run_eval.py && python3 run_journey.py                     # live evals -> results/ (BUDGET_USD caps spend)
python3 site/build.py results/<run>.json                          # rebuild the static replay page
```
Python 3 standard library only.

## Limitations
- Synthetic claims and plain-text EOBs only; no PDF/scan parsing yet.
- Tested on 3 EOB layouts and 10 claims; small samples, not a benchmark.
- The extractor can fail (truncated or malformed JSON); the system then says so and shows no conclusion. No automatic retry.
- English only. Guardrails check amounts and the total, not every phrase.
- The demo page replays a recorded run; it does not call a model live.
- Not medical, legal, or billing advice.
