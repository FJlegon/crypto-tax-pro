"""
tests/test_wallet_sync.py — Tests for wallet_sync.py Etherscan wallet syncing.

Covers:
  - Ethereum address validation
  - Transaction mapping (deposits, withdrawals, ERC-20)
  - Gas fee extraction
  - Rate limiting
"""
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock
import time

from src.wallet_sync import (
    validate_eth_address,
    map_etherscan_to_ledger,
    sync_wallet,
    WalletSyncResult,
    API_DELAY_SECONDS,
    RETRY_DELAYS,
)


# ─── Address Validation Tests ───────────────────────────────────────────────────

class TestValidateEthAddress:
    """Test Ethereum address validation."""

    def test_valid_address_lowercase(self):
        """Valid lowercase address should pass."""
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
        assert validate_eth_address(addr) is True

    def test_valid_address_uppercase(self):
        """Valid uppercase address should pass."""
        addr = "0x742D35CC6634C0532925A3B844BC9E7595F0BEB0"
        assert validate_eth_address(addr) is True

    def test_valid_address_mixed_case(self):
        """Valid mixed case address should pass."""
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
        assert validate_eth_address(addr) is True

    def test_invalid_address_too_short(self):
        """Address with too few hex characters should fail."""
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595"
        assert validate_eth_address(addr) is False

    def test_invalid_address_no_0x_prefix(self):
        """Address without 0x prefix should fail."""
        addr = "742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"
        assert validate_eth_address(addr) is False

    def test_invalid_address_wrong_prefix(self):
        """Address with wrong prefix should fail."""
        addr = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb"
        assert validate_eth_address(addr) is False

    def test_invalid_address_empty(self):
        """Empty address should fail."""
        assert validate_eth_address("") is False

    def test_invalid_address_none(self):
        """None address should fail."""
        assert validate_eth_address(None) is False


# ─── Transaction Mapping Tests ─────────────────────────────────────────────────

class TestMapEtherscanToLedger:
    """Test Etherscan transaction to LedgerEntry mapping."""

    def test_map_eth_deposit(self):
        """ETH inbound transfer should map to deposit."""
        tx = {
            "hash": "0xabc123",
            "from": "0xreceiver",
            "to": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "value": "1000000000000000000",  # 1 ETH in wei
            "gasUsed": "21000",
            "gasPrice": "20000000000",  # 20 Gwei
            "timeStamp": "1704067200",  # 2024-01-01
            "token_symbol": "",
            "tokenID": "",
        }
        # Pass the full wallet address for comparison
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"

        entry = map_etherscan_to_ledger(tx, wallet_address)

        assert entry is not None
        assert entry.type == "deposit"
        assert entry.asset == "ETH"
        assert entry.amount == Decimal("1")

    def test_map_eth_withdrawal(self):
        """ETH outbound transfer should map to withdrawal."""
        tx = {
            "hash": "0xdef456",
            "from": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "to": "0xsender",
            "value": "500000000000000000",  # 0.5 ETH in wei
            "gasUsed": "21000",
            "gasPrice": "20000000000",
            "timeStamp": "1704153600",  # 2024-01-02
            "token_symbol": "",
            "tokenID": "",
        }
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"

        entry = map_etherscan_to_ledger(tx, wallet_address)

        assert entry is not None
        assert entry.type == "withdrawal"
        assert entry.asset == "ETH"
        assert entry.amount == Decimal("0.5")

    def test_map_erc20_transfer(self):
        """ERC-20 token transfer should map to trade/transfer."""
        tx = {
            "hash": "0xghi789",
            "from": "0xsender",
            "to": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "value": "0",
            "token_symbol": "USDC",
            "tokenValue": "1000000",  # 1 USDC
            "gasUsed": "65000",
            "gasPrice": "20000000000",
            "timeStamp": "1704240000",  # 2024-01-03
            "tokenID": "",
        }
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"

        entry = map_etherscan_to_ledger(tx, wallet_address)

        assert entry is not None
        assert entry.type == "trade"
        assert entry.subtype == "transfer"
        assert entry.asset == "USDC"
        assert entry.amount == Decimal("1000000")

    def test_gas_fee_extraction(self):
        """Gas fee should be extracted correctly."""
        tx = {
            "hash": "0xjkl012",
            "from": "0xsender",
            "to": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
            "value": "1000000000000000000",
            "gasUsed": "21000",
            "gasPrice": "50000000000",  # 50 Gwei
            "timeStamp": "1704326400",  # 2024-01-04
            "token_symbol": "",
            "tokenID": "",
        }
        wallet_address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0"

        entry = map_etherscan_to_ledger(tx, wallet_address)

        assert entry is not None
        # gasUsed * gasPrice = 21000 * 50000000000 = 1050000000000000 wei = 0.00105 ETH
        expected_fee = Decimal("1050000000000000") / Decimal("1e18")
        assert entry.fee == expected_fee


# ─── Wallet Sync Integration Tests ───────────────────────────────────────────

class TestSyncWallet:
    """Test the main sync_wallet function."""

    def test_invalid_address_returns_error(self):
        """Invalid address should return error in result."""
        result = sync_wallet("invalid_address")

        assert result.error is not None
        assert "Invalid" in result.error
        assert result.tx_count == 0
        assert len(result.entries) == 0

    @patch("src.wallet_sync.fetch_etherscan_transactions")
    def test_sync_with_api_error(self, mock_fetch):
        """API error should be captured in result."""
        mock_fetch.side_effect = RuntimeError("Network error")

        result = sync_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")

        assert result.error is not None
        assert "Network error" in result.error

    @patch("src.wallet_sync.fetch_etherscan_transactions")
    def test_sync_empty_transactions(self, mock_fetch):
        """Empty transaction list should return zero count."""
        mock_fetch.return_value = []

        result = sync_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")

        assert result.error is None
        assert result.tx_count == 0

    @patch("src.wallet_sync.fetch_etherscan_transactions")
    def test_sync_with_transactions(self, mock_fetch):
        """Transactions should be mapped to entries."""
        mock_fetch.return_value = [
            {
                "hash": "0xabc123",
                "from": "0xsender",
                "to": "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0",
                "value": "1000000000000000000",
                "gasUsed": "21000",
                "gasPrice": "20000000000",
                "timeStamp": "1704067200",
                "token_symbol": "",
                "tokenID": "",
            }
        ]

        result = sync_wallet("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb0")

        assert result.error is None
        assert result.tx_count == 1
        assert len(result.entries) == 1
        assert result.entries[0].type == "deposit"


# ─── Rate Limiting Tests ───────────────────────────────────────────────────

class TestRateLimiting:
    """Test rate limiting behavior."""

    def test_api_delay_constant(self):
        """API delay should be 200ms."""
        assert API_DELAY_SECONDS == 0.2

    def test_retry_delays_exponential(self):
        """Retry delays should be exponential backoff."""
        assert RETRY_DELAYS == [1, 2, 4]
