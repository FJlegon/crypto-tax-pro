# Design: Native Coinbase Support

## Technical Approach

Enable Coinbase CSV import by:
1. Updating Coinbase config in `exchange_manager.py` to enable it
2. Adding a new parsing path in `data_loader.py` for "transactions" file_type (Coinbase's format)
3. Mapping Coinbase columns to internal LedgerEntry fields

This approach follows the existing pattern where each exchange has a config with column definitions, and the loader dispatches to the appropriate parsing logic.

## Architecture Decisions

### Decision: Parse Coinbase using separate parsing logic vs. generic column mapping

**Choice**: Separate parsing function for "transactions" file_type  
**Alternatives considered**: Use generic column mapping with runtime column alias resolution  
**Rationale**: Coinbase's CSV format is structurally different from Kraken's ledger format (different column names, different fee structure, different transaction grouping). A dedicated parsing function keeps the code clean and maintainable.

### Decision: Store Coinbase transactions as-is (one row = one entry)

**Choice**: Each Coinbase CSV row maps to one LedgerEntry  
**Alternatives considered**: Split into crypto leg + USD leg like Kraken  
**Rationale**: Coinbase CSV already provides both the quantity and USD value in each row. We don't need to create paired entries - we can directly use the "Total" column as amountusd.

### Decision: Enable Coinbase in config vs. create new exchange entry

**Choice**: Enable existing Coinbase config entry  
**Alternatives considered**: Create new "coinbasev2" entry for new format  
**Rationale**: The existing config already has the correct column definitions. Only need to flip `enabled=True` and `coming_soon=False`.

## Data Flow

```
CSV File (Coinbase)
       │
       ▼
validate_file() ──► ExchangeConfig (coinbase)
       │                    │
       │                    ▼
       │            check required_cols
       │
       ▼
load_ledgers(exchange_key="coinbase")
       │
       ├─► config.file_type == "transactions"
       │        │
       │        ▼
       │   _load_coinbase_csv()
       │        │
       │        ▼
       │   Map columns to LedgerEntry
       │   - Timestamp → time
       │   - Transaction Type → type/subtype
       │   - Quantity Transacted → amount
       │   - Total (fees) → fee
       │   - Spot Price × Qty → amountusd
       │
       ▼
List[LedgerEntry]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/exchange_manager.py` | Modify | Set `enabled=True`, `coming_soon=False` for Coinbase config |
| `src/data_loader.py` | Modify | Add `_load_coinbase_csv()` function and dispatch logic in `load_ledgers()` |
| `app/main_gui.py` | No change | Already reads from config - Coinbase will appear automatically |
| `tests/test_data_loader.py` | Create | Add tests for Coinbase CSV parsing |

## Interfaces / Contracts

### New Function: `_load_coinbase_csv()`

```python
def _load_coinbase_csv(
    df: pd.DataFrame,
    wallet_id: str,
) -> list[LedgerEntry]:
    """
    Parse Coinbase Transaction History CSV into LedgerEntry objects.
    
    Column mapping:
    - Timestamp → time
    - Transaction Type → type + subtype
    - Asset → asset
    - Quantity Transacted → amount
    - Total (inclusive of fees...) → fee
    - Spot Price at Transaction × Quantity → amountusd
    - ID → txid
    """
```

### Transaction Type Mapping

| Coinbase Type | LedgerEntry.type | LedgerEntry.subtype |
|---------------|------------------|---------------------|
| Buy | trade | buy |
| Sell | trade | sell |
| Deposit | deposit | |
| Withdrawal | withdrawal | |
| Reward | earn | reward |
| Staking | earn | staking |
| Coinbase Earn | income | earn |
| Advanced Trade Buy | trade | buy |
| Advanced Trade Sell | trade | sell |
| Receive | deposit | |
| Send | withdrawal | |

### Date Parsing

Coinbase timestamps come in formats like:
- `1/15/2025 10:30:45 AM`
- `2025-01-15T10:30:45Z`

Parser will try these formats in order:
1. `%m/%d/%Y %I:%M:%S %p` (12-hour with AM/PM)
2. `%Y-%m-%dT%H:%M:%SZ` (ISO)
3. `%Y-%m-%d %H:%M:%S` (24-hour)

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Column mapping correctness | Test each transaction type maps correctly |
| Unit | Date parsing | Test various Coinbase date formats |
| Unit | Fee extraction | Verify fees parsed from "Total" column |
| Unit | amountusd calculation | Verify Spot Price × Quantity |
| Integration | Full CSV load | Load sample Coinbase CSV, verify entries count |
| Integration | Validation | Test missing required columns |

## Migration / Rollback

No migration required. This is a pure feature addition:
- No database changes
- No data migration
- Rollback: revert `enabled=True` → `enabled=False` in Coinbase config

## Open Questions

- [ ] Should we support both old Coinbase format (pre-2024) and new format? Currently only new format defined in config.
- [ ] How to handle "Total" column when it's negative (refunds)? Need to verify actual Coinbase format.
- [ ] Should we add support for Coinbase Pro exports? Currently only main Coinbase.

These questions don't block implementation - can be addressed in future iterations.
