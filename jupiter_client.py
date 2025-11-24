
#!/usr/bin/env python3
"""
Minimal Jupiter REST helper.
"""

from __future__ import annotations

import base64
import os
from typing import Dict

import requests



JUP_QUOTE = "https://lite-api.jup.ag/swap/v1/quote"
JUP_SWAP  = "https://lite-api.jup.ag/swap/v1/swap"
SLIPPAGE_BPS = int(os.getenv("SLIPPAGE_BPS", 50))  # default 0.50 %

# ---------------------------------------------------------------------------

def _req(url: str, method: str = "get", **kw) -> Dict:
    """One wrapper for all HTTP calls (raises on non-200)."""
    r = requests.request(method, url, timeout=8, **kw)
    if r.status_code != 200:
        raise RuntimeError(f"{url} → {r.status_code}: {r.text}")
    return r.json()

# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def get_quote(input_mint: str,
              output_mint: str,
              amount: int,
              slippage: int = SLIPPAGE_BPS) -> Dict:
    params = dict(
        inputMint=input_mint,
        outputMint=output_mint,
        amount=amount,
        slippageBps=slippage,
    )
    rsp = _req(JUP_QUOTE, params=params)

    if "data" in rsp and rsp["data"]:
        return rsp["data"][0]

    if all(k in rsp for k in ("inAmount", "outAmount", "routePlan")):
        return rsp

    raise RuntimeError(f"Quote unavailable: {rsp}")

def leg_label(leg: dict) -> str:
    info = leg.get("swapInfo") or leg.get("ammInfo") or {}
    dex  = info.get("dexLabel") or info.get("dex") or "unknown"
    addr = info.get("dexAddress") or info.get("source") or ""
    return f"{dex} ({addr[:4]}…)" if addr else dex


def total_fees_ui(quote: Dict) -> float:
    """
    Sum `feeAmount` from every leg of routePlan and convert to *dst-token* units.
    Returns 0.0 if Jupiter omitted fee data.
    """
    total = 0.0
    for leg in quote.get("routePlan", []):
        fee  = leg.get("feeAmount", 0)
        dec  = leg.get("feeMintDecimals", 0)
        total += float(fee) / 10 ** dec
    return total

def price_impact_pct(quote: Dict) -> float | None:
    """Return price impact as float (pct) if present."""
    try:
        return float(quote["priceImpactPct"])
    except Exception:
        return None


def build_swap_tx(quote: Dict, user_pubkey: str) -> bytes:
    body = {
        "quoteResponse": quote,
        "userPublicKey": user_pubkey,
        "wrapUnwrapSol": False,
        "asLegacyTransaction": False,
        "computeUnitPriceMicroLamports": None,
        "feeAccount": None,
    }
    raw_b64 = _req(JUP_SWAP, method="post", json=body)["swapTransaction"]
    return base64.b64decode(raw_b64)



