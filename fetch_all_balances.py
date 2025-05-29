#!/usr/bin/env python3
# wallet.py
"""
SOL + SPL wallet helper with USD conversion timestamps.

Example
-------
from wallet import SolanaWallet
w = SolanaWallet.from_env()
w.refresh_balances()          # lamports / token units
w.refresh_prices()            # USD quotes
print(w.sol_info.usd_price)   # latest SOL-USD
print(w.balances['EPjFWd…'].value_usd)
"""

from __future__ import annotations

import datetime as dt
import os
import sys
from typing import Dict, List, Optional

import requests

from jupiter_helper import get_price, is_mint_tradable

# Wrapped-SOL mint used by Jupiter’s price API
WSOL_MINT = "So11111111111111111111111111111111111111112"


# ──────────────────────────────────────────────────────────────────────────
# Data containers
# ──────────────────────────────────────────────────────────────────────────
class TokenInfo:
    """
    Lightweight data holder for one token.

    Attributes
    ----------
    mint : str                SPL mint (or "SOL")
    amount : float            Balance in on-chain units
    balance_at : datetime     When `amount` was last fetched
    usd_price : float | None  Latest quote
    price_at : datetime | None
    """

    __slots__ = ("mint", "amount", "balance_at", "usd_price", "price_at")

    def __init__(self, mint: str, amount: float):
        self.mint: str = mint
        self.amount: float = amount
        self.balance_at: dt.datetime = dt.datetime.utcnow()

        self.usd_price: Optional[float] = None
        self.price_at: Optional[dt.datetime] = None

    # ────────────────────────────────
    # helpers
    # ────────────────────────────────
    @property
    def value_usd(self) -> Optional[float]:
        if self.usd_price is None:
            return None
        return self.amount * self.usd_price

    def set_price(self, price_usd: float) -> None:
        self.usd_price = price_usd
        self.price_at = dt.datetime.utcnow()


# ──────────────────────────────────────────────────────────────────────────
# Wallet
# ──────────────────────────────────────────────────────────────────────────
class SolanaWallet:
    RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
    TOKEN_PROGRAMS: List[str] = [
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    ]

    def __init__(self, pubkey: str):
        self.pubkey = pubkey

        # SOL is stored in its own TokenInfo for uniform access
        self.sol_info: TokenInfo = TokenInfo("SOL", 0.0)

        # mint → TokenInfo (excl. SOL)
        self.balances: Dict[str, TokenInfo] = {}

    # ────────────────────────────────
    # Construction helpers
    # ────────────────────────────────
    @classmethod
    def from_env(cls) -> "SolanaWallet":
        key = os.getenv("SOL_WALLET_PUBKEY")
        if not key:
            sys.exit("Error: set environment variable SOL_WALLET_PUBKEY first.")
        return cls(key)

    # ────────────────────────────────
    # Public API
    # ────────────────────────────────
    def refresh_balances(self) -> None:
        """Update SOL + token balances and timestamps."""
        self.sol_info.amount = self._get_sol_balance()
        self.sol_info.balance_at = dt.datetime.utcnow()
        self.balances = self._get_all_token_balances()

    def refresh_prices(self) -> None:
        """
        Fetch USD prices for SOL and every routable token.

        Non-tradable mints are skipped silently.
        """
        # SOL (via wrapped-SOL mint)
        try:
            sol_price = get_price(WSOL_MINT)
            self.sol_info.set_price(sol_price)
        except Exception:
            # Leave usd_price None if fetch fails
            pass

        # Tokens
        for mint, info in self.balances.items():
            if not is_mint_tradable(mint):
                continue
            try:
                info.set_price(get_price(mint))
            except Exception:
                continue

    def display(self) -> None:
        """Console table — amount + USD conversion (if available)."""
        col_w = max(3, *(len(m) for m in self.balances))  # ≥ len('SOL')
        headers = ("Mint address".ljust(col_w), "Balance", "Value (USD)")
        print("\n=== Wallet ===")
        print(f"{headers[0]}  {headers[1]:>15}  {headers[2]:>15}")
        print(f"{'-'*col_w}  {'-'*15}  {'-'*15}")

        def _row(name: str, tok: TokenInfo):
            val = f"{tok.value_usd:,.2f}" if tok.value_usd is not None else "—"
            print(f"{name.ljust(col_w)}  {tok.amount:15,.4f}  {val:>15}")

        _row("SOL", self.sol_info)
        for m, t in sorted(self.balances.items()):
            _row(m, t)

    # ────────────────────────────────
    # Convenience getters
    # ────────────────────────────────
    def get_mints(self) -> List[str]:
        return list(self.balances)

    # ────────────────────────────────
    # RPC helpers
    # ────────────────────────────────
    def _rpc(self, method: str, params):
        payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
        resp = requests.post(self.RPC_ENDPOINT, json=payload, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data:
            raise RuntimeError(f"RPC error: {data['error']}")
        return data["result"]

    def _get_sol_balance(self) -> float:
        lamports = self._rpc("getBalance", [self.pubkey])["value"]
        return lamports / 1e9

    def _get_all_token_balances(self) -> Dict[str, TokenInfo]:
        agg: Dict[str, float] = {}
        for prog in self.TOKEN_PROGRAMS:
            res = self._rpc(
                "getTokenAccountsByOwner",
                [self.pubkey, {"programId": prog}, {"encoding": "jsonParsed"}],
            )
            for acct in res["value"]:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info.get("mint", "Unknown")
                amt = float(info.get("tokenAmount", {}).get("uiAmount", 0))
                agg[mint] = agg.get(mint, 0.0) + amt

        return {m: TokenInfo(m, a) for m, a in agg.items()}



if __name__ == "__main__":
    wallet = SolanaWallet.from_env()
    wallet.refresh_balances()
    wallet.refresh_prices()
    wallet.display()
#    print(wallet.balances['3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh'].usd_price)
    
