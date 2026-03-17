# Delta for Exchange CSV Import (Binance)

## Purpose

Add native support for importing Binance/USDT trading history exports in CSV format, enabling users to process Binance trades without manual conversion.

## ADDED Requirements

### Requirement: Binance CSV Import Support

The system MUST support importing CSV files exported from Binance's trading history feature.

#### Scenario: Import valid Binance CSV

- GIVEN a valid Binance CSV file with all required columns
- WHEN the user selects Binance as exchange and uploads the CSV
- THEN the file MUST pass validation without errors
- AND entries MUST be loaded into the system as LedgerEntry objects

#### Scenario: Import Binance CSV with missing optional columns

- GIVEN a Binance CSV missing optional columns
- WHEN validation runs
- THEN status MUST be "warning" with informative message
- AND processing MUST continue with estimated values for missing columns

#### Scenario: Import Binance CSV with missing required columns

- GIVEN a Binance CSV missing required columns (e.g., "Date", "Type", "Amount")
- WHEN validation runs
- THEN status MUST be "error"
- AND the system MUST NOT attempt to parse the file

### Requirement: Binance Transaction Type Mapping

The system MUST correctly map Binance transaction types to internal LedgerEntry types.

#### Scenario: Map Buy transaction

- GIVEN a Binance row with "Type" = "Buy"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "trade"
- AND subtype MUST be "buy"

#### Scenario: Map Sell transaction

- GIVEN a Binance row with "Type" = "Sell"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "trade"
- AND subtype MUST be "sell"

#### Scenario: Map Deposit transaction

- GIVEN a Binance row with "Type" = "Deposit"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "deposit"

#### Scenario: Map Withdrawal transaction

- GIVEN a Binance row with "Type" = "Withdrawal"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "withdrawal"

#### Scenario: Map Reward/Staking transaction

- GIVEN a Binance row with "Type" = "Reward" or "Staking"
- WHEN processed into LedgerEntry
- THEN the type field MUST be "earn"

### Requirement: Binance Fee Handling

The system MUST correctly extract and store fees from Binance CSV rows.

#### Scenario: Extract fees from trade

- GIVEN a Binance trade row with fee information
- WHEN processed into LedgerEntry
- THEN the fee field MUST contain the fee amount

#### Scenario: Handle zero-fee transactions

- GIVEN a Binance row with no fees
- WHEN processed into LedgerEntry
- THEN the fee field MUST be Decimal("0")

### Requirement: Binance Date Parsing

The system MUST correctly parse Binance timestamp formats.

#### Scenario: Parse standard Binance date

- GIVEN a Binance CSV with "Date" column in format "2024-01-01"
- WHEN the row is parsed
- THEN the time field MUST be a valid datetime object representing that date

#### Scenario: Parse datetime with time

- GIVEN a Binance CSV with "Date" column in format "2024-01-01 10:30:45"
- WHEN the row is parsed
- THEN the time field MUST include both date and time

#### Scenario: Handle unparseable dates

- GIVEN Binance CSV rows with unparseable date formats
- WHEN parsing fails
- THEN rows with unparseable dates SHOULD be logged and skipped

### Requirement: Binance USD Value Extraction

The system MUST extract USD values from Binance CSV columns.

#### Scenario: Extract from Total column

- GIVEN a Binance row with "Total" column
- WHEN processed
- THEN amountusd MUST be extracted from the Total column
- AND if Total is not available, it SHOULD be calculated as Price × Amount

### Requirement: Binance Market Pair Parsing

The system MUST correctly parse the Market/Pair column to extract the asset.

#### Scenario: Parse standard pair format

- GIVEN a Binance row with "Market" = "BTC/USDT"
- WHEN processed
- THEN the asset field MUST be "BTC" (base currency)
- AND the quote currency (USDT) SHOULD be noted for reference

#### Scenario: Handle USDT pairs

- GIVEN a Binance row with "Market" = "ETH/USDT"
- WHEN processed
- THEN the asset MUST be "ETH"

## MODIFIED Requirements

### Requirement: Exchange Configuration Structure

The existing Binance.US configuration SHOULD be updated to enabled status.

(Previously: Binance.US was disabled with coming_soon=True)

#### Scenario: Enable Binance exchange

- GIVEN Binance.US exchange configuration
- WHEN the system loads exchanges
- THEN Binance.US MUST appear in the enabled exchanges list
- AND it MUST be selectable in the UI

## REMOVED Requirements

### Requirement: (None)

No existing requirements are being removed by this change.

## Implementation Notes

- Binance uses a simpler "trades" format compared to Coinbase's "transactions"
- Key columns: Date, Type, Market, Amount, Price, Total
- Market column contains trading pair (e.g., BTC/USDT) - need to parse base asset
- May need to handle Binance.US vs international Binance formats separately in future
