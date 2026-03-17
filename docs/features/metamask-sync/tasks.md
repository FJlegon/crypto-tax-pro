# Tasks: MetaMask/Etherscan Wallet Sync

## Phase 1: Configuration & Foundation

- [x] 1.1 Add `requests` library to `requirements.txt` if not present
- [x] 1.2 Create `src/wallet_sync.py` module structure with imports
- [x] 1.3 Add `WalletSyncResult` dataclass to wallet_sync module

## Phase 2: Core Implementation

- [x] 2.1 Implement `validate_eth_address()` function — regex check for 0x + 40 hex chars
- [x] 2.2 Implement `fetch_etherscan_transactions()` function with basic API call
- [x] 2.3 Implement rate limiting with 200ms delay between calls
- [x] 2.4 Implement exponential backoff retry logic (1s, 2s, 4s) on HTTP 429
- [x] 2.5 Implement `map_etherscan_to_ledger()` function — map ETH transfers to deposit/withdrawal
- [x] 2.6 Implement ERC-20 token transfer mapping to trade/transfer
- [x] 2.7 Implement gas fee extraction from transaction data
- [x] 2.8 Implement `sync_wallet()` main function combining validation, fetch, and mapping
- [x] 2.9 Add in-memory caching for API responses

## Phase 3: Exchange Manager Integration

- [x] 3.1 Add Etherscan exchange config in `src/exchange_manager.py`
- [x] 3.2 Configure required/optional columns (N/A for API-based, use placeholders)
- [x] 3.3 Add export URL and guide instructions for Etherscan

## Phase 4: Testing

- [x] 4.1 Write test: `test_validate_eth_address_valid` — verify valid address passes
- [x] 4.2 Write test: `test_validate_eth_address_invalid` — verify invalid address fails
- [x] 4.3 Write test: `test_validate_eth_address_too_short` — verify short address fails
- [x] 4.4 Write test: `test_map_eth_deposit` — verify inbound ETH maps to deposit
- [x] 4.5 Write test: `test_map_eth_withdrawal` — verify outbound ETH maps to withdrawal
- [x] 4.6 Write test: `test_map_erc20_transfer` — verify ERC-20 maps to trade/transfer
- [x] 4.7 Write test: `test_gas_fee_extraction` — verify gas fee extracted correctly
- [x] 4.8 Write test: `test_rate_limiting_delay` — verify 200ms delay between calls
- [x] 4.9 Write test: `test_retry_on_429` — verify exponential backoff on rate limit

## Phase 5: Integration & Verification

- [x] 5.1 Run full test suite: `pytest tests/ -v`
- [ ] 5.2 Test with real Etherscan API (using test address)
- [ ] 5.3 Verify error handling for network failures

## Phase 6: Cleanup & Documentation

- [x] 6.1 Add docstrings to all public functions in wallet_sync.py
- [x] 6.2 Update module docstring in wallet_sync.py
- [x] 6.3 Verify code follows project conventions (black, flake8)
