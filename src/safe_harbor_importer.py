import csv
from decimal import Decimal
from datetime import datetime
from typing import List, Dict

def parse_safe_harbor_csv(file_path: str) -> List[dict]:
    """
    Parses a CSV file containing pre-2025 starting balances for the Safe Harbor provision.
    Expected CSV columns (must include):
    - wallet_id (e.g., 'kraken', 'coinbase')
    - asset (e.g., 'BTC', 'ETH')
    - amount (e.g., '0.5')
    - cost_basis_usd (e.g., '14000.50')
    - date_acquired (e.g., '12/31/2024' or '2024-12-31')
    """
    records = []
    
    with open(file_path, mode='r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        # Lowercase and strip column names for robust matching
        header_map = {field.strip().lower(): field for field in reader.fieldnames}
        
        # Ensure required columns exist
        required_cols = {"wallet_id", "asset", "amount", "cost_basis_usd", "date_acquired"}
        if not required_cols.issubset(set(header_map.keys())):
            missing = required_cols - set(header_map.keys())
            raise ValueError(f"Safe Harbor CSV missing required columns: {missing}")

        for row in reader:
            try:
                # Extract and clean row data
                wallet_id = row[header_map["wallet_id"]].strip()
                asset = row[header_map["asset"]].strip()
                
                amount_str = row[header_map["amount"]].replace(',', '').strip()
                amount = Decimal(amount_str)
                
                cost_str = row[header_map["cost_basis_usd"]].replace('$', '').replace(',', '').strip()
                cost_basis_usd = Decimal(cost_str)
                
                date_str = row[header_map["date_acquired"]].strip()
                # Try standard parsing formats
                try:
                    # e.g., '12/31/2024'
                    date_acquired = datetime.strptime(date_str, "%m/%d/%Y").date()
                except ValueError:
                    # e.g., '2024-12-31'
                    date_acquired = datetime.strptime(date_str, "%Y-%m-%d").date()

                if amount <= 0:
                    continue  # Safely ignore zero amounts

                records.append({
                    "wallet_id": wallet_id,
                    "asset": asset,
                    "amount": amount,
                    "cost_basis_usd": cost_basis_usd,
                    "date_acquired": date_acquired
                })
            except Exception as e:
                # Log or ignore corrupted rows based on business logic
                continue

    return records
