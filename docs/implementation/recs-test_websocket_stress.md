 # WebSocket Test Performance Analysis

**Analysis Date:** March 2, 2026  
**Target File:** `src/scripts/tests/test_websocket_stress.py`  
**Analysis Type:** DyTopo Protocol Round 0 (Analysis Only)  

---

## Executive Summary

The WebSocket stress test file contains **multiple critical issues** causing slowness and hangs:
- **1 Critical Syntax Error** (`/ __init__`) preventing proper instantiation
- **Event Loop Blocking** via `threading.Lock` in async contexts - the primary cause of hangs
- **Fire-and-forget async tasks** causing resource leaks
- **Excessive timeouts** (2-5s) when tests should complete in <100ms
- **Threading/async boundary violations** creating undefined behavior

The most severe issue is the misuse of `threading.Lock` (synchronous) inside async coroutines, which blocks the entire event loop, defeating async concurrency and causing deadlocks under contention.

---

## Root Causes Identified

### 1. Critical: threading.Lock in Async Context (Primary Hang Cause)
- **Location:** MockTTSService lines 87, 96-97, 106, 130, 160
- **Issue:** `threading.Lock()` is used inside async methods; when acquired, it blocks the entire event loop
- **Impact:** All concurrent connections freeze when lock is held
- **Fix:** Replace with `asyncio.Lock()`

### 2. Critical: Syntax Error
- **Location:** Line 57 - `def /__init__(self...)` instead of `def __init__(self...)`
- **Impact:** Class instantiation may fail

### 3. High: Fire-and-Forget Tasks
- **Location:** Line 173 in `add_server_message()`
- **Issue:** `asyncio.create_task()` without storing reference leads to orphaned tasks
- **Impact:** Resource leaks and silent failures
- **Lines Affected:** 143-145, multiple test methods

### 4. High: Event Loop Issues in Threading Tests
- **Location:** Lines 434-437, 600
- **Issue:** `asyncio.run()` called from multiple threads creates nested/isolated event loops
- **Impact:** Thread-safety issues with shared MockTTSService state

### 5. High: Timeout Configuration Issues
- **Locations:** Lines 90, 170, 225, 288, 361, 443, 556-562
- **Issue:** Timeouts of 2.0-5.0s for mocked tests that should complete in <100ms
- **Impact:** Excessive wait times when queues are empty, masking real hangs

### 6. Medium: Race Conditions in Message Handling
- **Locations:** Lines 166, 224, 278, 361-370
- **Issue:** Tests check for 'done' message but skip binary data with `continue`, potentially missing 'done'
- **Impact:** Infinite loops in `while True` blocks

### 7. Medium: Duplicate/Unreachable Code
- **Locations:** Lines 165, 223
- **Issue:** Duplicate `isinstance(response, bytes)` check (already handled above)
- **Location:** Line 168-169: Double decode path logic

---

## Architectural Issues (from DT-Architect)

### Concurrency Model Conflicts
- **threading.Lock + async/await** creates event loop blocking - a classic anti-pattern
- **Boundary Mismatch:** Threading tests spawn threads that each create isolated event loops via `asyncio.run()`, not testing real threading concurrency

### Resource Lifecycle Management
- No structured teardown pattern
- Handler tasks cancellation doesn't propagate cleanly through nested queues
- `_send_queue`/`_receive_queue` remain populated after `close()`

### Scalability Concerns
- `threading.Lock` prevents horizontal scaling across event loop iterations
- Each client creates 2 `asyncio.Queues` - linear memory growth
- `MockTTSService.request_log` unbounded growth - memory leak potential

### Integration Patterns
- Producer-consumer pattern via queues is sound, but queue sizes are unbounded (no `maxsize`)
- No backpressure mechanism when service is overloaded
- Message protocol lacks versioning or capability negotiation

### Security/Replayability
- No request deduplication or idempotency handling
- Error handling doesn't distinguish recoverable vs non-recoverable failures

---

## Code-Level Issues (from DT-Developer)

### CRITICAL - Blocking Operations in Async Context
1. **Line 87:** `MockTTSService.__init__` uses `threading.Lock()` instead of `asyncio.Lock()`
2. **Lines 106, 130, 160:** Lock held during I/O operations including `await asyncio.sleep(self.processing_delay)` - blocks ALL connections

### HIGH - Event Loop Issues
3. **Lines 434-437:** `test_threading_with_websocket_clients` calls `asyncio.run(client_session())` from multiple threads - each creates its own event loop
4. Multiple event loops with shared `threading.Lock` create undefined behavior

### MEDIUM - Resource Leaks
5. **Line 173:** `add_server_message()` creates `asyncio.create_task()` without storing reference - orphaned tasks
6. **Lines 265, 285:** `handler_task = asyncio.create_task()` - local references may be cancelled before completion, exceptions not handled

### MEDIUM - Timeout Handling Gaps
7. **Lines 281-284:** `recv()` has timeout but inner loop (lines 288-294) lacks timeout on individual `recv()` calls - can hang forever
8. **Line 480:** Manual `max_wait = 5.0` workaround instead of proper timeout handling

### LOW - Queue Management
9. `handle_connection()` waits on `websocket._send_queue.get()` with 1.0s timeout, but pending messages at close are lost

---

## Execution Problems (from DT-Tester)

### 1. ASYNC/TIMEOUT ISSUES (Slowness Causes)
- Lines 170, 225, 288, 361, 443: 2.0-5.0s timeouts excessive for mocked tests
- Line 556-562: Nested poll loop with max_wait=5.0s creates busy-wait hang potential
- Line 90: Default 5.0s timeout propagates to all tests

### 2. RACE CONDITIONS & FLAKINESS
- Lines 93-94: `asyncio.create_task()` called synchronously - no await guarantees
- Lines 166, 224, 278: Message order [metadata, binary, done] - `continue` skips binary but may miss 'done'
- Lines 361-370: Race between binary data and done message handling

### 3. CLEANUP/TEARDOWN PROBLEMS (Major Hang Risk)
- Lines 176-181, 240-245, 326-331: Task cancellation pattern scattered with variations
- Line 600: Threading test runs new event loop per thread with shared service
- Missing session-level cleanup for `service.active_connections` Dict

### 4. FIXTURE DESIGN ISSUES
- Lines 126-128: `@pytest.fixture service()` creates new MockTTSService but tests share event loop
- No event_loop fixture override for pytest-asyncio mode config

### 5. CODE DEFECTS
- Lines 165, 223: Duplicate `isinstance(response, bytes)` check - unreachable code
- Line 78: Class typo `def /__init__` - invalid Python syntax
- Lines 168-169: Double decode path logic confusing

### 6. MISSING TEST CAPABILITIES
- No test for maximum connection limits
- No memory usage assertions beyond basic count
- Missing validation of error message propagation
- No test for simultaneous read/write on same connection

### 7. THREADING ISSUES
- Line 600: Service created in sync test scope, accessed by multiple threads
- `asyncio.Queue` is NOT thread-safe - multiple threads calling `asyncio.run()` with shared service creates race on internal queues

---

## Quality Concerns (from DT-Reviewer)

### CRITICAL (Fix Immediately)
1. **Line 57:** Syntax error `/__init__(self...)` should be `__init__(self...)`
2. **Lines 96-97, 123:** `threading.Lock` in async methods blocks event loop → use `asyncio.Lock`
3. **Lines 68-69:** `add_server_message()` uses `asyncio.create_task` without awaiting - orphaned tasks

### MAJOR
4. **Lines 157-158:** `request_counter = [0]` hack - use `asyncio.Lock` with proper integer
5. **Lines 143-145:** Multiple fire-and-forget `create_task` calls without cleanup
6. **Lines 419-421:** `asyncio.run()` inside threads creates nested event loops - undefined behavior
7. **Line 374:** Type `webscocket` should be `websocket`

### MEDIUM
8. **Lines 100-103:** Bare `except Exception` blocks mask real errors
9. Duplicate task cancellation pattern - extract helper
10. **Lines 78, 86:** Missing return type annotations
11. **Lines 280, 288, 297:** `print()` in tests - use logging or pytest fixtures

### MINOR
12. **Lines 131-132:** Audio sample calculation hardcoded magic numbers
13. Missing module-level security warnings about mock usage
14. No validation of input text for JSON injection
15. No limits on queue sizes - unbounded growth risk

### POSITIVE HIGHLIGHTS
- Good test coverage with 10 concurrent client scenarios
- Proper use of `pytest.mark.asyncio`
- Clean separation between MockWebSocket and MockTTSService
- Thoughtful race condition tests included

**APPROVAL STATUS: NEEDS MAJOR REVISION**

---

## Recommendations (Prioritized)

### High Priority
- [ ] **Fix Critical Syntax Error:** Change `def /__init__` to `def __init__` (line 57)
- [ ] **Replace threading.Lock with asyncio.Lock:** In MockTTSService (lines 87, 96-97, 106, 130, 160)
- [ ] **Fix Fire-and-Forget Tasks:** Store task references for cleanup (line 173, 143-145)
- [ ] **Add Queue Size Limits:** Add `maxsize` parameter to asyncio.Queue constructors
- [ ] **Reduce Timeout Defaults:** Change 2-5s timeouts to 0.5s for faster failure detection
- [ ] **Standardize Cleanup Pattern:** Extract helper for task cancellation/cleanup

### Medium Priority
- [ ] **Fix Asyncio.run() in Threads:** Use thread-safe async patterns instead
- [ ] **Add Timeouts to All recv() Loops:** Ensure no infinite waits
- [ ] **Remove Duplicate/Unreachable Code:** Lines 165, 223 bytes checks
- [ ] **Fix Typo:** `webscocket` → `websocket` (line 374)
- [ ] **Remove print() statements:** Use pytest fixtures or logging
- [ ] **Add Return Type Annotations:** Lines 78, 86

### Low Priority
- [ ] **Add Session-Level Fixture Teardown:** For service.active_connections
- [ ] **Add pytest-asyncio Config:** With `asyncio_mode=auto`
- [ ] **Extract Magic Numbers:** Audio sample calculation constants
- [ ] **Add Security Warnings:** About mock usage in production
- [ ] **Add Input Validation:** For JSON injection prevention

---

## Semantic Routing Summary

Analysis of worker insights sharing via nomic-embed-text embeddings:

| Route | Score | Insight |
|-------|-------|---------|
| DT-Tester ← DT-Developer | 0.75 | High overlap on test execution issues |
| DT-Reviewer ← DT-Architect | 0.76 | High overlap on architectural patterns |
| DT-Reviewer ← DT-Developer | 0.74 | High overlap on code-level fixes |
| DT-Tester ← DT-Architect | 0.72 | Moderate overlap on concurrency issues |
| DT-Tester ← DT-Reviewer | 0.72 | Moderate overlap on quality concerns |

All workers converged on the `threading.Lock` issue as the primary cause of hangs.

---

**Report Generated By:** DT-Manager via DyTopo Protocol  
**Round:** 0 (Analysis Phase)  
**Workers:** DT-Architect, DT-Developer, DT-Tester, DT-Reviewer  
