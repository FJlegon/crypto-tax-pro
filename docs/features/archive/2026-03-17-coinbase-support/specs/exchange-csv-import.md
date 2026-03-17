# Delta for Exchange CSV Import (Coinbase)

## Purpose

Add native support for importing Coinbase transaction history exports in CSV format, enabling users to process Coinbase trades without manual conversion.

## ADDED Requirements

### Requirement: Coinbase CSV Import Support

The system MUST support importing CSV files exported from Coinbase's Transaction History feature.

#### Scenario: Import valid Coinbase CSV

- GIVEN a valid Coinbase CSV file with all required columns
- WHEN the user selects Coinbase as exchange and uploads the CSV
- THEN the file MUST pass validation without errors
- AND entries MUST be loaded into the system as LedgerEntry objects

#### Scenario: Import Coinbase CSV with missing optional columns

- GIVEN a Coinbase CSV missing optional columns (e.g., "Notes", "ID")
- WHEN validation runs
- THEN status MUST be "warning" with informative message
- AND processing MUST continue with estimated values for missing columns

#### Scenario: Import Coinbase CSV with missing required columns

- GIVEN a Coinbase CSV missing required columns (e.g., "Timestamp", "Asset")
- WHEN validation runs
- THEN status MUST be "error"
- AND the system MUST NOT attempt to parse the file

### Requirement: Coinbase Transaction Type Mapping

The system MUST correctly map Coinbase transaction types to internal LedgerEntry types.

#### Scenario: Map Buy transaction

- GIVEN a Coinbase row with "Transaction Type" = "Buy"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "trade"
- AND subtype MUST be "buy"

#### Scenario: Map Sell transaction

- GIVEN a Coinbase row with "Transaction Type" = "Sell"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "trade"
- AND subtype MUST be "sell"

#### Scenario: Map Deposit transaction

- GIVEN a Coinbase row with "Transaction Type" = "Deposit"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "deposit"

#### Scenario: Map Withdrawal transaction

- GIVEN a Coinbase row with "Transaction Type" = "Withdrawal"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "withdrawal"

#### Scenario: Map Reward/Staking transaction

- GIVEN a Coinbase row with "Transaction Type" = "Reward" or "Staking"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "earn"

#### Scenario: Map Coinbase Earn transaction

- GIVEN a Coinbase row with "Transaction Type" = "Coinbase Earn"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "income"

### Requirement: Coinbase Fee Handling

The system MUST correctly extract and store fees from Coinbase CSV rows.

#### Scenario: Extract fees from Buy transaction

- GIVEN a Coinbase "Buy" row with "Fees and/or Spread" value
- WHEN processed into LedgerEntry
- THEN the fee field MUST contain the fee amount in the quote currency
- AND the amount field MUST contain quantity transacted minus fee

#### Scenario: Handle zero-fee transactions

- GIVEN a Coinbase row with no fees (empty or "0")
- WHEN processed into LedgerEntry
- THEN the fee field MUST be Decimal("0")

### Requirement: Coinbase Date Parsing

The system MUST correctly parse Coinbase timestamp formats.

#### Scenario: Parse standard Coinbase timestamp

- GIVEN a Coinbase CSV with "Timestamp" column in format "1/15/2025 10:30:45 AM"
- WHEN the row is parsed
- THEN the time field MUST be a valid datetime object representing that timestamp

#### Scenario: Handle multiple timestamp formats

- GIVEN Coinbase CSV rows with varying timestamp formats
- WHEN parsing fails on primary format
- THEN the system SHOULD attempt ISO format as fallback
- AND rows with unparseable timestamps SHOULD be logged and skipped

### Requirement: Coinbase USD Value Extraction

The system MUST extract USD values from Coinbase CSV columns.

#### Scenario: Extract spot price and total

- GIVEN a Coinbase row with "Spot Price at Transaction" and "Total (inclusive of fees and/or spread)"
- WHEN processed
- THEN amountusd MUST be calculated from Spot Price × Quantity
- AND if "Total" column exists, it SHOULD be used as proceeds for sales

### Requirement: UI Exchange Selection

The UI MUST display Coinbase as an available exchange option when enabled.

#### Scenario: Display enabled Coinbase in exchange list

- GIVEN Coinbase exchange is enabled in configuration
- WHEN the exchange selection step renders
- THEN Coinbase MUST appear in the list of available exchanges
- AND users MUST be able to select it

#### Scenario: Hide disabled Coinbase from exchange list

- GIVEN Coinbase exchange is disabled (coming_soon=True)
- WHEN the exchange selection step renders
- THEN Coinbase SHOULD either not appear OR appear as disabled with "Coming Soon" indicator

## MODIFIED Requirements

### Requirement: Exchange Configuration Structure

The existing ExchangeConfig dataclass SHOULD accept a new optional field for custom column mapping functions.

(Previously: ExchangeConfig only stores column names, no parsing logic)

#### Scenario: Use exchange-specific parser

- GIVEN an exchange with file_type="transactions" (like Coinbase)
- WHEN load_ledgers is called with that exchange_key
- THEN the system MUST use the exchange-specific parsing logic
- AND NOT fall back to generic ledger column mapping

## REMOVED Requirements

### Requirement: (None)

No existing requirements are being removed by this change.

## Implementation Notes

- Coinbase already has a config entry in `exchange_manager.py` but it's disabled
- Need to enable the config and implement the parsing logic in `data_loader.py`
- May need to add a new parsing path for "transactions" file_type vs "ledger" file_type
- Should preserve backward compatibility with existing Kraken and generic parsers
