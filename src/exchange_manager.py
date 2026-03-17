"""
exchange_manager.py — Registry of supported exchanges and their CSV formats.
Each ExchangeConfig defines required/optional columns, export guides, and
the validation logic needed by data_loader.py.
"""
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class ExchangeConfig:
    key: str                        # Internal key, e.g. "kraken"
    name: str                       # Display name, e.g. "Kraken"
    icon: str                       # Flet icon string
    color: str                      # Hex accent color
    file_type: str                  # "ledger" or "trades"
    required_cols: set[str]
    optional_cols: set[str]
    guide: list[str]                # Step-by-step export instructions
    export_url: str                 # URL to open in browser
    enabled: bool = True
    coming_soon: bool = False


EXCHANGES: dict[str, ExchangeConfig] = {
    "kraken": ExchangeConfig(
        key="kraken",
        name="Kraken",
        icon="account_balance",
        color="#5741d9",
        file_type="ledger",
        required_cols={"txid", "refid", "time", "type", "asset", "amount", "fee", "balance"},
        optional_cols={"amountusd", "subtype"},
        guide=[
            "1. Log in to Kraken → click your name (top-right) → History.",
            "2. Click 'Export' → select 'Ledgers' (NOT Trades or Orders).",
            "3. Set Start Date: Jan 1, 2025 | End Date: Dec 31, 2025.",
            "4. Leave all asset filters as 'All'.",
            "5. Click 'Submit' and download the CSV file.",
        ],
        export_url="https://pro.kraken.com/app/history/trades",
        enabled=True,
    ),
    "coinbase": ExchangeConfig(
        key="coinbase",
        name="Coinbase",
        icon="storefront",
        color="#0052ff",
        file_type="transactions",
        required_cols={"Timestamp", "Transaction Type", "Asset", "Quantity Transacted",
                       "Spot Price Currency", "Spot Price at Transaction", "Total (inclusive of fees and/or spread)"},
        optional_cols={"Notes", "ID"},
        guide=[
            "1. Log in to Coinbase → Profile → Statements.",
            "2. Click 'Generate' → select 'Transaction History'.",
            "3. Choose date range: Jan 1 – Dec 31, 2025.",
            "4. Download the CSV file.",
        ],
        export_url="https://accounts.coinbase.com/profile",
        enabled=False,
        coming_soon=True,
    ),
    "binanceus": ExchangeConfig(
        key="binanceus",
        name="Binance.US",
        icon="currency_exchange",
        color="#f0b90b",
        file_type="trades",
        required_cols=set(),
        optional_cols=set(),
        guide=["Coming soon."],
        export_url="https://www.binance.us/",
        enabled=False,
        coming_soon=True,
    ),
    "ledger": ExchangeConfig(
        key="ledger",
        name="Ledger (Hardware)",
        icon="usb",
        color="#ff5c00",
        file_type="generic",
        required_cols=set(),
        optional_cols=set(),
        guide=["Coming soon — connect via Ledger Live export."],
        export_url="https://www.ledger.com/ledger-live",
        enabled=False,
        coming_soon=True,
    ),
    "generic": ExchangeConfig(
        key="generic",
        name="Generic CSV",
        icon="table_chart",
        color="#607d8b",
        file_type="ledger",
        required_cols={"txid", "refid", "time", "type", "asset", "amount", "fee", "balance"},
        optional_cols={"amountusd"},
        guide=[
            "Ensure your CSV has these columns:",
            "  txid, refid, time, type, asset, amount, fee, balance",
            "Time format must be: YYYY-MM-DD HH:MM:SS",
            "Amount/fee/balance must be numeric (no currency symbols).",
        ],
        export_url="",
        enabled=True,
    ),
}


def get_enabled_exchanges() -> list[ExchangeConfig]:
    return [ex for ex in EXCHANGES.values()]


def get_exchange(key: str) -> Optional[ExchangeConfig]:
    return EXCHANGES.get(key)
