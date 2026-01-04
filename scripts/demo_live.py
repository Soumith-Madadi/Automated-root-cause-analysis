#!/usr/bin/env python3
"""Live demo script that triggers operational changes and lets the system monitor autonomously."""
import asyncio
import aiohttp
import time
import webbrowser
from datetime import datetime, timedelta, timezone


API_URL = "http://localhost:8000"
MOCK_SERVICE_URL = "http://localhost:8080"
SERVICE_NAME = "mock-service"
BASELINE_POINTS = 30  # Number of baseline data points to seed
BASELINE_INTERVAL_SECONDS = 10  # 10 seconds between points (matches mock service reporting)


async def wait_for_health(url: str, service_name: str, max_wait: int = 60):
    """Wait for a service to be healthy."""
    print(f"Waiting for {service_name} to be healthy...")
    start = time.time()
    
    async with aiohttp.ClientSession() as session:
        while time.time() - start < max_wait:
            try:
                async with session.get(f"{url}/health", timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        print(f"[OK] {service_name} is healthy")
                        return True
            except Exception:
                pass
            
            await asyncio.sleep(2)
    
    print(f"[ERROR] {service_name} did not become healthy within {max_wait} seconds")
    return False


async def seed_baseline_metrics():
    """Seed baseline metrics for the mock service so detector has historical data."""
    print(f"\n{'='*60}")
    print("STEP 1: Seeding baseline metrics")
    print(f"{'='*60}")
    print(f"Seeding {BASELINE_POINTS} baseline data points for {SERVICE_NAME}...")
    print("    (Detector needs ~20 data points before it can detect anomalies)")
    
    now = datetime.now(timezone.utc)
    baseline_metrics = []
    
    # Generate baseline metrics going back in time
    # Normal latency: 40-60ms (baseline)
    # QPS: 8-12 requests/second
    # Error rate: 0%
    for i in range(BASELINE_POINTS):
        ts = now - timedelta(seconds=(BASELINE_POINTS - i) * BASELINE_INTERVAL_SECONDS)
        baseline_metrics.extend([
            {
                "ts": ts.isoformat(),
                "service": SERVICE_NAME,
                "metric": "p95_latency_ms",
                "value": 45.0 + (i % 10) * 1.5,  # Vary between 45-60ms
                "tags": {}
            },
            {
                "ts": ts.isoformat(),
                "service": SERVICE_NAME,
                "metric": "qps",
                "value": 10.0 + (i % 5) * 0.4,  # Vary between 10-12
                "tags": {}
            },
            {
                "ts": ts.isoformat(),
                "service": SERVICE_NAME,
                "metric": "error_rate",
                "value": 0.0,
                "tags": {}
            }
        ])
    
    # Send metrics in batches
    batch_size = 30
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(baseline_metrics), batch_size):
            batch = baseline_metrics[i:i + batch_size]
            try:
                async with session.post(
                    f"{API_URL}/ingest/metrics",
                    json={"points": batch},
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as resp:
                    if resp.status == 200:
                        print(f"    Seeded batch {i // batch_size + 1} ({len(batch)} points)")
                    else:
                        text = await resp.text()
                        print(f"    [WARNING] Failed to seed batch: {resp.status} - {text}")
            except Exception as e:
                print(f"    [WARNING] Error seeding batch: {e}")
    
    print(f"[OK] Baseline metrics seeded ({len(baseline_metrics)} total points)")
    print("    Waiting 5 seconds for metrics to be processed...")
    await asyncio.sleep(5)


async def trigger_operational_change():
    """Trigger a realistic operational change (feature flag toggle or config change)."""
    print(f"\n{'='*60}")
    print("STEP 2: Triggering operational change")
    print(f"{'='*60}")
    print("Making a normal operational change that will cause latency as a side effect...")
    
    # Step 1: Toggle feature flag on mock service (causes latency)
    url = f"{MOCK_SERVICE_URL}/api/feature-flags/enable_extra_processing/toggle"
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    flag_enabled = data.get('enabled', False)
                    print(f"[OK] Feature flag toggled: {data.get('flag_name')} = {flag_enabled}")
                    print(f"    This will add 300-500ms processing delay to all requests")
                    
                    # Step 2: Ingest the change via API so it can be tracked as a suspect
                    now = datetime.now(timezone.utc)
                    flag_change_payload = {
                        "ts": now.isoformat(),
                        "flag_name": "enable_extra_processing",
                        "service": SERVICE_NAME,
                        "old_state": {"enabled": not flag_enabled},
                        "new_state": {"enabled": flag_enabled}
                    }
                    
                    try:
                        async with session.post(
                            f"{API_URL}/ingest/flag_changes",
                            json=flag_change_payload,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as api_resp:
                            if api_resp.status == 200:
                                print(f"[OK] Flag change ingested into RCA system")
                                print(f"    The system will detect this as an anomaly and create an incident autonomously")
                            else:
                                print(f"[WARNING] Failed to ingest flag change: {api_resp.status}")
                    except Exception as e:
                        print(f"[WARNING] Failed to ingest flag change: {e}")
                    
                    return True
                else:
                    text = await resp.text()
                    print(f"[ERROR] Failed to toggle feature flag: {resp.status} - {text}")
                    # Fallback: try config change
                    return await trigger_config_change()
        except Exception as e:
            print(f"[ERROR] Failed to connect to mock service: {e}")
            print(f"    Make sure the mock service is running at {MOCK_SERVICE_URL}")
            return False


async def trigger_config_change():
    """Fallback: Trigger a config change instead."""
    url = f"{MOCK_SERVICE_URL}/api/config/cache.enabled"
    payload = {"value": False}
    
    async with aiohttp.ClientSession() as session:
        try:
            async with session.post(
                url, 
                json=payload,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[OK] Config changed: {data.get('key')} = {data.get('new_value')}")
                    print(f"    This will disable caching, causing slower responses")
                    
                    # Ingest the change via API
                    now = datetime.now(timezone.utc)
                    config_change_payload = {
                        "ts": now.isoformat(),
                        "service": SERVICE_NAME,
                        "key": "cache.enabled",
                        "old_value_hash": "enabled",
                        "new_value_hash": "disabled",
                        "diff_summary": "Cache disabled",
                        "source": "demo"
                    }
                    
                    try:
                        async with session.post(
                            f"{API_URL}/ingest/config_changes",
                            json=config_change_payload,
                            timeout=aiohttp.ClientTimeout(total=10)
                        ) as api_resp:
                            if api_resp.status == 200:
                                print(f"[OK] Config change ingested into RCA system")
                            else:
                                print(f"[WARNING] Failed to ingest config change: {api_resp.status}")
                    except Exception as e:
                        print(f"[WARNING] Failed to ingest config change: {e}")
                    
                    return True
                else:
                    text = await resp.text()
                    print(f"[ERROR] Failed to change config: {resp.status} - {text}")
                    return False
        except Exception as e:
            print(f"[ERROR] Failed to change config: {e}")
            return False




async def main():
    """Main demo orchestration."""
    print("="*60)
    print("LIVE DEMO: Real-time Root Cause Analysis")
    print("="*60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    # Step 0: Wait for services
    print(f"{'='*60}")
    print("STEP 0: Checking service health")
    print(f"{'='*60}")
    
    api_healthy = await wait_for_health(API_URL, "API")
    mock_healthy = await wait_for_health(MOCK_SERVICE_URL, "Mock Service")
    
    if not api_healthy or not mock_healthy:
        print("\n[ERROR] Services are not healthy. Please start them with:")
        print("    docker compose up -d")
        return
    
    # Step 1: Seed baseline metrics
    await seed_baseline_metrics()
    
    # Step 2: Trigger operational change
    if not await trigger_operational_change():
        return
    
    # Step 3: Open browser to demo website
    print(f"\n{'='*60}")
    print("STEP 3: Opening demo website")
    print(f"{'='*60}")
    
    demo_url = "http://localhost:3001/demo"
    print(f"[OK] Opening demo website: {demo_url}")
    
    try:
        webbrowser.open(demo_url)
    except Exception as e:
        print(f"[WARNING] Could not open browser automatically: {e}")
        print(f"    Please open manually: {demo_url}")
    
    print(f"\n{'='*60}")
    print("DEMO STARTED")
    print(f"{'='*60}")
    print(f"Demo Website: {demo_url}")
    print(f"RCA Dashboard: http://localhost:3001")
    print(f"Grafana: http://localhost:3000 (admin/admin)")
    print(f"\nThe system is now monitoring autonomously.")
    print(f"Watch the dashboard for:")
    print(f"  - Anomalies to be detected (30-60 seconds)")
    print(f"  - Incidents to be created (1-2 minutes)")
    print(f"  - Suspects to be generated (10-30 seconds after incident)")
    print(f"\nThe demo website will show slow responses as a side effect of the change.")
    print(f"The activity log will show real-time system events.")


if __name__ == "__main__":
    asyncio.run(main())

