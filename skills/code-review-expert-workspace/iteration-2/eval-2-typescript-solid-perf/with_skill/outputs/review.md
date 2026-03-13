## Code Review Summary

**Files reviewed**: 1 file, 242 lines added (new file)
**Overall assessment**: REQUEST_CHANGES

### Top Issues

The most critical things to address before merging:

1. **SQL injection in `getOrdersByStatus`** -- User-supplied `status` is interpolated directly into the SQL string, allowing arbitrary query execution.
2. **Race condition on inventory: check-then-reserve without atomicity** -- Concurrent `createOrder` calls can pass the stock check simultaneously and oversell inventory.
3. **No transaction or rollback in `createOrder`** -- Payment is charged via Stripe before inventory is reserved; if reservation fails, the customer is charged with no order fulfillment and no automatic refund.
4. **Missing authorization/ownership checks** -- Any caller can read, cancel, or view orders belonging to other users (IDOR vulnerability).
5. **Floating-point arithmetic for currency** -- Multiplying dollar amounts by fractional discounts and by 100 for Stripe produces rounding errors on real transactions.

---

## Findings

### P0 - Critical

1. **[test_diff.ts:231-234] SQL injection in `getOrdersByStatus`**
   - The query uses string interpolation (`'${status}'`) to embed the `status` parameter directly into SQL. Despite also passing `[status]` as a parameterized argument, the interpolated value is what the database executes. An attacker passing `'; DROP TABLE orders; --` as the status can execute arbitrary SQL.
   - **Fix**: Replace the interpolated string with a parameterized placeholder:
     ```ts
     const result = await this.db.query(
       'SELECT * FROM orders WHERE status = $1',
       [status]
     );
     ```

2. **[test_diff.ts:44-51, 83-88] TOCTOU race condition: inventory check then reserve**
   - The stock availability check (lines 44-51) and inventory reservation (lines 83-88) are separated by payment processing and a database insert. Two concurrent orders for the same product can both pass the availability check before either reserves stock, resulting in overselling.
   - **Fix**: Use an atomic "reserve" operation that checks and decrements in a single step (ideally with a distributed lock or database-level atomic decrement), or perform the check-and-reserve inside a serializable transaction on the inventory service.

3. **[test_diff.ts:67-88] No transaction or compensation in `createOrder`**
   - The method charges payment (line 67), inserts the order (line 74), then reserves inventory (lines 83-88) as independent steps. If the inventory reservation HTTP call fails (network error, insufficient stock at reserve time), the payment has already been captured and the order row exists, but the order cannot be fulfilled. There is no rollback or compensation logic.
   - **Fix**: Wrap the critical section in a saga or compensation pattern: if inventory reservation fails, automatically cancel the Stripe payment intent and mark the order as failed. Alternatively, use Stripe payment intents in a two-phase approach (authorize first, capture after reservation succeeds).

### P1 - High

4. **[test_diff.ts:110-124, 156-187] Missing authorization and ownership checks (IDOR)**
   - `getOrder`, `getUserOrders`, and `cancelOrder` accept IDs without verifying that the requesting user owns the resource. Any authenticated user (or unauthenticated caller, since there is no auth middleware visible) can read or cancel another user's orders.
   - **Fix**: Accept the authenticated user's ID as a parameter or from the request context, and add a `WHERE user_id = $2` clause (or an ownership check after retrieval) to all order-access methods.

5. **[test_diff.ts:44-51, 55-59, 139-148] N+1 HTTP calls to inventory service (multiple locations)**
   - `createOrder` makes two sequential loops of HTTP calls: one per item for stock checks (lines 44-51) and one per item for price lookups (lines 55-59). `getUserOrders` has a nested loop fetching product details per item per order (lines 139-148). For an order with 10 items, this is 20+ sequential HTTP round-trips; for a user with 5 orders of 10 items each, it is 50+ round-trips.
   - **Fix**: Batch these into single requests. Request the inventory service to accept a list of product IDs and return stock/price data in one call. For `getUserOrders`, fetch all product details in a single batch call or pre-join at the database level.

6. **[test_diff.ts:54-64, 67-69] Floating-point arithmetic for currency**
   - Discount calculation uses fractional multipliers (`total * 0.15`, `total * 0.10`) and the Stripe charge multiplies by 100 (`total * 100`). Floating-point math produces rounding errors: e.g., `19.99 * 0.15 = 2.9985000000000004`. This leads to inconsistent charges and accounting discrepancies.
   - **Fix**: Use integer cents throughout (store prices in cents, compute discounts on cent values, round explicitly with `Math.round`) or use a decimal library like `decimal.js`.

### P2 - Medium

7. **[test_diff.ts:30-40] SRP violation: OrderService is a god class**
   - This single class handles order CRUD, payment processing (Stripe), inventory management (HTTP), discount/loyalty logic, caching (Redis), notification dispatch, and analytics/stats. It has at least six distinct reasons to change.
   - **Fix**: Extract responsibilities into focused services: `PaymentService`, `InventoryClient`, `DiscountCalculator`, `NotificationService`. `OrderService` should orchestrate these via injected dependencies.

8. **[test_diff.ts:35-39] No dependency injection (DIP violation)**
   - The constructor directly instantiates `Pool`, `Redis`, and reads `process.env` values. The module-level `stripe` and `logger` are also hardcoded. This makes the class impossible to unit test without mocking module internals and prevents swapping implementations.
   - **Fix**: Accept dependencies through the constructor (`constructor(db: Pool, redis: Redis, stripe: Stripe, ...)`), or better yet, accept interfaces rather than concrete types.

9. **[test_diff.ts:117-118, 195] Missing null checks on database query results**
   - `getOrder` accesses `result.rows[0]` without checking if the query returned any rows. If the order ID does not exist, this returns `undefined`, which is then cached and returned to the caller. `calculateDiscount` accesses `userResult.rows[0].loyalty_points` which will throw a TypeError if the user does not exist.
   - **Fix**: Check `result.rows.length > 0` and throw a meaningful `NotFoundError` or return `null` with appropriate typing (`Promise<Order | null>`).

10. **[test_diff.ts:101-103] Swallowed notification exception**
    - The catch block logs `'Failed to send notification'` without including the error object. The error variable `e` is captured but never used, losing all diagnostic information (HTTP status, timeout, network error details).
    - **Fix**: Log the error: `logger.warn('Failed to send notification', { error: e, orderId: order.id, userId })`. Consider also emitting a metric for monitoring notification failure rates.

11. **[test_diff.ts:189-205] Discount logic uses hardcoded thresholds and is not extensible (OCP violation)**
    - Discount tiers are hardcoded as magic numbers (10000, 5000, 1000 points and 15%, 10%, 5% rates). Adding a new tier or changing thresholds requires modifying this method.
    - **Fix**: Extract discount tiers into a configuration object or database table. Consider a strategy pattern if discount logic becomes more complex (e.g., combining loyalty + promo codes).

12. **[test_diff.ts:140, 175] Unsafe JSON.parse on items from database**
    - `JSON.parse(order.items)` is called in `getUserOrders` and `cancelOrder` without error handling. If the stored JSON is malformed (data migration issue, encoding bug), this throws an unhandled exception that will crash the request.
    - **Fix**: Wrap in try-catch, or validate the shape after parsing. Consider storing order items in a normalized table (`order_items`) rather than as a JSON string to avoid parsing entirely.

### P3 - Low

13. **[test_diff.ts:159] `==` instead of `===` for string comparison**
    - `order.status == 'shipped'` uses loose equality. While both operands are strings so the behavior is identical to `===`, strict equality is the TypeScript convention and avoids any ambiguity.
    - **Fix**: Change to `order.status === 'shipped' || order.status === 'delivered'`.

14. **[test_diff.ts:207] `getOrderStats` returns `Promise<any>`**
    - The `any` return type defeats TypeScript's type checking for all consumers of this method. The shape of the stats object is well-known from the SQL query.
    - **Fix**: Define an `OrderStats` interface with `totalOrders`, `totalRevenue`, `avgOrderValue`, and `cancelledCount` fields, and use it as the return type.

---

## Removal/Iteration Plan

### Safe to Remove Now

| Field | Details |
|-------|---------|
| **Item** | `exportOrders` method (lines 239-241) |
| **Location** | `test_diff.ts:239-241` |
| **Rationale** | Throws `Not implemented` -- dead code that adds noise to the API surface |
| **Impact** | None -- method is non-functional |
| **Steps** | Remove method. If a bulk export feature is planned, track it as a separate ticket. |

### Defer Removal (Plan Required)

| Field | Details |
|-------|---------|
| **Item** | `getOrdersByStatus` legacy method (lines 230-236) |
| **Location** | `test_diff.ts:230-236` |
| **Why defer** | Comment says "kept for backward compatibility with v1 API" -- there may be active consumers. |
| **Preconditions** | Verify v1 API traffic is zero via access logs or API gateway metrics. |
| **Immediate action** | **Fix the SQL injection (Finding #1) before anything else.** This method is actively dangerous. |
| **Timeline** | Fix SQL injection now. Deprecate the v1 endpoint and remove this method once traffic is confirmed at zero. |

---

## Additional Suggestions

- **Add request timeouts to all `axios` calls.** Currently, if the inventory or notification service hangs, `createOrder` blocks indefinitely. Use `axios.create({ timeout: 5000 })` with a shared client.
- **Add idempotency keys to `createOrder`.** If a client retries a failed request, the current implementation will create a duplicate order and double-charge the customer.
- **Consider pagination for `getUserOrders`.** Loading all orders for a user into memory (and caching them) will degrade as order history grows.
- **Add structured logging.** The current `logger.info` on line 105 embeds the total in the string, making it hard to query. Use structured fields: `logger.info('Order created', { orderId: order.id, userId, total })`.

---

## Next Steps

I found 14 issues (P0: 3, P1: 3, P2: 6, P3: 2).

**How would you like to proceed?**

1. **Fix all** - I'll implement all suggested fixes
2. **Fix P0/P1 only** - Address critical and high priority issues
3. **Fix specific items** - Tell me which issues to fix
4. **No changes** - Review complete, no implementation needed

Please choose an option or provide specific instructions.
