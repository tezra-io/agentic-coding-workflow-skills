## Code Review Summary

**Files reviewed**: 1 file, 245 lines changed (all new code)
**Overall assessment**: REQUEST_CHANGES

### Top Issues

The most critical things to address before merging:

1. **Race conditions on shared map and counter (multiple handlers)** -- `CreateSession`, `cleanupLoop`, `UpdateSession`, `ImportSessions`, and `GetStats` access `sm.sessions` and `activeCount` without holding the mutex, which will cause panics and data corruption under concurrent HTTP requests.
2. **Path traversal in ExportSessions / ImportSessions** -- User-controlled `file` query parameter is concatenated into a file path with no sanitization, allowing `../../etc/passwd`-style attacks.
3. **Predictable session IDs** -- Session IDs are derived from `time.Now().UnixNano()`, making them guessable and enabling session hijacking.

---

## Findings

### P0 - Critical

1. **[test_diff.go:49-59, 75-94, 117-134, 181-199, 202-212] Race conditions: unprotected access to `sm.sessions` map and `activeCount`**
   - Go maps are not safe for concurrent use. The `net/http` server calls handlers from separate goroutines. Several functions read/write `sm.sessions` without holding `sm.mu`:
     - `cleanupLoop` (lines 53-56): iterates and deletes from the map with no lock.
     - `CreateSession` (lines 75, 89-90): reads `len(sm.sessions)` and writes to the map with no lock.
     - `UpdateSession` (lines 120-132): reads and writes to the map with no lock.
     - `ImportSessions` (lines 194-198): writes to the map with no lock.
     - `GetStats` (lines 203-207): reads `len(sm.sessions)` and `activeCount` with no lock.
   - Additionally, the package-level `activeCount` variable (lines 37, 57, 90, 153, 198) is modified from multiple goroutines without any synchronization.
   - Concurrent map writes in Go trigger a fatal runtime panic (`concurrent map read and map write`), so this is not a theoretical issue -- it will crash the process under load.
   - **Suggested fix**: Hold `sm.mu.Lock()` / `defer sm.mu.Unlock()` for the entire critical section in every method that touches `sm.sessions` or `activeCount`. Consider using `sync.RWMutex` so read-only operations (`GetStats`, `GetSession`) can use `RLock`. Replace `activeCount` with an `atomic.Int64` or protect it under the same mutex.

2. **[test_diff.go:100-110] TOCTOU in `GetSession`: session mutated after lock release**
   - The mutex is acquired to look up the session (lines 100-102), then immediately released. Line 110 then mutates `session.ExpiresAt` outside the lock. Another goroutine (e.g., `cleanupLoop` or `DeleteSession`) could concurrently delete or modify this session, causing a data race on the `Session` struct fields.
   - **Suggested fix**: Extend the lock to cover the entire handler body, including the session mutation and JSON marshal, or copy the session data under the lock and work with the copy.

3. **[test_diff.go:140-155] TOCTOU in `DeleteSession`: double-lock with gap**
   - The session existence is checked under one lock (lines 140-142), the lock is released, then a second lock is acquired for the delete (lines 150-152). Between the two critical sections, another goroutine could delete the same session, making `activeCount` go negative. This also means the 404 check is unreliable.
   - **Suggested fix**: Use a single `Lock` / `defer Unlock` for the entire operation. Check existence and delete within the same critical section.

### P1 - High

4. **[test_diff.go:159-178, 181-199] Path traversal in `ExportSessions` and `ImportSessions`**
   - The `filename` query parameter is directly concatenated to `sm.config.StoragePath` (lines 164, 183). A request like `?file=../../../etc/passwd` can read or overwrite arbitrary files on the server.
   - **Suggested fix**: Sanitize `filename` to reject path separators and `..` components. Use `filepath.Base(filename)` and validate the resolved path stays within `StoragePath` using `filepath.Rel` or a prefix check after `filepath.Clean`.

5. **[test_diff.go:80] Predictable / guessable session IDs**
   - `fmt.Sprintf("sess_%d", time.Now().UnixNano())` produces session IDs that are trivially predictable. An attacker who knows the approximate server time can enumerate valid session IDs.
   - **Suggested fix**: Use `crypto/rand` to generate session IDs. For example, generate 16+ random bytes and hex-encode them.

6. **[test_diff.go:36-37, 41] Global mutable singleton**
   - `NewSessionManager` unconditionally overwrites the package-level `globalManager` (line 41). If called twice (e.g., in tests or a multi-tenant setup), the first manager's cleanup goroutine keeps running against a stale reference while the global points to the new one. The global `activeCount` is also shared across all instances.
   - **Suggested fix**: Remove the global variable. Return the manager directly and let the caller manage its lifecycle. Make `activeCount` a field on `SessionManager`.

### P2 - Medium

7. **[test_diff.go:72, 128, 192] Ignored `json.Unmarshal` errors**
   - `json.Unmarshal` return values are silently discarded at lines 72, 128, and 192. If the body is malformed JSON, the handler proceeds with zero-value data -- creating a session with an empty `UserID`, applying no updates silently, or importing zero sessions while reporting success.
   - **Suggested fix**: Check the error and return a 400 Bad Request with a descriptive message.

8. **[test_diff.go:92, 112] Ignored `json.Marshal` errors**
   - The `json.Marshal` calls at lines 92 and 112 discard the error. While marshalling simple structs rarely fails, silently dropping the error means a malformed response could be sent with a 200 status.
   - **Suggested fix**: Check the error and return 500 if marshalling fails.

9. **[test_diff.go:63, 126, 185] Use of deprecated `ioutil.ReadAll` / `ioutil.ReadFile`**
   - `io/ioutil` has been deprecated since Go 1.16. Use `io.ReadAll` and `os.ReadFile` instead.
   - **Suggested fix**: Replace `ioutil.ReadAll` with `io.ReadAll` and `ioutil.ReadFile` with `os.ReadFile`.

10. **[test_diff.go:62-94] No input validation on `UserID`**
    - `CreateSession` accepts any `UserID` including an empty string. There are no length limits on the request body either -- `ioutil.ReadAll(r.Body)` will read an unbounded amount of data into memory.
    - **Suggested fix**: Validate that `UserID` is non-empty. Use `http.MaxBytesReader` to cap request body size.

11. **[test_diff.go:49-59] `cleanupLoop` goroutine leaks (no shutdown mechanism)**
    - The goroutine runs an infinite `for` loop with no way to stop it. If the `SessionManager` is discarded, the goroutine leaks and the `sm` reference is never garbage collected.
    - **Suggested fix**: Accept a `context.Context` and select on `ctx.Done()` alongside a `time.Ticker` to allow graceful shutdown.

12. **[test_diff.go:15-18] SRP violation: `SessionManager` mixes HTTP handling with storage logic**
    - The `SessionManager` type is simultaneously a session store (create, read, update, delete sessions) and an HTTP handler (reads request bodies, writes response headers, sets status codes). This conflation makes it hard to test the storage logic in isolation or reuse it outside an HTTP context.
    - **Suggested fix**: Split into a `SessionStore` (pure CRUD with locking) and thin HTTP handlers that delegate to the store. This also makes unit testing straightforward without `httptest`.

### P3 - Low

13. **[test_diff.go:75, 98, 119, 139, 159, 181] Inconsistent session ID extraction**
    - Some handlers read the session ID from `r.URL.Query().Get("id")`, while `CreateSession` generates it internally. Consider using a URL path parameter (e.g., `/sessions/{id}`) for RESTful consistency and cleaner routing.

14. **[test_diff.go:172] File permissions too broad**
    - `os.WriteFile(filepath, data, 0644)` makes the exported session file world-readable. Session data may contain sensitive information.
    - **Suggested fix**: Use `0600` to restrict access to the owner only.

---

## Removal/Iteration Plan

### Safe to Remove Now

| Field | Details |
|-------|---------|
| **Location** | `test_diff.go:215-226` -- `BulkCleanup` |
| **Rationale** | Comment says "unused since migration to Redis" |
| **Evidence** | Dead code by the author's own annotation |
| **Impact** | None -- no callers |
| **Deletion steps** | Remove function, verify no references with `rg BulkCleanup` |

| Field | Details |
|-------|---------|
| **Location** | `test_diff.go:229-244` -- `migrateV1Sessions` |
| **Rationale** | Comment says "not needed after 2024-01 deploy" |
| **Evidence** | Dead code; unexported function with no callers |
| **Impact** | None |
| **Deletion steps** | Remove function, verify no references |

---

## Additional Suggestions

- Consider using `sync.RWMutex` instead of `sync.Mutex` so that read-only handlers (`GetSession`, `GetStats`) can hold a read lock concurrently, improving throughput under read-heavy workloads.
- The `ExportSessions` and `ImportSessions` endpoints are powerful admin operations. They should be behind authentication/authorization middleware. Currently any client can export or overwrite all session data.
- For production use, consider adding request logging/metrics middleware and setting timeouts on the `http.Server` (ReadTimeout, WriteTimeout, IdleTimeout) to prevent slowloris attacks.

---

## Next Steps

I found 14 issues (P0: 3, P1: 3, P2: 6, P3: 2).

**How would you like to proceed?**

1. **Fix all** - I'll implement all suggested fixes
2. **Fix P0/P1 only** - Address critical and high priority issues
3. **Fix specific items** - Tell me which issues to fix
4. **No changes** - Review complete, no implementation needed

Please choose an option or provide specific instructions.
