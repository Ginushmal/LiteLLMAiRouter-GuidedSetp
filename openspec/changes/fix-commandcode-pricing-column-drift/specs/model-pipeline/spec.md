# Spec Delta

## ADDED Requirements

### Requirement: Header-driven HTML pricing table extraction
When a provider adapter extracts pricing from an HTML table, it SHALL locate the price columns by their header text rather than by fixed cell position, and SHALL fail the fetch loudly when the table's schema no longer exposes the expected columns. A provider page layout change SHALL NOT silently shift a price from one field to another, and SHALL NOT silently yield missing prices while recording provider provenance.

#### Scenario: Columns are mapped by header text
- **WHEN** the CommandCode models page publishes its pricing table with a header row
- **THEN** the adapter SHALL identify the Model, Input, Output, Cache read, and Cache write columns from the header cells' text (ignoring sort-marker glyphs and surrounding whitespace) and read each row's prices from those column indices

#### Scenario: Column removal does not shift prices
- **WHEN** the pricing table's column set changes between fetches (for example a non-price column such as Intelligence is removed) while all required price headers remain present
- **THEN** each price SHALL still be stored in its correct field (input, output, cache read, cache write), and the parsed prices SHALL equal the values published under their own headers

#### Scenario: Column reordering does not shift prices
- **WHEN** the pricing table publishes the required price columns in a different order than a previous fetch
- **THEN** each price SHALL still be stored in the field named by its header

#### Scenario: Missing price column fails the fetch loudly
- **WHEN** the pricing table's header row is absent, or any of the Input, Output, Cache read, or Cache write headers cannot be located
- **THEN** the adapter SHALL raise an error that names the missing headers and indicates a page schema change, the fetch phase SHALL stop for that provider, and the error SHALL be recorded in the structured scraping log — no partially-shifted pricing SHALL be returned

#### Scenario: Price cell semantics are unchanged
- **WHEN** a price cell carries a plan marker suffix (e.g. "$0.10 + 1"), a strikethrough list price followed by an effective price, "Free", or a dash
- **THEN** the adapter SHALL keep its existing interpretation: the effective (last) dollar figure, 0.0 for Free, and no price for a dash — independent of which column index the cell occupies

#### Scenario: Historical and current layouts parse identically
- **WHEN** the same model's prices are published in both the historical layout (with an Intelligence column) and the current layout (without it)
- **THEN** both fetches SHALL produce identical normalized pricing records for that model