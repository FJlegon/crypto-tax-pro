from decimal import Decimal
from datetime import datetime
from dataclasses import dataclass, field
from typing import List, Optional

@dataclass
class LedgerEntry:
    txid: str
    refid: str
    time: datetime
    type: str # 'trade', 'deposit', 'withdrawal', 'earn', 'reward'
    subtype: str
    asset: str
    amount: Decimal
    fee: Decimal
    balance: Decimal
    amountusd: Decimal
    wallet_id: str = "Unknown" # Added for Wallet-by-Wallet tracking

    @property
    def net_amount(self) -> Decimal:
        """The actual amount added or removed from the balance."""
        return self.amount - self.fee

@dataclass
class TaxableEvent:
    description: str
    date_acquired: str
    date_sold: str
    proceeds: Decimal
    cost_basis: Decimal
    term: str # 'Short-Term' or 'Long-Term'
    wallet_id: str = "Unknown" # To track where the sale happened
    adjustment_code: str = ""  # Form 8949 Column f: T, W, L, etc.
    adjustment_amount: Decimal = Decimal('0')  # Form 8949 Column g
    box: str = ""  # Box selection: G/H/I (short-term), J/K/L (long-term)
    
    @property
    def gain_loss(self) -> Decimal:
        return self.proceeds - self.cost_basis

@dataclass
class AssetLot:
    asset: str
    amount: Decimal
    cost_basis_usd: Decimal
    date_acquired: datetime
    wallet_id: str = "Unknown" # Keeps track of where this specific lot is located
    
    @property
    def unit_cost(self) -> Decimal:
        if self.amount == Decimal('0'):
            return Decimal('0')
        return self.cost_basis_usd / self.amount

@dataclass
class Form1099DARecord:
    """Represents a single transaction from Form 1099-DA"""
    asset: str
    date_disposed: str
    proceeds: Decimal
    cost_basis: Decimal
    cost_basis_method: str  # e.g., "FIFO", "LIFO", "SPECID"
    is_covered: bool = True  # Whether this is a covered security
    transaction_type: str = "Sale"  # Sale, Exchange, etc.

DUST_THRESHOLD = Decimal('1e-8')
MISSING_BASIS_THRESHOLD = Decimal('1e-5')
