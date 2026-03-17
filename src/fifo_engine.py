"""
fifo_engine.py — FIFO Capital Gains Engine (Wallet-by-Wallet)
Compliant with IRS Rev. Proc. 2024-28.

NOTE: Modified to match Koinly behavior (2025-02-27):
  - Fees are deducted from proceeds (not added to cost basis)
  - This matches Koinly's treatment of trading fees

Kraken ledger structure:
  - Each trade has 2 legs grouped by refid: crypto leg + USD leg
  - amount: the raw amount added/removed (negative = outflow)
  - fee: trading fee charged in that asset (always positive, already deducted from balance)
  - net_amount property: amount - fee (what net hits your balance)
  - For USD legs: amount is the USD paid/received, fee is the USD trading fee

Treatment:
  - For acquisitions: lot amount = abs(amount), cost_basis does NOT include fees (Koinly mode)
  - For disposals: proceeds = USD value - fees, consumed amount = abs(amount)
  - Fee-only entries (amount==0, fee>0) are skipped (already embedded in the paired leg)
"""
from collections import defaultdict
from decimal import Decimal
from typing import List, Dict, Tuple
from .models import LedgerEntry, TaxableEvent, AssetLot, DUST_THRESHOLD, MISSING_BASIS_THRESHOLD


class FIFOEngine:
    def __init__(self, calc_method: str = "FIFO"):
        self.calc_method = calc_method
        self.inventory: Dict[Tuple[str, str], List[AssetLot]] = defaultdict(list)
        self.taxable_events: List[TaxableEvent] = []
        self.audit_log: List[str] = []
        self.ordinary_income_events: List[Tuple[object, Decimal]] = []  # List of (datetime, amount_usd)
        self.calc_method = calc_method

    @property
    def ordinary_income_usd(self) -> Decimal:
        """Sum of all ordinary income events."""
        return sum(amt for dt, amt in self.ordinary_income_events)

    def import_safe_harbor_inventory(self, safe_harbor_records: List[dict]):
        """
        Injects a synthetic starting inventory (pre-2025) to satisfy the Safe Harbor provision.
        Prevents "MISSING_BASIS" ($0 assigned) when carrying over balances from past years or exchanges.
        Format expected: [{"wallet_id": "kraken", "asset": "BTC", "amount": 0.5, "cost_basis_usd": 15000, "date_acquired": datetime.date.min}]
        """
        for record in safe_harbor_records:
            self.inventory[(record["wallet_id"], record["asset"])].append(AssetLot(
                asset=record["asset"],
                amount=Decimal(str(record["amount"])),
                cost_basis_usd=Decimal(str(record["cost_basis_usd"])),
                date_acquired=record["date_acquired"],
                wallet_id=record["wallet_id"],
            ))
            self.audit_log.append(f"SAFE HARBOR INJECTED: {record['amount']} {record['asset']} at ${record['cost_basis_usd']} cost basis into {record['wallet_id']}.")

    # ── USD value resolution ────────────────────────────────────────────────
    def _usd_value_of_event(self, entries: List[LedgerEntry]) -> Decimal:
        """
        Priority:
        1. USD leg amount (most accurate — direct cash amount)
        2. sum of |amountusd| from crypto disposal legs
        3. sum of |amountusd| from crypto acquisition legs
        """
        for e in entries:
            if e.asset == 'USD' and e.amount != Decimal('0'):
                return abs(e.amount)

        disposal_usd = sum(abs(e.amountusd) for e in entries if e.net_amount < 0 and e.asset != 'USD')
        if disposal_usd > Decimal('0'):
            return disposal_usd

        return sum(abs(e.amountusd) for e in entries if e.net_amount > 0 and e.asset != 'USD')

    def _usd_fees_of_event(self, entries: List[LedgerEntry]) -> Decimal:
        """Returns the total USD-denominated fee for the event (from USD leg fee field)."""
        for e in entries:
            if e.asset == 'USD':
                return abs(e.fee)
        return Decimal('0')

    def _crypto_fees_usd_value(self, entries: List[LedgerEntry]) -> Decimal:
        """Calculates the USD value of fees paid in crypto assets (non-USD)."""
        total = Decimal('0')
        for e in entries:
            if e.asset != 'USD' and e.fee > Decimal('0'):
                if abs(e.amount) > Decimal('0'):
                    price = abs(e.amountusd) / abs(e.amount)
                    total += e.fee * price
        return total

    # ── Main processing ─────────────────────────────────────────────────────
    def process_events(self, events: List[List[LedgerEntry]]):
        for entries in events:
            # Skip entirely empty or zero-amount events
            active = [e for e in entries if e.amount != Decimal('0') or e.fee != Decimal('0')]
            if not active:
                continue

            # Skip fee-only entries (amount=0, fee>0) — they are embedded in the paired leg
            non_fee_only = [e for e in active if e.amount != Decimal('0')]
            if not non_fee_only:
                continue

            # Separate USD legs from crypto legs
            usd_entries  = [e for e in non_fee_only if e.asset == 'USD']
            crypto_entries = [e for e in non_fee_only if e.asset != 'USD']

            if not crypto_entries:
                continue  # Pure USD event — not taxable

            # Detect internal transfers (same asset, two wallets, net zero)
            crypto_entries = self._process_internal_transfers(crypto_entries)
            if not crypto_entries:
                continue

            disposals    = [e for e in crypto_entries if e.amount < Decimal('0')]
            acquisitions = [e for e in crypto_entries if e.amount > Decimal('0')]

            usd_value = self._usd_value_of_event(non_fee_only)
            usd_fees  = self._usd_fees_of_event(non_fee_only)
            crypto_fees_val = self._crypto_fees_usd_value(non_fee_only)
            
            # Combine fees: direct USD fees + estimated USD value of crypto fees
            total_fees = usd_fees + crypto_fees_val

            event_type = self._classify_event(disposals, acquisitions, usd_entries)

            if event_type == 'staking_earn':
                self._handle_income(acquisitions, usd_value)

            elif event_type == 'buy_from_fiat':
                # Bought crypto with USD
                # Koinly method: fees ADDED to cost basis
                cost_with_fees = usd_value + total_fees
                self._handle_acquisition(acquisitions, cost_with_fees)

            elif event_type == 'deposit':
                # Pure crypto deposit — Basis is 0 unless amountusd exists
                total_usd = sum(abs(a.amountusd) for a in acquisitions)
                self._handle_acquisition(acquisitions, total_usd)

            elif event_type == 'sell_to_fiat':
                # Sold crypto for USD — Taxable Event!
                total_disp_amount_usd = sum(abs(d.amountusd) for d in disposals) or Decimal('1')
                for disp in disposals:
                    weight = abs(disp.amountusd) / total_disp_amount_usd \
                        if total_disp_amount_usd else Decimal('1') / Decimal(len(disposals))
                    # Deduct fees from proceeds (Koinly standard)
                    proceeds = (usd_value - total_fees) * weight
                    self._consume_inventory(
                        disp.wallet_id, disp.asset,
                        amount=abs(disp.net_amount),
                        proceeds_usd=proceeds,
                        disposal_time=disp.time,
                        description=str(disp.txid),
                        record_taxable_event=True,
                    )

            elif event_type == 'withdrawal_fee':
                # Pure withdrawal or fee deduction — non-taxable consumption
                for disp in disposals:
                    self._consume_inventory(
                        disp.wallet_id, disp.asset,
                        amount=abs(disp.net_amount),
                        proceeds_usd=Decimal('0'),
                        disposal_time=disp.time,
                        description=str(disp.txid),
                        record_taxable_event=False,
                    )

            elif event_type == 'trade':
                # Crypto-to-crypto exchange: disposals → proceeds, acquisitions → new lots
                total_disp_amount_usd = sum(abs(d.amountusd) for d in disposals) or Decimal('1')
                for disp in disposals:
                    weight = abs(disp.amountusd) / total_disp_amount_usd \
                        if total_disp_amount_usd else Decimal('1') / Decimal(len(disposals))
                    # Deduct fees from proceeds (Koinly standard)
                    proceeds = (usd_value - total_fees) * weight
                    self._consume_inventory(
                        disp.wallet_id, disp.asset,
                        amount=abs(disp.net_amount),
                        proceeds_usd=proceeds,
                        disposal_time=disp.time,
                        description=str(disp.txid),
                        record_taxable_event=True,
                    )

                total_acq_amount_usd = sum(abs(a.amountusd) for a in acquisitions) or Decimal('1')
                for acq in acquisitions:
                    weight = abs(acq.amountusd) / total_acq_amount_usd \
                        if total_acq_amount_usd else Decimal('1') / Decimal(len(acquisitions))
                    # Koinly method: fees ADDED to cost basis
                    cost = (usd_value + total_fees) * weight
                    self._add_lot(acq.wallet_id, acq.asset, abs(acq.net_amount), cost, acq.time)
    def _classify_event(self, disposals, acquisitions, usd_entries) -> str:
        """Classify what kind of event this is."""
        has_usd_inflow  = any(u.amount > 0 for u in usd_entries)
        has_usd_outflow = any(u.amount < 0 for u in usd_entries)

        if not disposals and acquisitions:
            for a in acquisitions:
                # Kraken uses 'earn', 'staking', or just 'reward' in some exports.
                # If it's an 'autoallocation' WITHOUT a matching disposal, it's organic income.
                # If it HAS a matching disposal, _process_internal_transfers would have cleared it.
                is_internal = 'autoallocation' in a.subtype.lower()
                if not is_internal and any(kw in a.type.lower() or kw in a.subtype.lower() for kw in ('earn', 'reward', 'staking')):
                    return 'staking_earn'
            if has_usd_outflow:
                return 'buy_from_fiat'
            return 'deposit'
            
        elif disposals and not acquisitions:
            if has_usd_inflow:
                return 'sell_to_fiat'
            return 'withdrawal_fee'
            
        elif disposals and acquisitions:
            return 'trade'
            
        return 'unknown'

    def _process_internal_transfers(self, crypto_entries: List[LedgerEntry]) -> List[LedgerEntry]:
        """
        Detect and handle internal wallet transfers (same asset, identical amounts).
        """
        remaining = list(crypto_entries)
        assets_in_event = set(e.asset for e in crypto_entries)

        for asset in assets_in_event:
            asset_entries = [e for e in remaining if e.asset == asset]
            outs = [e for e in asset_entries if e.amount < 0]
            ins  = [e for e in asset_entries if e.amount > 0]

            if len(outs) == 1 and len(ins) == 1:
                out_e, in_e = outs[0], ins[0]
                # Compare absolute nominal amounts to detect true transfers
                # (The withdrawal fee is handled separately below)
                if abs(abs(out_e.amount) - abs(in_e.amount)) < MISSING_BASIS_THRESHOLD:
                    # Allow internal moves even if wallet_id is the same (common for Kraken autoallocation)
                    self._move_lots(out_e.wallet_id, in_e.wallet_id, asset,
                                    abs(in_e.net_amount), in_e.time, str(in_e.txid))
                    # BUG-03 fix: consume the withdrawal fee from the source wallet as a
                    # non-taxable disposal so inventory stays balanced.
                    # Without this, out_e.fee BTC are silently "lost" — inventory inflates.
                    if out_e.fee > Decimal('0'):
                        self._consume_inventory(
                            out_e.wallet_id, out_e.asset,
                            amount=out_e.fee,
                            proceeds_usd=Decimal('0'),
                            disposal_time=out_e.time,
                            description=f"withdrawal_fee:{out_e.txid}",
                            record_taxable_event=False,
                        )
                    remaining = [e for e in remaining if e not in (out_e, in_e)]

        return remaining

    def _handle_income(self, acquisitions: List[LedgerEntry], total_usd: Decimal):
        for acq in acquisitions:
            weight = abs(acq.amountusd) / sum(abs(a.amountusd) for a in acquisitions) \
                if sum(abs(a.amountusd) for a in acquisitions) > 0 else Decimal('1')
            income_usd = total_usd * weight
            self.ordinary_income_events.append((acq.time, income_usd))
            # BUG-02 fix: use net_amount (after fees) so the lot reflects what actually arrives
            self._add_lot(acq.wallet_id, acq.asset, abs(acq.net_amount), income_usd, acq.time)

    def _handle_acquisition(self, acquisitions: List[LedgerEntry], total_cost_usd: Decimal):
        total_usd = sum(abs(a.amountusd) for a in acquisitions)
        for acq in acquisitions:
            weight = abs(acq.amountusd) / total_usd if total_usd > 0 else Decimal('1')
            self._add_lot(acq.wallet_id, acq.asset, abs(acq.amount), total_cost_usd * weight, acq.time)

    def _add_lot(self, wallet_id: str, asset: str, amount: Decimal,
                 cost_basis_usd: Decimal, date_acquired):
        self.inventory[(wallet_id, asset)].append(AssetLot(
            asset=asset,
            amount=amount,
            cost_basis_usd=cost_basis_usd,
            date_acquired=date_acquired,
            wallet_id=wallet_id,
        ))

    def _move_lots(self, from_wallet: str, to_wallet: str, asset: str,
                   amount: Decimal, time, txid: str):
        remaining = amount
        key = (from_wallet, asset)
        
        # Transfers usually rely on FIFO to preserve term status identically across wallets
        if key in self.inventory:
            self.inventory[key].sort(key=lambda x: x.date_acquired)

        while remaining > Decimal('0') and self.inventory.get(key):
            lot = self.inventory[key][0]
            move_qty = min(remaining, lot.amount)
            move_cost = lot.unit_cost * move_qty
            self._add_lot(to_wallet, asset, move_qty, move_cost, lot.date_acquired)
            lot.amount -= move_qty
            lot.cost_basis_usd -= move_cost
            if lot.amount <= DUST_THRESHOLD:
                self.inventory[key].pop(0)
            remaining -= move_qty

        if remaining > MISSING_BASIS_THRESHOLD:
            self._add_lot(to_wallet, asset, remaining, Decimal('0'), time)
            self.audit_log.append(
                f"MISSING_BASIS: {remaining} {asset} moved from {from_wallet} to {to_wallet} "
                f"on {time.strftime('%Y-%m-%d')} — no acquisition record found. Basis set to $0."
            )

    def _consume_inventory(self, wallet_id: str, asset: str, amount: Decimal,
                      proceeds_usd: Decimal, disposal_time, description: str,
                      record_taxable_event: bool = True):
        remaining = amount
        proceeds_per_unit = proceeds_usd / amount if amount > Decimal('0') else Decimal('0')
        key = (wallet_id, asset)
        used_lots = []
        
        if key in self.inventory:
            if self.calc_method == "LIFO":
                self.inventory[key].sort(key=lambda x: x.date_acquired, reverse=True)
            elif self.calc_method == "HIFO":
                self.inventory[key].sort(key=lambda x: x.unit_cost, reverse=True)
            else: # Default FIFO
                self.inventory[key].sort(key=lambda x: x.date_acquired)

        while remaining > Decimal('0') and self.inventory.get(key):
            lot = self.inventory[key][0]
            consume_qty = min(remaining, lot.amount)
            lot_cost   = lot.unit_cost * consume_qty
            lot_proc   = proceeds_per_unit * consume_qty

            if record_taxable_event:
                days_held = (disposal_time - lot.date_acquired).days
                # BUG-01 fix: IRS treats exactly 365 days as Long-Term (>= 365, not > 365)
                term = 'Long-Term' if days_held >= 365 else 'Short-Term'
                self.taxable_events.append(TaxableEvent(
                    description=f"{consume_qty.normalize():f} {asset}",
                    date_acquired=lot.date_acquired.strftime("%m/%d/%Y"),
                    date_sold=disposal_time.strftime("%m/%d/%Y"),
                    proceeds=lot_proc.quantize(Decimal('0.01')),
                    cost_basis=lot_cost.quantize(Decimal('0.01')),
                    term=term,
                    wallet_id=wallet_id,
                ))
                used_lots.append(
                    f"{consume_qty.normalize():f} {asset} acquired {lot.date_acquired.strftime('%Y-%m-%d')}"
                )

            lot.amount -= consume_qty
            lot.cost_basis_usd -= lot_cost
            if lot.amount <= DUST_THRESHOLD:
                self.inventory[key].pop(0)
            remaining -= consume_qty

        # Missing basis (sold more than acquired — e.g. pre-2025 holdings)
        if remaining > MISSING_BASIS_THRESHOLD:
            lot_proc = proceeds_per_unit * remaining
            if record_taxable_event:
                # RIESGO-02 fix: use 'Unknown' instead of defaulting to Short-Term.
                # The user will be prompted in the anomaly reviewer to assign the correct term.
                # tax_reporter.py maps 'Unknown' → 'Short-Term' as a conservative fallback.
                self.taxable_events.append(TaxableEvent(
                    description=f"{remaining.normalize():f} {asset} (Missing Basis)",
                    date_acquired="VARIOUS",
                    date_sold=disposal_time.strftime("%m/%d/%Y"),
                    proceeds=lot_proc.quantize(Decimal('0.01')),
                    cost_basis=Decimal('0.00'),
                    term='Unknown',
                    wallet_id=wallet_id,
                ))
                used_lots.append(f"{remaining.normalize():f} {asset} — MISSING_BASIS ($0)")
                self.audit_log.append(
                    f"MISSING_BASIS: {remaining} {asset} sold on "
                    f"{disposal_time.strftime('%Y-%m-%d')} in {wallet_id}. No acquisition record."
                )

        if record_taxable_event and used_lots:
            self.audit_log.append(
                f"SOLD {amount.normalize():f} {asset} in {wallet_id} "
                f"on {disposal_time.strftime('%Y-%m-%d')} ({description}): "
                + ", ".join(used_lots) + "."
            )
