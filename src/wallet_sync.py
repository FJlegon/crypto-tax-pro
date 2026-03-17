"""
wallet_sync.py — Etherscan API client for wallet transaction syncing.

Provides functionality to fetch Ethereum wallet transactions from Etherscan
and convert them to LedgerEntry objects for tax calculation.
"""
import re
import time
import logging
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Optional

logger = logging.getLogger(__name__)

# In-memory cache for API responses
_etherscan_cache: dict[str, list[dict]] = {}

# Rate limiting
API_DELAY_SECONDS = 0.2  # 200ms between calls
MAX_RETRIES = 3
RETRY_DELAYS = [1, 2, 4]  # Exponential backoff in seconds


@dataclass
class WalletSyncResult:
    """Result of a wallet sync operation."""
    wallet_id: str
    entries: list
    tx_count: int
    error: Optional[str] = None


def validate_eth_address(address: str) -> bool:
    """
    Validate Ethereum address format.
    
    Args:
        address: The Ethereum address to validate.
    
    Returns:
        True if valid (0x followed by 40 hex characters), False otherwise.
    """
    if not address:
        return False
    # Pattern: 0x followed by exactly 40 hex characters
    pattern = r"^0x[a-fA-F0-9]{40}$"
    return bool(re.match(pattern, address))


def _get_cache_key(address: str, api_key: Optional[str]) -> str:
    """Generate cache key for a wallet address."""
    return f"{address}:{api_key or 'no_key'}"


def fetch_etherscan_transactions(
    address: str,
    api_key: Optional[str] = None,
) -> list[dict]:
    """
    Fetch transactions from Etherscan API.
    
    Implements rate limiting (200ms delay) and exponential backoff retry
    on HTTP 429 (rate limit) errors.
    
    Args:
        address: Ethereum wallet address to fetch transactions for.
        api_key: Optional Etherscan API key for higher rate limits.
    
    Returns:
        List of transaction dictionaries from Etherscan.
    
    Raises:
        ValueError: If address is invalid.
        RuntimeError: If API call fails after retries.
    """
    if not validate_eth_address(address):
        raise ValueError(f"Invalid Ethereum address: {address}")

    # Check cache first
    cache_key = _get_cache_key(address, api_key)
    if cache_key in _etherscan_cache:
        logger.info(f"Returning cached transactions for {address}")
        return _etherscan_cache[cache_key]

    # Build API URL
    base_url = "https://api.etherscan.io/api"
    params = {
        "module": "account",
        "action": "txlist",
        "address": address,
        "startblock": 0,
        "endblock": 99999999,
        "sort": "asc",
    }
    if api_key:
        params["apikey"] = api_key

    # Fetch with rate limiting and retry logic
    for attempt in range(MAX_RETRIES):
        try:
            # Rate limiting delay
            time.sleep(API_DELAY_SECONDS)

            import requests
            response = requests.get(base_url, params=params, timeout=30)
            
            if response.status_code == 429:
                # Rate limited - retry with backoff
                if attempt < len(RETRY_DELAYS):
                    wait_time = RETRY_DELAYS[attempt]
                    logger.warning(f"Rate limited, waiting {wait_time}s before retry...")
                    time.sleep(wait_time)
                    continue
                else:
                    raise RuntimeError("Etherscan API rate limit exceeded after retries")

            response.raise_for_status()
            data = response.json()

            if data.get("status") == "0":
                # API returned error
                if "No transactions found" in data.get("message", ""):
                    return []
                raise RuntimeError(f"Etherscan API error: {data.get('message')}")

            txs = data.get("result", [])
            logger.info(f"Fetched {len(txs)} transactions for {address}")
            
            # Cache the results
            _etherscan_cache[cache_key] = txs
            return txs

        except requests.RequestException as e:
            if attempt < len(RETRY_DELAYS):
                wait_time = RETRY_DELAYS[attempt]
                logger.warning(f"Request failed: {e}, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"Failed to fetch transactions after {MAX_RETRIES} attempts: {e}")

    return []


def map_etherscan_to_ledger(
    tx: dict,
    wallet_address: str,
) -> Optional[object]:
    """
    Map Etherscan transaction to LedgerEntry.
    
    - ETH inbound transfer → deposit
    - ETH outbound transfer → withdrawal
    - ERC-20 token transfer → trade/transfer
    
    Args:
        tx: Etherscan transaction dictionary.
        wallet_address: The full Ethereum wallet address (0x...) to compare against.
    
    Returns:
        LedgerEntry object, or None if mapping fails.
    """
    from .models import LedgerEntry

    try:
        # Parse timestamp
        from datetime import datetime
        timestamp = int(tx.get("timeStamp", 0))
        if timestamp:
            time_val = datetime.fromtimestamp(timestamp)
        else:
            time_val = datetime.now()

        # Normalize addresses for comparison
        wallet_addr = wallet_address.lower()
        from_address = tx.get("from", "").lower()
        to_address = tx.get("to", "").lower()

        # Determine transaction type
        is_erc20 = tx.get("tokenID", "").strip() or tx.get("token_symbol", "").strip()

        if is_erc20:
            # ERC-20 transfer
            entry_type = "trade"
            subtype = "transfer"
            asset = tx.get("token_symbol", "UNKNOWN") or "UNKNOWN"
        elif wallet_addr == to_address and wallet_addr == from_address:
            # Self-transfer
            entry_type = "trade"
            subtype = "transfer"
            asset = "ETH"
        elif wallet_addr == to_address:
            # Inbound - deposit
            entry_type = "deposit"
            subtype = ""
            asset = "ETH"
        elif wallet_addr == from_address:
            # Outbound - withdrawal
            entry_type = "withdrawal"
            subtype = ""
            asset = "ETH"
        else:
            logger.warning(f"Cannot determine transaction direction for {tx.get('hash')}")
            return None

        # Parse amounts - convert wei to ETH
        try:
            value_wei = Decimal(tx.get("value", "0"))
            amount = value_wei / Decimal("1e18")
        except InvalidOperation:
            amount = Decimal("0")

        # Parse gas fee (gas used * gas price in wei)
        try:
            gas_used = Decimal(tx.get("gasUsed", "0"))
            gas_price = Decimal(tx.get("gasPrice", "0"))
            fee_wei = gas_used * gas_price
            fee = fee_wei / Decimal("1e18")
        except InvalidOperation:
            fee = Decimal("0")

        # For ERC-20, use token value instead of ETH value
        if entry_type == "trade" and subtype == "transfer":
            try:
                token_value = Decimal(tx.get("tokenValue", "0"))
                amount = token_value
            except InvalidOperation:
                pass

        # amountusd - not available from Etherscan, will need price lookup later
        amountusd = Decimal("0")

        # Generate txid from hash
        txid = tx.get("hash", "")

        entry = LedgerEntry(
            txid=txid,
            refid=tx.get("hash", ""),
            time=time_val,
            type=entry_type,
            subtype=subtype,
            asset=asset,
            amount=amount,
            fee=fee,
            balance=Decimal("0"),
            amountusd=amountusd,
            wallet_id=wallet_address,
        )
        return entry

    except Exception as e:
        logger.warning(f"Failed to map transaction {tx.get('hash')}: {e}")
        return None


def sync_wallet(
    address: str,
    wallet_id: Optional[str] = None,
    api_key: Optional[str] = None,
) -> WalletSyncResult:
    """
    Main entry point: validate, fetch, and map wallet transactions.
    
    Args:
        address: Ethereum wallet address to sync.
        wallet_id: Optional custom wallet ID, defaults to "etherscan_{short_address}".
        api_key: Optional Etherscan API key.
    
    Returns:
        WalletSyncResult containing entries and metadata.
    """
    # Validate address
    if not validate_eth_address(address):
        return WalletSyncResult(
            wallet_id=wallet_id or f"etherscan_{address[:6]}",
            entries=[],
            tx_count=0,
            error=f"Invalid Ethereum address format: {address}",
        )

    # Generate wallet_id if not provided
    if not wallet_id:
        short_addr = f"{address[:6]}...{address[-4:]}"
        wallet_id = f"etherscan_{short_addr}"

    # Fetch transactions
    try:
        txs = fetch_etherscan_transactions(address, api_key)
    except RuntimeError as e:
        return WalletSyncResult(
            wallet_id=wallet_id,
            entries=[],
            tx_count=0,
            error=str(e),
        )

    # Map to LedgerEntry
    entries = []
    for tx in txs:
        entry = map_etherscan_to_ledger(tx, address)  # Pass full address for comparison
        if entry:
            # Override wallet_id with display version
            entry.wallet_id = wallet_id
            entries.append(entry)

    return WalletSyncResult(
        wallet_id=wallet_id,
        entries=entries,
        tx_count=len(entries),
        error=None,
    )


def clear_cache() -> None:
    """Clear the in-memory transaction cache."""
    global _etherscan_cache
    _etherscan_cache = {}
    logger.info("Etherscan cache cleared")
