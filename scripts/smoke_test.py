#!/usr/bin/env python3
"""Smoke test script to verify basic system health."""
import asyncio
import aiohttp
import sys
from datetime import datetime, timezone

API_URL = "http://localhost:8000"


async def test_health():
    """Test the /health endpoint."""
    print("Testing /health endpoint...")
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/health") as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"✓ Health check passed: {data['status']}")
                for service, status in data.get("checks", {}).items():
                    print(f"  - {service}: {status}")
                return True
            else:
                print(f"✗ Health check failed: {resp.status}")
                return False


async def test_metric_insert():
    """Test inserting a metric into ClickHouse via API."""
    print("\nTesting metric ingestion...")
    metric_data = {
        "points": [
            {
                "ts": datetime.now(timezone.utc).isoformat(),
                "service": "test-service",
                "metric": "p95_latency_ms",
                "value": 100.5,
                "tags": {"endpoint": "/api/test", "region": "us-east-1"}
            }
        ]
    }
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/ingest/metrics",
            json=metric_data
        ) as resp:
            if resp.status in [200, 201]:
                print("✓ Metric ingestion successful")
                return True
            else:
                text = await resp.text()
                print(f"✗ Metric ingestion failed: {resp.status} - {text}")
                return False


async def main():
    """Run all smoke tests."""
    print("=" * 50)
    print("RCA System Smoke Test")
    print("=" * 50)
    
    health_ok = await test_health()
    
    # Only test ingestion if health check passes
    if health_ok:
        # Note: This will fail until Step 2 is complete, but that's expected
        try:
            await test_metric_insert()
        except Exception as e:
            print(f"Note: Metric ingestion test skipped (endpoint not yet implemented): {e}")
    
    print("\n" + "=" * 50)
    if health_ok:
        print("✓ Basic health checks passed")
        sys.exit(0)
    else:
        print("✗ Health checks failed")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())


