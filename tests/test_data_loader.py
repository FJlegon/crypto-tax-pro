"""
tests/test_data_loader.py — Tests for data_loader.py including Coinbase CSV parsing.

Covers:
  - Coinbase transaction type mapping
  - Coinbase date parsing
  - Coinbase validation
"""
import pytest
import pandas as pd
from decimal import Decimal
from datetime import datetime

from src.data_loader import (
    _parse_coinbase_timestamp,
    _map_coinbase_transaction_type,
    _load_coinbase_csv,
    validate_file,
    load_ledgers,
)
from src.models import LedgerEntry


# ─── Coinbase Transaction Type Mapping Tests ────────────────────────────────

class TestCoinbaseTransactionTypeMapping:
    """Test Coinbase transaction type to LedgerEntry type/subtype mapping."""

    def test_buy_maps_to_trade_buy(self):
        """Buy transaction should map to type='trade', subtype='buy'."""
        entry_type, subtype = _map_coinbase_transaction_type("Buy")
        assert entry_type == "trade"
        assert subtype == "buy"

    def test_sell_maps_to_trade_sell(self):
        """Sell transaction should map to type='trade', subtype='sell'."""
        entry_type, subtype = _map_coinbase_transaction_type("Sell")
        assert entry_type == "trade"
        assert subtype == "sell"

    def test_deposit_maps_to_deposit(self):
        """Deposit transaction should map to type='deposit'."""
        entry_type, subtype = _map_coinbase_transaction_type("Deposit")
        assert entry_type == "deposit"
        assert subtype == ""

    def test_withdrawal_maps_to_withdrawal(self):
        """Withdrawal transaction should map to type='withdrawal'."""
        entry_type, subtype = _map_coinbase_transaction_type("Withdrawal")
        assert entry_type == "withdrawal"
        assert subtype == ""

    def test_reward_maps_to_earn_reward(self):
        """Reward transaction should map to type='earn', subtype='reward'."""
        entry_type, subtype = _map_coinbase_transaction_type("Reward")
        assert entry_type == "earn"
        assert subtype == "reward"

    def test_staking_maps_to_earn_staking(self):
        """Staking transaction should map to type='earn', subtype='staking'."""
        entry_type, subtype = _map_coinbase_transaction_type("Staking")
        assert entry_type == "earn"
        assert subtype == "staking"

    def test_coinbase_earn_maps_to_income_earn(self):
        """Coinbase Earn should map to type='income', subtype='earn'."""
        entry_type, subtype = _map_coinbase_transaction_type("Coinbase Earn")
        assert entry_type == "income"
        assert subtype == "earn"

    def test_advanced_trade_buy_maps_to_trade_buy(self):
        """Advanced Trade Buy should map to type='trade', subtype='buy'."""
        entry_type, subtype = _map_coinbase_transaction_type("Advanced Trade Buy")
        assert entry_type == "trade"
        assert subtype == "buy"

    def test_receive_maps_to_deposit(self):
        """Receive should map to type='deposit'."""
        entry_type, subtype = _map_coinbase_transaction_type("Receive")
        assert entry_type == "deposit"
        assert subtype == ""

    def test_send_maps_to_withdrawal(self):
        """Send should map to type='withdrawal'."""
        entry_type, subtype = _map_coinbase_transaction_type("Send")
        assert entry_type == "withdrawal"
        assert subtype == ""

    def test_unknown_type_maps_to_unknown(self):
        """Unknown transaction type should map to 'unknown'."""
        entry_type, subtype = _map_coinbase_transaction_type("UnknownType")
        assert entry_type == "unknown"
        assert subtype == ""


# ─── Coinbase Date Parsing Tests ─────────────────────────────────────────────

class TestCoinbaseDateParsing:
    """Test Coinbase timestamp parsing."""

    def test_parse_12hour_format(self):
        """Parse 12-hour format: '1/15/2025 10:30:45 AM'."""
        result = _parse_coinbase_timestamp("1/15/2025 10:30:45 AM")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 10
        assert result.minute == 30
        assert result.second == 45

    def test_parse_12hour_format_pm(self):
        """Parse 12-hour PM format: '6/20/2025 3:45:30 PM'."""
        result = _parse_coinbase_timestamp("6/20/2025 3:45:30 PM")
        assert result is not None
        assert result.hour == 15
        assert result.minute == 45
        assert result.second == 30

    def test_parse_iso_format(self):
        """Parse ISO format: '2025-01-15T10:30:45Z'."""
        result = _parse_coinbase_timestamp("2025-01-15T10:30:45Z")
        assert result is not None
        assert result.year == 2025
        assert result.month == 1
        assert result.day == 15

    def test_parse_iso_format_lowercase_z(self):
        """Parse ISO format with lowercase z: '2025-01-15T10:30:45z'."""
        result = _parse_coinbase_timestamp("2025-01-15T10:30:45z")
        assert result is not None
        assert result.year == 2025

    def test_parse_24hour_format(self):
        """Parse 24-hour format: '2025-01-15 10:30:45'."""
        result = _parse_coinbase_timestamp("2025-01-15 10:30:45")
        assert result is not None
        assert result.hour == 10

    def test_parse_empty_returns_none(self):
        """Empty string should return None."""
        result = _parse_coinbase_timestamp("")
        assert result is None

    def test_parse_invalid_returns_none(self):
        """Invalid format should return None."""
        result = _parse_coinbase_timestamp("not-a-date")
        assert result is None


# ─── Coinbase CSV Loading Tests ─────────────────────────────────────────────

class TestLoadCoinbaseCSV:
    """Test full Coinbase CSV loading."""

    def test_load_buy_transaction(self):
        """Load a Buy transaction from Coinbase CSV."""
        df = pd.DataFrame([
            {
                "Timestamp": "1/15/2025 10:30:45 AM",
                "Transaction Type": "Buy",
                "Asset": "BTC",
                "Quantity Transacted": "0.5",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "50000",
                "Total (inclusive of fees and/or spread)": "-25000",
                "Notes": "",
                "ID": "TX123",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.type == "trade"
        assert entry.subtype == "buy"
        assert entry.asset == "BTC"
        assert entry.amount == Decimal("0.5")
        assert entry.txid == "TX123"

    def test_load_sell_transaction(self):
        """Load a Sell transaction from Coinbase CSV."""
        df = pd.DataFrame([
            {
                "Timestamp": "2025-01-15T10:30:45Z",
                "Transaction Type": "Sell",
                "Asset": "ETH",
                "Quantity Transacted": "2.0",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "3000",
                "Total (inclusive of fees and/or spread)": "6000",
                "Notes": "",
                "ID": "TX456",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.type == "trade"
        assert entry.subtype == "sell"
        assert entry.asset == "ETH"
        assert entry.amount == Decimal("2.0")
        assert entry.amountusd == Decimal("6000.00")

    def test_load_deposit_transaction(self):
        """Load a Deposit transaction from Coinbase CSV."""
        df = pd.DataFrame([
            {
                "Timestamp": "2025-01-20 08:00:00",
                "Transaction Type": "Deposit",
                "Asset": "USDC",
                "Quantity Transacted": "1000",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "1",
                "Total (inclusive of fees and/or spread)": "1000",
                "Notes": "",
                "ID": "TX789",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.type == "deposit"
        assert entry.asset == "USDC"
        assert entry.amount == Decimal("1000")

    def test_load_reward_transaction(self):
        """Load a Reward/Staking transaction from Coinbase CSV."""
        df = pd.DataFrame([
            {
                "Timestamp": "2/1/2025 12:00:00 PM",
                "Transaction Type": "Staking",
                "Asset": "ETH",
                "Quantity Transacted": "0.05",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "3200",
                "Total (inclusive of fees and/or spread)": "160",
                "Notes": "ETH2.0 Staking Reward",
                "ID": "TX999",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 1
        entry = entries[0]
        assert entry.type == "earn"
        assert entry.subtype == "staking"
        assert entry.amount == Decimal("0.05")
        assert entry.amountusd == Decimal("160.00")

    def test_skip_invalid_timestamp(self):
        """Rows with invalid timestamps should be skipped."""
        df = pd.DataFrame([
            {
                "Timestamp": "invalid",
                "Transaction Type": "Buy",
                "Asset": "BTC",
                "Quantity Transacted": "0.5",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "50000",
                "Total (inclusive of fees and/or spread)": "-25000",
                "Notes": "",
                "ID": "TX123",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 0  # Skip invalid rows

    def test_skip_missing_asset(self):
        """Rows with missing asset should be skipped."""
        df = pd.DataFrame([
            {
                "Timestamp": "1/15/2025 10:30:45 AM",
                "Transaction Type": "Buy",
                "Asset": "",
                "Quantity Transacted": "0.5",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "50000",
                "Total (inclusive of fees and/or spread)": "-25000",
                "Notes": "",
                "ID": "TX123",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 0  # Skip rows without asset

    def test_amountusd_calculation(self):
        """Verify amountusd = Spot Price × Quantity."""
        df = pd.DataFrame([
            {
                "Timestamp": "2025-01-15T10:30:45Z",
                "Transaction Type": "Buy",
                "Asset": "SOL",
                "Quantity Transacted": "10",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "150.25",
                "Total (inclusive of fees and/or spread)": "-1502.50",
                "Notes": "",
                "ID": "TX001",
            }
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 1
        # Spot Price × Quantity = 150.25 × 10 = 1502.50
        assert entries[0].amountusd == Decimal("1502.50")

    def test_multiple_rows(self):
        """Load multiple transactions from CSV."""
        df = pd.DataFrame([
            {
                "Timestamp": "1/15/2025 10:30:45 AM",
                "Transaction Type": "Buy",
                "Asset": "BTC",
                "Quantity Transacted": "0.5",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "50000",
                "Total (inclusive of fees and/or spread)": "-25000",
                "Notes": "",
                "ID": "TX001",
            },
            {
                "Timestamp": "1/20/2025 2:00:00 PM",
                "Transaction Type": "Sell",
                "Asset": "BTC",
                "Quantity Transacted": "0.2",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "52000",
                "Total (inclusive of fees and/or spread)": "10400",
                "Notes": "",
                "ID": "TX002",
            },
            {
                "Timestamp": "2/1/2025 12:00:00 PM",
                "Transaction Type": "Staking",
                "Asset": "ETH",
                "Quantity Transacted": "0.05",
                "Spot Price Currency": "USD",
                "Spot Price at Transaction": "3200",
                "Total (inclusive of fees and/or spread)": "160",
                "Notes": "",
                "ID": "TX003",
            },
        ])
        entries = _load_coinbase_csv(df, "coinbase_wallet")

        assert len(entries) == 3
        assert entries[0].type == "trade"
        assert entries[1].type == "trade"
        assert entries[2].type == "earn"


# ─── Coinbase Validation Tests ───────────────────────────────────────────

class TestCoinbaseValidation:
    """Test Coinbase file validation."""

    def test_validate_valid_coinbase_csv(self, tmp_path):
        """Valid Coinbase CSV should pass validation (or warning if missing optional)."""
        csv_file = tmp_path / "coinbase_test.csv"
        csv_file.write_text(
            "Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,"
            "Spot Price at Transaction,Total (inclusive of fees and/or spread),Notes,ID\n"
            "1/15/2025 10:30:45 AM,Buy,BTC,0.5,USD,50000,-25000,,TX001\n"
        )

        result = validate_file(str(csv_file), "coinbase")
        # Should be valid (or warning is acceptable due to optional columns)
        assert result.status in ("valid", "warning")
        assert result.row_count == 1

    def test_validate_missing_required_columns(self, tmp_path):
        """Missing required columns should fail validation."""
        csv_file = tmp_path / "coinbase_invalid.csv"
        csv_file.write_text(
            "Timestamp,Transaction Type\n"
            "1/15/2025 10:30:45 AM,Buy\n"
        )

        result = validate_file(str(csv_file), "coinbase")
        assert result.status == "error"
        assert len(result.missing_required) > 0
        assert "Asset" in result.missing_required

    def test_validate_missing_optional_columns(self, tmp_path):
        """Missing optional columns should give warning."""
        csv_file = tmp_path / "coinbase_optional.csv"
        csv_file.write_text(
            "Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,"
            "Spot Price at Transaction,Total (inclusive of fees and/or spread)\n"
            "1/15/2025 10:30:45 AM,Buy,BTC,0.5,USD,50000,-25000\n"
        )

        result = validate_file(str(csv_file), "coinbase")
        assert result.status == "warning"
        assert "Notes" in result.missing_optional


# ─── Integration: load_ledgers with Coinbase ─────────────────────────────

class TestLoadLedgersCoinbase:
    """Integration test: load_ledgers with Coinbase exchange."""

    def test_load_ledgers_coinbase(self, tmp_path):
        """Test load_ledgers with Coinbase exchange key."""
        csv_file = tmp_path / "coinbase.csv"
        csv_file.write_text(
            "Timestamp,Transaction Type,Asset,Quantity Transacted,Spot Price Currency,"
            "Spot Price at Transaction,Total (inclusive of fees and/or spread),Notes,ID\n"
            "1/15/2025 10:30:45 AM,Buy,BTC,0.5,USD,50000,-25000,,TX001\n"
            "1/20/2025 2:00:00 PM,Sell,ETH,2.0,USD,3000,6000,,TX002\n"
        )

        entries = load_ledgers(str(csv_file), wallet_id="Coinbase", exchange_key="coinbase")

        assert len(entries) == 2
        assert entries[0].wallet_id == "Coinbase"
        assert entries[0].type == "trade"
        assert entries[1].wallet_id == "Coinbase"
        assert entries[1].type == "trade"
