#!/usr/bin/env python3
"""
Async RPC connection pool.

Keeps a primary + fallback `AsyncClient`, plus a cached block-hash that
auto-refreshes every 30 s (well inside Solana’s 2-minute validity window).
"""

from __future__ import annotations
import asyncio, os, time
from typing import Optional

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

REFRESH_SEC = 30
_DEFAULT_COMMIT = Commitment("finalized")

class RpcPool:
    """Owns two `AsyncClient`s and a recent block-hash."""

    def __init__(self,
                 primary_rpc: str | None = None,
                 fallback_rpc: str | None = None,
                 commitment: Commitment = _DEFAULT_COMMIT) -> None:

        if primary_rpc is None:
            primary_rpc = os.getenv("RPC_PRIMARY")
        if primary_rpc is None:
            raise RuntimeError("Set RPC_PRIMARY env var or pass explicit URL")

        self._primary_url = primary_rpc 
        self.primary      = AsyncClient(primary_rpc, commitment=commitment)
        self.backup    = AsyncClient(
            fallback_rpc or os.getenv("RPC_FALLBACK", "https://api.mainnet-beta.solana.com"),
            commitment=commitment
        )
        self.commitment = commitment

        self._blockhash: Optional[str] = None
        self._expiry: float = 0.0
        self._lock   = asyncio.Lock()
        self._task   = asyncio.create_task(self._refresh_loop())

    # ───────────────────────────── public ─────────────────────────────
    async def get_blockhash(self) -> str:
        """Guaranteed <90 s old."""
        if time.time() >= self._expiry:
            await self._refresh()
        assert self._blockhash                # mypy
        return self._blockhash

    async def close(self) -> None:
        self._task.cancel()
        await asyncio.gather(
            self.primary.close(), self.backup.close(), return_exceptions=True
        )

    # ───────────────────────────── internals ──────────────────────────
    async def _refresh_loop(self) -> None:
        while True:
            try:
                await self._refresh()
            except Exception:
                pass
            await asyncio.sleep(REFRESH_SEC)

    async def _refresh(self) -> None:
        async with self._lock:
            resp = await self.primary.get_latest_blockhash()
            self._blockhash = resp.value.blockhash
            self._expiry    = time.time() + 90      # conservative TTL
