# **solana_swap**
Python toolkit for **querying balances, executing token–to-token swaps, and keeping an ledger of Solana-based transaction details**

---

## What it does

| Capability | Details |
|------------|---------|
| **Balance look-ups** | One-liner helpers to fetch wallet balances for any SPL mint (native SOL included). |
| **Live USD pricing** | Pulls real-time prices from Jupiter’s public API for any routable mint. |
| **One-call swap** | `Transaction.transact()` wraps quote → tx build → signing → submission → confirmation. |
| **Full audit trail** | Automatically records 40+ fields per swap (before/after/delta for SRC, DST & SOL in *units* **and** *USD*, fees, price impact, signature, timestamp) into `transactions.csv`. |
| **Human-readable console output** | `pretty_print()` displays the swap in four tidy sections: **IN UNITS → IN USD → DELTAS → FEES & META** with correct rounding (2 dec, fees at 6 dec). |
| **Data reload** | `Transaction.load_all()` hydrates every CSV row back into rich objects for analytics. |

---

## Requirements
*(pinned versions in `requirements.txt`)*

| Package   | Version |
|-----------|---------|
| Python    | 3.10 +  |
| `solana`  | ≥ 0.30 |
| `solders` | latest |
| `requests`| latest |
| `aiohttp` | latest |

You’ll also need a Solana RPC endpoint – defaults to  
`https://api.mainnet-beta.solana.com`.

---

## Disclaimer - Read Carefully ##
THIS SOFTWARE IS PROVIDED “AS IS,” WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED.
USE AT YOUR OWN RISK.

By cloning, compiling, running, or otherwise using any portion of this repository:

1. No Warranty   
You acknowledge that the code may be incomplete, contain errors, or fail in ways that could lead to financial loss, including but not limited to the loss of digital assets. I make no representations or warranties—express, implied, statutory, or otherwise—including, without limitation, warranties of merchantability, fitness for a particular purpose, non-infringement, or that the software will operate uninterrupted, be error-free, or achieve any intended result.

3. No Professional Advice   
Nothing in this repository constitutes legal, financial, or investment advice. You are solely responsible for verifying the correctness, legality, security, and suitability of the software for your needs.

5. Assumption of Risk   
You assume all risks associated with compiling, deploying, or executing the code, including interactions with the Solana blockchain, third-party APIs, smart contracts, and potential bugs or vulnerabilities.

7. Limitation of Liability   
In no event shall I (the author/contributors) be liable for any direct, indirect, incidental, special, exemplary, or consequential damages—including loss of funds, loss of profits, loss of data, or business interruption—arising out of or in connection with the software or its use, even if advised of the possibility of such damages.

9. Indemnification    
You agree to indemnify and hold harmless the author/contributors from and against any and all claims, liabilities, damages, losses, or expenses (including reasonable attorneys’ fees) arising out of or in any way connected with your use of the software.

If any of these terms are unacceptable to you, do not use the software.

---

## Installation

```bash
TBD
```
---

### Example Usage: Check a balance

```python
import asyncio
from session import SolanaSession

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"

async def run():
    async with SolanaSession() as sess:
        bal = await sess.ui_balance(USDC, sess.kp.pubkey())
        print(f"USDC balance: {bal}")

asyncio.run(run())

```

### Example Usage: Swap $25 of USDC to wBTC
```python
import asyncio
from decimal import Decimal
from transaction import Transaction

USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
WBTC = "3NZ9JMVBmGAqocybic2c7LQCJScmgsAZ6vQqTDzcqmJh"

async def run():
    tx = await Transaction.transact(
        src_token=USDC,
        dst_token=WBTC,
        usd_amount=Decimal("25")
    )
    tx.pretty_print()

asyncio.run(run())
```

