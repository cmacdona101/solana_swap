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

from functools import lru_cache
from typing import Optional

import requests

# Jupiter endpoints
JUPITER_TRADABLE_MINTS_URL = "https://lite-api.jup.ag/tokens/v1/mints/tradable"
JUPITER_PRICE_URL = "https://lite-api.jup.ag/price/v2"

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _fetch_tradable_mints() -> set[str]:
    """Download the full routable-mint list once per process (cached)."""
    resp = requests.get(JUPITER_TRADABLE_MINTS_URL, timeout=15)
    resp.raise_for_status()
    return {m.lower() for m in resp.json()}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def is_mint_tradable(mint_address: str) -> bool:
    """Return True if `mint_address` is routable on Jupiter."""
    return mint_address.lower() in _fetch_tradable_mints()


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
        SPL-token mint to quote.
    vs_token : str, optional
        Quote against another SPL mint instead of USD.
    show_extra_info : bool, default False
        Whether to ask Jupiter for the extended payload (ignored by caller).

    Returns
    -------
    float
        Price expressed in USD (or `vs_token`) units.

    Raises
    ------
    ValueError
        If Jupiter returns no price for the given mint.
    requests.HTTPError
        For non-200 responses.
    """
    params: dict[str, str] = {"ids": mint_address}
    if vs_token:
        params["vsToken"] = vs_token
    if show_extra_info:
        params["showExtraInfo"] = "true"

    resp = requests.get(JUPITER_PRICE_URL, params=params, timeout=15)
    resp.raise_for_status()
    data = resp.json()

    price_str = data.get("data", {}).get(mint_address, {}).get("price")
    if price_str is None:
        raise ValueError(f"No price available for mint {mint_address}")

    return float(price_str)


# ---------------------------------------------------------------------------
# Quick-and-dirty manual test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    USDC_MINT = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

    print("Is USDC tradable?", is_mint_tradable(USDC_MINT))
    print("USDC price (USD):", get_price(USDC_MINT))
