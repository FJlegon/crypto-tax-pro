import os
import sys

# Ensure the root of the project is in the path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from src.data_loader import load_ledgers, group_entries_by_event
from src.fifo_engine import FIFOEngine
from src.tax_reporter import print_tax_summary

def test_wallet_refactor():
    print("Testing Wallet-by-Wallet Refactor...")
    ledger_file = 'data/kraken/kraken_stocks_etfs_ledgers_2025-01-01-2026-01-01.csv'
    
    if not os.path.exists(ledger_file):
        print(f"Error: {ledger_file} not found.")
        return

    # Load as 'Kraken' wallet
    entries = load_ledgers(ledger_file, wallet_id="Kraken")
    print(f"Loaded {len(entries)} entries for 'Kraken'.")
    
    events = group_entries_by_event(entries)
    print(f"Grouped into {len(events)} events.")
    
    engine = FIFOEngine()
    engine.process_events(events)
    
    print(f"Processed {len(engine.taxable_events)} taxable events.")
    ordinary_income = sum(amt for dt, amt in engine.ordinary_income_events)
    print_tax_summary(engine.taxable_events, ordinary_income)
    
    # Check inventory structure
    first_key = list(engine.inventory.keys())[0] if engine.inventory else None
    print(f"Sample Inventory Key: {first_key} (Should be a tuple)")
    
    if isinstance(first_key, tuple):
        print("Success: Inventory is correctly keyed by (wallet_id, asset).")
    else:
        print("Failure: Inventory is not keyed correctly.")

if __name__ == "__main__":
    test_wallet_refactor()
