import csv
import io
from decimal import Decimal
from typing import List
from .models import TaxableEvent


# ── In-memory generators (return string content) ─────────────────────────────

def determine_box(term: str, proceeds: Decimal, cost_basis: Decimal) -> str:
    """
    Determine the correct Form 8949 box based on holding period and gain/loss type.
    If term is 'Unknown' (Missing Basis, holding period unverifiable), we default to
    the most conservative short-term loss box ('I') to avoid underreporting.
    """
    has_gain = proceeds > cost_basis

    if term == 'Short-Term':
        return 'G' if has_gain else 'I'
    elif term == 'Long-Term':
        return 'J' if has_gain else 'L'
    else:  # 'Unknown' — conservative fallback: treat as short-term loss (code I)
        return 'G' if has_gain else 'I'

def build_form_8949_csv(events: List[TaxableEvent], apply_boxes: bool = True) -> str:
    """Returns the IRS Form 8949 data as a CSV string (in memory)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Description of property (a)",
        "Date acquired (b)",
        "Date sold or disposed of (c)",
        "Proceeds (d)",
        "Cost or other basis (e)",
        "Code(s) (f)",
        "Amount of adjustment (g)",
        "Gain or (loss) (h)",
        "Term",
        "Wallet/Account",
    ])
    for e in events:
        box = determine_box(e.term, e.proceeds, e.cost_basis) if apply_boxes else ""
        # Map 'Unknown' term to 'Short-Term' label in the CSV (conservative IRS fallback)
        term_label = e.term if e.term != 'Unknown' else 'Short-Term (Unverified)'
        writer.writerow([
            e.description,
            e.date_acquired,
            e.date_sold,
            f"{e.proceeds:.2f}",
            f"{e.cost_basis:.2f}",
            e.adjustment_code if e.adjustment_code else box,
            f"{e.adjustment_amount:.2f}" if e.adjustment_amount != Decimal('0') else "0.00",
            f"{e.gain_loss:.2f}",
            term_label,
            e.wallet_id,
        ])
    return output.getvalue()


def build_turbotax_csv(events: List[TaxableEvent]) -> str:
    """Returns the TurboTax Gain/Loss CSV as a string (in memory)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Currency Name", "Purchase Date", "Cost Basis", "Date Sold", "Proceeds"])
    for e in events:
        writer.writerow([
            e.description,
            e.date_acquired if e.date_acquired != "VARIOUS" else "",
            f"{e.cost_basis:.2f}",
            e.date_sold,
            f"{e.proceeds:.2f}",
        ])
    return output.getvalue()


def build_audit_log(audit_log: List[str], calc_method: str = "FIFO", form_8949_csv: str = "", turbotax_csv: str = "") -> str:
    """Returns the audit trail as a plain text string with cryptographic hashes (in memory)."""
    import hashlib
    import platform
    import uuid
    from datetime import datetime
    
    lines = [
        "=== CRYPTO FIFO AUDIT TRAIL LOG (WALLET-BY-WALLET) ===\n",
        "This document records the exact acquisition lots consumed for each taxable disposal.\n",
        "Keep this file alongside your Form 8949 as an algorithmic backup for IRS audits.\n",
        "\n",
    ]
    for log in audit_log:
        lines.append(log + "\n")
        
    content = "".join(lines)
    signature = hashlib.sha256(content.encode('utf-8')).hexdigest()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
    
    footer = [
        "\n",
        "-" * 60 + "\n",
        "--- END OF AUDIT TRAIL ---\n",
        f"Execution Timestamp : {timestamp}\n",
        f"Calculated Engine   : Crypto Tax Pro 2026 Engine\n",
        f"Accounting Method   : {calc_method}\n",
        f"Host Machine ID     : {uuid.getnode()}\n",
        f"OS Architecture     : {platform.platform()}\n",
        f"Audit Text SHA-256  : {signature}\n"
    ]
    
    if form_8949_csv:
        f8949_hash = hashlib.sha256(form_8949_csv.encode('utf-8')).hexdigest()
        footer.append(f"Form 8949 SHA-256   : {f8949_hash}\n")
    if turbotax_csv:
        tt_hash = hashlib.sha256(turbotax_csv.encode('utf-8')).hexdigest()
        footer.append(f"TurboTax SHA-256    : {tt_hash}\n")
        
    footer.append("-" * 60 + "\n")
    
    return content + "".join(footer)


# ── File writers (save to disk) ───────────────────────────────────────────────

def export_form_8949(events: List[TaxableEvent], filepath: str):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(build_form_8949_csv(events))


def export_turbotax_csv(events: List[TaxableEvent], filepath: str):
    with open(filepath, "w", newline="", encoding="utf-8") as f:
        f.write(build_turbotax_csv(events))


def export_audit_log(audit_log: List[str], filepath: str):
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(build_audit_log(audit_log))


def print_tax_summary(events: List[TaxableEvent], ordinary_income_usd: Decimal):
    short_term = sum((e.gain_loss for e in events if e.term == "Short-Term"), Decimal("0"))
    long_term  = sum((e.gain_loss for e in events if e.term == "Long-Term"),  Decimal("0"))
    unknown    = sum((e.gain_loss for e in events if e.term == "Unknown"),     Decimal("0"))
    total_proceeds = sum((e.proceeds    for e in events), Decimal("0"))
    total_cost     = sum((e.cost_basis  for e in events), Decimal("0"))

    print("=" * 50)
    print("        CRYPTO TAX SUMMARY (FIFO)         ")
    print("=" * 50)
    print(f"Total Transactions:   {len(events)}")
    print(f"Total Proceeds:       ${total_proceeds:,.2f}")
    print(f"Total Cost Basis:     ${total_cost:,.2f}")
    print("-" * 50)
    print(f"Short-Term Cap Gain:  ${short_term:,.2f}")
    print(f"Long-Term Cap Gain:   ${long_term:,.2f}")
    if unknown != Decimal("0"):
        print(f"Unknown Term Gain:    ${unknown:,.2f}  ⚠ Review Missing Basis events")
    print(f"Total Capital Gain:   ${(short_term + long_term + unknown):,.2f}")
    print("-" * 50)
    print(f"Ordinary Income:      ${ordinary_income_usd:,.2f}  (Staking/Earn/Rewards)")
    print("=" * 50)

def reconcile_and_export(
    events: List[TaxableEvent],
    da_records: List,
    output_path: str
) -> List[dict]:
    """
    Reconcile calculated events with 1099-DA records and export Form 8949 with adjustments.
    Returns list of discrepancies found.
    """
    from .form_1099_da_importer import reconcile_1099_da
    
    matched_events, discrepancies = reconcile_1099_da(events, da_records)
    export_form_8949(matched_events, output_path)
    return discrepancies
