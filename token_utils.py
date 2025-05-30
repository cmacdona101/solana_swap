#!/usr/bin/env python3
"""
Decimal discovery + balance helpers.

Runs four fallback strategies for decimals: getTokenSupply,
jsonParsed getAccountInfo, raw layout parse, and a small static map.
"""

from __future__ import annotations
import base64, math, aiohttp, os
from typing import Dict, List

from solders.pubkey import Pubkey
from solana.rpc.async_api import AsyncClient
from solana.rpc.types import TokenAccountOpts

DEC_OFFSET = 44                            # SPL-Mint: u8 decimals
STATIC_DEC = {
    "EPjFWdd5AufqSSqeM2qcxkEzY6BpyHQzdDrRmqw5yHq3": 6,   # USDC
    "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh": 8,   # wBTC
}

class TokenTools:
    """Mix-in that expects `.primary` and `.backup` AsyncClients."""

    _dec_cache: Dict[str, int]

    async def decimals(self, mint: str) -> int:
        if not hasattr(self, "_dec_cache"):
            self._dec_cache = {}
        if mint in self._dec_cache:
            return self._dec_cache[mint]
        d = await self._discover_decimals(mint)
        self._dec_cache[mint] = d
        return d

    async def ui_balance(self, mint: str, owner: Pubkey) -> float:
        """Return balance in user-friendly units."""
        body = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "getTokenAccountsByOwner",
            "params": [
                str(owner),
                {"mint": mint},
                {"encoding": "jsonParsed", "commitment": "finalized"},
            ],
        }
        async with aiohttp.ClientSession() as sess:
            async with sess.post(self._primary_url, json=body) as r:
                raw = await r.json()

        lamports = sum(
            int(acc["account"]["data"]["parsed"]["info"]["tokenAmount"]["amount"])
            for acc in raw.get("result", {}).get("value", [])
        )
        return lamports / 10 ** await self.decimals(mint)

    # ───────────────────────────── private ────────────────────────────
    async def _discover_decimals(self, mint: str) -> int:
        pub = Pubkey.from_string(mint)

        # try token-supply then jsonParsed account-info
        for cli in (self.primary, self.backup):
            try:
                r = await cli.get_token_supply(pub)
                if r.value:
                    return int(r.value.decimals)
            except Exception:
                pass
            try:
                r = await cli.get_account_info(pub, encoding="jsonParsed")
                if r.value:
                    return int(r.value.data["parsed"]["info"]["decimals"])
            except Exception:
                pass

        # raw base64 layout
        for cli in (self.primary, self.backup):
            try:
                r = await cli.get_account_info(pub)        # default b64
                if r.value:
                    raw = base64.b64decode(r.value.data[0])
                    return raw[DEC_OFFSET]
            except Exception:
                pass

        if mint in STATIC_DEC:
            return STATIC_DEC[mint]

        raise RuntimeError(f"Decimals unavailable for {mint}")

# simple stand-alone helper
async def decimals(client: AsyncClient, mint: str) -> int:
    tool = TokenTools()
    tool.primary = tool.backup = client      # hacky: inject dep
    return await tool.decimals(mint)
