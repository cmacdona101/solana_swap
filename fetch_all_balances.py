#!/usr/bin/env python3
"""
all_balances_checker.py

Fetch SOL and SPL-token balances for a wallet whose public key is supplied via
the environment variable `SOL_WALLET_PUBKEY`.  Results are printed in a tidy
two-column table.

Usage:
    $ export SOL_WALLET_PUBKEY=rfHttsMQnurnrqVeBajzcTC1ZKifU5L68Lpv4G3mGBv
    $ python all_balances_checker.py
"""

import os
import sys
import requests
from typing import Dict

RPC_ENDPOINT = "https://api.mainnet-beta.solana.com"
TOKEN_PROGRAMS = [
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",  # SPL token program
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb",  # Token22 (e.g. ai16z)
]


# ──────────────────────────────────────────────────────────────────────────
# RPC helpers
# ──────────────────────────────────────────────────────────────────────────
def _rpc(method: str, params):
    payload = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    resp = requests.post(RPC_ENDPOINT, json=payload, timeout=15)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"RPC error: {data['error']}")
    return data["result"]


def get_sol_balance(pubkey: str) -> float:
    """Return SOL balance in SOL (1 SOL = 10⁹ lamports)."""
    lamports = _rpc("getBalance", [pubkey])["value"]
    return lamports / 1e9


def get_all_token_balances(pubkey: str) -> Dict[str, float]:
    """Aggregate balances across SPL token programs."""
    balances: Dict[str, float] = {}

    for program_id in TOKEN_PROGRAMS:
        result = _rpc(
            "getTokenAccountsByOwner",
            [pubkey, {"programId": program_id}, {"encoding": "jsonParsed"}],
        )

        for acct in result["value"]:
            info = acct["account"]["data"]["parsed"]["info"]
            mint = info.get("mint", "Unknown")
            amt = float(info.get("tokenAmount", {}).get("uiAmount", 0))
            balances[mint] = balances.get(mint, 0.0) + amt

    return balances


# ──────────────────────────────────────────────────────────────────────────
# Presentation
# ──────────────────────────────────────────────────────────────────────────
def display_balances(sol_balance: float, token_balances: Dict[str, float]) -> None:
    """Pretty-print balances in aligned columns (two decimals)."""
    header_mint = "Mint address"
    header_bal = "Balance"
    col_width = max(len(header_mint), max((len(m) for m in token_balances), default=0))

    print("\n=== Wallet Balances ===")
    print(f"{'SOL'.ljust(col_width)}  \t\t{sol_balance:,.2f} SOL")
    if token_balances:
        print("\n=== Token Balances ===")
        print(f"{header_mint.ljust(col_width)}  \t\t{header_bal}")
        print(f"{'-'*col_width}  \t\t{'-'*len(header_bal)}")
        for mint, bal in sorted(token_balances.items()):
            print(f"{mint.ljust(col_width)}  \t\t{bal:,.2f} units")


# ──────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────
def main() -> None:
    pubkey = os.getenv("SOL_WALLET_PUBKEY")
    if not pubkey:
        sys.exit("Error: set environment variable SOL_WALLET_PUBKEY first.")

    sol_bal = get_sol_balance(pubkey)
    token_bals = get_all_token_balances(pubkey)
    display_balances(sol_bal, token_bals)


if __name__ == "__main__":
    main()
