"""
Script de comparación entre Crypto Tax Pro y Koinly
Compara los resultados generados con el reporte de Koinly
"""
import csv
from decimal import Decimal
from pathlib import Path

# Rutas
KOINLY_FILE = "data/koinly-2024/koinly_2024_capital_gains_report.csv"
APP_FORM_FILE = "reports/app_form_8949_debug.csv"

def safe_decimal(value):
    """Convierte a Decimal de forma segura"""
    try:
        if value is None or value == '':
            return Decimal('0')
        return Decimal(str(value).replace(',', ''))
    except:
        return Decimal('0')

def load_koinly(filepath):
    """Carga el reporte de Koinly"""
    koinly_data = []
    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        header = None
        for i, row in enumerate(reader):
            if i == 0:
                continue
            if i == 1:
                continue
            if i == 2:
                header = row
                continue
            if not row or not header:
                continue
            data = dict(zip(header, row))
            if not data.get('Asset'):
                continue
            koinly_data.append({
                'asset': data['Asset'].upper(),
                'date_sold': data['Date Sold'].split()[0],
                'date_acquired': data['Date Acquired'].split()[0],
                'amount': safe_decimal(data['Amount']),
                'cost': safe_decimal(data['Cost (USD)']),
                'proceeds': safe_decimal(data['Proceeds (USD)']),
                'gain_loss': safe_decimal(data['Gain / loss']),
                'term': data['Holding period'],
            })
    return koinly_data

def load_app_form8949(filepath):
    """Carga el Form 8949 generado por la app"""
    app_data = []
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
            
            # Parsear descripción (ej: "0.00140948 BTC")
            desc = data.get('Description of property (a)', '')
            parts = desc.split()
            amount = safe_decimal(parts[0]) if parts else Decimal('0')
            asset = parts[1].upper() if len(parts) > 1 else 'UNKNOWN'
            
            app_data.append({
                'asset': asset,
                'amount': amount,
                'date_acquired': data.get('Date acquired (b)', ''),
                'date_sold': data.get('Date sold or disposed of (c)', ''),
                'proceeds': safe_decimal(data.get('Proceeds (d)', '0')),
                'cost': safe_decimal(data.get('Cost or other basis (e)', '0')),
                'gain_loss': safe_decimal(data.get('Gain or (loss) (h)', '0')),
                'term': data.get('Term', ''),
                'wallet': data.get('Wallet/Account', ''),
            })
    return app_data

def summarize_data(data, source_name):
    """Resume los datos"""
    summary = {
        'source': source_name,
        'total_events': len(data),
        'total_proceeds': Decimal('0'),
        'total_cost': Decimal('0'),
        'total_gain_loss': Decimal('0'),
        'short_term_gain': Decimal('0'),
        'short_term_loss': Decimal('0'),
        'long_term_gain': Decimal('0'),
        'long_term_loss': Decimal('0'),
        'by_asset': {},
    }
    
    for row in data:
        summary['total_proceeds'] += row['proceeds']
        summary['total_cost'] += row['cost']
        summary['total_gain_loss'] += row['gain_loss']
        
        # Por asset
        asset = row['asset']
        if asset not in summary['by_asset']:
            summary['by_asset'][asset] = {'count': 0, 'gain_loss': Decimal('0'), 'proceeds': Decimal('0')}
        summary['by_asset'][asset]['count'] += 1
        summary['by_asset'][asset]['gain_loss'] += row['gain_loss']
        summary['by_asset'][asset]['proceeds'] += row['proceeds']
        
        # Short/Long term
        term = row.get('term', 'Short-Term')
        if 'Short' in term:
            if row['gain_loss'] >= 0:
                summary['short_term_gain'] += row['gain_loss']
            else:
                summary['short_term_loss'] += row['gain_loss']
        else:
            if row['gain_loss'] >= 0:
                summary['long_term_gain'] += row['gain_loss']
            else:
                summary['long_term_loss'] += row['gain_loss']
    
    return summary

def compare_summaries(koinly_sum, app_sum):
    """Compara los dos resúmenes"""
    print("\n" + "=" * 70)
    print("COMPARACIÓN: Crypto Tax Pro vs Koinly")
    print("=" * 70)
    
    print(f"\n{'Métrica':<25} {'Koinly':>15} {'Crypto Tax Pro':>18} {'Diferencia':>15}")
    print("-" * 70)
    
    print(f"{'Transacciones':<25} {koinly_sum['total_events']:>15} {app_sum['total_events']:>18} {app_sum['total_events'] - koinly_sum['total_events']:>15}")
    print(f"{'Total Proceeds':<25} ${koinly_sum['total_proceeds']:>13,.2f} ${app_sum['total_proceeds']:>16,.2f} ${app_sum['total_proceeds'] - koinly_sum['total_proceeds']:>14,.2f}")
    print(f"{'Total Cost Basis':<25} ${koinly_sum['total_cost']:>13,.2f} ${app_sum['total_cost']:>16,.2f} ${app_sum['total_cost'] - koinly_sum['total_cost']:>14,.2f}")
    print(f"{'NET GAIN/LOSS':<25} ${koinly_sum['total_gain_loss']:>13,.2f} ${app_sum['total_gain_loss']:>16,.2f} ${app_sum['total_gain_loss'] - koinly_sum['total_gain_loss']:>14,.2f}")
    
    print(f"\n{'SHORT-TERM GAIN':<25} ${koinly_sum['short_term_gain']:>13,.2f} ${app_sum['short_term_gain']:>16,.2f} ${app_sum['short_term_gain'] - koinly_sum['short_term_gain']:>14,.2f}")
    print(f"{'SHORT-TERM LOSS':<25} ${koinly_sum['short_term_loss']:>13,.2f} ${app_sum['short_term_loss']:>16,.2f} ${app_sum['short_term_loss'] - koinly_sum['short_term_loss']:>14,.2f}")
    print(f"{'LONG-TERM GAIN':<25} ${koinly_sum['long_term_gain']:>13,.2f} ${app_sum['long_term_gain']:>16,.2f} ${app_sum['long_term_gain'] - koinly_sum['long_term_gain']:>14,.2f}")
    print(f"{'LONG-TERM LOSS':<25} ${koinly_sum['long_term_loss']:>13,.2f} ${app_sum['long_term_loss']:>16,.2f} ${app_sum['long_term_loss'] - koinly_sum['long_term_loss']:>14,.2f}")
    
    # Diferencia total
    diff = app_sum['total_gain_loss'] - koinly_sum['total_gain_loss']
    print(f"\n{'='*70}")
    print(f"DIFERENCIA TOTAL: ${diff:,.2f}")
    if abs(diff) < 1:
        print("[OK] EXCELENTE: Diferencia menor a $1")
    elif abs(diff) < 10:
        print("[OK] BUENO: Diferencia menor a $10")
    elif abs(diff) < 100:
        print("[!] ATENCION: Diferencia entre $10 y $100")
    else:
        print("[X] REVISAR: Diferencia mayor a $100")
    print(f"{'='*70}")
    
    return diff

def compare_by_asset(koinly_sum, app_sum):
    """Compara por asset"""
    print("\n" + "-" * 70)
    print("COMPARACIÓN POR ASSET")
    print("-" * 70)
    print(f"{'Asset':<10} {'Koinly Tx':>10} {'App Tx':>10} {'Koinly $':>12} {'App $':>12} {'Diff $':>12}")
    print("-" * 70)
    
    all_assets = set(koinly_sum['by_asset'].keys()) | set(app_sum['by_asset'].keys())
    
    for asset in sorted(all_assets):
        k_data = koinly_sum['by_asset'].get(asset, {'count': 0, 'gain_loss': Decimal('0')})
        a_data = app_sum['by_asset'].get(asset, {'count': 0, 'gain_loss': Decimal('0')})
        
        diff = a_data['gain_loss'] - k_data['gain_loss']
        
        print(f"{asset:<10} {k_data['count']:>10} {a_data['count']:>10} ${k_data['gain_loss']:>10,.2f} ${a_data['gain_loss']:>10,.2f} ${diff:>10,.2f}")

def main():
    print("=" * 70)
    print("COMPARACIÓN: Crypto Tax Pro vs Koinly")
    print("=" * 70)
    
    # Cargar Koinly
    print("\n[1] Cargando datos de Koinly...")
    koinly_data = load_koinly(KOINLY_FILE)
    print(f"    {len(koinly_data)} transacciones cargadas")
    
    # Cargar App Form 8949
    print("\n[2] Cargando Form 8949 de Crypto Tax Pro...")
    app_data = load_app_form8949(APP_FORM_FILE)
    print(f"    {len(app_data)} transacciones cargadas")
    
    # Resumir
    koinly_summary = summarize_data(koinly_data, "Koinly")
    app_summary = summarize_data(app_data, "Crypto Tax Pro")
    
    # Comparar
    diff = compare_summaries(koinly_summary, app_summary)
    
    # Comparar por asset
    compare_by_asset(koinly_summary, app_summary)
    
    print("\n" + "=" * 70)
    print("ANÁLISIS COMPLETADO")
    print("=" * 70)

if __name__ == "__main__":
    main()
