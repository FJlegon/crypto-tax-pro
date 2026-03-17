import csv
from decimal import Decimal, InvalidOperation
from typing import List, Dict, Tuple
from .models import Form1099DARecord, TaxableEvent
from .tax_reporter import determine_box  # P2-C: single canonical implementation

def parse_1099_da_csv(filepath: str) -> List[Form1099DARecord]:
    records = []
    
    with open(filepath, 'r', newline='', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        
        for row in reader:
            try:
                asset = row.get('Asset', row.get('Currency', row.get('Symbol', ''))).strip()
                if not asset:
                    continue
                
                proceeds_str = row.get('Proceeds', row.get('Gross Proceeds', row.get('Amount Received', '0'))).replace('$', '').replace(',', '').strip()
                cost_basis_str = row.get('Cost Basis', row.get('Basis', '0')).replace('$', '').replace(',', '').strip()
                
                proceeds = Decimal(proceeds_str) if proceeds_str else Decimal('0')
                cost_basis = Decimal(cost_basis_str) if cost_basis_str else Decimal('0')
                
                date_disposed = row.get('Date of Disposition', row.get('Date Sold', row.get('Date', ''))).strip()
                cost_basis_method = row.get('Cost Basis Method', row.get('Method', 'FIFO')).strip()
                is_covered = row.get('Covered', row.get('Is Covered', 'Yes')).strip().lower() != 'no'
                transaction_type = row.get('Transaction Type', row.get('Type', 'Sale')).strip()
                
                record = Form1099DARecord(
                    asset=asset,
                    date_disposed=date_disposed,
                    proceeds=proceeds,
                    cost_basis=cost_basis,
                    cost_basis_method=cost_basis_method,
                    is_covered=is_covered,
                    transaction_type=transaction_type
                )
                records.append(record)
                
            except (InvalidOperation, ValueError, KeyError) as e:
                continue
    
    return records

def reconcile_1099_da(
    calculated_events: List[TaxableEvent],
    da_records: List[Form1099DARecord]
) -> Tuple[List[TaxableEvent], List[Dict]]:
    """
    Reconcile calculated events with 1099-DA records.
    Returns tuple of (matched_events, discrepancies)
    """
    discrepancies = []
    matched = []
    
    da_by_key = {}
    for rec in da_records:
        key = (rec.asset, rec.date_disposed)
        if key not in da_by_key:
            da_by_key[key] = []
        da_by_key[key].append(rec)
    
    for event in calculated_events:
        key = (event.description.split()[1] if len(event.description.split()) > 1 else event.description, 
               event.date_sold)
        
        if key in da_by_key:
            da_rec = da_by_key[key][0]
            basis_diff = event.cost_basis - da_rec.cost_basis
            
            if abs(basis_diff) > Decimal('0.01'):
                event.adjustment_code = "T"
                event.adjustment_amount = basis_diff
                discrepancies.append({
                    'event': event,
                    '1099da_basis': da_rec.cost_basis,
                    'calculated_basis': event.cost_basis,
                    'difference': basis_diff
                })
            
            matched.append(event)
        else:
            matched.append(event)
    
    return matched, discrepancies

