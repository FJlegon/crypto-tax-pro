"""
data_loader.py — CSV parser with per-exchange validation.
Returns ValidationResult for UI feedback, then loads LedgerEntry objects.
"""
import pandas as pd
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Optional
from datetime import datetime
import logging
from .models import LedgerEntry
from .exchange_manager import ExchangeConfig, EXCHANGES

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    status: str                  # "valid" | "warning" | "error"
    row_count: int = 0
    date_start: Optional[str] = None
    date_end: Optional[str] = None
    missing_required: list = field(default_factory=list)
    missing_optional: list = field(default_factory=list)
    message: str = ""
    exchange_key: str = ""       # Which exchange config was matched


def validate_file(filepath: str, exchange_key: str = "kraken") -> ValidationResult:
    """
    Reads the first rows of a CSV and validates it against the exchange config.
    Returns a ValidationResult with status, row count, date range, and any issues.
    """
    config: ExchangeConfig = EXCHANGES.get(exchange_key)
    if not config:
        return ValidationResult(status="error", message=f"Unknown exchange: {exchange_key}")

    try:
        df = pd.read_csv(filepath)
    except Exception as ex:
        return ValidationResult(status="error", message=f"Cannot read file: {ex}")

    cols = set(df.columns.tolist())
    missing_required = sorted(config.required_cols - cols)
    missing_optional = sorted(config.optional_cols - cols)

    if missing_required:
        return ValidationResult(
            status="error",
            row_count=len(df),
            missing_required=missing_required,
            missing_optional=missing_optional,
            message=f"Missing required columns: {', '.join(missing_required)}",
            exchange_key=exchange_key,
        )

    # Try to extract date range from "time" column
    date_start = date_end = None
    if "time" in cols:
        try:
            times = pd.to_datetime(df["time"], errors="coerce").dropna()
            if not times.empty:
                date_start = times.min().strftime("%Y-%m-%d")
                date_end = times.max().strftime("%Y-%m-%d")
        except Exception:
            pass

    status = "warning" if missing_optional else "valid"
    msg = ""
    if missing_optional:
        msg = f"Optional columns not found: {', '.join(missing_optional)}. Values will be estimated."

    return ValidationResult(
        status=status,
        row_count=len(df),
        date_start=date_start,
        date_end=date_end,
        missing_required=[],
        missing_optional=missing_optional,
        message=msg,
        exchange_key=exchange_key,
    )


def load_ledgers(
    filepath: str,
    wallet_id: str = "Kraken",
    exchange_key: str = "kraken",
    fallback_amountusd: bool = True,
) -> list[LedgerEntry]:
    """
    Loads a ledger CSV and returns a list of LedgerEntry objects.
    Raises ValueError with a user-friendly message if the file is invalid.
    """
    result = validate_file(filepath, exchange_key)
    if result.status == "error":
        raise ValueError(
            f"'{filepath}' cannot be loaded.\n"
            f"{result.message}\n\n"
            f"Please export a '{exchange_key}' Ledger CSV and try again."
        )

    df = pd.read_csv(filepath).fillna("")
    entries = []

    for _, row in df.iterrows():
        # amountusd — optional, fall back to 0 if missing
        if fallback_amountusd:
            raw_usd = str(row.get("amountusd", "0")).strip()
        else:
            raw_usd = str(row.get("amountusd", "")).strip()

        try:
            amountusd = Decimal(raw_usd) if raw_usd and raw_usd not in ("", "nan") else Decimal("0")
        except InvalidOperation:
            amountusd = Decimal("0")

        try:
            time_val = datetime.strptime(str(row["time"]).strip(), "%Y-%m-%d %H:%M:%S")
        except ValueError:
            # Try alternate format
            try:
                time_val = datetime.fromisoformat(str(row["time"]).strip())
            except Exception as e:
                logger.warning(f"Row skipped: unparseable time '{row.get('time')}' ({e})")
                continue  # Skip unparseable rows

        try:
            entry = LedgerEntry(
                txid=str(row["txid"]),
                refid=str(row["refid"]) if str(row.get("refid", "")).strip() else str(row["txid"]),
                time=time_val,
                type=str(row["type"]),
                subtype=str(row.get("subtype", "")),
                asset=str(row["asset"]),
                amount=Decimal(str(row["amount"])),
                fee=Decimal(str(row["fee"])),
                balance=Decimal(str(row["balance"])),
                amountusd=amountusd,
                wallet_id=wallet_id,
            )
            entries.append(entry)
        except (KeyError, InvalidOperation) as e:
            logger.warning(f"Row skipped: missing/invalid required field for TXID '{row.get('txid', 'Unknown')}' ({e})")
            continue  # Skip malformed rows silently

    return entries


def group_entries_by_event(all_entries: list[LedgerEntry]) -> list[list[LedgerEntry]]:
    """
    Groups ledger entries by refid (transaction reference).
    Returns a chronologically sorted list of events.
    """
    grouped: dict[str, list[LedgerEntry]] = {}
    for entry in all_entries:
        grouped.setdefault(entry.refid, []).append(entry)

    events = list(grouped.values())
    events.sort(key=lambda ev: ev[0].time)
    return events


# Legacy compatibility shim
def detect_file_type(filepath: str) -> str:
    """Quick file type check used by the file badge in the legacy UI."""
    result = validate_file(filepath, "kraken")
    if result.status in ("valid", "warning"):
        return "ledger"
    # Try generic
    result2 = validate_file(filepath, "generic")
    if result2.status in ("valid", "warning"):
        return "ledger"
    return "unknown"
