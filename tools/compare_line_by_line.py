"""
Comparación línea por línea: Koinly vs Crypto Tax Pro
"""
import csv
from decimal import Decimal
from collections import defaultdict

KOINLY_FILE = "data/koinly-2024/koinly_2024_capital_gains_report.csv"
APP_FORM_FILE = "reports/form_8949_2024.csv"

def safe_decimal(value):
    try:
        if value is None or value == '':
            return Decimal('0')
        return Decimal(str(value).replace(',', ''))
    except:
        return Decimal('0')

def load_koinly():
    data = []
    with open(KOINLY_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = None
        for i, row in enumerate(reader):
            if i == 0:
                continue  # Title
            if i == 1:
                continue  # Empty line
            if i == 2:
                header = row  # Header
                continue
            
            if not row or len(row) < 8:
                continue
            
            # Create dict from row
            d = dict(zip(header, row))
            
            asset = d.get('Asset', '')
            if not asset:
                continue
            
            data.append({
                'asset': asset.upper(),
                'date_sold': d.get('Date Sold', '').split()[0],
                'date_acquired': d.get('Date Acquired', '').split()[0],
                'amount': safe_decimal(d.get('Amount', '0')),
                'cost': safe_decimal(d.get('Cost (USD)', '0')),
                'proceeds': safe_decimal(d.get('Proceeds (USD)', '0')),
                'gain_loss': safe_decimal(d.get('Gain / loss', '0')),
            })
    return data

def load_app():
    data = []
    with open(APP_FORM_FILE, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = None
        for i, row in enumerate(reader):
            if i == 0:
                header = row
                continue
            if not row:
                continue
            
            d = dict(zip(header, row))
            
            desc = d.get('Description of property (a)', '')
            parts = desc.split()
            if len(parts) < 2:
                continue
            
            data.append({
                'asset': parts[1].upper(),
                'date_sold': d.get('Date sold or disposed of (c)', ''),
                'date_acquired': d.get('Date acquired (b)', ''),
                'amount': safe_decimal(parts[0]),
                'cost': safe_decimal(d.get('Cost or other basis (e)', '0')),
                'proceeds': safe_decimal(d.get('Proceeds (d)', '0')),
                'gain_loss': safe_decimal(d.get('Gain or (loss) (h)', '0')),
            })
    return data

# Load data
print("=" * 70)
print("COMPARACION KOINLY vs CRYPTO TAX PRO")
print("=" * 70)

koinly = load_koinly()
app = load_app()

print(f"\nKoinly: {len(koinly)} events")
print(f"App:    {len(app)} events")

# Compare by asset
print("\n" + "-" * 70)
print("COMPARACION POR ASSET")
print("-" * 70)

koinly_by_asset = defaultdict(lambda: {'count': 0, 'proceeds': Decimal(0), 'cost': Decimal(0), 'gain': Decimal(0)})
for k in koinly:
    a = k['asset']
    koinly_by_asset[a]['count'] += 1
    koinly_by_asset[a]['proceeds'] += k['proceeds']
    koinly_by_asset[a]['cost'] += k['cost']
    koinly_by_asset[a]['gain'] += k['gain_loss']

app_by_asset = defaultdict(lambda: {'count': 0, 'proceeds': Decimal(0), 'cost': Decimal(0), 'gain': Decimal(0)})
for a in app:
    asset = a['asset']
    app_by_asset[asset]['count'] += 1
    app_by_asset[asset]['proceeds'] += a['proceeds']
    app_by_asset[asset]['cost'] += a['cost']
    app_by_asset[asset]['gain'] += a['gain_loss']

all_assets = set(koinly_by_asset.keys()) | set(app_by_asset.keys())

print(f"\n{'Asset':<10} {'K-Cnt':>6} {'A-Cnt':>6} {'K-Proceeds':>12} {'A-Proceeds':>12} {'K-Cost':>12} {'A-Cost':>12}")
print("-" * 70)

for asset in sorted(all_assets):
    k = koinly_by_asset[asset]
    a = app_by_asset[asset]
    print(f"{asset:<10} {k['count']:>6} {a['count']:>6} ${k['proceeds']:>10,.2f} ${a['proceeds']:>10,.2f} ${k['cost']:>10,.2f} ${a['cost']:>10,.2f}")

# Overall totals
print("\n" + "=" * 70)
print("TOTALS")
print("=" * 70)

k_proceeds = sum(k['proceeds'] for k in koinly_by_asset.values())
k_cost = sum(k['cost'] for k in koinly_by_asset.values())
k_gain = sum(k['gain'] for k in koinly_by_asset.values())

a_proceeds = sum(a['proceeds'] for a in app_by_asset.values())
a_cost = sum(a['cost'] for a in app_by_asset.values())
a_gain = sum(a['gain'] for a in app_by_asset.values())

print(f"\n{'Metric':<20} {'Koinly':>15} {'App':>15} {'Diff':>15}")
print("-" * 70)
print(f"{'Proceeds':<20} ${k_proceeds:>13,.2f} ${a_proceeds:>13,.2f} ${a_proceeds - k_proceeds:>13,.2f}")
print(f"{'Cost Basis':<20} ${k_cost:>13,.2f} ${a_cost:>13,.2f} ${a_cost - k_cost:>13,.2f}")
print(f"{'Gain/Loss':<20} ${k_gain:>13,.2f} ${a_gain:>13,.2f} ${a_gain - k_gain:>13,.2f}")

diff = a_gain - k_gain
print(f"\n{'='*70}")
print(f"DIFERENCIA: ${diff:,.2f}")
print(f"{'='*70}")
