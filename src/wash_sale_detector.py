"""
wash_sale_detector.py — Post-processing engine for Wash Sale Compliance.
Adheres to SEC/IRS guidelines for crypto security tokens.
"""

from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Set
from .models import TaxableEvent, LedgerEntry

# As per regulatory focus, these layer-1 and popular tokens are often targeted
# under the "Howey Test" heuristics by the SEC. We strictly apply wash sale
# rules (Section 1091) exclusively to these security-classified tokens.
#
# NOTE: This list is a CONSERVATIVE heuristic — the IRS has NOT published an
# official list of crypto securities. Pass a custom set to override, or pass
# an empty set to disable wash sale detection entirely.
DEFAULT_SECURITY_TOKENS: frozenset[str] = frozenset({
    "ADA",    # Cardano
    "SOL",    # Solana
    "MATIC",  # Polygon
    "ALGO",   # Algorand
    "FIL",    # Filecoin
    "ATOM",   # Cosmos
    "SAND",   # The Sandbox
    "MANA",   # Decentraland
    "CHZ",    # Chiliz
    "COTI"    # COTI
})

def detect_security_wash_sales(
    taxable_events: List[TaxableEvent],
    raw_events: List[List[LedgerEntry]],
    *,
    security_tokens: frozenset[str] | None = None,
) -> int:
    """
    Scans the engine's realized capital losses on Security Tokens.
    If a replacement lot was acquired within +-30 days (61-day window),
    the loss is disallowed. Mutates `taxable_events` in-place by injecting
    adjustment Code="W" into the Form 8949 reporting structure.

    Args:
        taxable_events: Events produced by FIFOEngine.
        raw_events:     Raw grouped ledger entries (pre-engine).
        security_tokens: Set of ticker symbols to which wash sale rules apply.
                         Defaults to DEFAULT_SECURITY_TOKENS.
                         Pass an empty frozenset() to disable wash sale detection entirely.

    Returns:
        Total number of flagged wash sale events.
    """
    tokens_to_check = security_tokens if security_tokens is not None else DEFAULT_SECURITY_TOKENS

    # 1. Flatten all acquisitions from raw events to create a fast lookup table
    #    An acquisition is a LedgerEntry with amount > 0 for a crypto asset.
    acquisitions: List[dict] = []
    for event_group in raw_events:
        for entry in event_group:
            if entry.asset != 'USD' and entry.amount > Decimal('0'):
                acquisitions.append({
                    "asset": entry.asset,
                    "date": entry.time.date(),
                    "amount": abs(entry.amount),
                    "wallet_id": entry.wallet_id
                })
                
    wash_sales_flagged = 0
    
    for tx in taxable_events:
        # Wash sales only apply to SECURITY assets incurring a LOSS
        # tx.asset usually needs extraction from description (e.g. "Sold 10 ADA")
        parts = tx.description.split()
        if len(parts) >= 2:
            asset = parts[-1]
        else:
            continue
            
        if asset not in tokens_to_check:
            continue
            
        if tx.gain_loss >= Decimal('0'):
            continue  # Gains are not subject to wash sale disallowance
            
        # Parse the disposal (sell) date
        try:
            sell_date = datetime.strptime(tx.date_sold, "%m/%d/%Y").date()
        except ValueError:
            continue
            
        # 61-day window definition (30 days before, day of, 30 days after)
        window_start = sell_date - timedelta(days=30)
        window_end = sell_date + timedelta(days=30)
        
        # Look for replacement purchases within the window
        replacement_found = False
        for acq in acquisitions:
            if acq["asset"] == asset and window_start <= acq["date"] <= window_end:
                # We found a wash sale!
                replacement_found = True
                break
                
        if replacement_found:
            # IRS Form 8949 Instruction:
            # Enter "W" in column (f) and the disallowed loss as a positive number in column (g).
            
            # tx.adjustment_code and tx.adjustment_amount were defined in Phase 1 (1099-DA module)
            tx.adjustment_code = "W"
            # The adjustment is the positive amount added back to nullify the loss
            tx.adjustment_amount = abs(tx.gain_loss)
            
            wash_sales_flagged += 1
            
    return wash_sales_flagged
