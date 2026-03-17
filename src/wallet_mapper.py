"""
wallet_mapper.py — Identifies wallets and detects orphan inflows.
Runs after all ledger files are loaded, before the FIFO engine.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from .models import LedgerEntry


@dataclass
class WalletInfo:
    wallet_id: str
    assets: set = field(default_factory=set)
    inflow_count: int = 0
    outflow_count: int = 0
    orphan_inflows: list = field(default_factory=list)  # LedgerEntry items with no prior acquisition


def identify_wallets(entries: list[LedgerEntry]) -> dict[str, WalletInfo]:
    """
    Scans all loaded LedgerEntry objects and builds a per-wallet inventory map.
    Detects orphan inflows (received asset before any recorded buy/staking/deposit).
    """
    # First pass: build wallet inventory timeline per (wallet_id, asset)
    inventory: dict[tuple[str, str], Decimal] = {}
    wallet_map: dict[str, WalletInfo] = {}

    for entry in sorted(entries, key=lambda e: e.time):
        key = (entry.wallet_id, entry.asset)
        if entry.wallet_id not in wallet_map:
            wallet_map[entry.wallet_id] = WalletInfo(wallet_id=entry.wallet_id)

        info = wallet_map[entry.wallet_id]
        info.assets.add(entry.asset)

        current_balance = inventory.get(key, Decimal("0"))

        if entry.type in ("buy", "deposit", "receive", "staking", "earn", "airdrop", "reward"):
            info.inflow_count += 1
            inventory[key] = current_balance + entry.amount

        elif entry.type in ("sell", "withdrawal", "send", "spend"):
            info.outflow_count += 1
            if current_balance <= Decimal("0") and entry.amount < Decimal("0"):
                # Selling/withdrawing an asset not previously acquired in this wallet
                info.orphan_inflows.append(entry)
            inventory[key] = current_balance + entry.amount  # amount is negative for sells

        elif entry.type in ("trade", "swap"):
            if entry.amount > Decimal("0"):
                info.inflow_count += 1
            elif entry.amount < Decimal("0"):
                info.outflow_count += 1
                if current_balance <= Decimal("0"):
                    # Selling an asset not previously acquired
                    info.orphan_inflows.append(entry)
            inventory[key] = current_balance + entry.amount

        elif entry.type in ("transfer",):
            # Internal transfer — just track flow
            if entry.amount > Decimal("0"):
                info.inflow_count += 1
            else:
                info.outflow_count += 1
            inventory[key] = current_balance + entry.amount

    return wallet_map


def find_orphan_inflows(entries: list[LedgerEntry]) -> list[LedgerEntry]:
    """
    Returns a flat list of all LedgerEntry items where an asset was sold/withdrawn
    from a wallet that had no prior record of acquiring it.
    These require user confirmation: 'internal transfer' vs 'OTC purchase'.
    """
    wallet_map = identify_wallets(entries)
    orphans = []
    for info in wallet_map.values():
        orphans.extend(info.orphan_inflows)
    return orphans


def get_wallet_summary(entries: list[LedgerEntry]) -> list[dict]:
    """
    Returns a list of dicts suitable for rendering in the wallet mapping table.
    """
    wallet_map = identify_wallets(entries)
    summary = []
    for wallet_id, info in wallet_map.items():
        summary.append({
            "wallet_id": wallet_id,
            "assets": sorted(info.assets),
            "inflows": info.inflow_count,
            "outflows": info.outflow_count,
            "orphan_count": len(info.orphan_inflows),
            "has_issues": len(info.orphan_inflows) > 0,
        })
    return summary
