# @lam/stripe

A dependency-free [Stripe](https://stripe.com) API client for
[Lammergeier](https://lammergeier-lang.dev) (Lam), the Python-like language
that compiles to Go.

- **Typed results.** Every call returns `Result[StripeResponse]`,
  `Result[StripeList]`, `Result[StripeEvent]`, ... and fails with a
  `StripeError` that carries Stripe's `type`, `code`, `decline_code`,
  `param`, message, HTTP status and `Request-Id`.
- **Safe by default.** Generated idempotency keys on every POST, retries
  with exponential backoff and jitter on network errors, 409, 429 and 5xx
  (honouring `Stripe-Should-Retry` and `Retry-After`), per-attempt timeouts,
  `Stripe-Version` pinning.
- **Billing ready.** Billing Meters and meter events, products, flat /
  recurring / metered / tiered prices, subscription checkout, the customer
  portal, plan changes with proration, cancellation and resumption,
  invoices and events.
- **Webhooks.** `Stripe-Signature` verification with several signatures,
  secret rotation, constant-time comparison and a timestamp tolerance,
  returning a typed `StripeEvent`.
- **Everything else.** Nested form encoding, `expand[]`, auto-paging lists,
  Stripe Connect (`Stripe-Account`) and raw `get` / `post` / `delete`
  escape hatches for endpoints without a typed method.
- **No dependencies.** Only the Lam standard library and the Go standard
  library; nothing is added to your `go.mod`.

> Stripe is a trademark of Stripe, Inc. This is an unofficial,
> community-maintained library; it is not developed, endorsed or supported
> by Stripe, Inc.

## Contents

- [Install](#install)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [API reference](#api-reference)
- [Examples](#examples)
- [Security notes](#security-notes)
- [Testing](#testing)
- [Upgrading from lamstripe 0.x](#upgrading-from-lamstripe-0x)
- [Compiler notes](#compiler-notes)
- [License](#license)

## Install

Requires `lamc` 2.1 or newer. Add the dependency to your project's
`lamlib.toml`:

```toml
[dependencies]
"@lam/stripe" = { git = "https://github.com/thallium-solutions/lam-stripe.git", ref = "1.0.0" }
```

and run `lamc install`, or install it directly:

```sh
lamc install https://github.com/thallium-solutions/lam-stripe.git@1.0.0
```

Import from the scoped package:

```lammergeier
from @lam/stripe import StripeClient, StripeConfig, StripeWebhook
```

## Quick start

```lammergeier
from @lam/stripe import StripeClient, StripeResponse
from lamerrors import Result

func main() {
    # Reads STRIPE_SECRET_KEY, STRIPE_API_VERSION, ... from the environment.
    client: StripeClient = StripeClient.fromEnv()

    do {
        customer: StripeResponse = client.createCustomer("ada@example.com", "Ada Lovelace")?
        print(f"created {customer.id()} (request {customer.requestId})")

        intent: StripeResponse = client.createPaymentIntent(2599, "eur", "Order #42")?
        print(f"client secret for the browser: {intent.clientSecret()}")
    } catch err {
        print(f"Stripe failed: {err}")
    }
}
```

`err` prints like
`StripeCardError: Your card was declined. [status=402 type=card_error code=card_declined decline_code=insufficient_funds request_id=req_...]`.

## Configuration

`StripeConfig` holds the client settings. The constructor keeps the 0.x
positional order; the other settings are named arguments or public fields:

```lammergeier
cfg: StripeConfig = StripeConfig("sk_test_...", "https://api.stripe.com/v1", "2024-06-20", 20000, maxRetries=3)
cfg.retryBaseDelayMs = 250
cfg.appInfo = "billing-service/4.2"
client: StripeClient = StripeClient(cfg)
```

| Field | Environment (`StripeConfig.fromEnv()`) | Default | Meaning |
|---|---|---|---|
| `secretKey` | `STRIPE_SECRET_KEY` | `""` | Secret (`sk_...`) or restricted (`rk_...`) key. Publishable keys are rejected. |
| `baseUrl` | `STRIPE_BASE_URL` | `https://api.stripe.com/v1` | API root including `/v1`; point it at a mock in tests. |
| `apiVersion` | `STRIPE_API_VERSION` | `""` (account default) | Sent as `Stripe-Version`. Pin it so upgrades are deliberate. |
| `timeoutMs` | `STRIPE_TIMEOUT_MS` | `30000` | Per-attempt timeout. |
| `maxRetries` | `STRIPE_MAX_RETRIES` | `2` | Retries after the first attempt (`0` disables them). |
| `stripeAccount` | `STRIPE_ACCOUNT` | `""` | `Stripe-Account` header for Stripe Connect. |
| `retryBaseDelayMs` / `retryMaxDelayMs` | | `500` / `5000` | Backoff: `base * 2^(n-1)`, capped, jittered into `[50%, 100%]`. |
| `autoIdempotencyKeys` | | `true` | Give every POST without a key a generated `Idempotency-Key`. |
| `appInfo` | | `""` | Appended to the `User-Agent`. |

Unset or malformed optional variables keep their defaults.
`cfg.validate()` (run before every request) returns a `StripeConfigError`
for a missing or publishable key, a non-HTTP base URL or negative retry
settings; `cfg.isTestMode()` is true for `sk_test_` / `rk_test_` keys.

### Per-request options

`StripeRequestOptions` overrides the client for one call:

```lammergeier
opts: StripeRequestOptions = StripeRequestOptions("order-42-capture")   # Idempotency-Key
opts.account("acct_123").retries(0).expandField("latest_invoice")
opts.timeoutMs = 5000
opts.apiVersion = "2025-03-31.basil"
res: StripeResponse = client.post("/subscriptions", params, opts)?
```

Typed methods that create objects take an `idempotencyKey` argument
directly (`client.createPrice(opts, "price-pro-v3")`).

## API reference

All classes are imported from `@lam/stripe`.

### `StripeClient`

| Method | Returns | Endpoint |
|---|---|---|
| `StripeClient(cfg)`, `StripeClient.fromEnv()` | `StripeClient` | |
| `setIdempotencyKey(key)`, `clearIdempotencyKey()` | | sticky key for following POSTs (0.x behaviour) |
| `request(method, path, params = {}, opts = None)` | `Result[StripeResponse]` | any; `params` nested, query string for GET/DELETE, form body for POST |
| `get` / `post` / `delete(path, params = {}, opts = None)` | `Result[StripeResponse]` | any |
| `postForm(path, fields: dict[str, str], opts = None)` | `Result[StripeResponse]` | flat bracket keys used verbatim |
| `rawGet(path)`, `rawPostForm(path, fields)`, `rawDelete(path)` | `Result[StripeResponse]` | 0.x escape hatches |
| `list(path, params = {}, opts = None)` | `Result[StripeList]` | one page |
| `pager(path, params = {}, opts = None)` | `StripePager` | every page |
| `listAll(path, params = {}, maxItems = 0, opts = None)` | `Result[list[StripeObject]]` | every object |
| `createCustomer(email, name = "")`, `createCustomerWithOptions(opts, idempotencyKey = "")` | `Result[StripeResponse]` | `POST /customers` |
| `retrieveCustomer(id, expand = [])`, `updateCustomer(id, params, idempotencyKey = "")`, `deleteCustomer(id)`, `listCustomers(params = {})` | | `/customers/:id` |
| `createPaymentIntent(amount, currency, description = "")`, `createPaymentIntentWithOptions(opts, idempotencyKey = "")`, `retrievePaymentIntent(id)` | | `/payment_intents` |
| `createCheckoutSession(successUrl, cancelUrl, mode = "payment", priceId = "", quantity = 1)`, `createCheckoutSessionWithOptions(opts, idempotencyKey = "")`, `retrieveCheckoutSession(id, expand = [])` | | `/checkout/sessions` |
| `createPortalSession(customerId, returnUrl, configurationId = "", locale = "")` | | `POST /billing_portal/sessions` |
| `createProduct(name, metadata = {}, idempotencyKey = "")`, `createProductWithOptions(opts, idempotencyKey = "")`, `retrieveProduct(id)` | | `/products` |
| `createPrice(opts, idempotencyKey = "")`, `retrievePrice(id, expand = [])` | | `/prices` |
| `listPricesByLookupKeys(keys, activeOnly = true)` | `Result[StripeList]` | `GET /prices?lookup_keys[]=...` |
| `findPriceByLookupKey(key)` | `Result[StripeObject]` (`None` when absent) | |
| `listMeters(status = "active")` | `Result[list[StripeObject]]` (all pages) | `GET /billing/meters` |
| `findMeterByEventName(eventName)` | `Result[StripeObject]` (`None` when absent) | |
| `createMeter(opts, idempotencyKey = "")` | | `POST /billing/meters` |
| `createMeterEvent(eventName, customerId, value, identifier = "", timestamp = 0)`, `createMeterEventWithOptions(opts, idempotencyKey = "")` | | `POST /billing/meter_events` |
| `retrieveSubscription(id, expand = [])`, `listSubscriptions(params = {})` | | `/subscriptions` |
| `updateSubscription(id, update, idempotencyKey = "")` | | `POST /subscriptions/:id` |
| `cancelSubscriptionAtPeriodEnd(id)`, `reactivateSubscription(id)` | | `cancel_at_period_end=true/false` |
| `cancelSubscription(id, invoiceNow = false, prorate = false)` | | `DELETE /subscriptions/:id` |
| `resumeSubscription(id, prorationBehavior = "", billingCycleAnchor = "")` | | `POST /subscriptions/:id/resume` (paused subscriptions) |
| `listInvoices(customerId = "", status = "", limit = 0)`, `retrieveInvoice(id, expand = [])` | | `/invoices` |
| `retrieveEvent(id)` | `Result[StripeEvent]` | `GET /events/:id` |
| `listEvents(params = {})`, `retrieveBalance()` | | `/events`, `/balance` |

Fields: `cfg`, `requestCount` (attempts sent, retries included),
`lastRequestId`. Ids are validated (empty ids fail with
`StripeValidationError` before sending) and escaped as one path segment.
A client can be reused for any number of sequential calls; its counters are
informational and not synchronised, so give concurrent workers their own
client.

### Responses and objects

- `StripeObject(data: json)`: null-safe accessors over a decoded object.
  Paths are dotted, list indexes are numbers (`"items.data.0.price.id"`). A
  missing value is `""`, `0`, `false`, an empty list or JSON null.
  `getStr(path)`, `getInt(path)`, `getBool(path)`, `getJson(path)`,
  `getLen(path)`, `getList(path) -> list[StripeObject]`,
  `getObject(path)`, `has(path)`, `metadata(key)` (keys may contain dots),
  `field(name)`, `id()`, `objectType()`, `url()`, `clientSecret()`,
  `toJson()`. An expanded object read with `getStr` returns its `id`, so
  `res.getStr("customer")` works with and without `expand`.
- `StripeResponse(status, body, transportError = "", headers = {})` extends
  `StripeObject`: `status`, `body`, `headers`, `requestId`,
  `idempotencyKey`, `attempts`, `ok()`, `json()`, `header(name)`.
- `StripeList(response)`: `data: list[StripeObject]`, `hasMore`, `url`,
  `nextPage` (search), `response`, `size()`, `isEmpty()`, `first()`,
  `firstId()`, `lastId()`, `ids()`.
- `StripePager(client, path, params = {}, opts = None)`: `hasNext()`,
  `next() -> Result[StripeList]`, `pages`. Continues with `starting_after`
  (`ending_before` when the first request used it) or with the search
  `page` token.
- `StripeEvent(raw: json)` / `StripeEvent.parse(payload)`: `id`, `type`,
  `created`, `livemode`, `apiVersion`, `account`, `pendingWebhooks`,
  `requestId`, `requestIdempotencyKey`, `object` (`data.object` as `json`),
  `previousAttributes`, `raw`; `dataObject()`, `objectId()`,
  `objectType()`, `objectStr/Int/Bool(path)`, `isType("invoice.*")`,
  `wasUpdated(field)`.

### Request builders

Each has public fields, chainable setters, `validate() -> Result[bool]`
(run by the client before sending) and `fields() -> dict[str, str]`.

| Class | Constructor | Notable members |
|---|---|---|
| `StripeCustomerOptions` | `(email, name = "")` | `phone`, `description`, `setMetadata(k, v)` |
| `StripePaymentIntentOptions` | `(amount, currency)` | `description`, `customerId`, `receiptEmail`, `captureMethod`, `automaticPaymentMethods`, `setMetadata` |
| `StripeCheckoutSessionOptions` | `(successUrl, cancelUrl, priceId = "", quantity = 1)` | `mode` (`payment`/`subscription`/`setup`), `customerId` or `customerEmail`, `clientReferenceId`, `allowPromotionCodes`, `locale`, `trialPeriodDays`, `setMetadata`, `setSubscriptionMetadata`, `addLineItem(priceId, quantity = 1)`; quantity `0` omits it (metered prices) |
| `StripeProductOptions` | `(name)` | `description`, `active`, `taxCode`, `unitLabel`, `statementDescriptor`, `setMetadata` |
| `StripePriceOptions` | `(currency, productId)` | `unitAmount`, `unitAmountDecimal`, `nickname`, `lookupKey`, `transferLookupKey`, `recurring(interval, usageType = "licensed", meterId = "")`, `recurringIntervalCount`, `tiersMode` (`graduated`/`volume`), `addTier(upTo, unitAmountDecimal, flatAmountDecimal = "")` (`upTo <= 0` is the last, open-ended tier), `taxBehavior`, `setMetadata` |
| `StripeSubscriptionUpdate` | `(prorationBehavior = "create_prorations")` | `updateItem(itemId, priceId, quantity = 0)`, `deleteItem(itemId)`, `addItem(priceId, quantity = 0)`, `cancelAtPeriodEnd` (`"true"`/`"false"`), `setMetadata` |
| `StripeMeterOptions` | `(displayName, eventName)` | `aggregation` (`sum`/`count`/`last`), `customerPayloadKey` (`stripe_customer_id`), `valuePayloadKey` (`value`), `eventTimeWindow` |
| `StripeMeterEventOptions` | `(eventName, customerId, value)` | `identifier` (also the default `Idempotency-Key`), `timestamp`, `setPayload(k, v)`, payload key names |
| `StripeRequestOptions` | `(idempotencyKey = "")` | `stripeAccount`/`account()`, `apiVersion`, `timeoutMs`, `maxRetries`/`retries()`, `expand`/`expandField()`, `headers`/`header()` |

### `StripeWebhook`

| Method | Returns |
|---|---|
| `verify(payload, header, secret, toleranceSeconds, nowUnix)` | `Result[StripeEvent]` |
| `verifyAny(payload, header, secrets: list[str], toleranceSeconds, nowUnix)` | `Result[StripeEvent]` |
| `verifySignature(...)`, `verifySignatureAny(...)` | `Result[bool]` (signature only) |
| `constructEvent(payload, header, secret, toleranceSeconds = 300)` | `Result[StripeEvent]` at the current time; `secret` may list several secrets |
| `parseHeader(header)` | `Result[StripeSignatureHeader]` (`timestamp`, `signatures`) |
| `splitSecrets(text)` | `list[str]` from `"whsec_new,whsec_old"` (commas, spaces, new lines) |
| `sign(payload, secret, timestamp)` | hex HMAC-SHA256 of `"<timestamp>.<payload>"` |
| `testHeader(payload, secret, timestamp)` | `"t=<timestamp>,v1=<signature>"` for tests |
| `defaultTolerance()` | `300` |

`toleranceSeconds <= 0` disables the timestamp check; otherwise a
timestamp more than `toleranceSeconds` away from `nowUnix` in either
direction is rejected. Failures are `StripeSignatureError`; a correctly
signed body that is not an event is a `StripeValidationError`.

### `StripeError`

`StripeError(kind, message, status = 0, cause = None)` extends
`lamerrors.Error`, so `err.kind` / `err.message` work in
`do { } catch err` blocks. Fields: `status`, `type`, `code`, `declineCode`,
`param`, `docUrl`, `requestLogUrl`, `requestId`, `idempotencyKey`,
`attempts`, `retryable`, `body`, `raw` (the decoded `error` object).
`StripeError.of(err)` returns the `StripeError` inside a `catch` binding or
`r.error` (`None` for other errors); `isinstance(err, StripeError)` also
narrows. Helpers: `isCardError()`, `isRateLimit()`, `isConnectionError()`.

| `kind` | When |
|---|---|
| `StripeCardError` | `error.type == "card_error"` or HTTP 402 |
| `StripeInvalidRequestError` | `invalid_request_error`, 400, 404 |
| `StripeAuthenticationError` | 401 |
| `StripePermissionError` | 403 |
| `StripeRateLimitError` | 429 (after retries) |
| `StripeIdempotencyError` | `idempotency_error` (a key reused with other parameters) |
| `StripeApiError` | other responses (5xx after retries) |
| `StripeConnectionError` | no response: DNS, refused connection, TLS, timeout (after retries) |
| `StripeConfigError` | invalid `StripeConfig`; nothing was sent |
| `StripeValidationError` | invalid arguments caught locally (`param` names the field); nothing was sent |
| `StripeSignatureError` | webhook signature verification |

### `Stripe` statics

`version()`, `userAgent()`, `encodeForm(fields)`, `encodeParams(params)`
(nested: dicts become `key[sub]`, lists of scalars `key[]`, lists of dicts
`key[0][sub]`, an empty list `key=`, `None` is skipped, booleans are
`true`/`false`, `json` values are walked), `decodeForm(body)`,
`formValue(body, key)`, `escapeId(id)`, `normalizeCurrency(currency)`,
`addMetadata(fields, metadata)`, `validateAmount(amount)`,
`validateCurrency(currency)`, `errorMessage(response)`,
`shouldRetry(status, shouldRetryHeader = "")`,
`retryDelayMs(attempt, baseMs, maxMs, retryAfterSeconds = 0, jitter = 1.0)`.

## Examples

### Subscription checkout with metered usage

One-time catalog setup: a Billing Meter that sums usage, a product, a
licensed base price and a graduated metered price with a free allowance.
Lookup keys make the setup idempotent.

```lammergeier
from @lam/stripe import StripeClient, StripeObject, StripeResponse, StripeMeterOptions, StripePriceOptions
from lamerrors import Result

func ensurePrice(client: StripeClient, lookupKey: str, opts: StripePriceOptions) -> Result[str] {
    existing: StripeObject = client.findPriceByLookupKey(lookupKey)?
    if existing != None {
        return Result.Ok(existing.id())
    }
    opts.lookupKey = lookupKey
    created: StripeResponse = client.createPrice(opts, f"price-{lookupKey}")?
    return Result.Ok(created.id())
}

func setupCatalog(client: StripeClient) -> Result[list[str]] {
    meter: StripeObject = client.findMeterByEventName("storage_gib_hours")?
    meterId: str = ""
    if meter != None {
        meterId = meter.id()
    } else {
        created: StripeResponse = client.createMeter(StripeMeterOptions("Storage (GiB-hours)", "storage_gib_hours"), "meter-storage")?
        meterId = created.id()
    }
    product: StripeResponse = client.createProduct("Pro plan", {"plan": "pro"}, "product-pro")?

    base: StripePriceOptions = StripePriceOptions("eur", product.id())
    base.unitAmount = 4900
    base.recurring("month")
    baseId: str = ensurePrice(client, "pro_base_v1", base)?

    storage: StripePriceOptions = StripePriceOptions("eur", product.id())
    storage.tiersMode = "graduated"
    storage.recurring("month", "metered", meterId)
    storage.addTier(1000, "0").addTier(0, "0.25")   # first 1000 free, then 0.25 cents
    storageId: str = ensurePrice(client, "pro_storage_v1", storage)?
    return Result.Ok([baseId, storageId])
}
```

Checkout for a customer, with the tenant id on the session and the
subscription:

```lammergeier
from @lam/stripe import StripeClient, StripeResponse, StripeCheckoutSessionOptions, StripeCustomerOptions
from lamerrors import Result

func startCheckout(client: StripeClient, tenantId: str, email: str, basePrice: str, meteredPrice: str) -> Result[str] {
    customerOpts: StripeCustomerOptions = StripeCustomerOptions(email)
    customerOpts.setMetadata("tenant_id", tenantId)
    customer: StripeResponse = client.createCustomerWithOptions(customerOpts, f"customer-{tenantId}")?

    opts: StripeCheckoutSessionOptions = StripeCheckoutSessionOptions("https://app.example.com/billing?done=1", "https://app.example.com/billing")
    opts.mode = "subscription"
    opts.customerId = customer.id()
    opts.clientReferenceId = tenantId
    opts.setMetadata("tenant_id", tenantId)
    opts.setSubscriptionMetadata("tenant_id", tenantId)
    opts.addLineItem(basePrice, 1)
    opts.addLineItem(meteredPrice, 0)    # metered prices take no quantity
    session: StripeResponse = client.createCheckoutSessionWithOptions(opts)?
    return Result.Ok(session.url())     # redirect the browser here
}
```

Report usage as meter events. A stable `identifier` makes a replayed report
count once; it is also sent as the `Idempotency-Key`:

```lammergeier
from @lam/stripe import StripeClient, StripeError, StripeMeterEventOptions, StripeResponse
from lamerrors import Result

func reportUsage(client: StripeClient, tenantId: str, customerId: str, periodStart: int, total: int, alreadyReported: int, nowUnix: int) -> Result[int] {
    delta: int = total - alreadyReported
    if delta <= 0 {
        return Result.Ok(0)
    }
    usage: StripeMeterEventOptions = StripeMeterEventOptions("storage_gib_hours", customerId, delta)
    usage.identifier = f"{tenantId}:storage:{periodStart}:{total}"
    usage.timestamp = nowUnix
    sent: Result[StripeResponse] = client.createMeterEventWithOptions(usage)
    if not sent.ok() and StripeError.of(sent.error).code != "meter_event_duplicate_identifier" {
        return Result.Err(sent.error)
    }
    return Result.Ok(delta)
}
```

Plan changes swap subscription items with an explicit proration
behaviour:

```lammergeier
func moveToTeam(client: StripeClient, subscriptionId: str, teamPrices: dict[str, str]) -> Result[StripeResponse] {
    sub: StripeResponse = client.retrieveSubscription(subscriptionId, ["items.data.price"])?
    update: StripeSubscriptionUpdate = StripeSubscriptionUpdate("create_prorations")
    for item in sub.getList("items.data") {
        lookupKey: str = item.getStr("price.lookup_key")
        if lookupKey in teamPrices {
            update.updateItem(item.id(), teamPrices[lookupKey])
        } else {
            update.deleteItem(item.id())
        }
    }
    update.setMetadata("plan", "team")
    return client.updateSubscription(subscriptionId, update, f"plan-{subscriptionId}-team")
}
```

`client.cancelSubscriptionAtPeriodEnd(id)` keeps access until the period
ends, `client.reactivateSubscription(id)` undoes it,
`client.cancelSubscription(id, invoiceNow=true)` cancels now and
`client.resumeSubscription(id)` resumes a paused subscription.

### Webhook endpoint with verification

Verify the exact raw body, deduplicate by event id, then dispatch. The
handler below takes the raw body, the `Stripe-Signature` header and the
current time from whatever HTTP server you use:

```lammergeier
from @lam/stripe import StripeWebhook, StripeEvent
from lamenv import Env
from lamerrors import Result

func handleStripeWebhook(rawBody: str, signatureHeader: str, nowUnix: int, seen: list[str]) -> Result[str] {
    # "whsec_new,whsec_old" while a signing secret is being rolled.
    secrets: list[str] = StripeWebhook.splitSecrets(Env.getOr("STRIPE_WEBHOOK_SECRET", ""))
    event: StripeEvent = StripeWebhook.verifyAny(rawBody, signatureHeader, secrets, 300, nowUnix)?
    if event.id in seen {
        return Result.Ok("duplicate")      # Stripe retries deliveries
    }
    seen.append(event.id)
    match event.type {
        case "checkout.session.completed" {
            tenantId: str = event.objectStr("client_reference_id")
            subscriptionId: str = event.objectStr("subscription")
            return Result.Ok(f"subscribed {tenantId} {subscriptionId}")
        }
        case "customer.subscription.updated" | "customer.subscription.deleted" {
            return Result.Ok(f"subscription {event.objectId()} is {event.objectStr('status')}")
        }
        case t if event.isType("invoice.*") {
            return Result.Ok(f"{t} {event.objectId()} due {event.objectInt('amount_due')}")
        }
        case _ {
            return Result.Ok("ignored")
        }
    }
}
```

Answer `2xx` quickly and do slow work afterwards; answer `400` for a
`StripeSignatureError`. When the payload must not be trusted beyond its id,
re-fetch it: `fresh: StripeEvent = client.retrieveEvent(event.id)?`.

In tests, sign payloads yourself:

```lammergeier
header: str = StripeWebhook.testHeader(payload, "whsec_test", 1700000000)
event: StripeEvent = StripeWebhook.verify(payload, header, "whsec_test", 300, 1700000000).unwrap()
```

### Customer portal

```lammergeier
func portalUrl(client: StripeClient, customerId: str) -> Result[str] {
    session: StripeResponse = client.createPortalSession(customerId, "https://app.example.com/billing")?
    return Result.Ok(session.url())
}
```

### Pagination

```lammergeier
func printCustomers(client: StripeClient) -> Result[int] {
    pages: StripePager = client.pager("/customers", {"limit": 100, "created": {"gte": 1700000000}})
    count: int = 0
    while pages.hasNext() {
        page: StripeList = pages.next()?
        for customer in page.data {
            print(customer.id(), customer.getStr("email"))
            count += 1
        }
    }
    return Result.Ok(count)
}

# Or collect everything (bounded by maxItems):
func openInvoices(client: StripeClient) -> Result[list[StripeObject]] {
    return client.listAll("/invoices", {"status": "open", "limit": 100}, maxItems=1000)
}
```

### Errors and retries

```lammergeier
func charge(client: StripeClient, customerId: str, orderId: str) -> str {
    opts: StripePaymentIntentOptions = StripePaymentIntentOptions(2599, "eur")
    opts.customerId = customerId
    r: Result[StripeResponse] = client.createPaymentIntentWithOptions(opts, f"order-{orderId}")
    if r.ok() {
        return r.unwrap().id()
    }
    err: StripeError = StripeError.of(r.error)
    if err.isCardError() {
        return f"declined: {err.declineCode}"          # show to the customer
    }
    if err.kind == "StripeConnectionError" or err.kind == "StripeApiError" {
        # Already retried err.attempts times with the same idempotency key;
        # safe to retry later with the same key.
        return f"try again later (request {err.requestId})"
    }
    return f"bug: {err}"                                 # invalid request, auth, ...
}
```

Retries happen inside the client: network errors, 409, 429 and 5xx are
retried `maxRetries` times with exponential backoff and jitter, honouring
`Retry-After` and `Stripe-Should-Retry`. Every attempt of one call reuses
the same `Idempotency-Key`, so Stripe applies a POST at most once. A POST
without any key (`autoIdempotencyKeys = false` and none given) is never
retried.

### Testing against a mock

Point `baseUrl` at a local server. `Stripe.decodeForm` / `formValue` read
the form bodies the client sends:

```lammergeier
from @lam/stripe import StripeClient, StripeConfig, StripeResponse, Stripe
from lamhttp import Http, HttpServer

class Seen {
    static body: str = ""
}

func fakeStripe(_method: str, _path: str, body: str) -> str {
    Seen.body = body
    return "{\"id\":\"cus_test\",\"object\":\"customer\"}"
}

func main() {
    srv: HttpServer = Http.serve(39281, fakeStripe).unwrap()
    cfg: StripeConfig = StripeConfig("sk_test_mock", "http://127.0.0.1:39281/v1", maxRetries=0)
    client: StripeClient = StripeClient(cfg)
    customer: StripeResponse = client.createCustomer("ada@example.com").unwrap()
    print(customer.id(), Stripe.formValue(Seen.body, "email"))   # cus_test ada@example.com
    srv.close().unwrap()
}
```

`tests/stripe_mock.lam` in this repository is a fuller mock (headers,
status codes, delays, recorded requests) you can copy.
[stripe-mock](https://github.com/stripe/stripe-mock) also works:
`StripeConfig("sk_test_123", "http://localhost:12111/v1")`.

## Security notes

- Keep secret keys out of source control and logs; read them from the
  environment or a secret store. Prefer
  [restricted keys](https://docs.stripe.com/keys#limit-access) (`rk_...`)
  with only the permissions the service needs. `StripeError` never
  contains the key.
- Webhooks: verify the raw request body before parsing it, keep the
  default 300 s tolerance (replay protection), compare with the provided
  constant-time check, and deduplicate by event id because Stripe delivers
  at least once. Use `verifyAny` with both secrets while rolling a signing
  secret.
- Idempotency keys should identify the business operation
  (`order-42-capture`), not the attempt, so a retried job cannot charge
  twice. Keys are retained by Stripe for 24 hours.
- Pin `apiVersion` so a Stripe API upgrade cannot change response shapes
  under a running service.
- `baseUrl` accepts `http://` for local mocks; production must use the
  default HTTPS endpoint.
- Amounts are integers in the currency's minor unit; never use floats for
  money (`unitAmountDecimal` / tier amounts are decimal strings).

## Testing

```sh
python3 tests/run_lamstripe_tests.py --verbose          # or: lamc lib run test
python3 tests/run_lamstripe_tests.py webhook retries    # name filters
```

The runner uses `lamc` from `PATH` (2.1.0 or newer), copies the package
into a temporary `extlibs/@lam/stripe` and compiles every `tests/test_*.lam`
against it, exactly as an installed dependency. Offline tests use
ephemeral local mock servers and never see your `STRIPE_*` variables.

The live smoke test only reads (balance, one customer page, a missing
customer) and needs an explicit opt-in and a test-mode key:

```sh
LAMSTRIPE_LIVE_TESTS=1 STRIPE_SECRET_KEY=sk_test_... python3 tests/run_lamstripe_tests.py --live
```

## Upgrading from lamstripe 0.x

- `from lamstripe import ...` becomes `from @lam/stripe import ...`.
- Results are typed: `res: StripeResponse = client.rawGet(path)?` replaces
  `result.Value.(*StripeResponse)` casts and `Result`-to-`json` helpers;
  `client.rawGet(path).unwrap().json()` gives the body.
- Errors are `StripeError` with specific kinds; a decline is
  `StripeCardError` instead of `StripeApiError`, a transport failure
  `StripeConnectionError` instead of `HttpError`.
- Retries and generated idempotency keys are on by default.
- Environment variable names are unchanged.

## Compiler notes

Written against the released `lamc` 2.1.1. Contributors should know these
compiler limitations, which the library code avoids:

- A local variable named like a Go package used by the program (`http`,
  `strings`, ...) is treated as the package: `http.header(...)` is emitted
  unmangled. Use another name.
- A `match` class pattern (`case StripeError() as se`) does not accept a
  class re-exported through a package `__init__.lam`; use
  `isinstance(err, StripeError)` or `StripeError.of(err)`.
- An inline list comprehension used as an operand (`[...][1:]`,
  `[...].reduce(...)`) loses its element type; assign it to a typed local
  first.
- `list == list` literals do not compile; compare joined strings or loop.
- `lamc fmt` rewrites double-backtick spans inside `//` comments of `go!`
  blocks into typographic quotes, so it is not run on this repository.

## License

Apache License 2.0; see [LICENSE](LICENSE) and [NOTICE](NOTICE).

Stripe is a trademark of Stripe, Inc. `@lam/stripe` is an unofficial
library and is not affiliated with or endorsed by Stripe, Inc.

Part of the Lammergeier ecosystem:
[lammergeier-lang](https://github.com/thallium-solutions/lammergeier-lang) ·
[lammergeier-lang.dev](https://lammergeier-lang.dev)
