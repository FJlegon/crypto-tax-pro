# Proposal: Native Binance CSV Support

## Intent

Add native CSV import support for Binance and Binance.US exchange exports. Users have requested Binance support to process their trades without manual CSV conversion. This follows the successful pattern established with Coinbase support.

## Scope

### In Scope
- Parse Binance.US CSV export format (trade history)
- Map Binance transaction types to internal LedgerEntry events
- Handle Binance-specific fee structures
- Support both Binance.US and potentially international Binance CSV formats
- Integrate with existing wallet mapping and anomaly detection

### Out of Scope
- Real-time API integration with Binance (future phase)
- Binance Smart Chain (BSC) DeFi transactions
- Tax calculation differences specific to Binance products

## Approach

1. Update existing Binance.US config in `src/exchange_manager.py` to enable it
2. Research actual Binance.US CSV column format
3. Add parsing function in `src/data_loader.py` similar to Coinbase implementation
4. Map Binance transaction types:
   - `Buy`/`Sell` → `trade`
   - `Deposit`/`Withdrawal` → `deposit`/`withdrawal`
   - `Reward`/`Staking` → `earn`
5. Test with sample Binance CSVs to ensure correct parsing
6. Add to exchange selection dropdown in UI

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/exchange_manager.py` | Modified | Enable Binance.US config, add column definitions |
| `src/data_loader.py` | Modified | Add Binance CSV format detection and parsing |
| `app/main_gui.py` | Modified | Add Binance to exchange dropdown options |
| `tests/test_data_loader.py` | Modified | Add Binance integration tests |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Binance changes CSV format | Medium | Build flexible column mapping, validate on load |
| Fee calculation differs from other exchanges | Low | Compare against known Binance fee structure |
| Test data availability | Medium | Generate synthetic Binance CSVs for testing |
| Different Binance.US vs international format | Medium | Support common subset, add separate handler if needed |

## Rollback Plan

1. Revert changes to `src/exchange_manager.py` and `src/data_loader.py`
2. Remove Binance from dropdown in `app/main_gui.py`
3. Remove test files added for Binance
4. No database migrations needed (stateless CSV parsing)

## Dependencies

- Existing Coinbase CSV parser as reference implementation
- Sample Binance CSV exports for testing (can be synthetic)

## Success Criteria

- [ ] Can import Binance.US transaction history CSV without errors
- [ ] All transaction types correctly mapped to internal events
- [ ] Fees calculated correctly per Binance export
- [ ] UI shows Binance as available exchange option
- [ ] Existing tests pass
- [ ] New Binance-specific tests added
