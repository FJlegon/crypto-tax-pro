# Tasks: Native Binance CSV Support

## Phase 1: Configuration & Foundation

- [ ] 1.1 Update Binance.US config in `src/exchange_manager.py` — set `enabled=True`, `coming_soon=False`
- [ ] 1.2 Add required columns: `{"Date", "Type", "Market", "Amount", "Price", "Total"}`
- [ ] 1.3 Add optional columns: `{"Fee"}`
- [ ] 1.4 Update Binance config `guide` with accurate export instructions

## Phase 2: Core Implementation

- [ ] 2.1 Add `_load_binance_csv()` function in `src/data_loader.py`
- [ ] 2.2 Implement `_parse_binance_date()` helper for date parsing (date-only and datetime)
- [ ] 2.3 Implement `_map_binance_transaction_type()` helper with mapping table
- [ ] 2.4 Implement `_parse_binance_market_pair()` helper to extract base asset from "BTC/USDT" format
- [ ] 2.5 Add dispatch logic in `load_ledgers()` to call `_load_binance_csv()` when `file_type == "trades"`
- [ ] 2.6 Handle missing/empty optional columns gracefully (fee, price)

## Phase 3: Testing

- [ ] 3.1 Write test: `test_binance_transaction_type_mapping_buy` — verify "Buy" maps to type="trade", subtype="buy"
- [ ] 3.2 Write test: `test_binance_transaction_type_mapping_sell` — verify "Sell" maps to type="trade", subtype="sell"
- [ ] 3.3 Write test: `test_binance_transaction_type_mapping_deposit` — verify "Deposit" maps to type="deposit"
- [ ] 3.4 Write test: `test_binance_transaction_type_mapping_withdrawal` — verify "Withdrawal" maps to type="withdrawal"
- [ ] 3.5 Write test: `test_binance_transaction_type_mapping_reward` — verify "Reward" maps to type="earn"
- [ ] 3.6 Write test: `test_binance_date_parsing_with_time` — verify parsing of "2024-01-01 10:30:45"
- [ ] 3.7 Write test: `test_binance_date_parsing_date_only` — verify parsing of "2024-01-01"
- [ ] 3.8 Write test: `test_binance_market_pair_parsing` — verify "BTC/USDT" parses to asset="BTC"
- [ ] 3.9 Write test: `test_binance_fee_extraction` — verify fee parsed correctly
- [ ] 3.10 Write test: `test_binance_amountusd_from_total` — verify amountusd from Total column
- [ ] 3.11 Write test: `test_binance_validation_missing_required_columns` — verify validation fails with error

## Phase 4: Integration & Verification

- [ ] 4.1 Create sample Binance CSV file in `data/binance/` for manual testing
- [ ] 4.2 Run full test suite: `pytest tests/test_data_loader.py -v`
- [ ] 4.3 Verify Binance appears in UI exchange selector (run `python app/main_gui.py`)
- [ ] 4.4 Run existing tests to ensure no regression: `pytest tests/ -v`

## Phase 5: Cleanup & Documentation

- [ ] 5.1 Add docstring to `_load_binance_csv()` documenting column mapping
- [ ] 5.2 Update `src/data_loader.py` module docstring to mention Binance support
- [ ] 5.3 Update `docs/TECHNICAL_REFERENCE.md` to include Binance in supported exchanges list
