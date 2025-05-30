#!/usr/bin/env python3
"""
High-level session: balances, prices, swap orchestration.
"""

from __future__ import annotations
import asyncio, json, os
from typing import Tuple

from solders.keypair import Keypair
from solders.pubkey import Pubkey
from solana.rpc.types import TxOpts

from rpc_pool import RpcPool
from token_utils import TokenTools
from signer import sign_swap_tx
from jupiter_client import get_quote, build_swap_tx
from jupiter_helper import get_price, is_mint_tradable

class SolanaSession(TokenTools, RpcPool):
    """Compose networking + token helpers into one object."""

    def __init__(self, wallet_file: str | None = None, **kw) -> None:
        RpcPool.__init__(self, **kw)
        TokenTools.__init__(self)

        wallet_file = wallet_file or os.getenv("WALLET_FILE", "wallet.json")
        with open(wallet_file, "r", encoding="utf-8") as f:
            secret = json.load(f)
        self.kp = Keypair.from_bytes(bytes(secret))

    # ───────────────────────── balances / prices ──────────────────────
    async def price_usd(self, mint: str) -> float:
        if not is_mint_tradable(mint):
            return 0.0
        return await asyncio.to_thread(get_price, mint)

    async def pair_balances(self, src: str, dst: str) -> Tuple[float, float]:
        owner = self.kp.pubkey()
        return (
            await self.ui_balance(src, owner),
            await self.ui_balance(dst, owner),
        )

    # ───────────────────────── swap ───────────────────────────────────
    async def swap(self, src: str, dst: str, src_ui: float):
        if src_ui <= 0:
            raise ValueError("Amount must be positive")

        lamports = int(src_ui * 10 ** await self.decimals(src))

        quote = get_quote(src, dst, lamports)
        if "outAmount" not in quote:
            raise RuntimeError("No swap route")

        raw    = build_swap_tx(quote, str(self.kp.pubkey()))
        tx     = sign_swap_tx(raw, self.kp)
        sig    = await self._submit(tx)

        dst_ui = float(quote["outAmount"]) / 10 ** await self.decimals(dst)
        return sig, dst_ui

    # ───────────────────────── internals ──────────────────────────────
    async def _submit(self, tx):
        sig = await self.primary.send_raw_transaction(
            bytes(tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment="processed")
        )
        await self.primary.confirm_transaction(sig.value, self.commitment)
        return str(sig.value)
