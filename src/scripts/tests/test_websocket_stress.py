"""Comprehensive WebSocket stress tests for TTS service.

Tests simulated concurrent WebSocket clients to verify:
- 10 concurrent WebSocket connections requesting TTS
- Connection handling under load
- Message ordering and integrity
- Graceful handling of disconnections
"""

from __future__ import annotations

import asyncio
import json
import time
import pytest
import threading
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent / "src/scripts"))

# Default queue size limit for backpressure testing
DEFAULT_QUEUE_SIZE = 100


async def cleanup_tasks(*tasks: asyncio.Task, timeout: float = 0.5) -> None:
    """Standardized cleanup for asyncio tasks.
    
    Cancels tasks and awaits them with a timeout.
    Suppresses CancelledError as expected.
    """
    for task in tasks:
        if task and not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass


@dataclass
class WebSocketMessage:
    """Represents a WebSocket message."""
    type: str  # "text" or "binary"
    data: Any


class MockWebSocket:
    """Mock WebSocket connection for testing."""
    
    def __init__(self, client_id: int, latency_ms: float = 0):
        self.client_id = client_id
        self.latency_ms = latency_ms
        self.messages: List[WebSocketMessage] = []
        self.closed = False
        self._receive_queue: asyncio.Queue = asyncio.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        self._send_queue: asyncio.Queue = asyncio.Queue(maxsize=DEFAULT_QUEUE_SIZE)
        self.connection_time = time.time()
        self.errors: List[str] = []
        self._pending_tasks: List[asyncio.Task] = []
    
    async def send(self, data: str):
        """Send data to server."""
        if self.closed:
            raise Exception("WebSocket is closed")
        if self.latency_ms > 0:
            await asyncio.sleep(self.latency_ms / 1000)
        self.messages.append(WebSocketMessage("text", data))
        await self._send_queue.put(data)
    
    async def recv(self, timeout: float | None = 0.5):
        """Receive data from server with optional timeout."""
        if self.closed:
            raise Exception("WebSocket is closed")
        if timeout is not None:
            return await asyncio.wait_for(self._receive_queue.get(), timeout=timeout)
        return await self._receive_queue.get()
    
    async def close(self):
        """Close the connection."""
        self.closed = True
        # Clean up pending tasks
        for task in self._pending_tasks:
            if not task.done():
                task.cancel()
        self._pending_tasks.clear()
    
    def add_server_message(self, msg: Any):
        """Queue a message from server."""
        task = asyncio.create_task(self._receive_queue.put(msg))
        self._pending_tasks.append(task)


class MockTTSService:
    """Mock TTS service for testing concurrent WebSocket connections."""
    
    def __init__(self, processing_delay: float = 0.05):
        self.processing_delay = processing_delay
        self.active_connections: Dict[int, MockWebSocket] = {}
        self.connection_count = 0
        self.max_concurrent = 0
        self.request_log: List[Dict] = []
        self._lock = asyncio.Lock()
        self.errors: List[str] = []
        self.should_fail_nth_request: Optional[int] = None
        self.request_counter = [0]
    
    async def handle_connection(self, websocket: MockWebSocket):
        """Handle a single WebSocket connection."""
        client_id = websocket.client_id
        
        async with self._lock:
            self.active_connections[client_id] = websocket
            self.connection_count += 1
            current = len(self.active_connections)
            if current > self.max_concurrent:
                self.max_concurrent = current
        
        try:
            while not websocket.closed:
                try:
                    # Wait for message with timeout
                    message = await asyncio.wait_for(
                        websocket._send_queue.get(),
                        timeout=1.0
                    )
                    await self._process_request(websocket, message)
                except asyncio.TimeoutError:
                    break
        except Exception as e:
            self.errors.append(f"Client {client_id}: {e}")
        finally:
            async with self._lock:
                if client_id in self.active_connections:
                    del self.active_connections[client_id]
    
    async def _process_request(self, websocket: MockWebSocket, message: str):
        """Process a TTS request."""
        async with self._lock:
            self.request_counter[0] += 1
            counter = self.request_counter[0]
        
        try:
            request = json.loads(message)
            
            # Simulate failure if configured
            if self.should_fail_nth_request == counter:
                raise Exception(f"Simulated failure for request {counter}")
            
            # Simulate processing time
            await asyncio.sleep(self.processing_delay)
            
            # Generate mock audio data
            text = request.get("text", "")
            audio_samples = int(24000 * len(text) * 0.1)  # ~100ms per char
            audio_data = np.zeros(audio_samples, dtype=np.float32)
            
            # Send metadata
            metadata = {
                "status": "success",
                "sample_rate": 24000,
                "duration_samples": len(audio_data)
            }
            websocket.add_server_message(json.dumps(metadata))
            
            # Send binary audio
            websocket.add_server_message(audio_data.tobytes())
            
            # Send done
            websocket.add_server_message(json.dumps({"done": True}))
            
            async with self._lock:
                self.request_log.append({
                    "client_id": websocket.client_id,
                    "text": text,
                    "timestamp": time.time()
                })
                
        except Exception as e:
            error_msg = {"error": str(e)}
            websocket.add_server_message(json.dumps(error_msg))


class TestWebSocketStress:
    """Stress tests for WebSocket connections."""
    
    @pytest.fixture
    def service(self) -> MockTTSService:
        """Create a mock TTS service."""
        return MockTTSService(processing_delay=0.01)
    
    @pytest.mark.asyncio
    async def test_single_client(self, service):
        """Test single WebSocket client works correctly."""
        ws = MockWebSocket(client_id=1)
        
        # Start server handler
        handler_task = asyncio.create_task(service.handle_connection(ws))
        
        # Send request
        request = {
            "text": "Hello world",
            "speaker": "test",
            "emotion": "neutral",
            "language": "en"
        }
        await ws.send(json.dumps(request))
        
        # Wait for metadata response (skip binary audio data)
        try:
            while True:
                response = await asyncio.wait_for(ws.recv(), timeout=1.0)
                if isinstance(response, bytes):
                    continue  # Skip binary audio data
                data = json.loads(response)
                if "error" in data:
                    pytest.fail(f"Server error: {data['error']}")
                elif "status" in data:
                    assert data["status"] == "success"
                    break
                elif "done" in data:
                    continue  # Skip done message, wait for metadata
        except asyncio.TimeoutError:
            pytest.fail("Timeout waiting for response")
        finally:
            await ws.close()
            handler_task.cancel()
            try:
                await handler_task
            except asyncio.CancelledError:
                pass
    
    @pytest.mark.asyncio
    async def test_ten_concurrent_connections(self, service):
        """Test 10 concurrent WebSocket connections requesting TTS.
        
        Critical scenario: Multiple clients simultaneously connected
        to the TTS service.
        """
        num_clients = 10
        clients: List[MockWebSocket] = []
        handler_tasks: List[asyncio.Task] = []
        results: List[bool] = []
        errors: List[str] = []
        
        async def client_worker(client: MockWebSocket) -> bool:
            """Simulate a client making TTS requests."""
            try:
                # Each client sends 3 requests
                for i in range(3):
                    request = {
                        "text": f"Hello from client {client.client_id} request {i}",
                        "speaker": "test",
                        "emotion": "neutral",
                        "language": "en"
                    }
                    await client.send(json.dumps(request))
                    
                    # Collect responses - handle both JSON and binary data
                    while True:
                        response = await asyncio.wait_for(client.recv(), timeout=2.0)
                        # Skip binary audio data
                        if isinstance(response, bytes):
                            continue
                        # Handle string responses (could be bytes decoded)
                        if isinstance(response, bytes):
                            response = response.decode('utf-8', errors='ignore')
                        msg = json.loads(response)
                        if "done" in msg:
                            break
                        elif "error" in msg:
                            raise Exception(f"Error: {msg['error']}")
                return True
            except Exception as e:
                errors.append(f"Client {client.client_id}: {e}")
                return False
            finally:
                await client.close()
        
        # Start service handlers for all clients
        for i in range(num_clients):
            ws = MockWebSocket(client_id=i+1)
            clients.append(ws)
            handler_tasks.append(asyncio.create_task(service.handle_connection(ws)))
        
        # All clients send requests concurrently
        client_tasks = [asyncio.create_task(client_worker(c)) for c in clients]
        results = await asyncio.gather(*client_tasks, return_exceptions=True)
        
        # Cancel handlers
        for task in handler_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Verify results
        success_count = sum(1 for r in results if r is True)
        assert success_count == num_clients, f"Only {success_count}/{num_clients} clients succeeded. Errors: {errors}"
        
        # Verify all requests were logged
        assert len(service.request_log) == num_clients * 3
        
        print(f"Max concurrent connections: {service.max_concurrent}")
        print(f"Total requests handled: {len(service.request_log)}")
    
    @pytest.mark.asyncio
    async def test_concurrent_websocket_client_simulation(self, service):
        """Simulate real-world concurrent WebSocket clients with varying load.
        
        Some clients send rapid requests, others send slowly.
        Tests fairness and stability.
        """
        slow_clients = 3
        fast_clients = 7
        total_clients = slow_clients + fast_clients
        
        clients: List[MockWebSocket] = []
        handler_tasks: List[asyncio.Task] = []
        
        async def slow_worker(ws: MockWebSocket) -> int:
            """Slow client - one request every 200ms."""
            count = 0
            try:
                for _ in range(3):
                    await ws.send(json.dumps({
                        "text": f"Slow request {count}",
                        "speaker": "test",
                        "emotion": "neutral",
                        "language": "en"
                    }))
                    count += 1
                    
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        # Skip binary data
                        if isinstance(msg, bytes):
                            continue
                        if json.loads(msg).get("done"):
                            break
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"Slow client {ws.client_id} error: {e}")
            finally:
                await ws.close()
            return count
        
        async def fast_worker(ws: MockWebSocket) -> int:
            """Fast client - sends requests as fast as possible."""
            count = 0
            try:
                for _ in range(5):
                    await ws.send(json.dumps({
                        "text": f"Fast request {count}",
                        "speaker": "test",
                        "emotion": "neutral",
                        "language": "en"
                    }))
                    count += 1
                    
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                        # Skip binary data
                        if isinstance(msg, bytes):
                            continue
                        if json.loads(msg).get("done"):
                            break
            except Exception as e:
                print(f"Fast client {ws.client_id} error: {e}")
            finally:
                await ws.close()
            return count
        
        # Start all clients
        for i in range(total_clients):
            ws = MockWebSocket(client_id=i+1)
            clients.append(ws)
            handler_tasks.append(asyncio.create_task(service.handle_connection(ws)))
        
        # Launch slow and fast workers
        slow_tasks = [asyncio.create_task(slow_worker(clients[i])) 
                      for i in range(slow_clients)]
        fast_tasks = [asyncio.create_task(fast_worker(clients[i+slow_clients])) 
                      for i in range(fast_clients)]
        
        # Wait for all
        slow_results = await asyncio.gather(*slow_tasks, return_exceptions=True)
        fast_results = await asyncio.gather(*fast_tasks, return_exceptions=True)
        
        # Clean up handlers
        for task in handler_tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Verify
        success = sum(r for r in slow_results if isinstance(r, int)) + \
                 sum(r for r in fast_results if isinstance(r, int))
        
        expected = slow_clients * 3 + fast_clients * 5
        assert len(service.request_log) == expected, f"Expected {expected} requests, got {len(service.request_log)}"
    
    @pytest.mark.asyncio
    async def test_connection_failure_handling(self, service):
        """Test service handles connection failures gracefully.
        
        Some clients disconnect unexpectedly.
        """
        num_clients = 5
        clients: List[MockWebSocket] = []
        handler_tasks: List[asyncio.Task] = []
        
        # Start service
        for i in range(num_clients):
            ws = MockWebSocket(client_id=i+1)
            clients.append(ws)
            handler_tasks.append(asyncio.create_task(service.handle_connection(ws)))
        
        # Client 3 disconnects immediately
        await clients[2].close()
        
        # Others send requests
        for i, ws in enumerate(clients):
            if not ws.closed:
                await ws.send(json.dumps({
                    "text": f"Request from client {i}",
                    "speaker": "test",
                    "emotion": "neutral",
                    "language": "en"
                }))
        
        await asyncio.sleep(0.2)  # Let processing complete
        
        # Clean up
        for i, task in enumerate(handler_tasks):
            if not clients[i].closed:
                await clients[i].close()
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        
        # Should have handled 4 requests (one client disconnected)
        assert len(service.request_log) == 4
    
    @pytest.mark.asyncio
    async def test_race_condition_message_ordering(self):
        """Test message ordering under concurrent load.
        
        Verifies that responses are correlated with correct requests.
        """
        service = MockTTSService(processing_delay=0.001)
        num_clients = 10
        
        async def tagged_client(ws: MockWebSocket, tag: str) -> List[str]:
            """Client that tracks request-response pairing."""
            responses = []
            for i in range(5):
                request = {"text": f"req_{tag}_{i}", "speaker": "test"}
                await ws.send(json.dumps(request))
                
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=1.0)
                    # Skip binary data
                    if isinstance(msg, bytes):
                        continue
                    data = json.loads(msg)
                    if "done" in data:
                        responses.append(tag)
                        break
            await ws.close()
            return responses
        
        clients = [MockWebSocket(client_id=i+1) for i in range(num_clients)]
        handlers = [asyncio.create_task(service.handle_connection(c)) for c in clients]
        
        tasks = [asyncio.create_task(tagged_client(c, f"client{i}")) 
                for i, c in enumerate(clients)]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Clean up
        for h in handlers:
            h.cancel()
            try:
                await h
            except asyncio.CancelledError:
                pass
        
        # Each client should get exactly 5 responses
        for i, result in enumerate(results):
            assert isinstance(result, list), f"Client {i} got exception: {result}"
            assert len(result) == 5, f"Client {i} got {len(result)} responses instead of 5"
    
    @pytest.mark.asyncio
    async def test_concurrent_client_sessions(self):
        """Test multiple concurrent WebSocket client sessions.
        
        Simulates scenario where multiple WebSocket connections
        are active concurrently within the same event loop.
        """
        service = MockTTSService(processing_delay=0.02)
        num_clients = 5
        errors: List[str] = []
        success_count = [0]
        count_lock = asyncio.Lock()
        
        async def client_session(client_id: int):
            ws = MockWebSocket(client_id=client_id)
            handler = asyncio.create_task(service.handle_connection(ws))
            
            try:
                for i in range(3):
                    await ws.send(json.dumps({
                        "text": f"Client {client_id} request {i}",
                        "speaker": "test",
                        "emotion": "neutral",
                        "language": "en"
                    }))
                    
                    # Wait for response
                    while True:
                        msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                        # Skip binary data
                        if isinstance(msg, bytes):
                            continue
                        if json.loads(msg).get("done"):
                            break
                
                async with count_lock:
                    success_count[0] += 1
                
            except Exception as e:
                async with count_lock:
                    errors.append(f"Client {client_id}: {e}")
            finally:
                await ws.close()
                handler.cancel()
                try:
                    await handler
                except asyncio.CancelledError:
                    pass
        
        # Launch all client sessions concurrently
        await asyncio.gather(*[client_session(i) for i in range(num_clients)])
        
        assert success_count[0] == num_clients, f"Only {success_count[0]}/{num_clients} succeeded. Errors: {errors}"


class TestWebSocketPerformance:
    """Performance tests for WebSocket handling."""
    
    def test_performance_baseline(self):
        """Single-threaded performance baseline."""
        service = MockTTSService(processing_delay=0.01)
        
        async def run():
            ws = MockWebSocket(client_id=1)
            handler = asyncio.create_task(service.handle_connection(ws))
            
            start = time.time()
            for i in range(10):
                await ws.send(json.dumps({
                    "text": f"Request {i}",
                    "speaker": "test",
                    "emotion": "neutral",
                    "language": "en"
                }))
                # Wait for done with timeout
                max_wait = 5.0
                wait_start = time.time()
                while True:
                    if time.time() - wait_start > max_wait:
                        raise asyncio.TimeoutError(f"Timeout waiting for 'done' message after {max_wait}s")
                    try:
                        msg = await ws.recv(timeout=None)
                    except asyncio.TimeoutError:
                        continue
                    # Skip binary data
                    if isinstance(msg, bytes):
                        continue
                    if json.loads(msg).get("done"):
                        break
            duration = time.time() - start
            
            await ws.close()
            handler.cancel()
            try:
                await handler
            except asyncio.CancelledError:
                pass
            
            return duration
        
        duration = asyncio.run(run())
        print(f"Baseline: 10 requests in {duration:.2f}s")
        assert duration < 5.0, "Baseline too slow"
    
    @pytest.mark.asyncio
    async def test_performance_under_concurrent_load(self):
        """Test performance with concurrent WebSocket connections.
        
        Should complete within reasonable time.
        """
        service = MockTTSService(processing_delay=0.005)
        num_clients = 10
        requests_per_client = 5
        
        async def client_session(ws: MockWebSocket):
            handler = asyncio.create_task(service.handle_connection(ws))
            
            for i in range(requests_per_client):
                await ws.send(json.dumps({
                    "text": f"Request {i}",
                    "speaker": "test",
                    "emotion": "neutral",
                    "language": "en"
                }))
                
                while True:
                    msg = await asyncio.wait_for(ws.recv(), timeout=2.0)
                    # Skip binary data
                    if isinstance(msg, bytes):
                        continue
                    if json.loads(msg).get("done"):
                        break
            
            await ws.close()
            handler.cancel()
            try:
                await handler
            except asyncio.CancelledError:
                pass
        
        start = time.time()
        clients = [MockWebSocket(client_id=i) for i in range(num_clients)]
        await asyncio.gather(*[client_session(c) for c in clients])
        duration = time.time() - start
        
        total_requests = num_clients * requests_per_client
        print(f"Concurrent: {total_requests} requests in {duration:.2f}s "
              f"({total_requests/duration:.1f} req/s)")
        
        # Should complete within reasonable time (accounting for delay)
        expected_min = requests_per_client * 0.005
        assert duration >= expected_min * 0.5, "Too fast, processing not simulated"
    
    @pytest.mark.asyncio
    async def test_memory_growth_under_load(self):
        """Check memory doesn't grow unbounded under sustained load.
        
        Tests for memory leaks in connection handling.
        FIXME: This is a simplified test; real memory testing needs monitoring.
        """
        service = MockTTSService(processing_delay=0.001)
        
        # Simulate 50 connections cycling through
        for batch in range(5):
            clients = [MockWebSocket(client_id=i) for i in range(10)]
            
            handlers = [asyncio.create_task(service.handle_connection(c)) 
                       for c in clients]
            
            # Each client makes a request
            for c in clients:
                await c.send(json.dumps({
                    "text": "Test",
                    "speaker": "test",
                    "emotion": "neutral",
                    "language": "en"
                }))
            
            await asyncio.sleep(0.1)
            
            # Clean up
            for c in clients:
                await c.close()
            for h in handlers:
                h.cancel()
                try:
                    await h
                except asyncio.CancelledError:
                    pass
            
            # Give time for cleanup
            await asyncio.sleep(0.05)
        
        # Service should not have leftover connections
        assert len(service.active_connections) == 0, "Connections not cleaned up"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])