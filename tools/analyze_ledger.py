"""
Análisis detallado: Ledger Kraken vs Form 8949 generado
"""
import csv
from decimal import Decimal

KRAKEN_FILE = "data/kraken/kraken_stocks_etfs_ledgers_2024-07-12-2024-12-31.csv"
APP_FORM_FILE = "reports/form_8949_2024.csv"

def safe_decimal(value):
    try:
        if value is None or value == '':
            return Decimal('0')
        return Decimal(str(value).replace(',', ''))
    except:
        return Decimal('0')

def load_ledger(filepath):
    """Carga el ledger de Kraken"""
    trades = []
    deposits = []
    withdrawals = []
    
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            tx_type = row['type']
            asset = row['asset']
            amount = safe_decimal(row['amount'])
            amount_usd = safe_decimal(row['amountusd'])
            
            if tx_type == 'trade':
                # Trade tiene amount negativo (venta) o positivo (compra)
                trades.append({
                    'type': 'buy' if amount > 0 else 'sell',
                    'asset': asset,
                    'amount': abs(amount),
                    'amount_usd': abs(amount_usd),
                    'time': row['time'],
                })
            elif tx_type == 'deposit':
                deposits.append({'asset': asset, 'amount': amount})
            elif tx_type == 'withdrawal':
                withdrawals.append({'asset': asset, 'amount': amount})
    
    return {'trades': trades, 'deposits': deposits, 'withdrawals': withdrawals}

def load_app_form8949(filepath):
    """Carga el Form 8949"""
    app_events = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = None
        for i, row in enumerate(reader):
            if i == 0:
                header = row
                continue
            if not row or not header:
                continue
            data = dict(zip(header, row))
            
            # Solo ventas (tienen proceeds > 0)
            proceeds = safe_decimal(data.get('Proceeds (d)', '0'))
            if proceeds > 0:
                desc = data.get('Description of property (a)', '')
                parts = desc.split()
                asset = parts[1].upper() if len(parts) > 1 else 'UNKNOWN'
                
                app_events.append({
                    'asset': asset,
                    'proceeds': proceeds,
                    'cost': safe_decimal(data.get('Cost or other basis (e)', '0')),
                    'gain_loss': safe_decimal(data.get('Gain or (loss) (h)', '0')),
                })
    return app_events

# Cargar datos
print("=" * 70)
print("ANÁLISIS: Ledger Kraken vs Form 8949")
print("=" * 70)

ledger = load_ledger(KRAKEN_FILE)
app_events = load_app_form8949(APP_FORM_FILE)

print(f"\n[1] LEDGER KRAKEN:")
print(f"    Deposits:     {len(ledger['deposits'])}")
print(f"    Withdrawals: {len(ledger['withdrawals'])}")
print(f"    Trades:      {len(ledger['trades'])}")
buys = [t for t in ledger['trades'] if t['type'] == 'buy']
sells = [t for t in ledger['trades'] if t['type'] == 'sell']
print(f"      - Buys:   {len(buys)}")
print(f"      - Sells:  {len(sells)}")
print(f"    TOTAL:       {len(ledger['deposits']) + len(ledger['withdrawals']) + len(ledger['trades'])}")

print(f"\n[2] FORM 8949 (App):")
print(f"    Taxable Events: {len(app_events)}")

# Contar trades por asset
print(f"\n[3] TRADES EN LEDGER (sells):")
sells_by_asset = {}
for t in sells:
    asset = t['asset']
    if asset not in sells_by_asset:
        sells_by_asset[asset] = {'count': 0, 'amount': Decimal('0')}
    sells_by_asset[asset]['count'] += 1
    sells_by_asset[asset]['amount'] += t['amount']

for asset, data in sorted(sells_by_asset.items(), key=lambda x: x[1]['count'], reverse=True)[:15]:
    print(f"    {asset:8}: {data['count']:3} sells, {data['amount']:>15.4f}")

print(f"\n[4] TAXABLE EVENTS EN APP:")
events_by_asset = {}
for e in app_events:
    asset = e['asset']
    if asset not in events_by_asset:
        events_by_asset[asset] = {'count': 0}
    events_by_asset[asset]['count'] += 1

for asset, data in sorted(events_by_asset.items(), key=lambda x: x[1]['count'], reverse=True)[:15]:
    print(f"    {asset:8}: {data['count']:3} events")

# Comparar counts
print(f"\n[5] COMPARACIÓN:")
all_assets = set(sells_by_asset.keys()) | set(events_by_asset.keys())
diff_assets = []
for asset in all_assets:
    ledger_count = sells_by_asset.get(asset, {'count': 0})['count']
    app_count = events_by_asset.get(asset, {'count': 0})['count']
    if ledger_count != app_count:
        diff_assets.append((asset, ledger_count, app_count, ledger_count - app_count))

if diff_assets:
    print("    Assets con diferencia:")
    for asset, lc, ac, diff in sorted(diff_assets, key=lambda x: abs(x[3]), reverse=True):
        print(f"      {asset:8}: Ledger={lc}, App={ac}, Diff={diff}")

# Comparar totals
ledger_sell_total = sum(t['amount_usd'] for t in sells)
app_proceeds_total = sum(e['proceeds'] for e in app_events)
app_cost_total = sum(e['cost'] for e in app_events)

print(f"\n[6] TOTALS:")
print(f"    Ledger sells (USD):  ${ledger_sell_total:,.2f}")
print(f"    App proceeds:        ${app_proceeds_total:,.2f}")
print(f"    App cost basis:     ${app_cost_total:,.2f}")
print(f"    App gain/loss:      ${app_proceeds_total - app_cost_total:,.2f}")
