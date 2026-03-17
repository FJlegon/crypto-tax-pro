"""
tests/test_fifo_engine.py — Comprehensive pytest test suite for the FIFO engine.

Covers:
  - P1-A: Long-Term threshold (>= 365 days)
  - P1-B: Staking lots use net_amount (after fees)
  - P1-C: Missing Basis produces term='Unknown', triggers anomaly
  - P2-A: Internal transfer withdrawal fee consumed as non-taxable
  - P2-B: detect_security_wash_sales accepts custom security_tokens param
  - P2-C: determine_box imported from tax_reporter only (no duplicate)
  - Edge cases: dust threshold, zero-fee staking, long-term boundary exact day
"""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta

from src.models import LedgerEntry, AssetLot, TaxableEvent
from src.fifo_engine import FIFOEngine
from src.tax_reporter import determine_box, build_form_8949_csv, print_tax_summary
from src.anomaly_detector import detect_anomalies, get_anomaly_summary
from src.wash_sale_detector import detect_security_wash_sales, DEFAULT_SECURITY_TOKENS


# ─── Helpers ────────────────────────────────────────────────────────────────

def make_entry(
    asset: str,
    amount: float,
    fee: float = 0.0,
    type_: str = "trade",
    wallet: str = "kraken",
    time: datetime | None = None,
    amountusd: float = 0.0,
    txid: str = "TX1",
    refid: str = "R1",
) -> LedgerEntry:
    """Factory function for LedgerEntry — reduces boilerplate in tests."""
    return LedgerEntry(
        txid=txid,
        refid=refid,
        time=time or datetime(2025, 1, 1),
        type=type_,
        subtype="",
        asset=asset,
        amount=Decimal(str(amount)),
        fee=Decimal(str(fee)),
        balance=Decimal("0"),
        amountusd=Decimal(str(amountusd)),
        wallet_id=wallet,
    )


def engine_with_lot(
    asset: str = "BTC",
    amount: float = 1.0,
    cost_usd: float = 40_000.0,
    acquired: datetime | None = None,
    wallet: str = "kraken",
) -> FIFOEngine:
    """Returns an engine pre-loaded with a single lot."""
    engine = FIFOEngine()
    engine.inventory[(wallet, asset)].append(
        AssetLot(
            asset=asset,
            amount=Decimal(str(amount)),
            cost_basis_usd=Decimal(str(cost_usd)),
            date_acquired=acquired or datetime(2024, 1, 1),
            wallet_id=wallet,
        )
    )
    return engine


# ─── P1-A: Long-Term threshold ───────────────────────────────────────────────

class TestLongTermThreshold:
    """BUG-01: term should be Long-Term when days_held >= 365."""

    def test_exactly_365_days_is_long_term(self):
        """A disposal exactly 1 year after acquisition must be Long-Term."""
        acquired = datetime(2024, 1, 1)
        disposed = datetime(2025, 1, 1)  # exactly 365 days later
        engine = engine_with_lot(acquired=acquired)
        engine._consume_inventory(
            "kraken", "BTC", Decimal("1"), Decimal("50000"), disposed, "test", True
        )
        assert engine.taxable_events[0].term == "Long-Term"

    def test_364_days_is_short_term(self):
        """364 days must still be Short-Term."""
        acquired = datetime(2024, 1, 1)
        disposed = acquired + timedelta(days=364)
        engine = engine_with_lot(acquired=acquired)
        engine._consume_inventory(
            "kraken", "BTC", Decimal("1"), Decimal("50000"), disposed, "test", True
        )
        assert engine.taxable_events[0].term == "Short-Term"

    def test_366_days_is_long_term(self):
        """366 days must also be Long-Term."""
        acquired = datetime(2024, 1, 1)
        disposed = acquired + timedelta(days=366)
        engine = engine_with_lot(acquired=acquired)
        engine._consume_inventory(
            "kraken", "BTC", Decimal("1"), Decimal("50000"), disposed, "test", True
        )
        assert engine.taxable_events[0].term == "Long-Term"

    def test_zero_days_is_short_term(self):
        """Same-day buy and sell must be Short-Term."""
        now = datetime(2025, 6, 15)
        engine = engine_with_lot(acquired=now)
        engine._consume_inventory(
            "kraken", "BTC", Decimal("1"), Decimal("50000"), now, "test", True
        )
        assert engine.taxable_events[0].term == "Short-Term"


# ─── P1-B: Staking lot uses net_amount ───────────────────────────────────────

class TestStakingNetAmount:
    """BUG-02: staking lots must reflect amount minus fee, not gross amount."""

    def test_staking_lot_excludes_fee(self):
        """Earn reward of 1.0 ETH with 0.001 fee → lot must be 0.999 ETH."""
        engine = FIFOEngine()
        acq = make_entry("ETH", 1.0, fee=0.001, type_="earn", amountusd=3000.0)
        engine._handle_income([acq], Decimal("3000"))
        lot = engine.inventory[("kraken", "ETH")][0]
        assert lot.amount == Decimal("0.999")

    def test_staking_zero_fee_lot_equals_amount(self):
        """Earn reward with 0 fee → lot equals gross amount."""
        engine = FIFOEngine()
        acq = make_entry("ETH", 2.0, fee=0.0, type_="earn", amountusd=6000.0)
        engine._handle_income([acq], Decimal("6000"))
        lot = engine.inventory[("kraken", "ETH")][0]
        assert lot.amount == Decimal("2.0")

    def test_staking_income_usd_recorded(self):
        """ordinary_income_usd must accumulate from staking rewards."""
        engine = FIFOEngine()
        acq = make_entry("ETH", 1.0, fee=0.0, type_="earn", amountusd=3000.0)
        engine._handle_income([acq], Decimal("3000"))
        assert engine.ordinary_income_usd == Decimal("3000")

    def test_staking_cost_basis_matches_income(self):
        """The cost basis of the staking lot must equal the income recorded."""
        engine = FIFOEngine()
        acq = make_entry("ETH", 1.0, fee=0.001, type_="earn", amountusd=3000.0)
        engine._handle_income([acq], Decimal("3000"))
        lot = engine.inventory[("kraken", "ETH")][0]
        assert lot.cost_basis_usd == Decimal("3000")


# ─── P1-C: Missing Basis → term='Unknown' ────────────────────────────────────

class TestMissingBasisUnknownTerm:
    """RIESGO-02: missing basis disposals must use term='Unknown'."""

    def _make_event(self) -> TaxableEvent:
        return TaxableEvent(
            description="0.1 BTC (Missing Basis)",
            date_acquired="VARIOUS",
            date_sold="06/01/2025",
            proceeds=Decimal("5000"),
            cost_basis=Decimal("0"),
            term="Unknown",
            wallet_id="kraken",
        )

    def test_missing_basis_term_is_unknown(self):
        """Engine must set term='Unknown' for missing basis disposals."""
        engine = FIFOEngine()
        # Sell BTC that was never acquired — forces missing basis path
        engine._consume_inventory(
            "kraken", "BTC", Decimal("0.1"), Decimal("5000"),
            datetime(2025, 6, 1), "test_tx", True
        )
        assert engine.taxable_events[0].term == "Unknown"

    def test_unknown_term_generates_anomaly(self):
        """detect_anomalies must produce an 'unknown_term' anomaly."""
        ev = self._make_event()
        anomalies = detect_anomalies([ev], [])
        types = {a.anomaly_type for a in anomalies}
        assert "unknown_term" in types

    def test_unknown_term_anomaly_has_resolution_options(self):
        """unknown_term anomaly must offer Short-Term and Long-Term options."""
        ev = self._make_event()
        anomalies = detect_anomalies([ev], [])
        unknown = next(a for a in anomalies if a.anomaly_type == "unknown_term")
        assert len(unknown.resolution_options) >= 2

    def test_determine_box_unknown_gain(self):
        """determine_box with Unknown term and a gain must return 'G' (conservative ST)."""
        assert determine_box("Unknown", Decimal("5000"), Decimal("0")) == "G"

    def test_determine_box_unknown_loss(self):
        """determine_box with Unknown term and a loss must return 'I' (conservative ST)."""
        assert determine_box("Unknown", Decimal("100"), Decimal("5000")) == "I"

    def test_form_8949_csv_maps_unknown_to_unverified_label(self):
        """Form 8949 CSV must label 'Unknown' term as 'Short-Term (Unverified)'."""
        ev = self._make_event()
        csv_output = build_form_8949_csv([ev])
        assert "Short-Term (Unverified)" in csv_output

    def test_print_tax_summary_includes_unknown_line(self, capsys):
        """print_tax_summary must display an 'Unknown Term Gain' line when applicable."""
        ev = self._make_event()
        print_tax_summary([ev], Decimal("0"))
        captured = capsys.readouterr()
        assert "Unknown Term" in captured.out


# ─── P2-A: Transfer withdrawal fee consumed ──────────────────────────────────

class TestTransferWithdrawalFee:
    """BUG-03: withdrawal fees during internal transfers must reduce source inventory."""

    def _build_transfer_entries(self, fee: float = 0.0001):
        """Create a matched pair of out/in entries simulating a cross-wallet transfer."""
        out_e = make_entry(
            "BTC", -1.0, fee=fee, type_="withdrawal",
            wallet="kraken", txid="TX_OUT", refid="R_TRANSFER",
            time=datetime(2025, 3, 1)
        )
        in_e = make_entry(
            "BTC", 1.0, fee=0.0, type_="deposit",
            wallet="ledger", txid="TX_IN", refid="R_TRANSFER",
            time=datetime(2025, 3, 1)
        )
        return out_e, in_e

    def test_transfer_fee_reduces_source_inventory(self):
        """After transfer with 0.0001 BTC fee, source wallet should have 0 inventory."""
        engine = engine_with_lot("BTC", amount=1.0, wallet="kraken")
        out_e, in_e = self._build_transfer_entries(fee=0.0001)
        engine._process_internal_transfers([out_e, in_e])

        # Source should have no remaining BTC
        source_lots = engine.inventory.get(("kraken", "BTC"), [])
        source_balance = sum(l.amount for l in source_lots)
        assert source_balance == Decimal("0"), f"Expected 0, got {source_balance}"

    def test_transfer_destination_receives_correct_amount(self):
        """Destination wallet must receive the gross transfer amount (not net of fee)."""
        engine = engine_with_lot("BTC", amount=1.0, wallet="kraken")
        out_e, in_e = self._build_transfer_entries(fee=0.0001)
        engine._process_internal_transfers([out_e, in_e])

        dest_lots = engine.inventory.get(("ledger", "BTC"), [])
        dest_balance = sum(l.amount for l in dest_lots)
        assert dest_balance == Decimal("1.0"), f"Expected 1.0, got {dest_balance}"

    def test_transfer_zero_fee_no_extra_consumption(self):
        """A transfer with 0 fee must not alter total inventory balance."""
        engine = engine_with_lot("BTC", amount=1.0, wallet="kraken")
        out_e, in_e = self._build_transfer_entries(fee=0.0)
        engine._process_internal_transfers([out_e, in_e])

        dest_balance = sum(
            l.amount for l in engine.inventory.get(("ledger", "BTC"), [])
        )
        assert dest_balance == Decimal("1.0")

    def test_transfer_fee_not_taxable(self):
        """The withdrawal fee consumption must NOT create a taxable event."""
        engine = engine_with_lot("BTC", amount=1.0, wallet="kraken")
        out_e, in_e = self._build_transfer_entries(fee=0.0001)
        engine._process_internal_transfers([out_e, in_e])
        assert len(engine.taxable_events) == 0


# ─── P2-B: Configurable SECURITY_TOKENS ──────────────────────────────────────

class TestConfigurableSecurityTokens:
    """RIESGO-01: wash sale detection must respect the security_tokens parameter."""

    def _make_loss_event(self, asset: str = "SOL") -> TaxableEvent:
        return TaxableEvent(
            description=f"10 {asset}",
            date_acquired="01/01/2025",
            date_sold="06/15/2025",
            proceeds=Decimal("100"),
            cost_basis=Decimal("500"),
            term="Short-Term",
            wallet_id="kraken",
        )

    def _make_raw_acq(self, asset: str = "SOL", days_offset: int = 10):
        acq_time = datetime(2025, 6, 15) + timedelta(days=days_offset)
        entry = make_entry(asset, 10.0, time=acq_time, wallet="kraken", refid="R_ACQ")
        return [[entry]]

    def test_default_tokens_flag_sol(self):
        """With default tokens, a SOL loss followed by re-buy should be flagged."""
        event = self._make_loss_event("SOL")
        raw = self._make_raw_acq("SOL")
        flagged = detect_security_wash_sales([event], raw)
        assert flagged == 1
        assert event.adjustment_code == "W"

    def test_empty_set_disables_wash_sale(self):
        """Passing empty frozenset must NOT flag any wash sales."""
        event = self._make_loss_event("SOL")
        raw = self._make_raw_acq("SOL")
        flagged = detect_security_wash_sales([event], raw, security_tokens=frozenset())
        assert flagged == 0
        assert event.adjustment_code == ""

    def test_custom_set_flags_custom_token(self):
        """A custom token set must flag losses on tokens in that set."""
        event = self._make_loss_event("XRP")
        raw = self._make_raw_acq("XRP")
        flagged = detect_security_wash_sales(
            [event], raw, security_tokens=frozenset({"XRP"})
        )
        assert flagged == 1

    def test_custom_set_ignores_default_tokens(self):
        """When a custom set is provided, default tokens not in it must NOT be flagged."""
        event = self._make_loss_event("ADA")
        raw = self._make_raw_acq("ADA")
        # Pass a set that has XRP but not ADA
        flagged = detect_security_wash_sales(
            [event], raw, security_tokens=frozenset({"XRP"})
        )
        assert flagged == 0

    def test_gains_never_flagged(self):
        """Wash sale must never apply to gains, regardless of token."""
        event = TaxableEvent(
            description="10 SOL",
            date_acquired="01/01/2025",
            date_sold="06/15/2025",
            proceeds=Decimal("1000"),
            cost_basis=Decimal("100"),
            term="Short-Term",
            wallet_id="kraken",
        )
        raw = self._make_raw_acq("SOL")
        flagged = detect_security_wash_sales([event], raw)
        assert flagged == 0


# ─── P2-C: DRY — single determine_box source ─────────────────────────────────

class TestDryDetermineBox:
    """P2-C: both modules must share the same determine_box implementation."""

    def test_same_function_object(self):
        """form_1099_da_importer must re-export the exact same function from tax_reporter."""
        from src.tax_reporter import determine_box as from_reporter
        from src.form_1099_da_importer import determine_box as from_importer
        assert from_reporter is from_importer

    def test_short_term_gain_box_g(self):
        assert determine_box("Short-Term", Decimal("1000"), Decimal("500")) == "G"

    def test_short_term_loss_box_i(self):
        assert determine_box("Short-Term", Decimal("100"), Decimal("500")) == "I"

    def test_long_term_gain_box_j(self):
        assert determine_box("Long-Term", Decimal("1000"), Decimal("500")) == "J"

    def test_long_term_loss_box_l(self):
        assert determine_box("Long-Term", Decimal("100"), Decimal("500")) == "L"

    def test_unknown_term_gain_box_g(self):
        assert determine_box("Unknown", Decimal("1000"), Decimal("500")) == "G"

    def test_unknown_term_loss_box_i(self):
        assert determine_box("Unknown", Decimal("100"), Decimal("500")) == "I"


# ─── Anomaly Detector general ────────────────────────────────────────────────

class TestAnomalyDetector:
    """General anomaly detection correctness."""

    def test_empty_events_returns_no_anomalies(self):
        assert detect_anomalies([], []) == []

    def test_missing_basis_with_proceeds_generates_anomaly(self):
        ev = TaxableEvent("0.1 BTC", "VARIOUS", "01/01/2025",
                          Decimal("5000"), Decimal("0"), "Short-Term", "kraken")
        anomalies = detect_anomalies([ev], [])
        assert any(a.anomaly_type == "missing_basis" for a in anomalies)

    def test_zero_basis_zero_proceeds_no_anomaly(self):
        """$0 basis with $0 proceeds is a dust event, not a reportable anomaly."""
        ev = TaxableEvent("0.00000001 BTC", "VARIOUS", "01/01/2025",
                          Decimal("0"), Decimal("0"), "Short-Term", "kraken")
        anomalies = detect_anomalies([ev], [])
        missing = [a for a in anomalies if a.anomaly_type == "missing_basis"]
        assert len(missing) == 0

    def test_anomaly_summary_counts(self):
        ev = TaxableEvent("0.1 BTC", "VARIOUS", "01/01/2025",
                          Decimal("5000"), Decimal("0"), "Unknown", "kraken")
        anomalies = detect_anomalies([ev], [])
        summary = get_anomaly_summary(anomalies)
        assert summary["total"] >= 1
        assert summary["warnings"] >= 1
