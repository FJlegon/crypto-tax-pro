# Design: MetaMask/Etherscan Wallet Sync

## Technical Approach

Implement direct wallet syncing via Etherscan API by creating a new `wallet_sync` module that:
1. Validates Ethereum addresses locally before API calls
2. Fetches transactions from Etherscan API with rate limiting
3. Maps blockchain transactions to LedgerEntry format
4. Supports multiple wallet addresses with caching

This approach follows the existing pattern of exchange CSV loaders but uses API calls instead of file parsing.

## Architecture Decisions

### Decision: Use dedicated wallet_sync module vs. extend data_loader

**Choice**: Create new `src/wallet_sync.py` module  
**Alternatives considered**: Extend existing `data_loader.py` with API methods  
**Rationale**: Wallet syncing is fundamentally different from CSV parsing (async API calls, rate limiting, caching). A separate module keeps concerns isolated and maintains clean architecture.

### Decision: Validate addresses locally before API calls

**Choice**: Validate Ethereum address format client-side before API call  
**Alternatives considered**: Rely on API to validate and return error  
**Rationale**: Saves API calls, provides faster feedback to users, and reduces rate limit consumption.

### Decision: Use requests library vs. web3.py

**Choice**: Use Python `requests` library for Etherscan API  
**Alternatives considered**: Use `web3.py` for direct Ethereum node access  
**Rationale**: Etherscan API is simpler and doesn't require running a local Ethereum node. More reliable for users without technical setup.

### Decision: In-memory caching for API responses

**Choice**: Cache API responses in memory during session  
**Alternatives considered**: Persist cache to disk between sessions  
**Rationale**: Simpler implementation, reduces API calls on retry, acceptable for MVP. Can add disk caching in future.

## Data Flow

```
User Input (Wallet Address)
         │
         ▼
validate_eth_address() ─── Error? ───► Show validation error
         │
         ▼
fetch_etherscan_transactions()
         │
         ├─► Check cache
         │
         ├─► API call (with rate limiting)
         │
         ▼
map_etherscan_to_ledger_entry()
         │
         ▼
Combine multiple wallets
         │
         ▼
List[LedgerEntry]
```

## File Changes

| File | Action | Description |
|------|--------|-------------|
| `src/wallet_sync.py` | Create | Main wallet syncing module |
| `src/exchange_manager.py` | Modified | Add Etherscan exchange config |
| `app/main_gui.py` | Modified | Add wallet sync UI step |
| `tests/test_wallet_sync.py` | Create | Unit tests |

## Interfaces / Contracts

### New Module: `src/wallet_sync.py`

```python
@dataclass
class WalletSyncResult:
    """Result of a wallet sync operation."""
    wallet_id: str
    entries: list[LedgerEntry]
    tx_count: int
    error: Optional[str] = None


def validate_eth_address(address: str) -> bool:
    """
    Validate Ethereum address format.
    Returns True if valid (0x followed by 40 hex chars).
    """
    

def fetch_etherscan_transactions(
    address: str,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Fetch transactions from Etherscan API.
    Implements rate limiting and retry logic.
    """
    

def map_etherscan_to_ledger(
    tx: dict,
    wallet_id: str,
) -> LedgerEntry:
    """
    Map Etherscan transaction to LedgerEntry.
    - ETH inbound → deposit
    - ETH outbound → withdrawal
    - ERC-20 → trade/transfer
    """
    

def sync_wallet(
    address: str,
    wallet_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> WalletSyncResult:
    """
    Main entry point: validate, fetch, and map wallet transactions.
    """
```

### Rate Limiting

- Free tier: 5 calls/second
- Implement 200ms delay between calls
- Exponential backoff on 429 errors (1s, 2s, 4s)
- Max 3 retries

### Wallet ID Format

- Format: `etherscan_{short_address}`
- Example: `etherscan_0x1234...abcd`

## Testing Strategy

| Layer | What to Test | Approach |
|-------|-------------|----------|
| Unit | Address validation | Test valid/invalid addresses |
| Unit | Transaction mapping | Test ETH deposits, withdrawals, ERC-20 |
| Unit | Rate limiting | Mock API responses |
| Integration | Full sync flow | Use testnet address |

## Migration / Rollback

No migration required:
- No database changes
- New module with no data dependencies
- Rollback: delete `wallet_sync.py`, remove UI, remove exchange config

## Open Questions

- [ ] Should we support Etherscan testnet (Sepolia) for testing?
- [ ] How to handle very large transaction histories (>10k txs)?
- [ ] Should we add option to sync only specific date ranges?
- [ ] Cache expiry time for API responses?

These questions don't block MVP implementation - can be addressed in future iterations.
