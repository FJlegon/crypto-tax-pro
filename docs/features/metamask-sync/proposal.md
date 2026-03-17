# Proposal: Direct MetaMask/Etherscan Wallet Syncing

## Intent

Add the ability to directly import wallet transactions from MetaMask and Etherscan into Crypto Tax Pro. Currently, users must manually export CSV files from these sources. This feature will enable automatic syncing of non-custodial wallet activity, completing the multi-exchange support for the tax calculation engine.

## Scope

### In Scope
- Etherscan API integration for transaction history fetching
- MetaMask wallet connection via wallet_connect or manual address entry
- Fetch ETH and ERC-20 token transfers (deposits/withdrawals)
- Map blockchain transactions to internal LedgerEntry events
- Support for multiple wallet addresses per user
- Rate limiting and API key management for Etherscan

### Out of Scope
- Real-time push notifications for new transactions
- NFT transaction tracking (ERC-721/ERC-1155)
- DeFi protocol interactions (swap, lend, borrow) - future phase
- Multi-chain support beyond Ethereum mainnet (Polygon, Arbitrum, etc.)

## Approach

1. **Etherscan API Integration**:
   - Use Etherscan API to fetch transaction history for a given address
   - Support both normal transactions and internal transactions
   - Handle API rate limits with configurable delays

2. **MetaMask Integration**:
   - Option 1: Direct address entry (no wallet connection required)
   - Option 2: WalletConnect protocol for read-only access
   - Store wallet addresses in the app state

3. **Transaction Mapping**:
   - Map Etherscan transactions to LedgerEntry:
     - ETH transfers: type="deposit" or "withdrawal"
     - ERC-20 transfers: type="trade" with subtype="transfer"
   - Extract gas fees from transaction data

4. **UI Integration**:
   - Add "Wallet Sync" step in the wizard
   - Input field for wallet address or MetaMask connection button
   - Show fetched transactions before proceeding

## Affected Areas

| Area | Impact | Description |
|------|--------|-------------|
| `src/exchange_manager.py` | Modified | Add "etherscan" and "metamask" exchange configs |
| `src/data_loader.py` | Modified | Add Etherscan API client and transaction parser |
| `src/wallet_sync.py` | Create | New module for wallet syncing logic |
| `app/main_gui.py` | Modified | Add wallet sync wizard step |
| `tests/test_wallet_sync.py` | Create | Tests for wallet syncing |

## Risks

| Risk | Likelihood | Mitigation |
|------|------------|-------------|
| Etherscan API rate limits | High | Implement exponential backoff, cache results |
| API key required for production | Medium | Make API key optional, use free tier limits |
| Privacy concerns with wallet connection | Medium | Emphasize read-only, local processing only |
| Complex DeFi transactions | High | Start with simple transfers only, expand later |

## Rollback Plan

1. Remove wallet sync code from `data_loader.py`
2. Delete `src/wallet_sync.py` module
3. Remove wallet sync UI from wizard
4. Remove exchange configs from `exchange_manager.py`
5. No database migrations needed

## Dependencies

- Etherscan API key (free tier available)
- Python `requests` library for HTTP calls
- Optional: `web3.py` for MetaMask integration

## Success Criteria

- [ ] Can fetch transaction history from Etherscan for any ETH address
- [ ] Transactions correctly mapped to LedgerEntry format
- [ ] UI allows users to add wallet addresses
- [ ] Gas fees extracted and recorded
- [ ] API rate limiting works correctly
- [ ] Existing tests pass
- [ ] New wallet sync tests added
