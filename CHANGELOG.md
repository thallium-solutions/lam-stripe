# Changelog

All notable changes to `@lam/stripe` are documented here. Versions follow
[Semantic Versioning](https://semver.org/) and are tagged without a `v`
prefix (`1.0.0`).

## [1.0.1] - 2026-10-21

### Changed

- Requires `lamc` 3.0 (`>=3.0, <4`); the compiler notes are gone: every limitation they described is fixed in 3.0.
- Tests use a `match` class pattern on the re-exported `StripeError`.

## 1.0.0

First release as an official Lammergeier library. It replaces the vendored
`lamstripe` 0.2.0 package that lived in `third_party/lamstripe` of the
compiler repository.

### Breaking changes

- Import path: `from lamstripe import ...` becomes
  `from @lam/stripe import ...`.
- License: Apache-2.0 (0.x declared MIT).
- Every client call returns a payload-typed `Result`
  (`Result[StripeResponse]`, `Result[StripeList]`, `Result[StripeEvent]`,
  ...) instead of an untyped `Result`, so `r.unwrap()` and `?` give the
  response directly; no more `result.Value.(*StripeResponse)` casts.
- Failures are `StripeError` values (an `lamerrors.Error` subclass) whose
  `kind` follows the Stripe error: `StripeCardError` (402 / `card_error`),
  `StripeInvalidRequestError`, `StripeAuthenticationError`,
  `StripePermissionError`, `StripeRateLimitError`, `StripeIdempotencyError`,
  `StripeApiError`, `StripeConnectionError` (transport failures and
  timeouts, which 0.x reported as a bare `HttpError`), `StripeConfigError`,
  `StripeValidationError` and `StripeSignatureError`. In 0.x every non-2xx
  response was `StripeApiError`.
- Requests are retried by default (`maxRetries = 2`) and POSTs carry a
  generated `Idempotency-Key` unless one is set; set
  `StripeConfig.maxRetries = 0` / `autoIdempotencyKeys = false` for the 0.x
  behaviour.
- `StripeConfig.validate()` rejects publishable keys (`pk_...`) and
  non-HTTP base URLs before any request is sent.
- The User-Agent is `lam-stripe/1.0.0 (Lammergeier; +https://github.com/thallium-solutions/lam-stripe)`
  (0.x sent the stale `lamstripe/0.1.0`).

### Added

- Request core: `Stripe-Version` pinning, optional `Stripe-Account`
  (Connect), per-request `StripeRequestOptions` (idempotency key, account,
  version, timeout, retries, `expand[]`, headers), exponential backoff with
  jitter on network errors, 409, 429 and 5xx that honours
  `Stripe-Should-Retry` and `Retry-After`, per-attempt timeouts, a
  configurable base URL for mocks, and `X-Stripe-Client-User-Agent`.
- `STRIPE_ACCOUNT`, `STRIPE_TIMEOUT_MS` and `STRIPE_MAX_RETRIES`
  environment variables next to the existing `STRIPE_SECRET_KEY`,
  `STRIPE_BASE_URL` and `STRIPE_API_VERSION`.
- Nested form encoding (`Stripe.encodeParams`: `metadata[k]`,
  `items[0][price]`, `expand[]`), `Stripe.decodeForm` / `formValue` for mock
  servers, `Stripe.escapeId`, `Stripe.shouldRetry` and
  `Stripe.retryDelayMs`.
- `StripeObject` null-safe dotted-path accessors (`getStr`, `getInt`,
  `getBool`, `getJson`, `getList`, `getObject`, `metadata`, `has`);
  `StripeResponse` now extends it and exposes headers, `requestId`,
  `idempotencyKey` and `attempts`.
- Pagination: `StripeList`, `StripePager` (`starting_after`,
  `ending_before`, search `page` tokens) and `StripeClient.listAll`.
- Typed calls for customers (create, retrieve, update, delete, list),
  products, prices (`StripePriceOptions`: flat, recurring, metered with a
  Billing Meter, graduated / volume tiers; lookup by `lookup_keys[]`),
  billing meters (`StripeMeterOptions`, list, find by event name) and meter
  events (`StripeMeterEventOptions` with `identifier`), checkout sessions
  (subscription mode, several line items, subscription metadata, trials),
  customer portal sessions, subscriptions (`StripeSubscriptionUpdate` item
  swaps / additions / deletions with proration behaviour, cancel at period
  end, reactivate, cancel now, resume), invoices, events and balance.
- `StripeEvent` (type, id, created, livemode, API version, account,
  request id, `data.object`, `data.previous_attributes`).
- `StripeWebhook`: `verify` / `verifyAny` (several `v1` signatures, secret
  rotation, constant-time comparison, timestamp tolerance) returning a
  typed `StripeEvent`, `verifySignature[Any]`, `constructEvent`,
  `parseHeader`, `splitSecrets`, `sign` and `testHeader`. This absorbs the
  Stripe signature code of the managed-file-transfer application.
- Test suite through the installed-package boundary
  (`tests/run_lamstripe_tests.py`) with unit cases, composed cases against
  an ephemeral local mock Stripe API, and a guarded live test.

### Kept from 0.2.0

- `StripeConfig(secretKey, baseUrl, apiVersion, timeoutMs)`, `fromEnv`,
  `isReady`; `StripeCustomerOptions`, `StripePaymentIntentOptions`,
  `StripeCheckoutSessionOptions` (`setMetadata`, `fields`);
  `StripeResponse(status, body, transportError)` with `ok`, `json`,
  `field`, `id`, `url`, `clientSecret`; `Stripe.encodeForm`,
  `errorMessage`, `normalizeCurrency`, `addMetadata`, `validateAmount`,
  `validateCurrency`; `StripeClient.fromEnv`, `setIdempotencyKey`,
  `rawGet`, `rawPostForm`, `createCustomer[WithOptions]`,
  `createPaymentIntent[WithOptions]`, `retrievePaymentIntent`,
  `createCheckoutSession[WithOptions]`.

## 0.2.0 (as `lamstripe`, in the compiler repository)

- Offline composed checkout/refund test against an ephemeral local mock.
- ISO currency validation rejects non-letter codes.
- `Env.getOr` defaults, `Result[HttpResponse]` transport errors, unsuffixed
  JSON Result contracts.
