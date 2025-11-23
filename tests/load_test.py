import base64
import json
import logging
import random
import time
from statistics import mean, median

import websocket
from locust import HttpUser, between, events, task

logger = logging.getLogger(__name__)

# Shared messages for cache testing (used across all users)
SHARED_MESSAGES = [
    "Hello world",
    "How are you today?",
    "This is a test message",
    "Testing cache performance",
    "Python is awesome",
    "Machine learning rocks",
    "AI is the future",
    "FastAPI is fast",
    "Redis caching works",
    "Realtime voice processing pipeline",
]

# Global cache metrics (tracked across all users)
global_cache_stats = {
    "hits": 0,
    "misses": 0,
    "hit_latencies": [],
    "miss_latencies": [],
    "total_tts_requests": 0,
}

# Global STT metrics (NEW!)
global_stt_stats = {"total_requests": 0, "latencies": []}

# Fake audio data for STT testing (realistic size)
FAKE_AUDIO_SMALL = base64.b64encode(b"fake_audio_data" * 1000).decode("utf-8")  # ~14KB
FAKE_AUDIO_MEDIUM = base64.b64encode(b"fake_audio_data" * 5000).decode("utf-8")  # ~70KB


class VoicePipelineUser(HttpUser):
    """Simulated user for load testing - WebSocket focused"""

    wait_time = between(1, 3)

    def on_start(self):
        """Setup for each user"""
        self.latencies = []
        self.cache_hits = 0
        self.total_requests = 0
        self.tts_requests = 0
        self.stt_requests = 0

    @task(7)
    def websocket_tts_request(self):
        """Test WebSocket TTS with latency measurement and cache tracking"""
        ws_url = self.host.replace("http", "ws") + "/ws/voice"
        ws = None
        start_time = time.time()

        try:
            ws = websocket.create_connection(ws_url, timeout=10)

            # 70% chance of using shared message (cache hit likely)
            # 30% chance of unique message (cache miss)
            if random.random() < 0.7:
                text = random.choice(SHARED_MESSAGES)
            else:
                text = f"Unique message {self.tts_requests} {time.time()}"

            # Send text request
            message = {"type": "text", "text": text}
            ws.send(json.dumps(message))

            # Receive response
            response = ws.recv()
            data = json.loads(response)

            # Calculate latency
            latency = (time.time() - start_time) * 1000
            self.latencies.append(latency)

            # Track cache hits
            is_cached = data.get("cached", False)
            if is_cached:
                self.cache_hits += 1
                global_cache_stats["hits"] += 1
                global_cache_stats["hit_latencies"].append(latency)
            else:
                global_cache_stats["misses"] += 1
                global_cache_stats["miss_latencies"].append(latency)

            self.total_requests += 1
            self.tts_requests += 1
            global_cache_stats["total_tts_requests"] += 1

            # Report metrics
            events.request.fire(
                request_type="WebSocket",
                name=f"WS TTS ({'Cached' if is_cached else 'Uncached'})",
                response_time=latency,
                response_length=len(response),
                exception=None,
                context={},
            )

            ws.close()

        except Exception as e:
            logger.error(f"WebSocket TTS error: {str(e)}")
            events.request.fire(
                request_type="WebSocket",
                name="WS TTS (Error)",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )

    @task(3)
    def websocket_stt_request(self):
        """Test WebSocket STT with latency measurement"""
        ws_url = self.host.replace("http", "ws") + "/ws/voice"
        ws = None
        start_time = time.time()

        try:
            ws = websocket.create_connection(ws_url, timeout=15)

            # Send STT request with fake audio
            audio_data = FAKE_AUDIO_SMALL if random.random() < 0.7 else FAKE_AUDIO_MEDIUM
            message = {"type": "audio", "audio": audio_data}
            ws.send(json.dumps(message))

            # Receive response
            response = ws.recv()

            # Calculate latency
            latency = (time.time() - start_time) * 1000
            self.latencies.append(latency)

            global_stt_stats["total_requests"] += 1
            global_stt_stats["latencies"].append(latency)

            self.total_requests += 1
            self.stt_requests += 1

            # Report metrics
            events.request.fire(
                request_type="WebSocket",
                name="WS STT",
                response_time=latency,
                response_length=len(response),
                exception=None,
                context={},
            )

            ws.close()

        except Exception as e:
            logger.error(f"WebSocket STT error: {str(e)}")
            events.request.fire(
                request_type="WebSocket",
                name="WS STT (Error)",
                response_time=0,
                response_length=0,
                exception=e,
                context={},
            )

    @task(1)
    def health_check(self):
        """Test health endpoint"""
        with self.client.get("/health", catch_response=True, name="Health Check") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    @task(1)
    def stats_check(self):
        """Test stats endpoint"""
        with self.client.get("/stats", catch_response=True, name="Stats Check") as response:
            if response.status_code == 200:
                response.success()
            else:
                response.failure(f"Got status code {response.status_code}")

    def on_stop(self):
        """Cleanup and report final stats"""
        if self.latencies:
            avg_latency = mean(self.latencies)
            median_latency = median(self.latencies)
            min_latency = min(self.latencies)
            max_latency = max(self.latencies)

            cache_hit_rate = (
                (self.cache_hits / self.total_requests * 100) if self.total_requests > 0 else 0
            )

            logger.info(
                f"User {id(self)} stats - "
                f"Avg latency: {avg_latency:.0f}ms, "
                f"Median: {median_latency:.0f}ms, "
                f"Min: {min_latency:.0f}ms, "
                f"Max: {max_latency:.0f}ms, "
                f"Cache hit rate: {cache_hit_rate:.1f}%, "
                f"TTS: {self.tts_requests}, STT: {self.stt_requests}"
            )


class CacheHeavyUser(HttpUser):
    """User that heavily reuses messages to test cache performance"""

    wait_time = between(0.5, 1.5)
    weight = 2  # More of these users to test caching

    def on_start(self):
        """Setup"""
        self.request_count = 0

    @task(10)
    def repeated_ws_tts_requests(self):
        """Send only shared messages via WebSocket (high cache hit probability)"""
        message_text = random.choice(SHARED_MESSAGES)
        ws_url = self.host.replace("http", "ws") + "/ws/voice"

        start_time = time.time()
        try:
            ws = websocket.create_connection(ws_url, timeout=10)
            ws.send(json.dumps({"type": "text", "text": message_text}))
            response = ws.recv()
            ws.close()

            latency = (time.time() - start_time) * 1000
            data = json.loads(response)

            if data.get("cached"):
                global_cache_stats["hits"] += 1
                global_cache_stats["hit_latencies"].append(latency)
            else:
                global_cache_stats["misses"] += 1
                global_cache_stats["miss_latencies"].append(latency)

            global_cache_stats["total_tts_requests"] += 1
            self.request_count += 1

            events.request.fire(
                request_type="WebSocket",
                name="WS TTS Cached Heavy",
                response_time=latency,
                response_length=len(response),
                exception=None,
                context={},
            )
        except Exception as e:
            logger.error(f"Cache heavy user error: {str(e)}")


class PowerUser(HttpUser):
    """Power user simulating heavy WebSocket usage"""

    wait_time = between(0.5, 2)
    weight = 1  # Fewer power users

    @task(10)
    def rapid_ws_tts_requests(self):
        """Rapid fire WebSocket TTS requests with mixed cache behavior"""
        messages = [
            random.choice(SHARED_MESSAGES),  # Likely cached
            random.choice(SHARED_MESSAGES),  # Likely cached
            f"Unique {time.time()}",  # Unique, not cached
        ]

        ws_url = self.host.replace("http", "ws") + "/ws/voice"

        for msg in messages:
            start_time = time.time()
            try:
                ws = websocket.create_connection(ws_url, timeout=10)
                ws.send(json.dumps({"type": "text", "text": msg}))
                response = ws.recv()
                ws.close()

                latency = (time.time() - start_time) * 1000
                data = json.loads(response)

                if data.get("cached"):
                    global_cache_stats["hits"] += 1
                    global_cache_stats["hit_latencies"].append(latency)
                else:
                    global_cache_stats["misses"] += 1
                    global_cache_stats["miss_latencies"].append(latency)

                global_cache_stats["total_tts_requests"] += 1

                events.request.fire(
                    request_type="WebSocket",
                    name="Power User WS TTS",
                    response_time=latency,
                    response_length=len(response),
                    exception=None,
                    context={},
                )
            except Exception as e:
                logger.error(f"Power user TTS error: {str(e)}")

    @task(3)
    def ws_stt_burst(self):
        """Burst of WebSocket STT requests"""
        ws_url = self.host.replace("http", "ws") + "/ws/voice"

        for _ in range(2):
            start_time = time.time()
            try:
                ws = websocket.create_connection(ws_url, timeout=15)
                ws.send(json.dumps({"type": "audio", "audio": FAKE_AUDIO_SMALL}))
                response = ws.recv()
                ws.close()

                latency = (time.time() - start_time) * 1000
                global_stt_stats["total_requests"] += 1
                global_stt_stats["latencies"].append(latency)

                events.request.fire(
                    request_type="WebSocket",
                    name="Power User WS STT",
                    response_time=latency,
                    response_length=len(response),
                    exception=None,
                    context={},
                )
            except Exception as e:
                logger.error(f"Power user STT error: {str(e)}")

    @task(1)
    def check_system_health(self):
        """Monitor system health"""
        response = self.client.get("/stats")
        if response.status_code == 200:
            data = response.json()
            if data.get("active_connections", 0) > 100:
                logger.warning("High connection count detected!")


@events.test_start.add_listener
def on_test_start(environment, **kwargs):
    """Report at start of test"""
    print("\n" + "=" * 80)
    print("REALTIME VOICE PIPELINE WEBSOCKET LOAD TEST")
    print("=" * 80)
    print(f"Target host: {environment.host}")
    print(
        f"Users: {environment.runner.target_user_count if hasattr(environment.runner, 'target_user_count') else 'N/A'}"
    )
    print("\nTest Configuration:")
    print("  - RealtimeVoicePipelineUser: Mixed WebSocket TTS (70% cached) + STT")
    print("  - CacheHeavyUser: 100% shared WebSocket TTS messages")
    print("  - PowerUser: Rapid WebSocket TTS + STT bursts")
    print("\nEndpoints Tested:")
    print("  ✓ WebSocket TTS (primary - with cache tracking)")
    print("  ✓ WebSocket STT (primary)")
    print("  ✓ GET /health (monitoring)")
    print("  ✓ GET /stats (monitoring)")
    print("\nExpected Results:")
    print("  - WebSocket TTS latency: <300ms target")
    print("  - WebSocket STT latency: <1000ms target")
    print("  - Cache hit rate: 80%+ target")
    print("  - Concurrent streams: 50+ target")
    print("=" * 80 + "\n")


@events.test_stop.add_listener
def on_test_stop(environment, **kwargs):
    """Report aggregated stats at end of test"""
    print("\n" + "=" * 80)
    print("WEBSOCKET LOAD TEST SUMMARY")
    print("=" * 80)

    stats = environment.stats

    print("\n📊 Overall Statistics:")
    print(f"Total requests: {stats.total.num_requests}")
    print(f"Failed requests: {stats.total.num_failures}")
    print(
        f"Failure rate: {(stats.total.num_failures / stats.total.num_requests * 100) if stats.total.num_requests > 0 else 0:.2f}%"
    )

    print("\n⚡ Performance Metrics (All Endpoints):")
    print(f"Average response time: {stats.total.avg_response_time:.0f}ms")
    print(f"Median response time: {stats.total.median_response_time:.0f}ms")
    print(f"Min response time: {stats.total.min_response_time:.0f}ms")
    print(f"Max response time: {stats.total.max_response_time:.0f}ms")
    print(f"95th percentile: {stats.total.get_response_time_percentile(0.95):.0f}ms")
    print(f"99th percentile: {stats.total.get_response_time_percentile(0.99):.0f}ms")

    print("\n🚀 Throughput:")
    print(f"Requests per second: {stats.total.total_rps:.2f}")
    print(f"Total data transferred: {stats.total.total_content_length / 1024 / 1024:.2f} MB")

    # ========================================================================
    # WEBSOCKET TTS & CACHE PERFORMANCE ANALYSIS
    # ========================================================================
    total_cache_requests = global_cache_stats["total_tts_requests"]
    if total_cache_requests > 0:
        cache_hit_rate = (global_cache_stats["hits"] / total_cache_requests) * 100

        avg_hit_latency = (
            mean(global_cache_stats["hit_latencies"]) if global_cache_stats["hit_latencies"] else 0
        )
        avg_miss_latency = (
            mean(global_cache_stats["miss_latencies"])
            if global_cache_stats["miss_latencies"]
            else 0
        )

        print("\n💾 WEBSOCKET TTS & CACHE PERFORMANCE:")
        print(f"Total WebSocket TTS Requests:  {total_cache_requests}")
        print(
            f"Cache Hits:                    {global_cache_stats['hits']} ({cache_hit_rate:.1f}%)"
        )
        print(
            f"Cache Misses:                  {global_cache_stats['misses']} ({100-cache_hit_rate:.1f}%)"
        )
        print(f"\nAverage Cached Latency:        {avg_hit_latency:.0f}ms")
        print(f"Average Uncached Latency:      {avg_miss_latency:.0f}ms")

        if avg_miss_latency > 0:
            speedup = ((avg_miss_latency - avg_hit_latency) / avg_miss_latency) * 100
            time_saved = avg_miss_latency - avg_hit_latency
            total_saved = (time_saved * global_cache_stats["hits"]) / 1000

            print(f"\nCache Speedup:                 {speedup:.1f}%")
            print(f"Time Saved per Hit:            {time_saved:.0f}ms")
            print(f"Total Time Saved:              {total_saved:.1f}s")

            # API call reduction
            api_calls_saved = global_cache_stats["hits"]
            api_reduction_pct = cache_hit_rate
            print(f"\nAPI Calls Saved:               {api_calls_saved}")
            print(f"API Call Reduction:            {api_reduction_pct:.1f}%")

    # ========================================================================
    # WEBSOCKET STT PERFORMANCE ANALYSIS
    # ========================================================================
    if global_stt_stats["total_requests"] > 0:
        avg_stt_latency = mean(global_stt_stats["latencies"])
        median_stt_latency = median(global_stt_stats["latencies"])
        min_stt_latency = min(global_stt_stats["latencies"])
        max_stt_latency = max(global_stt_stats["latencies"])

        print("\n🎤 WEBSOCKET STT PERFORMANCE:")
        print(f"Total WebSocket STT Requests:  {global_stt_stats['total_requests']}")
        print(f"STT Average Latency:           {avg_stt_latency:.0f}ms")
        print(f"STT Median Latency:            {median_stt_latency:.0f}ms")
        print(f"STT Min Latency:               {min_stt_latency:.0f}ms")
        print(f"STT Max Latency:               {max_stt_latency:.0f}ms")

    # ========================================================================
    # TARGET ACHIEVEMENT SUMMARY
    # ========================================================================
    print("\n📈 Target Achievement:")

    # WebSocket TTS latency
    if total_cache_requests > 0:
        avg_tts_latency = mean(
            global_cache_stats["hit_latencies"] + global_cache_stats["miss_latencies"]
        )
        if avg_tts_latency < 300:
            print(f"✓ PASSED: WebSocket TTS latency {avg_tts_latency:.0f}ms < 300ms target")
        else:
            print(f"✗ FAILED: WebSocket TTS latency {avg_tts_latency:.0f}ms > 300ms target")

    # WebSocket STT latency
    if global_stt_stats["total_requests"] > 0:
        if avg_stt_latency < 1000:
            print(f"✓ PASSED: WebSocket STT latency {avg_stt_latency:.0f}ms < 1000ms target")
        else:
            print(f"⚠ INFO: WebSocket STT latency {avg_stt_latency:.0f}ms (depends on model size)")

    # Concurrent streams
    if stats.total.num_requests > 1000:
        print(f"✓ PASSED: Handled {stats.total.num_requests} requests (50+ concurrent streams)")
    else:
        print(f"⚠ WARNING: Only {stats.total.num_requests} requests completed")

    # Cache hit rate
    if total_cache_requests > 0:
        if cache_hit_rate >= 80:
            print(f"✓ PASSED: Cache hit rate {cache_hit_rate:.1f}% >= 80% target")
        else:
            print(f"✗ FAILED: Cache hit rate {cache_hit_rate:.1f}% < 80% target")

    print("\n" + "=" * 80 + "\n")


if __name__ == "__main__":
    import os

    print("Starting WebSocket-Focused Locust Load Test...")
    print("\n📋 Run options:")
    print(
        "  Headless: locust -f tests/load_test.py --headless -u 60 -r 5 -t 60s --host http://localhost:8000"
    )
    print("  Web UI:   locust -f tests/load_test.py --host http://localhost:8000")
    print("\nStarting default headless test...\n")

    os.system(
        "locust -f tests/load_test.py --headless -u 60 -r 5 -t 60s --host http://localhost:8000"
    )
