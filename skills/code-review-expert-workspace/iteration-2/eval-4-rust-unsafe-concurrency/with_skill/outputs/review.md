## Code Review Summary

**Files reviewed**: 1 file (ws.rs), ~140 lines
**Overall assessment**: REQUEST_CHANGES

### Top Issues

1. **Command injection via `execute_command`** — passes raw user input to `sh -c`, giving any WebSocket client full shell access
2. **`unsafe static mut` data race** — `CONNECTION_COUNT` is mutated from multiple threads without synchronization, which is undefined behavior in Rust
3. **Hardcoded production secret key** — `sk_live_hardcoded_key_12345` is in source code and leaks via `serialize_state`

---

## Findings

### P0 - Critical

1. **[ws.rs:68-73] Command injection — `execute_command` passes unsanitized input to shell**
   - Any WebSocket client sending `{"action": "exec", "payload": "rm -rf /"}` gets arbitrary command execution
   - This is the most critical finding — it's a full RCE vulnerability
   - Fix: Remove this entirely, or if needed, use a strict allowlist of commands with no shell interpolation

2. **[ws.rs:8] Undefined behavior — `unsafe static mut CONNECTION_COUNT`**
   - Mutated in `add_connection` (line 34) and `remove_connection` (line 39) without synchronization
   - With concurrent WebSocket connections, this is a data race — undefined behavior per Rust's memory model, not just a wrong count
   - Fix: Replace with `AtomicU64` — `static CONNECTION_COUNT: AtomicU64 = AtomicU64::new(0);` and use `.fetch_add(1, Ordering::Relaxed)`

3. **[ws.rs:27] Hardcoded secret key leaks via `serialize_state`**
   - `secret_key: "sk_live_hardcoded_key_12345"` is hardcoded in `new()` and included in `serialize_state` output (line 82)
   - Any call to `serialize_state` exposes the signing key alongside connection data
   - Fix: Load from environment variable, never include in serialized output

### P1 - High

4. **[ws.rs:75-77] Path traversal in `load_config`**
   - `path` parameter is user-controlled (from WebSocket `config` action) and appended to `/etc/rustyclaw/`
   - Payload `"../../etc/passwd"` reads arbitrary files
   - Fix: Canonicalize the path and verify it stays within `/etc/rustyclaw/`

5. **[ws.rs:56] `unwrap()` on channel send — panics on closed connection**
   - `send_to_user` calls `.unwrap()` on `sender.send()`, which panics if the receiving end dropped
   - In a WebSocket server, connections close constantly — this will crash the process
   - Fix: Use `if let Err(e) = conn.sender.send(...)` and remove the dead connection

### P2 - Medium

6. **[ws.rs:48-51] Broadcast silently drops send errors**
   - `let _ = conn.sender.send(...)` discards errors. While not crashing (unlike #5), stale connections accumulate in the map
   - Fix: Collect failed sends and remove dead connections, or log the failure

7. **[ws.rs:12-14] SRP violation — `WsState` does too much**
   - Manages connections, signs messages, executes shell commands, loads config files, serializes state
   - Fix: Extract `execute_command` and `load_config` into separate services

8. **[ws.rs:130-141] Meaningless tests — `assert!(true)`**
   - `test_add_connection` asserts nothing useful — a broken implementation would still pass
   - `test_broadcast` just checks "no panic" with zero connections
   - Fix: Assert connection count after add, assert message received after broadcast, test error paths

### P3 - Low

9. **[ws.rs:103-104] Silent no-op on unknown action**
   - `_ => {}` silently ignores unknown message types — at minimum log unknown actions for debugging

---

## Next Steps

I found 9 issues (P0: 3, P1: 2, P2: 3, P3: 1).

**How would you like to proceed?**

1. **Fix all** - I'll implement all suggested fixes
2. **Fix P0/P1 only** - Address critical and high priority issues
3. **Fix specific items** - Tell me which issues to fix
4. **No changes** - Review complete, no implementation needed
