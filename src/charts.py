from decimal import Decimal
from typing import List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime
from .models import TaxableEvent

@dataclass
class AssetSummary:
    asset: str
    total_proceeds: Decimal
    total_cost_basis: Decimal
    gain_loss: Decimal
    event_count: int
    term: str

def get_asset_breakdown(events: List[TaxableEvent]) -> List[AssetSummary]:
    asset_data = {}
    
    for e in events:
        asset = e.description.split()[1] if len(e.description.split()) > 1 else e.description
        
        if asset not in asset_data:
            asset_data[asset] = {
                'proceeds': Decimal('0'),
                'cost_basis': Decimal('0'),
                'count': 0,
                'st_gain': Decimal('0'),
                'lt_gain': Decimal('0'),
            }
        
        asset_data[asset]['proceeds'] += e.proceeds
        asset_data[asset]['cost_basis'] += e.cost_basis
        asset_data[asset]['count'] += 1
        
        if e.term == 'Short-Term':
            asset_data[asset]['st_gain'] += e.gain_loss
        else:
            asset_data[asset]['lt_gain'] += e.gain_loss
    
    summaries = []
    for asset, data in asset_data.items():
        total_gain = data['st_gain'] + data['lt_gain']
        term = 'Mixed' if data['st_gain'] != 0 and data['lt_gain'] != 0 else ('Short-Term' if data['st_gain'] != 0 else 'Long-Term')
        
        summaries.append(AssetSummary(
            asset=asset,
            total_proceeds=data['proceeds'],
            total_cost_basis=data['cost_basis'],
            gain_loss=total_gain,
            event_count=data['count'],
            term=term,
        ))
    
    return sorted(summaries, key=lambda x: abs(x.gain_loss), reverse=True)

def get_wallet_breakdown(events: List[TaxableEvent]) -> Dict[str, Dict]:
    wallet_data = {}
    
    for e in events:
        parts = e.description.split()
        wallet = parts[0] if parts else 'Unknown'
        
        if wallet not in wallet_data:
            wallet_data[wallet] = {
                'proceeds': Decimal('0'),
                'cost_basis': Decimal('0'),
                'count': 0,
            }
        
        wallet_data[wallet]['proceeds'] += e.proceeds
        wallet_data[wallet]['cost_basis'] += e.cost_basis
        wallet_data[wallet]['count'] += 1
    
    return wallet_data

def get_tax_summary(events: List[TaxableEvent], ordinary_income: Decimal) -> Dict:
    st_gain = sum((e.gain_loss for e in events if e.term == 'Short-Term'), Decimal('0'))
    lt_gain = sum((e.gain_loss for e in events if e.term == 'Long-Term'), Decimal('0'))
    
    total_proceeds = sum((e.proceeds for e in events), Decimal('0'))
    total_cost = sum((e.cost_basis for e in events), Decimal('0'))
    
    return {
        'total_events': len(events),
        'short_term_gain': st_gain,
        'long_term_gain': lt_gain,
        'net_capital_gain': st_gain + lt_gain,
        'ordinary_income': ordinary_income,
        'total_proceeds': total_proceeds,
        'total_cost_basis': total_cost,
    }

def get_monthly_breakdown(events: List[TaxableEvent]) -> Dict[str, Dict]:
    """Returns monthly data keyed as YYYY-MM."""
    monthly_data = {}
    
    for e in events:
        # Try various formats
        month_key = "Unknown"
        date_str = str(e.date_sold).strip()
        
        try:
            # Format: MM/DD/YYYY (Standard from FIFOEngine)
            if '/' in date_str:
                dt = datetime.strptime(date_str, "%m/%d/%Y")
                month_key = dt.strftime("%Y-%m")
            # Format: YYYY-MM-DD or YYYY-MM (ISO-like)
            elif '-' in date_str:
                if len(date_str) >= 10:
                    dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
                    month_key = dt.strftime("%Y-%m")
                elif len(date_str) >= 7:
                    # Already looks like YYYY-MM
                    month_key = date_str[:7]
        except Exception:
            # Fallback if specific parsing fails
            if len(date_str) >= 7 and date_str[4] == '-':
                month_key = date_str[:7]
            elif len(date_str) >= 10 and date_str[2] == '/' and date_str[5] == '/':
                month_key = f"{date_str[6:10]}-{date_str[0:2]}"
        
        if month_key not in monthly_data:
            monthly_data[month_key] = {
                'proceeds': Decimal('0'),
                'cost_basis': Decimal('0'),
                'gain': Decimal('0'),
                'count': 0,
            }
        
        monthly_data[month_key]['proceeds'] += e.proceeds
        monthly_data[month_key]['cost_basis'] += e.cost_basis
        monthly_data[month_key]['gain'] += e.gain_loss
        monthly_data[month_key]['count'] += 1
    
    return dict(sorted(monthly_data.items()))

def generate_pie_chart_data(asset_summaries: List[AssetSummary], max_items: int = 6) -> Tuple[List, Decimal]:
    total_gain = sum((s.gain_loss for s in asset_summaries), Decimal('0'))
    total_absolute_gain = sum((abs(s.gain_loss) for s in asset_summaries), Decimal('0'))
    
    top_assets = asset_summaries[:max_items]
    other_gain = sum((abs(s.gain_loss) for s in asset_summaries[max_items:]), Decimal('0'))
    real_other_gain = sum((s.gain_loss for s in asset_summaries[max_items:]), Decimal('0'))
    
    chart_data = []
    colors = [
        '#4CAF50', '#2196F3', '#FF9800', '#E91E63', 
        '#9C27B0', '#00BCD4', '#795548', '#607D8B'
    ]
    
    for i, asset in enumerate(top_assets):
        chart_data.append({
            'asset': asset.asset,
            'gain_loss': asset.gain_loss,
            'percentage': (abs(asset.gain_loss) / total_absolute_gain * 100) if total_absolute_gain != 0 else 0,
            'color': colors[i % len(colors)],
        })
    
    if other_gain != 0:
        chart_data.append({
            'asset': 'Other',
            'gain_loss': real_other_gain,
            'percentage': (other_gain / total_absolute_gain * 100) if total_absolute_gain != 0 else 0,
            'color': '#9E9E9E',
        })
    
    return chart_data, total_gain

def format_bar_chart(width: int, value: Decimal, max_value: Decimal) -> str:
    if max_value == 0:
        return ' ' * width
    
    ratio = float(value / max_value)
    filled = int(ratio * width)
    bar = '█' * filled + '░' * (width - filled)
    return bar
