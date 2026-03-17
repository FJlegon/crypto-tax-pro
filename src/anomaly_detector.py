"""
anomaly_detector.py — Post-processing anomaly detection for the FIFO engine output.
Runs after fifo_engine.process_events() to flag edge cases for user review.
"""
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Optional
from .models import TaxableEvent


@dataclass
class Anomaly:
    anomaly_type: str           # "negative_inventory" | "large_variance" | "missing_basis"
    severity: str               # "warning" | "error"
    description: str
    asset: str
    wallet_id: str
    event_date: Optional[str] = None
    amount: Optional[Decimal] = None
    term: Optional[str] = None
    event_ref: Optional[TaxableEvent] = None
    resolution_options: list = field(default_factory=list)
    resolved: bool = False
    resolution_chosen: str = ""


def detect_anomalies(
    taxable_events: list[TaxableEvent],
    audit_log: list[str],
) -> list[Anomaly]:
    """
    Analyses the FIFO engine output and returns a list of detected anomalies.

    Detected patterns:
    - missing_basis: events where cost_basis == 0 (likely staking/airdrop origin)
    - large_variance: gain/loss > 3 standard deviations from the user's mean
    """
    anomalies: list[Anomaly] = []

    if not taxable_events:
        return anomalies

    # ── Missing basis ──────────────────────────────────────────────────────────
    for ev in taxable_events:
        if ev.cost_basis == Decimal("0") and ev.proceeds > Decimal("0"):
            anomalies.append(Anomaly(
                anomaly_type="missing_basis",
                severity="warning",
                description=(
                    f"Sale of {ev.description} on {ev.date_sold} has $0 cost basis. "
                    f"This may be a staking reward, airdrop, or transfer from an untracked wallet."
                ),
                asset=ev.description,
                wallet_id=ev.wallet_id,
                event_date=ev.date_sold,
                amount=ev.proceeds,
                term=ev.term,
                event_ref=ev,
                resolution_options=[
                    "Keep $0 basis (conservative — maximizes taxable gain)",
                    "Mark as ordinary income at fair market value",
                    "Enter manual cost basis",
                ],
            ))

    # ── Unknown holding period (Missing Basis disposals) ───────────────────────
    for ev in taxable_events:
        if ev.term == "Unknown":
            anomalies.append(Anomaly(
                anomaly_type="unknown_term",
                severity="warning",
                description=(
                    f"Holding period for {ev.description} (sold {ev.date_sold}) is unknown. "
                    f"Currently treated as Short-Term (conservative). "
                    f"If you can document a prior acquisition date, you may qualify for Long-Term rates."
                ),
                asset=ev.description,
                wallet_id=ev.wallet_id,
                event_date=ev.date_sold,
                amount=ev.proceeds,
                resolution_options=[
                    "Keep as Short-Term (conservative — higher tax rate)",
                    "Classify as Long-Term (requires documentation of acquisition date)",
                ],
            ))

    # ── Large variance (statistical outlier) ───────────────────────────────────
    gains = [ev.gain_loss for ev in taxable_events]
    if len(gains) >= 3:
        mean = sum(gains, Decimal("0")) / Decimal(len(gains))
        variance = sum((g - mean) ** 2 for g in gains) / Decimal(len(gains))
        std_dev = variance.sqrt()
        threshold = mean + 3 * std_dev

        for ev in taxable_events:
            if abs(ev.gain_loss) > abs(threshold) and abs(ev.gain_loss) > Decimal("1000"):
                anomalies.append(Anomaly(
                    anomaly_type="large_variance",
                    severity="warning",
                    description=(
                        f"Unusual gain/loss of ${ev.gain_loss:,.2f} on {ev.description} "
                        f"({ev.date_sold}). This is >3σ from your average. "
                        f"Verify cost basis and proceeds are correct."
                    ),
                    asset=ev.description,
                    wallet_id=ev.wallet_id,
                    event_date=ev.date_sold,
                    amount=ev.gain_loss,
                    resolution_options=[
                        "Accept calculated values",
                        "Flag for CPA review",
                    ],
                ))

    # ── Detect from audit log (negative inventory markers) ────────────────────
    for log_line in audit_log:
        if "MISSING_BASIS" in log_line and "moved from" in log_line:
            # This is a missing basis during a TRANSFER, not a SALE.
            # It indicates a pure negative inventory situation that didn't generate a taxable event yet.
            # Extract basic info
            parts = log_line.split(" ")
            try:
                amt = Decimal(parts[1])
                asset = parts[2]
                wallet = parts[5] # moved from {wallet}
                date_str = parts[8] # on {date}
            except Exception:
                amt = None
                asset = "Unknown"
                wallet = "Unknown"
                date_str = None
                
            anomalies.append(Anomaly(
                anomaly_type="negative_inventory",
                severity="error",
                description=(
                    f"Negative inventory on transfer: {log_line}"
                ),
                asset=asset,
                wallet_id=wallet,
                event_date=date_str,
                amount=amt,
                resolution_options=[
                    "Check for missing deposits/buys prior to this transfer",
                    "Import Safe Harbor balances to fix starting inventory",
                ],
            ))

    return anomalies


def get_anomaly_summary(anomalies: list[Anomaly]) -> dict:
    """Returns counts by severity for the review screen badge."""
    return {
        "total": len(anomalies),
        "errors": sum(1 for a in anomalies if a.severity == "error"),
        "warnings": sum(1 for a in anomalies if a.severity == "warning"),
        "resolved": sum(1 for a in anomalies if a.resolved),
    }
