#!/usr/bin/env python3
"""Manually trigger RCA for an incident."""
import asyncio
import aiohttp
import sys

API_URL = "http://localhost:8000"


async def trigger_rca(incident_id: str):
    """Trigger RCA rerun for an incident."""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"{API_URL}/incidents/{incident_id}/rerun_rca"
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                print(f"[OK] RCA triggered: {data.get('message')}")
                print(f"    Suspects should appear in the UI within 10-30 seconds")
                return True
            else:
                text = await resp.text()
                print(f"[ERROR] Failed to trigger RCA: {resp.status} - {text}")
                return False


async def list_incidents():
    """List all incidents to help find an ID."""
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}/incidents") as resp:
            if resp.status == 200:
                data = await resp.json()
                incidents = data.get("incidents", [])
                if incidents:
                    print("Available incidents:")
                    for inc in incidents:
                        print(f"  - {inc['id']}: {inc['title']} ({inc['status']})")
                    return incidents
                else:
                    print("No incidents found. Run seed_demo_data.py first.")
                    return []
            else:
                print(f"[ERROR] Failed to list incidents: {resp.status}")
                return []


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/trigger_rca.py <incident_id>")
        print("       python scripts/trigger_rca.py --list  (to see available incidents)")
        sys.exit(1)
    
    if sys.argv[1] == "--list":
        asyncio.run(list_incidents())
    else:
        asyncio.run(trigger_rca(sys.argv[1]))




