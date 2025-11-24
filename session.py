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

from solders.signature import Signature

from rpc_pool import RpcPool
from token_utils import TokenTools
from signer import sign_swap_tx
from jupiter_client import (
    get_quote,
    build_swap_tx,
    total_fees_ui,
    price_impact_pct,
)
from jupiter_helper import get_price, is_mint_tradable

from dotenv import load_dotenv
load_dotenv() 

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
        #return sig, dst_ui
        
        fees_ui       = total_fees_ui(quote)
        price_impact  = price_impact_pct(quote)
        

        tx_meta = await self.primary.get_transaction(
            Signature.from_string(sig),
            encoding="jsonParsed",
            max_supported_transaction_version=0,
        )

        # handle both old and new structures in solana-py
        val = tx_meta.value
        if val is None:
            lamports_fee = 0
        elif hasattr(val, "meta"):                       # < solana-py 0.28
            lamports_fee = val.meta.fee
        elif hasattr(val, "transaction") and hasattr(val.transaction, "meta"):
            lamports_fee = val.transaction.meta.fee      # ≥ 0.30
        else:                                            # future-proof fallback
            as_dict = getattr(val, "to_json", lambda: val)()
            lamports_fee = as_dict.get("meta", {}).get("fee", 0)


        # base fee = lamportsPerSignature * signature_count (Jupiter tx has 1 sig)
        #latest = await self.primary.get_latest_blockhash()
        #base_fee = latest.value.fee_calculator.lamports_per_signature
        
        # -- network / priority fee ---------------------------
        #lamports_fee = fee_meta    # meta.fee you extracted earlier
        base_fee     = await self.base_sig_fee_lamports(self.primary)
        
        priority_fee = max(lamports_fee - base_fee, 0)
        sol_fee      = lamports_fee / 1e9
        priority_sol = priority_fee / 1e9


        

        return {
            "signature":   sig,
            "dst_ui":      dst_ui,
            "route_fees_ui":     fees_ui,
            "priceImpact": price_impact,
            "routePlan":   quote.get("routePlan"),
            "solNetworkFee": sol_fee,
            "priorityFeeSol": priority_sol
        }        
        
    async def base_sig_fee_lamports(self, client: AsyncClient) -> int:
        """
        Return lamports_per_signature according to the current fee schedule.
        Works on solana-py 0.30+; falls back to 5_000 lamports if needed.
        """
        try:
            latest = await client.get_latest_blockhash()
            # New API exposes it under 'value.feePerSignature' (>=1.18 RPC)
            if hasattr(latest.value, "fee_per_signature"):
                return latest.value.fee_per_signature
            # Older RPC nodes (1.17) don't expose it; simulate a dummy message
            from solders.message import Message
            dummy = Message.new_with_blockhash([], [], latest.value.blockhash)
            fee_resp = await client.get_fee_for_message(dummy)
            if fee_resp.value is not None:
                return fee_resp.value
        except Exception:
            pass
        # Absolute fallback: default network fee
        return 5_000      # lamports


    # ───────────────────────── internals ──────────────────────────────
    async def _submit(self, tx):
        sig = await self.primary.send_raw_transaction(
            bytes(tx),
            opts=TxOpts(skip_preflight=False, preflight_commitment="processed")
        )
        await self.primary.confirm_transaction(sig.value, self.commitment)
        return str(sig.value)
    
    
    
    
