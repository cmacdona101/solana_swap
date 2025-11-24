#!/usr/bin/env python3
"""
jupiter_helper.py

Lightweight helpers around Jupiter's public APIs.

Functions
---------
is_mint_tradable(mint_address: str) -> bool
    True if the mint is routable on Jupiter.

get_price(mint_address: str,
          vs_token: str | None = None,
          show_extra_info: bool = False) -> float
    Latest quoted price.  Defaults to USD denomination.
"""

from __future__ import annotations
from typing import Optional
import requests, os

# Jupiter endpoints
JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v3"

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def is_mint_tradable(mint_address: str) -> bool:
    """
    Return True if `mint_address` has a current USD price from Price v3.
    This is a pragmatic proxy for tradability without relying on legacy token lists.
    """
    try:
        resp = requests.get(
            JUPITER_PRICE_URL,
            params={"ids": mint_address},
            timeout=15,
        )
        resp.raise_for_status()
        obj = resp.json() 
        return mint_address in obj and "usdPrice" in obj[mint_address]
    except Exception:
        return False


def get_price(
    mint_address: str,
    *,
    vs_token: Optional[str] = None,
    show_extra_info: bool = False,
) -> float:
    """
    Fetch the latest price for `mint_address`.

    Parameters
    ----------
    mint_address : str
        SPL-token mint to quote. (USD based)


    Returns
    -------
    float
        Price expressed in USD units.

    Raises
    ------
    ValueError
        If Jupiter returns no price for the given mint.
    requests.HTTPError
        For non-200 responses.
    """
    params: dict[str, str] = {"ids": mint_address}
    

    resp = requests.get(JUPITER_PRICE_URL, params=params, timeout=15)
    resp.raise_for_status()
    obj = resp.json() 

    entry = obj.get(mint_address)
    price_val = entry.get("usdPrice") if isinstance(entry, dict) else None


    if price_val is None:
        raise ValueError(f"No price available for mint {mint_address}")

    return float(price_val)


# ---------------------------------------------------------------------------
# Quick-and-dirty manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    print("Is USDC tradable?", is_mint_tradable(USDC_MINT))
    print("USDC price (USD):", get_price(USDC_MINT))
