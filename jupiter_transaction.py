#!/usr/bin/env python3
# transaction.py — tracks every balance/fee in both token units and USD.

from __future__ import annotations

import csv, json, os, datetime as dt
from dataclasses import dataclass, field, asdict
from decimal import Decimal
from typing import Any, ClassVar, List

from session import SolanaSession
from jupiter_helper import get_price, is_mint_tradable

try:
    import pandas as pd
except ImportError:
    pd = None


SOL_MINT = "So11111111111111111111111111111111111111112"  # native-SOL pseudo-mint
_CSV_PATH = "transactions.csv"


# ──────────────────────────────────────────────────────────────────────────
# Dataclass
# ──────────────────────────────────────────────────────────────────────────
@dataclass(slots=True)
class Transaction:
    # raw Jupiter response
    result: dict[str, Any]

    # token identifiers
    src_token: str
    dst_token: str

    # balances (token UNITS) ────────────────────────────────────────────
    src_before_units: Decimal
    dst_before_units: Decimal
    sol_before_units: Decimal
    src_after_units:  Decimal
    dst_after_units:  Decimal
    sol_after_units:  Decimal
    src_delta_units:  Decimal
    dst_delta_units:  Decimal
    sol_delta_units:  Decimal

    # USD snapshots & deltas ────────────────────────────────────────────
    src_before_usd: Decimal
    dst_before_usd: Decimal
    sol_before_usd: Decimal
    src_after_usd:  Decimal
    dst_after_usd:  Decimal
    sol_after_usd:  Decimal
    src_delta_usd:  Decimal
    dst_delta_usd:  Decimal
    sol_delta_usd:  Decimal

    # unit prices
    src_unit_price_usd: Decimal
    dst_unit_price_usd: Decimal
    sol_unit_price_usd: Decimal

    # fees & impact
    route_fee_dst_units:   Decimal
    network_fee_sol_units: Decimal
    priority_fee_sol_units: Decimal
    price_impact_pct:      Decimal

    # timestamp
    ts_utc: dt.datetime = field(
        default_factory=lambda: dt.datetime.utcnow().replace(tzinfo=dt.timezone.utc)
    )

    # CSV header (explicit denominations)
    _CSV_HEADER: ClassVar[List[str]] = [
        "ts_utc", "src_token", "dst_token",
        # balances in units
        "src_before_units", "dst_before_units", "sol_before_units",
        "src_after_units",  "dst_after_units",  "sol_after_units",
        "src_delta_units",  "dst_delta_units",  "sol_delta_units",
        # balances in USD
        "src_before_usd",   "dst_before_usd",   "sol_before_usd",
        "src_after_usd",    "dst_after_usd",    "sol_after_usd",
        "src_delta_usd",    "dst_delta_usd",    "sol_delta_usd",
        # unit prices
        "src_unit_price_usd", "dst_unit_price_usd", "sol_unit_price_usd",
        # fees
        "route_fee_dst_units", "network_fee_sol_units",
        "priority_fee_sol_units", "price_impact_pct",
        "result_json",
    ]

    # =================================================================
    # high-level factory
    # =================================================================
    @classmethod
    async def transact(
        cls,
        src_token: str,
        dst_token: str,
        usd_amount: Decimal | float,
        *,
        session: SolanaSession | None = None,
        autoprint: bool = True,
    ) -> "Transaction":

        if not (is_mint_tradable(src_token) and is_mint_tradable(dst_token)):
            raise ValueError("One or both mints are not routable on Jupiter")

        owns_session = session is None
        session = session or SolanaSession()
        wallet = session.kp.pubkey()

        try:
            # balances BEFORE
            src_before, dst_before = await session.pair_balances(src_token, dst_token)
            lamports_before = (await session.primary.get_balance(wallet)).value
            sol_before = Decimal(lamports_before) / Decimal(1e9)

            # live prices
            src_price = Decimal(str(get_price(src_token)))
            dst_price = Decimal(str(get_price(dst_token)))
            sol_price = Decimal(str(get_price(SOL_MINT)))

            # before USD snapshots
            src_before_usd = Decimal(src_before) * src_price
            dst_before_usd = Decimal(dst_before) * dst_price
            sol_before_usd = sol_before * sol_price

            # convert USD→units & swap
            units = Decimal(usd_amount) / src_price
            result = await session.swap(src_token, dst_token, units)

            # balances AFTER
            src_after, dst_after = await session.pair_balances(src_token, dst_token)
            lamports_after = (await session.primary.get_balance(wallet)).value
            sol_after = Decimal(lamports_after) / Decimal(1e9)

            # after USD snapshots
            src_after_usd = Decimal(src_after) * src_price
            dst_after_usd = Decimal(dst_after) * dst_price
            sol_after_usd = sol_after * sol_price

            # deltas
            src_delta_units = Decimal(src_after) - Decimal(src_before)
            dst_delta_units = Decimal(dst_after) - Decimal(dst_before)
            sol_delta_units = sol_after - sol_before

            tx = cls(
                result=result,
                src_token=src_token,
                dst_token=dst_token,
                # units
                src_before_units=Decimal(src_before),
                dst_before_units=Decimal(dst_before),
                sol_before_units=sol_before,
                src_after_units=Decimal(src_after),
                dst_after_units=Decimal(dst_after),
                sol_after_units=sol_after,
                src_delta_units=src_delta_units,
                dst_delta_units=dst_delta_units,
                sol_delta_units=sol_delta_units,
                # USD snapshots & deltas
                src_before_usd=src_before_usd,
                dst_before_usd=dst_before_usd,
                sol_before_usd=sol_before_usd,
                src_after_usd=src_after_usd,
                dst_after_usd=dst_after_usd,
                sol_after_usd=sol_after_usd,
                src_delta_usd=src_after_usd - src_before_usd,
                dst_delta_usd=dst_after_usd - dst_before_usd,
                sol_delta_usd=sol_after_usd - sol_before_usd,
                # prices
                src_unit_price_usd=src_price,
                dst_unit_price_usd=dst_price,
                sol_unit_price_usd=sol_price,
                # fees & impact
                route_fee_dst_units=Decimal(str(result.get("route_fees_ui", 0))),
                network_fee_sol_units=Decimal(str(result.get("solNetworkFee", 0))),
                priority_fee_sol_units=Decimal(str(result.get("priorityFeeSol", 0))),
                price_impact_pct=Decimal(str(result.get("priceImpact", 0))),
            )

            tx.save_to_csv()
            if autoprint:
                tx.pretty_print()
            return tx

        finally:
            if owns_session:
                await session.close()

    # -----------------------------------------------------------------
    # persistence
    # -----------------------------------------------------------------
    def save_to_csv(self, path: str = _CSV_PATH) -> None:
        data = asdict(self)
        data["result_json"] = json.dumps(data.pop("result"), separators=(",", ":"))
        row = {col: str(data.get(col, "")) for col in self._CSV_HEADER}

        write_header = not os.path.exists(path)
        with open(path, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=self._CSV_HEADER)
            if write_header:
                w.writeheader()
            w.writerow(row)

    # -----------------------------------------------------------------
    # console view
    # -----------------------------------------------------------------
    def _fmt(self, val: Decimal | float, *, fee: bool = False) -> str:
        return f"{Decimal(val):.6f}" if fee else f"{Decimal(val):.2f}"

    def pretty_print(self) -> None:
        fees_usd = self.result.get("routeFeesUSD")
        fees_by_mint = self.result.get("routeFeesByMint") or {}
        if isinstance(fees_by_mint, dict):
            fees_by_mint_str = ", ".join(
                f"{mint}:{self._fmt(val, fee=True)}" for mint, val in fees_by_mint.items()
            ) if fees_by_mint else "—"
        else:
            fees_by_mint_str = "—"

        rec = {
            "UTC time": self.ts_utc.isoformat(timespec="seconds"),
            "Source token": self.src_token,
            "Destination token": self.dst_token,
            # units before/after
            "Src before (units)": self._fmt(self.src_before_units),
            "Dst before (units)": self._fmt(self.dst_before_units),
            "SOL before (units)": self._fmt(self.sol_before_units),
            "Src after  (units)": self._fmt(self.src_after_units),
            "Dst after  (units)": self._fmt(self.dst_after_units),
            "SOL after  (units)": self._fmt(self.sol_after_units),
            # USD before/after
            "Src before (USD)": self._fmt(self.src_before_usd),
            "Dst before (USD)": self._fmt(self.dst_before_usd),
            "SOL before (USD)": self._fmt(self.sol_before_usd),
            "Src after  (USD)": self._fmt(self.src_after_usd),
            "Dst after  (USD)": self._fmt(self.dst_after_usd),
            "SOL after  (USD)": self._fmt(self.sol_after_usd),
            # deltas
            "Src delta (units)": self._fmt(self.src_delta_units),
            "Dst delta (units)": self._fmt(self.dst_delta_units),
            "SOL delta (units)": self._fmt(self.sol_delta_units),
            "Src delta (USD)":   self._fmt(self.src_delta_usd),
            "Dst delta (USD)":   self._fmt(self.dst_delta_usd),
            "SOL delta (USD)":   self._fmt(self.sol_delta_usd),
            # fees & impact
            "Route fee (dst units)": self._fmt(self.route_fee_dst_units, fee=True),
            "Route fee (USD)":       self._fmt(fees_usd or 0.0),
            "Fees by mint (units)":  fees_by_mint_str,
            "Network fee (SOL)":     self._fmt(self.network_fee_sol_units, fee=True),
            "Priority fee (SOL)":    self._fmt(self.priority_fee_sol_units, fee=True),
            "Price impact %":        self._fmt(self.price_impact_pct),
            "Signature":             self.result.get("signature", "—"),
        }

        if pd:
            df = pd.DataFrame(rec, index=[0]).T.rename(columns={0: "value"})
            print(df)
        else:
            print("\n".join(f"{k:>34}: {v}" for k, v in rec.items()))

    # -----------------------------------------------------------------
    # loader
    # -----------------------------------------------------------------
    @classmethod
    def load_all(cls, path: str = _CSV_PATH) -> List["Transaction"]:
        if not os.path.exists(path):
            return []
        txs: List[Transaction] = []
        with open(path, newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                vals = {k: row[k] for k in cls._CSV_HEADER}
                vals["result"] = json.loads(vals.pop("result_json"))
                # cast decimals
                for k, v in vals.items():
                    if k not in {"ts_utc", "src_token", "dst_token", "result"}:
                        vals[k] = Decimal(v) if v else Decimal("0")
                vals["ts_utc"] = dt.datetime.fromisoformat(vals["ts_utc"])
                txs.append(cls(**vals))  # type: ignore[arg-type]
        return txs
