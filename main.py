import os
from src.data_loader import load_ledgers
from src.fifo_engine import FIFOEngine
from src.tax_reporter import export_form_8949, export_turbotax_csv, export_audit_log, print_tax_summary

def main():
    kraken_dir = 'data/kraken'
    
    if not os.path.exists(kraken_dir):
        print(f"Directory {kraken_dir} not found.")
        return
        
    # We look for the ledgers file
    ledger_files = [f for f in os.listdir(kraken_dir) if 'ledgers' in f.lower() and f.endswith('.csv')]
    if not ledger_files:
        print(f"No ledgers CSV found in {kraken_dir}.")
        return
        
    filepath = os.path.join(kraken_dir, ledger_files[0])
    print(f"Loading data from {filepath}...")
    
    events = load_ledgers(filepath)
    
    print(f"Loaded {len(events)} transaction events.")
    
    engine = FIFOEngine()
    engine.process_events(events)
    
    print(f"Processed into {len(engine.taxable_events)} taxable events.")
    
    output_csv = 'form_8949_report.csv'
    export_form_8949(engine.taxable_events, output_csv)
    print(f"Exported Form 8949 details to {output_csv}")
    
    turbotax_csv = 'turbotax_gain_loss.csv'
    export_turbotax_csv(engine.taxable_events, turbotax_csv)
    print(f"Exported TurboTax Gain/Loss format to {turbotax_csv}")
    
    audit_txt = 'audit_trail_log.txt'
    export_audit_log(engine.audit_log, audit_txt)
    print(f"Exported Audit Trail Log to {audit_txt}")
    
    print_tax_summary(engine.taxable_events, engine.ordinary_income_usd)

if __name__ == '__main__':
    main()
