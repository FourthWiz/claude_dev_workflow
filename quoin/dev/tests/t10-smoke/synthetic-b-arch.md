---
artifact_type: architecture
task: t10-smoke-b
created: 2026-04-27
---
## For human

Architecture approved for adding retry and circuit-breaker logic to the payment service. Current state is a single PaymentClient with no retry mechanism; proposed design adds a RetryDecorator (3 attempts, exponential backoff) and circuit breaker (opens after 5 consecutive failures). Two risks identified: Stripe SDK incompatibility (HIGH) and backoff aggressiveness under load (MEDIUM). Work is decomposed into two stages: stage 1 covers retry core and unit tests; stage 2 adds circuit breaker and integration tests. Neither stage has started.

## Context
Payment service needs retry logic for transient Stripe failures.
Currently: no retry, all timeouts return 500 to caller.

## Current state
Single PaymentClient class, no retry, no circuit breaker.

## Proposed architecture
Add RetryDecorator wrapping PaymentClient. Max 3 attempts, exponential backoff (1s/2s/4s). Circuit breaker opens after 5 consecutive failures.

## Risk register
| ID | Risk | Severity |
|----|------|----------|
| R-01 | Stripe SDK incompatibility | HIGH |
| R-02 | Backoff too aggressive under load | MEDIUM |

## Stage decomposition
| Stage | Name | Description |
|-------|------|-------------|
| 1 | retry-core | RetryDecorator + unit tests |
| 2 | circuit-breaker | Circuit breaker + integration tests |

## Stage Summary Table
| Stage | Status |
|-------|--------|
| 1 | not started |
| 2 | not started |
