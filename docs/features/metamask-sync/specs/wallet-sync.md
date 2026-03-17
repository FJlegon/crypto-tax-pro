# Wallet Sync Specification

## Purpose

Add capability to directly import non-custodial wallet transactions from Etherscan and MetaMask into Crypto Tax Pro. This enables automatic syncing of blockchain wallet activity without manual CSV exports.

## Requirements

### Requirement: Etherscan API Connection

The system MUST be able to connect to Etherscan API and fetch transaction history for a given Ethereum address.

#### Scenario: Fetch transactions with valid API key

- GIVEN a valid Etherscan API key and an Ethereum wallet address
- WHEN the user initiates a wallet sync
- THEN the system MUST fetch transactions from Etherscan API
- AND return a list of transaction records

#### Scenario: Fetch transactions without API key (rate limited)

- GIVEN no Etherscan API key is provided
- WHEN the user initiates a wallet sync
- THEN the system SHOULD use the free tier (5 calls/sec)
- AND implement rate limiting to avoid throttling

#### Scenario: Handle invalid wallet address

- GIVEN an invalid Ethereum address format
- WHEN the user attempts to sync
- THEN the system MUST return an error with clear message
- AND NOT attempt to call the API

### Requirement: Transaction Type Mapping

The system MUST correctly map Etherscan transaction types to internal LedgerEntry types.

#### Scenario: Map ETH inbound transfer

- GIVEN an Etherscan transaction where the wallet address received ETH
- WHEN processed into LedgerEntry
- THEN the type field MUST be "deposit"
- AND the amount MUST be the value in ETH

#### Scenario: Map ETH outbound transfer

- GIVEN an Etherscan transaction where the wallet address sent ETH
- WHEN processed into LedgerEntry
- THEN the type field MUST be "withdrawal"
- AND the amount MUST be the value in ETH

#### Scenario: Map ERC-20 token transfer

- GIVEN an Etherscan transaction for an ERC-20 token transfer
- WHEN processed into LedgerEntry
- THEN the type field MUST be "trade"
- AND subtype MUST be "transfer"
- AND asset MUST be the token symbol (e.g., "USDC")

### Requirement: Gas Fee Extraction

The system MUST extract gas fees from Etherscan transaction data.

#### Scenario: Extract gas fee from transaction

- GIVEN an Etherscan transaction with gas fee data
- WHEN processed into LedgerEntry
- THEN the fee field MUST contain the gas fee in ETH
- AND the fee MUST be converted to Decimal format

### Requirement: Rate Limiting

The system MUST implement rate limiting to comply with Etherscan API limits.

#### Scenario: Handle API rate limit response

- GIVEN Etherscan API returns rate limit error (HTTP 429)
- WHEN fetching transactions
- THEN the system MUST wait and retry with exponential backoff
- AND log a warning to the user

#### Scenario: Maximum retry attempts

- GIVEN API keeps returning rate limit after 3 retries
- WHEN fetching transactions
- THEN the system MUST stop and return error
- AND inform the user to try again later

### Requirement: Multiple Wallet Support

The system MUST support adding multiple wallet addresses.

#### Scenario: Add second wallet address

- GIVEN user has already added one wallet address
- WHEN user adds a second wallet address
- THEN the system MUST fetch transactions for both wallets
- AND combine them in the final ledger

#### Scenario: Duplicate wallet address

- GIVEN user attempts to add a wallet address that already exists
- WHEN the duplicate is detected
- THEN the system MUST notify the user
- AND NOT add the duplicate

### Requirement: Wallet Address Validation

The system MUST validate Ethereum addresses before attempting API calls.

#### Scenario: Validate correct address format

- GIVEN a valid Ethereum address (0x followed by 40 hex characters)
- WHEN validated
- THEN the address MUST be accepted

#### Scenario: Reject invalid address format

- GIVEN an invalid address (not 0x + 40 hex)
- WHEN validated
- THEN the system MUST reject with error message

## Implementation Notes

- Use Etherscan API endpoints: `api.etherscan.io/api?module=account&action=txlist`
- Support both normal transactions and internal transactions for full coverage
- Cache transaction results to avoid redundant API calls
- Store API key in app settings (encrypted)
- Default wallet_id format: "etherscan_0xABC..."
