# Product Data Simulation Design

## Objective

Add a deterministic "advance one day" simulation so product metrics visibly change while dashboard, Agent diagnosis, campaign selection, and risk analysis continue to use one consistent business state.

## User Experience

The product analysis page shows the current simulation date, an "advance one day" command, and a reset command. Advancing displays the business events generated for that day and refreshes the product table. Changed metrics show direction and delta without changing table dimensions.

The operation affects GMV, orders, conversion, inventory, advertising ROI, rating, competitor price, ABC segment, turnover days, and risk tags. Dashboard, Agent, campaign, customer, and product APIs all read the same simulated dataset.

## State Model

Simulation state is stored in SQLite with a singleton scenario record:

- current date
- step number
- deterministic seed
- generated event list
- per-product metric overrides
- update timestamp

The initial state points to the checked-in baseline date. Reset deletes overrides and restores the baseline date and step. State survives browser refresh and backend restart.

## Deterministic Engine

Each step derives a random generator from the base seed and step number. The same baseline, seed, and step always produce the same result. Events are selected from a controlled catalog:

- promotion traffic increase
- negative-review conversion decline
- low-stock sales loss
- replenishment arrival
- competitor price reduction
- ad creative improvement

Events update related signals together. For example, a negative review reduces rating and conversion instead of changing only a label. Inventory is reduced by simulated units and increased when replenishment arrives. Values are bounded to prevent negative stock, invalid ratings, or impossible conversion rates.

## Data Integration

The simulator builds an in-memory `EcommerceDataset` overlay from the immutable CSV baseline and persisted state. API code obtains data through one simulation-aware provider. The original CSV files are never rewritten during a user simulation.

Endpoints:

- `GET /api/ecommerce/simulation/state`
- `POST /api/ecommerce/simulation/advance`
- `POST /api/ecommerce/simulation/reset`

Advance returns the new date, events, and product-level before/after deltas. Reset returns the baseline state.

## Frontend

The product page adds simulation date, advance, and reset controls. A compact event band lists the current day's business events. Delta markers are shown for GMV, orders, conversion, stock, ROI, rating, and competitor price. The page reloads product data after each transition.

Reset requires confirmation because it discards the current simulated timeline. Advancing is disabled while a request is in progress.

## Error Handling

State writes are transactional. If persistence fails, the API returns an error and no partial day is exposed. Concurrent advance requests use optimistic version checks so only one step succeeds. Invalid or missing state is rebuilt from the baseline.

## Testing

Tests verify deterministic output, bounded metrics, inventory accounting, restart persistence, reset behavior, optimistic conflicts, and cross-endpoint consistency. Frontend contracts and Playwright verify controls, event display, changing product values, refresh persistence, and reset.

## Acceptance Criteria

- Each advance changes at least one product metric and returns at least one event.
- The same seed and step produce the same result.
- Product, dashboard, Agent, and campaign endpoints use the advanced state.
- Refresh and restart preserve the current simulation date.
- Reset restores the baseline metrics and date.
- Backend tests, frontend build, and desktop/mobile E2E pass.
