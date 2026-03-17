# Design: Native Binance CSV Support

## Technical Approach

Enable Binance CSV import by:
1. Updating Binance.US config in `src/exchange_manager.py` to enable it with correct column definitions
2. Adding a new parsing function in `src/data_loader.py` for "trades" file_type (Binance's format)
3. Mapping Binance columns to internal LedgerEntry fields

This approach follows the existing pattern established with Coinbase - use file_type dispatch to select the appropriate parser.

## Architecture Decisions

### Decision: Use file_type="trades" for Binance

**Choice**: Use "trades" file_type for Binance  
**Alternatives considered**: Use "transactions" like Coinbase, use "ledger" like Kraken  
**Rationale**: Binance CSV is a trade history format (like Coinbase transactions but simpler). Using "trades" distinguishes it from both "ledger" (Kraken) and "transactions" (Coinbase).

### Decision: Enable existing Binance.US config vs. create new entry

**Choice**: Enable existing Binance.US config entry  
**Alternatives considered**: Create separate "binance" entry for international Binance  
**Rationale**: The existing config entry can be updated. Can add separate international Binance later if needed.

### Decision: Market pair parsing strategy

**Choice**: Parse base currency from Market column (e.g., "BTC/USDT" → "BTC")  
**Alternatives considered**: Store full pair, parse quote currency  
**Rationale**: Internal system uses base asset as primary - consistent with other exchanges.

## Data Flow

```
CSV File (Binance)
       │
       ▼
validate_file() ──► ExchangeConfig (binanceus)
       │                    │
       │                    ▼
       │            check required_cols
       │
       ▼
load_ledgers(exchange_key="binanceus")
       │
       ├─► config.file_type == "trades"
       │        │
       │        ▼
       │   _load_binance_csv()
       │        │
       │        ▼
       │   Map columns to LedgerEntry
       │   - Date → time
       │   - Type → type + subtype
       │   - Market → asset (parse base)
       │   - Amount → amount
       │   - Total → amountusd
       │   - Fee → fee
       │
       ▼
List[LedgerEntry]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/exchange_manager.py` | Modify | Enable Binance.US, add column definitions |
| `src/data_loader.py` | Modify | Add `_load_binance_csv()` function and dispatch logic |
| `app/main_gui.py` | No change | Already reads from config - Binance will appear automatically |
| `tests/test_data_loader.py` | Modify | Add Binance tests |

## Interfaces / Contracts

### New Function: `_load_binance_csv()`

```python
def _load_binance_csv(
    df: pd.DataFrame,
    wallet_id: str,
) -> list[LedgerEntry]:
    """
    Parse Binance trade history CSV into LedgerEntry objects.
    
    Column mapping:
    - Date → time
    - Type → type + subtype
    - Market → asset (parse base currency from pair)
    - Amount → amount
    - Total → amountusd
    - Fee → fee
    """
```

### Transaction Type Mapping

| Binance Type | LedgerEntry.type | LedgerEntry.subtype |
|-------------|------------------|---------------------|
| Buy | trade | buy |
| Sell | trade | sell |
| Deposit | deposit | |
| Withdrawal | withdrawal | |
| Reward | earn | reward |
| Staking | earn | staking |

### Market Pair Parsing

- Input: "BTC/USDT" → Output: asset="BTC"
- Input: "ETH/USDT" → Output: asset="ETH"
- Split on "/" and take first element

### Date Parsing

Binance dates come in formats like:
- `2024-01-01` (date only)
- `2024-01-01 10:30:45` (date with time)

Parser will try these formats in order:
1. `%Y-%m-%d %H:%M:%S` (with time)
2. `%Y-%m-%d` (date only)

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Column mapping correctness | Test each transaction type maps correctly |
| Unit | Date parsing | Test various Binance date formats |
| Unit | Market pair parsing | Test BTC/USDT → BTC extraction |
| Unit | Fee extraction | Verify fees parsed correctly |
| Integration | Full CSV load | Load sample Binance CSV, verify entries count |
| Integration | Validation | Test missing required columns |

## Migration / Rollback

No migration required. This is a pure feature addition:
- No database changes
- No data migration
- Rollback: revert `enabled=True` → `enabled=False` in Binance config

## Open Questions

- [ ] Should we support international Binance (non-US) exports? Currently only Binance.US defined.
- [ ] How to handle fiat deposits/withdrawals (USD transfers)?
- [ ] Should we validate that quote currency is USDT for tax calculations?

These questions don't block implementation - can be addressed in future iterations.
