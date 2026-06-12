# Micro Trader Hardening Roadmap

## Current Direction

The app should become a safe unattended paper-trading system before any live-capital work.

Current implementation focus:

- ETF-first defaults for autonomous execution and simulation
- stale-data and provider-health autopilot guards
- clearer operator visibility into when the engine is safe to act

## Phase 1

- Keep autonomous execution limited to configured asset kinds
- Block trading and simulation when quote freshness or provider coverage is below threshold
- Surface autopilot state directly in the UI
- Preserve skipped-trade reasons for auditability

## Phase 2

- Add benchmark and drawdown reporting
- Split strategies by universe instead of one shared blended score
- Add trade journal and post-trade attribution
- Require stronger setup evidence before opening new simulations

## Phase 3

- Add broker reconciliation
- Add order intent idempotency and mismatch alerts
- Add explicit live-readiness checklist and tiny-capital launch mode

## Non-Negotiables

- No unattended trading on stale data
- No unattended trading on partial provider coverage
- Default to doing nothing when inputs are ambiguous
- Scale only after paper results survive multiple regimes
