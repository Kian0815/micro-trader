# Micro Trader

Local-first paper-trading MVP built for a very small budget. It ingests crypto, ETF, and starter stock market data, scores news sentiment from RSS feeds, generates signals, and simulates trades with hard risk limits around a `30 EUR` account.

## Why this setup

- `Docker Compose` keeps the Mac setup reproducible.
- `FastAPI` gives both JSON APIs and a lightweight dashboard.
- `Postgres` stores everything you need to inspect decisions and performance.
- The system defaults to `paper trading`, which is the right mode for a micro-budget strategy.

## What it does today

- Tracks a small crypto watchlist plus paper-only ETF and stock watchlists.
- Pulls crypto market data from Binance spot EUR pairs with CoinGecko fallback.
- Pulls ETF and stock quotes from Twelve Data when `TWELVEDATA_API_KEY` is configured.
- Pulls crypto and market news from configurable RSS feeds.
- Scores news sentiment with a transparent rules-based engine.
- Creates `BUY`, `SELL`, or `HOLD` signals.
- Splits decision logic into separate `ETF`, `stock`, and `crypto` strategy lanes.
- Executes simulated trades with strict account limits.
- Shows current state, autopilot safety, and benchmark checks on a local dashboard.
- Tracks expectancy, drawdown, and benchmark-relative performance in the dashboard and API.
- Scores each setup family as `approved`, `watch`, or `disabled` from resolved 4h and 24h outcomes before it earns unattended trust.
- Runs a short-horizon walk-forward split by setup so train/test evidence is visible before a lane is promoted.
- Extends that walk-forward report with replayed stock and ETF setup candidates from stored tick history, while keeping unattended approval gates tied to live resolved evidence.
- Records durable execution intents and reconciliation snapshots so the paper ledger has an auditable execution trail.

## Quick start

1. Copy the environment file:

```bash
cp .env.example .env
```

2. Start the stack:

```bash
docker compose up --build
```

3. Open the dashboard:

- [Dashboard](http://localhost:8000/)
- [API docs](http://localhost:8000/docs)

## US market setup

To enable ETF and stock quotes, add your market-data credentials to `.env`:

```bash
ALPACA_API_KEY=your_key_here
ALPACA_API_SECRET=your_secret_here
API_PORT_BIND=8000:8000
DB_PORT_BIND=127.0.0.1:5432:5432
PUBLIC_EQUITY_STATE_PATH=/app/state/plugins/oai-maintained-plugins/public-equity-investing/onboarding-state.json
ETF_DATA_PROVIDER=alpaca
ALPACA_QUOTE_CACHE_TTL_SECONDS=3600
TWELVEDATA_API_KEY=your_key_here
FINIMPULSE_API_TOKEN=
```

The default ETF watchlist is:

```bash
ETF_WATCHLIST=SPY,QQQ,VTI
```

The default stock watchlist is:

```bash
STOCK_WATCHLIST=AAPL,MSFT,NVDA
```

Without a working market-data credential path, the crypto side keeps running normally and ETFs/stocks stay seeded but inactive until quotes are available.

You can choose the crypto quote source explicitly:

```bash
CRYPTO_DATA_PROVIDER=binance
```

Supported crypto providers today:

- `binance` for exchange-native EUR spot quotes
- `coingecko` as a fallback path for broader crypto coverage

You can also switch ETF market data to `Twelve Data` or `FinImpulse`:

```bash
ETF_DATA_PROVIDER=twelvedata
TWELVEDATA_API_KEY=your_key_here
```

```bash
ETF_DATA_PROVIDER=finimpulse
FINIMPULSE_API_TOKEN=your_token_here
```

Supported ETF/stock provider order now includes:

- `alpaca` for authenticated ETF/stock snapshots
- `twelvedata`
- `alphavantage`
- `finimpulse`

The app prefers the selected provider and then falls back through the rest of the chain if it returns no usable quotes.

You can also switch to `Twelve Data`:

```bash
ETF_DATA_PROVIDER=twelvedata
TWELVEDATA_API_KEY=your_key_here
```

The ETF/stock lane now treats `alpaca` as the normal primary source, reuses recent `alpaca` quotes as a trusted cache window, and only falls back across `twelvedata`, `alphavantage`, and `finimpulse` as an emergency backfill path.

## Production hardening controls

The app now includes a few execution-grade safeguards:

```bash
TRADING_ENABLED=true
SIMULATION_ENABLED=true
TRADEABLE_ASSET_KINDS=etf,stock,crypto
SIMULATION_ASSET_KINDS=etf,stock,crypto
UNATTENDED_SETUP_STATUSES=approved
MIN_DATA_COVERAGE_RATIO=1.0
MAX_TICK_AGE_SECONDS=900
MIN_MINUTES_BETWEEN_TRADES=30
MAX_GROSS_EXPOSURE_PCT=0.4
MAX_SYMBOL_EXPOSURE_PCT=0.2
MAX_PORTFOLIO_DRAWDOWN_PCT=5.0
ASSET_KIND_EXPOSURE_LIMITS=etf:0.7,stock:0.2,crypto:0.1
```

- `TRADING_ENABLED=false` disables automatic paper execution while leaving data ingestion and signals running.
- `SIMULATION_ENABLED=false` pauses the dedicated best-asset simulation loop.
- `TRADEABLE_ASSET_KINDS` and `SIMULATION_ASSET_KINDS` now let the engine rank opportunities across `etf`, `stock`, and `crypto`, while still letting you narrow the universe if you want.
- `UNATTENDED_SETUP_STATUSES=approved` means only evidence-cleared setups may open unattended entries. You can widen this to `approved,watch` if you explicitly want a looser mode.
- The stock lane is now evaluated separately: `stock_event` still needs real catalyst coverage, while `stock_momentum` can surface from tape strength alone. Both remain gated by the same unattended proof board.
- `MIN_DATA_COVERAGE_RATIO` blocks unattended execution when fresh quote coverage is incomplete.
- `MAX_TICK_AGE_SECONDS` blocks execution on stale market data.
- `MIN_MINUTES_BETWEEN_TRADES` applies a cooldown per asset to reduce churn and duplicate fills.
- `MAX_GROSS_EXPOSURE_PCT` caps total deployed capital as a share of current equity.
- `MAX_SYMBOL_EXPOSURE_PCT` caps concentration in any one symbol.
- `MAX_PORTFOLIO_DRAWDOWN_PCT` activates a capital-preservation lock when equity falls too far from peak.
- `ASSET_KIND_EXPOSURE_LIMITS` caps exposure by lane so crypto and stocks cannot silently dominate the book.
- `PROVIDER_RATE_LIMIT_COOLDOWN_SECONDS` temporarily skips a rate-limited market data provider after recent `429` failures.
- `PROVIDER_ERROR_COOLDOWN_SECONDS` temporarily skips a provider after recent non-rate-limit errors.

## Real broker prep

The project now includes a broker adapter layer. It is disabled by default.

Supported today:

- `alpaca` as the first official API adapter
- internal `paper` ledger as the default execution source of truth

Environment variables:

```bash
BROKER_PROVIDER=none
BROKER_MODE=paper
BROKER_ENABLED=false
BROKER_EXECUTION_TARGET=internal
BROKER_LIVE_CONFIRMED=false
LIVE_EMERGENCY_STOP=true
LIVE_RUNBOOK_ACKNOWLEDGED=false
LIVE_ALERTS_CONFIGURED=false
OPERATOR_ALERT_WEBHOOK_URL=
OPERATOR_ALERT_EVENTS=worker_failure,trade_fill,trade_rejection
ALPACA_API_KEY=
ALPACA_API_SECRET=
ALPACA_BASE_URL=
```

Useful endpoints:

- `GET /api/broker/status`
- `GET /api/broker/capabilities`
- `GET /api/broker/positions`
- `GET /api/broker/orders`
- `GET /api/broker/preview-order?symbol=SPY&side=buy&notional=5`
- `POST /api/broker/submit-order`
- `GET /api/execution/intents`
- `GET /api/execution/reconciliation`
- `GET /api/execution/reconciliation/details`

Notes:

- Alpaca's official Trading API supports paper trading globally and uses paper credentials with the paper endpoint.
- The current project prepares the broker integration but does not switch real order placement on automatically.
- Broker preview and submit now treat `notional` as an `EUR` budget for supported equity orders and convert it into `USD` before building the Alpaca payload.
- The conversion uses a live EUR/USD quote plus a configurable safety buffer via `FX_USD_BUFFER_PCT`, and broker submission is blocked if the FX quote is unavailable.
- `BROKER_EXECUTION_TARGET=internal` keeps the internal ledger as the source of truth even when a broker adapter is configured.
- Internal paper execution now stops itself if `BROKER_MODE` is not `paper` or `BROKER_EXECUTION_TARGET` is not `internal`, instead of letting the ledger drift away from broker reality.
- Broker order submission now supports durable `client_order_id` values and the reconciliation layer compares broker positions and recent orders against the internal execution-intent ledger.
- `BROKER_LIVE_CONFIRMED=false` blocks live broker submission until you explicitly remove that guard.
- `LIVE_EMERGENCY_STOP=true` is a second hard block that prevents live submission even if broker live mode is turned on.
- `LIVE_RUNBOOK_ACKNOWLEDGED=false` and `LIVE_ALERTS_CONFIGURED=false` keep the live deployment checklist red until the operating process is intentionally prepared.
- `OPERATOR_ALERT_WEBHOOK_URL` lets the VM send operator notifications to a webhook receiver for worker failure, fill, and rejection events.
- `OPERATOR_ALERT_EVENTS` controls which of `worker_failure`, `trade_fill`, and `trade_rejection` can emit webhook alerts.

## Main endpoints

- `GET /` dashboard
- `GET /health`
- `GET /api/assets`
- `GET /api/signals`
- `GET /api/trades`
- `GET /api/positions`
- `GET /api/summary`
- `GET /api/performance`
- `GET /api/benchmarks`
- `GET /api/setups/scorecards`
- `GET /api/setups/walk-forward`
- `POST /api/engine/run-once`

## Notes

- This project is evolving toward ETF-first unattended paper trading, while still supporting crypto and a starter stock universe.
- The system uses real market data and public RSS feeds, but execution is simulated.
- If a feed or market call fails, the engine falls back safely and avoids taking action on incomplete data.

## Development without Docker

If you want to run it directly on macOS:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
uvicorn app.main:app --reload
```

You will still need a local Postgres instance, or you can temporarily point `HOST_DATABASE_URL` to another reachable database.
