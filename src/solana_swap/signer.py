#!/usr/bin/env python3
"""Patch Jupiter swap transactions with a 64-byte Ed25519 signature."""

from solders.keypair import Keypair
from solders.transaction import VersionedTransaction

def sign_swap_tx(raw_tx: bytes, kp: Keypair) -> VersionedTransaction:
    """
    Jupiter returns a tx template with zeroed signature slot.
    This writes the payer’s signature at bytes 1..64 and returns
    a ready-to-send `VersionedTransaction`.
    """
    vt = VersionedTransaction.from_bytes(raw_tx)
    payload = b"\x80" + bytes(vt.message)        # v0 prefix
    sig = kp.sign_message(payload)

    buf = bytearray(raw_tx)
    buf[1:65] = bytes(sig)
    return VersionedTransaction.from_bytes(bytes(buf))
