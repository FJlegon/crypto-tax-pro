# Proposal: Native Coinbase Support

## Intent

Add native CSV import support for Coinbase exchange exports. Currently the app only supports Kraken. Users have requested Coinbase support to process their trades without manual CSV conversion.

## Scope

### In Scope
- Parse Coinbase CSV export format (transactions history)
- Map Coinbase transaction types to internal `LedgerEntry` events
- Handle Coinbase-specific fee structures
- Support multiple CSV formats (old and new Coinbase export formats)
- Integrate with existing wallet mapping and anomaly detection

### Out of Scope
- Real-time API integration with Coinbase (future phase)
- Coinbase Pro specific exports
- Tax calculation differences for Coinbase-specific products

## Approach

1. Add Coinbase configuration in `src/exchange_manager.py` with required/optional columns
2. Implement CSV parser in `src/data_loader.py` that detects Coinbase format
3. Map Coinbase transaction types:
   - `Buy`/`Sell` → `trade`
   - `Deposit`/`Withdrawal` → `deposit`/`withdrawal`
   - `Reward`/`Staking` → `earn`
   - `Coinbase Earn` → `income`
4. Test with sample Coinbase CSVs to ensure correct parsing
5. Add to exchange selection dropdown in UI

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/exchange_manager.py` | Modified | Add Coinbase config with column mapping |
| `src/data_loader.py` | Modified | Add Coinbase CSV format detection and parsing |
| `app/main_gui.py` | Modified | Add Coinbase to exchange dropdown options |
| `tests/test_fifo_engine.py` | Modified | Add Coinbase integration tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Coinbase changes CSV format | Medium | Build flexible column mapping, validate on load |
| Fee calculation differs from Kraken | Low | Compare against known Coinbase fee structure |
| Test data availability | Medium | Generate synthetic Coinbase CSVs for testing |

## Rollback Plan

1. Revert changes to `src/exchange_manager.py` and `src/data_loader.py`
2. Remove Coinbase from dropdown in `app/main_gui.py`
3. Remove test files added for Coinbase
4. No database migrations needed (stateless CSV parsing)

## Dependencies

- Existing Kraken CSV parser as reference implementation
- Sample Coinbase CSV exports for testing (can be synthetic)

## Success Criteria

- [ ] Can import Coinbase transaction history CSV without errors
- [ ] All transaction types correctly mapped to internal events
- [ ] Fees calculated correctly per Coinbase export
- [ ] UI shows Coinbase as available exchange option
- [ ] Existing tests pass
- [ ] New Coinbase-specific tests added
