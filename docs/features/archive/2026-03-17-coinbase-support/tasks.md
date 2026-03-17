# Tasks: Native Coinbase Support

## Phase 1: Configuration & Foundation

- [x] 1.1 Enable Coinbase in `src/exchange_manager.py` — set `enabled=True` and `coming_soon=False`
- [x] 1.2 Verify Coinbase config columns match actual Coinbase CSV export format
- [x] 1.3 Update Coinbase config `guide` with accurate export instructions if needed

## Phase 2: Core Implementation

- [x] 2.1 Add `_load_coinbase_csv()` function in `src/data_loader.py`
- [x] 2.2 Implement `_parse_coinbase_timestamp()` helper for date parsing (12-hour, ISO, 24-hour)
- [x] 2.3 Implement `_map_coinbase_transaction_type()` helper with mapping table
- [x] 2.4 Add dispatch logic in `load_ledgers()` to call `_load_coinbase_csv()` when `file_type == "transactions"`
- [x] 2.5 Handle missing/empty optional columns gracefully (spot price, total)

## Phase 3: Testing

- [x] 3.1 Create `tests/test_data_loader.py` test file
- [x] 3.2 Write test: `test_coinbase_transaction_type_mapping_buy` — verify "Buy" maps to type="trade", subtype="buy"
- [x] 3.3 Write test: `test_coinbase_transaction_type_mapping_sell` — verify "Sell" maps to type="trade", subtype="sell"
- [x] 3.4 Write test: `test_coinbase_transaction_type_mapping_deposit` — verify "Deposit" maps to type="deposit"
- [x] 3.5 Write test: `test_coinbase_transaction_type_mapping_withdrawal` — verify "Withdrawal" maps to type="withdrawal"
- [x] 3.6 Write test: `test_coinbase_transaction_type_mapping_reward` — verify "Reward" maps to type="earn"
- [x] 3.7 Write test: `test_coinbase_date_parsing_12hour` — verify parsing of "1/15/2025 10:30:45 AM"
- [x] 3.8 Write test: `test_coinbase_date_parsing_iso` — verify parsing of "2025-01-15T10:30:45Z"
- [x] 3.9 Write test: `test_coinbase_fee_extraction` — verify fee parsed from "Total (inclusive of fees...)" column
- [x] 3.10 Write test: `test_coinbase_amountusd_calculation` — verify amountusd = Spot Price × Quantity
- [x] 3.11 Write test: `test_coinbase_validation_missing_required_columns` — verify validation fails with error for missing columns

## Phase 4: Integration & Verification

- [ ] 4.1 Create sample Coinbase CSV file in `data/coinbase/` for manual testing
- [x] 4.2 Run full test suite: `pytest tests/test_data_loader.py -v`
- [x] 4.3 Test via CLI: `python tools/run_test_logic.py` with Coinbase sample data
- [x] 4.4 Verify Coinbase appears in UI exchange selector (run `python app/main_gui.py`)
- [x] 4.5 Run existing tests to ensure no regression: `pytest tests/ -v`

## Phase 5: Cleanup & Documentation

- [x] 5.1 Add docstring to `_load_coinbase_csv()` documenting column mapping
- [x] 5.2 Update `src/data_loader.py` module docstring to mention Coinbase support
- [ ] 5.3 Clean up any temporary test files
