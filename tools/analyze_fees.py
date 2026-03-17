"""
Análisis detallado: cómo Kraken/Koinly aplican fees
Muestra el costo real vs lo que reporta Koinly
"""
import csv
from decimal import Decimal

KRAKEN_FILE = "data/kraken/kraken_stocks_etfs_ledgers_2024-07-12-2024-12-31.csv"
KOINLY_FILE = "data/koinly-2024/koinly_2024_capital_gains_report.csv"

def safe_decimal(value):
    try:
        if value is None or value == '':
            return Decimal('0')
        return Decimal(str(value).replace(',', ''))
    except:
        return Decimal('0')

# Cargar trades del ledger agrupados por refid
trades_by_refid = {}
with open(KRAKEN_FILE, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    for row in reader:
        refid = row['refid']
        if refid not in trades_by_refid:
            trades_by_refid[refid] = []
        trades_by_refid[refid].append({
            'txid': row['txid'],
            'time': row['time'],
            'asset': row['asset'],
            'amount': safe_decimal(row['amount']),
            'fee': safe_decimal(row['fee']),
            'amountusd': safe_decimal(row['amountusd']),
        })

# Cargar Koinly
koinly = []
with open(KOINLY_FILE, 'r', encoding='utf-8') as f:
    reader = csv.reader(f)
    header = None
    for i, row in enumerate(reader):
        if i < 3:
            continue
        if i == 3:
            header = row
            continue
        if not row or not header:
            continue
        d = dict(zip(header, row))
        if d.get('Asset'):
            koinly.append({
                'asset': d['Asset'],
                'date_sold': d['Date Sold'],
                'date_acquired': d['Date Acquired'],
                'amount': safe_decimal(d['Amount']),
                'cost': safe_decimal(d['Cost (USD)']),
                'proceeds': safe_decimal(d['Proceeds (USD)']),
                'gain': safe_decimal(d['Gain / loss']),
            })

# Buscar el trade de BTC específico (0.00140948 BTC)
target_amount = Decimal('0.00140948')
for k in koinly:
    if k['asset'] == 'BTC' and abs(k['amount'] - target_amount) < Decimal('0.00000001'):
        print("=" * 70)
        print("TRANSACCIÓN BTC ENCONTRADA:")
        print("=" * 70)
        print(f"Fecha Venta: {k['date_sold']}")
        print(f"Fecha Compra: {k['date_acquired']}")
        print(f"Cantidad: {k['amount']}")
        print(f"Cost Basis (Koinly): ${k['cost']:,.2f}")
        print(f"Proceeds (Koinly): ${k['proceeds']:,.2f}")
        print(f"Gain (Koinly): ${k['gain']:,.2f}")
        
        # Buscar en el ledger por timestamp cercano
        date_sold = k['date_sold'].split()[0]
        print(f"\nBuscando en ledger alrededor de {date_sold}...")
        
        # Buscar trades de BTC alrededor de esa fecha
        for refid, legs in list(trades_by_refid.items())[:20]:
            btc_legs = [l for l in legs if l['asset'] == 'BTC']
            if btc_legs:
                btc = btc_legs[0]
                if '2024-07-15' in btc['time']:
                    print(f"\nRefID: {refid}")
                    for leg in legs:
                        print(f"  {leg['asset']:6} | Amount: {leg['amount']:>14.8f} | Fee: {leg['fee']:>8.4f} | USD: {leg['amountusd']:>10.2f}")
                    
                    # Calcular como Koinly
                    usd_legs = [l for l in legs if l['asset'] == 'USD']
                    if usd_legs:
                        usd = usd_legs[0]
                        # Método Koinly parece ser:
                        # proceeds = abs(crypto_amountusd) - fee? 
                        # cost = abs(usd_amount) + fee?
                        
                        cost_calc = abs(usd['amount']) + usd['fee']
                        proceeds_calc = abs(btc['amountusd'])
                        
                        print(f"\nCÁLCULO:")
                        print(f"  USD amount (sin fee): ${abs(usd['amount']):.4f}")
                        print(f"  USD fee: ${usd['fee']:.4f}")
                        print(f"  Cost Basis (USD + fee): ${cost_calc:.4f}")
                        print(f"  crypto USD value: ${proceeds_calc:.4f}")
                        print(f"  Gain calc: ${proceeds_calc - cost_calc:.4f}")
        
        break

# Ahora analizar el patrón general
print("\n" + "=" * 70)
print("ANÁLISIS DEL PATRÓN DE FEES")
print("=" * 70)

# Para cada trade de crypto -> USD (venta)
fee_diffs = []
for k in koinly[:10]:
    # Buscar en ledger
    date_sold = k['date_sold'].split()[0]
    amount = k['amount']
    
    # Buscar trade similar
    for refid, legs in list(trades_by_refid.items())[:50]:
        btc_legs = [l for l in legs if l['asset'] == k['asset']]
        if btc_legs and abs(btc_legs[0]['amount']) == amount:
            usd_legs = [l for l in legs if l['asset'] == 'USD']
            if usd_legs:
                usd = usd_legs[0]
                # Calcular
                cost_method1 = abs(usd['amount']) + usd['fee']  # fee al cost
                cost_method2 = abs(usd['amount'])  # sin fee
                
                proceeds_method1 = abs(btc_legs[0]['amountusd'])  # sin deducir fee
                proceeds_method2 = abs(btc_legs[0]['amountusd']) - usd['fee']  # deduciendo fee
                
                print(f"\n{k['asset']} {amount}:")
                print(f"  Koinly Cost: ${k['cost']:.2f}")
                print(f"  Método 1 (cost = |USD| + fee): ${cost_method1:.4f}")
                print(f"  Método 2 (cost = |USD|): ${cost_method2:.4f}")
                print(f"  Koinly Proceeds: ${k['proceeds']:.2f}")
                print(f"  Ledger crypto USD: ${proceeds_method1:.4f}")
                break
    break
