#!/usr/bin/env python3
# wallet.py
"""
Object-oriented refactor of the balance checker.

Example
-------
>>> from wallet import SolanaWallet
>>> w = SolanaWallet.from_env()          # reads $SOL_WALLET_PUBKEY
>>> w.refresh()                          # pull latest balances
>>> print(w.sol_balance)                 # SOL in SOL units
>>> print(w.balances["7XS5…eVSV"].amount)  # token balance
>>> w.display()                          # pretty table
"""

from __future__ import annotations

import os
import sys
import time
from typing import Dict, List

import requests


class TokenInfo:
    """Container for a single token’s balance and (future) metadata."""

    __slots__ = ("mint", "amount", "usd_price", "updated_at")

    def __init__(self, mint: str, amount: float):
        self.mint: str = mint
        self.amount: float = amount
        self.usd_price: float | None = None    # placeholder
        self.updated_at: float = time.time()

    # For upcoming price support
    @property
    def value_usd(self) -> float | None:
        if self.usd_price is None:
            return None
        return self.amount * self.usd_price


class SolanaWallet:
    RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
    TOKEN_PROGRAMS: List[str] = [
        "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
        "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",
    ]

    # ────────────────────────────────
    # construction helpers
    # ────────────────────────────────
    def __init__(self, pubkey: str):
        self.pubkey = pubkey
        self.sol_balance: float = 0.0
        self.balances: Dict[str, TokenInfo] = {}  # mint → TokenInfo

    @classmethod
    def from_env(cls) -> "SolanaWallet":
        pk = os.getenv("SOL_WALLET_PUBKEY")
        if not pk:
            sys.exit("Error: set environment variable SOL_WALLET_PUBKEY first.")
        return cls(pk)

    # ────────────────────────────────
    # public API
    # ────────────────────────────────
    def refresh(self) -> None:
        """Fetch SOL + SPL balances."""
        self.sol_balance = self._get_sol_balance()
        self.balances = self._get_all_token_balances()

    def get_mints(self) -> List[str]:
        """Return a list of mint addresses present in the wallet."""
        return list(self.balances)

    def display(self) -> None:
        """Pretty-print balances (two decimals)."""
        col_width = max(3, *(len(m) for m in self.balances))  # min width for “SOL”
        hdr_mint, hdr_bal = "Mint address", "Balance"
        print("\n=== Wallet Balances ===")
        print(f"{'SOL'.ljust(col_width)}  {self.sol_balance:,.2f} SOL")
        if self.balances:
            print("\n=== Token Balances ===")
            print(f"{hdr_mint.ljust(col_width)}  {hdr_bal}")
            print(f"{'-'*col_width}  {'-'*len(hdr_bal)}")
            for mint, info in sorted(self.balances.items()):
                print(f"{mint.ljust(col_width)}  {info.amount:,.2f}")

    # ────────────────────────────────
    # internals
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
        balances: Dict[str, float] = {}
        for program_id in self.TOKEN_PROGRAMS:
            result = self._rpc(
                "getTokenAccountsByOwner",
                [self.pubkey, {"programId": program_id}, {"encoding": "jsonParsed"}],
            )
            for acct in result["value"]:
                info = acct["account"]["data"]["parsed"]["info"]
                mint = info.get("mint", "Unknown")
                amt = float(info.get("tokenAmount", {}).get("uiAmount", 0))
                balances[mint] = balances.get(mint, 0.0) + amt

        return {m: TokenInfo(m, a) for m, a in balances.items()}





if __name__ == "__main__":
    wallet = SolanaWallet.from_env()
    wallet.refresh()
    wallet.display()
