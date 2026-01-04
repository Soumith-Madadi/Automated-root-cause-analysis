#!/usr/bin/env python3
"""Script to inject latency into the mock service."""
import argparse
import asyncio
import aiohttp
import sys


async def inject_latency(service_url: str, latency_ms: float, duration: int):
    """Inject latency into the mock service."""
    url = f"{service_url}/inject-latency"
    params = {
        "ms": latency_ms,
        "duration": duration
    }
    
    try:
        async with aiohttp.ClientSession() as session:
            print(f"Injecting {latency_ms}ms latency for {duration} seconds...")
            async with session.post(url, params=params, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"[OK] Latency injected successfully")
                    print(f"    Service: {service_url}")
                    print(f"    Latency: {latency_ms}ms")
                    print(f"    Duration: {duration} seconds")
                    return True
                else:
                    text = await resp.text()
                    print(f"[ERROR] Failed to inject latency: {resp.status}")
                    print(f"    Response: {text}")
                    return False
    except Exception as e:
        print(f"[ERROR] Failed to connect to mock service: {e}")
        print(f"    Make sure the mock service is running at {service_url}")
        return False


async def reset_latency(service_url: str):
    """Reset latency to normal."""
    url = f"{service_url}/reset"
    
    try:
        async with aiohttp.ClientSession() as session:
            print("Resetting latency to normal...")
            async with session.post(url, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                if resp.status == 200:
                    print("[OK] Latency reset successfully")
                    return True
                else:
                    text = await resp.text()
                    print(f"[ERROR] Failed to reset latency: {resp.status}")
                    print(f"    Response: {text}")
                    return False
    except Exception as e:
        print(f"[ERROR] Failed to connect to mock service: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description="Inject latency into mock service")
    parser.add_argument(
        "--service",
        default="http://localhost:8080",
        help="Mock service URL (default: http://localhost:8080)"
    )
    parser.add_argument(
        "--latency",
        type=float,
        default=500.0,
        help="Latency in milliseconds (default: 500)"
    )
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Duration in seconds (default: 60)"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset latency to normal instead of injecting"
    )
    
    args = parser.parse_args()
    
    if args.reset:
        success = await reset_latency(args.service)
    else:
        success = await inject_latency(args.service, args.latency, args.duration)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    asyncio.run(main())




