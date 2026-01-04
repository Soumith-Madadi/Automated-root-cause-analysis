"""Mock microservice that can inject latency and report metrics."""
import asyncio
import os
import time
from collections import deque
from datetime import datetime, timezone
from typing import Optional, Dict, Any
import aiohttp
from fastapi import FastAPI, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

app = FastAPI(title="Mock Service")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global state
latency_offset_ms: float = 0.0
latency_reset_time: Optional[float] = None
request_times: deque = deque(maxlen=100)  # Rolling window of request latencies
request_count: int = 0
start_time: float = time.time()
api_url: str = os.getenv("API_URL", "http://localhost:8000")
service_name: str = os.getenv("SERVICE_NAME", "mock-service")
metrics_task: Optional[asyncio.Task] = None
latency_ramp_task: Optional[asyncio.Task] = None
latency_ramp_start_time: Optional[float] = None
latency_ramp_target_ms: float = 0.0
latency_ramp_duration_seconds: float = 60.0
extra_processing_ramp_start_time: Optional[float] = None
extra_processing_ramp_duration_seconds: float = 60.0
extra_processing_ramp_target_ms: float = 300.0
extra_processing_ramp_current_ms: float = 0.0  # Current ramp value (for smooth transitions)
extra_processing_ramp_direction: int = 1  # 1 for ramping up, -1 for ramping down

# Feature flags and configs
feature_flags: Dict[str, bool] = {
    "enable_extra_processing": False,
    "enable_debug_mode": False,
}
configs: Dict[str, Any] = {
    "cache.enabled": True,
    "retry.max_attempts": 1,
    "processing.batch_size": 10,
}


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy", "service": service_name}


@app.get("/api/users")
async def get_users():
    """Simulated API endpoint with configurable latency."""
    global request_count
    
    start = time.time()
    request_count += 1
    
    # Apply side effects from feature flags and configs
    # Feature flag: enable_extra_processing gradually increases processing delay to 300ms over 60 seconds
    if feature_flags.get("enable_extra_processing", False):
        # Calculate current latency based on ramp progress (same logic as get_demo_state)
        current_extra_processing_ms = 0.0
        
        if extra_processing_ramp_start_time is not None:
            elapsed = time.time() - extra_processing_ramp_start_time
            progress = min(elapsed / extra_processing_ramp_duration_seconds, 1.0)
            
            if extra_processing_ramp_direction == 1:
                # Ramping up
                start_value = extra_processing_ramp_current_ms
                target_value = extra_processing_ramp_target_ms
                current_extra_processing_ms = start_value + (target_value - start_value) * progress
            else:
                # Ramping down (shouldn't happen if flag is enabled, but handle it)
                start_value = extra_processing_ramp_current_ms
                target_value = 0.0
                current_extra_processing_ms = start_value + (target_value - start_value) * progress
        
        # Add some variation to make it more realistic
        variation_ms = (request_count % 20) * 0.5  # 0-10ms variation
        total_processing_ms = current_extra_processing_ms + variation_ms
        await asyncio.sleep(total_processing_ms / 1000.0)
    
    # Config: cache.enabled=false causes slower responses (cache miss simulation)
    if not configs.get("cache.enabled", True):
        cache_miss_delay = 50 + (request_count % 30)  # 50-80ms
        await asyncio.sleep(cache_miss_delay / 1000.0)
    
    # Config: retry.max_attempts > 1 causes retry delays
    max_retries = configs.get("retry.max_attempts", 1)
    if max_retries > 1:
        # Simulate occasional failures requiring retries
        if request_count % 5 == 0:  # 20% failure rate
            retry_delay = 100 * (max_retries - 1)  # 100ms per retry
            await asyncio.sleep(retry_delay / 1000.0)
    
    # Legacy: Add injected latency (for backward compatibility)
    if latency_offset_ms > 0:
        await asyncio.sleep(latency_offset_ms / 1000.0)
    
    # Simulate some processing time (10-50ms baseline)
    processing_time = 0.010 + (request_count % 40) * 0.001
    await asyncio.sleep(processing_time)
    
    elapsed_ms = (time.time() - start) * 1000
    request_times.append(elapsed_ms)
    
    return {
        "users": [
            {"id": 1, "name": "Alice"},
            {"id": 2, "name": "Bob"},
        ],
        "latency_ms": round(elapsed_ms, 2)
    }


@app.post("/inject-latency")
async def inject_latency(
    ms: float = Query(..., description="Latency in milliseconds"),
    duration: int = Query(60, description="Duration in seconds")
):
    """Inject latency into all requests. [DEPRECATED: Use feature flags or config changes instead]"""
    global latency_offset_ms, latency_reset_time
    
    latency_offset_ms = ms
    latency_reset_time = time.time() + duration
    
    return {
        "status": "ok",
        "message": f"Injected {ms}ms latency for {duration} seconds",
        "latency_ms": ms,
        "duration_seconds": duration,
        "deprecated": True,
        "note": "Consider using /api/feature-flags or /api/config instead"
    }


@app.post("/reset")
async def reset():
    """Reset latency to normal."""
    global latency_offset_ms, latency_reset_time, latency_ramp_task, latency_ramp_start_time
    
    latency_offset_ms = 0.0
    latency_reset_time = None
    
    # Cancel any ongoing latency ramp
    if latency_ramp_task:
        latency_ramp_task.cancel()
        latency_ramp_task = None
        latency_ramp_start_time = None
    
    return {"status": "ok", "message": "Latency reset to normal"}


@app.post("/api/ramp-latency")
async def ramp_latency(
    target_ms: float = Query(300.0, description="Target latency in milliseconds"),
    duration_seconds: float = Query(60.0, description="Duration to reach target in seconds")
):
    """Gradually ramp latency to target over specified duration."""
    global latency_ramp_task, latency_ramp_start_time, latency_ramp_target_ms, latency_ramp_duration_seconds
    
    # Cancel any existing ramp task
    if latency_ramp_task:
        latency_ramp_task.cancel()
        try:
            await latency_ramp_task
        except asyncio.CancelledError:
            pass
    
    # Start new ramp
    latency_ramp_target_ms = target_ms
    latency_ramp_duration_seconds = duration_seconds
    latency_ramp_start_time = time.time()
    latency_ramp_task = asyncio.create_task(gradual_latency_ramp())
    
    return {
        "status": "ok",
        "message": f"Latency ramping to {target_ms}ms over {duration_seconds} seconds",
        "target_ms": target_ms,
        "duration_seconds": duration_seconds
    }


async def gradual_latency_ramp():
    """Background task to gradually increase latency over time."""
    global latency_offset_ms, latency_ramp_start_time, latency_ramp_target_ms, latency_ramp_duration_seconds
    
    start_latency = latency_offset_ms
    start_time = latency_ramp_start_time
    
    try:
        while True:
            await asyncio.sleep(0.1)  # Update every 100ms for smooth ramp
            
            if latency_ramp_start_time != start_time:
                # Ramp was reset/cancelled
                break
            
            elapsed = time.time() - start_time
            progress = min(elapsed / latency_ramp_duration_seconds, 1.0)
            
            # Linear interpolation from start to target
            latency_offset_ms = start_latency + (latency_ramp_target_ms - start_latency) * progress
            
            if progress >= 1.0:
                # Ramp complete
                latency_offset_ms = latency_ramp_target_ms
                break
                
    except asyncio.CancelledError:
        pass


# Feature flag endpoints
@app.get("/api/feature-flags")
async def list_feature_flags():
    """List all feature flags and their current state."""
    return {"feature_flags": feature_flags}


@app.get("/api/feature-flags/{flag_name}")
async def get_feature_flag(flag_name: str):
    """Get the current state of a feature flag."""
    if flag_name not in feature_flags:
        return JSONResponse(
            status_code=404,
            content={"error": f"Feature flag '{flag_name}' not found"}
        )
    return {"flag_name": flag_name, "enabled": feature_flags[flag_name]}


@app.post("/api/feature-flags/{flag_name}/toggle")
async def toggle_feature_flag(flag_name: str):
    """Toggle a feature flag on or off."""
    global feature_flags, extra_processing_ramp_start_time, extra_processing_ramp_current_ms, extra_processing_ramp_direction
    
    if flag_name not in feature_flags:
        return JSONResponse(
            status_code=404,
            content={"error": f"Feature flag '{flag_name}' not found"}
        )
    
    old_state = feature_flags[flag_name]
    feature_flags[flag_name] = not feature_flags[flag_name]
    
    # If enabling enable_extra_processing, start the gradual ramp up from current value
    if flag_name == "enable_extra_processing" and feature_flags[flag_name] and not old_state:
        # Calculate current ramp value (might be 0 if starting fresh, or partial if resuming)
        if extra_processing_ramp_start_time is not None:
            # We're resuming from an existing ramp, calculate where we are
            elapsed = time.time() - extra_processing_ramp_start_time
            progress = min(elapsed / extra_processing_ramp_duration_seconds, 1.0)
            if extra_processing_ramp_direction == 1:
                # Was ramping up, continue from current position
                start_value = extra_processing_ramp_current_ms
                target_value = extra_processing_ramp_target_ms
                extra_processing_ramp_current_ms = start_value + (target_value - start_value) * progress
            else:
                # Was ramping down, start from current position
                start_value = extra_processing_ramp_current_ms
                target_value = 0.0
                extra_processing_ramp_current_ms = max(0.0, start_value + (target_value - start_value) * progress)
        else:
            # Starting fresh, begin from 0
            extra_processing_ramp_current_ms = 0.0
        # Start ramping up from current value
        extra_processing_ramp_start_time = time.time()
        extra_processing_ramp_direction = 1
    # If disabling, start gradual ramp down from current value
    elif flag_name == "enable_extra_processing" and not feature_flags[flag_name] and old_state:
        # Calculate current ramp value at the moment of disabling
        if extra_processing_ramp_start_time is not None:
            elapsed = time.time() - extra_processing_ramp_start_time
            progress = min(elapsed / extra_processing_ramp_duration_seconds, 1.0)
            if extra_processing_ramp_direction == 1:
                # Was ramping up, capture current position
                start_value = extra_processing_ramp_current_ms
                target_value = extra_processing_ramp_target_ms
                extra_processing_ramp_current_ms = start_value + (target_value - start_value) * progress
            else:
                # Was ramping down, continue from current position
                start_value = extra_processing_ramp_current_ms
                target_value = 0.0
                extra_processing_ramp_current_ms = max(0.0, start_value + (target_value - start_value) * progress)
        else:
            # No active ramp, but flag was enabled, so we're at full target
            extra_processing_ramp_current_ms = extra_processing_ramp_target_ms
        # Start ramping down from current value
        extra_processing_ramp_start_time = time.time()
        extra_processing_ramp_direction = -1
    
    return {
        "status": "ok",
        "flag_name": flag_name,
        "enabled": feature_flags[flag_name],
        "message": f"Feature flag '{flag_name}' {'enabled' if feature_flags[flag_name] else 'disabled'}"
    }


@app.post("/api/feature-flags/{flag_name}")
async def set_feature_flag(flag_name: str, enabled: bool = Body(..., embed=True)):
    """Set a feature flag to a specific state."""
    global feature_flags, extra_processing_ramp_start_time
    
    if flag_name not in feature_flags:
        return JSONResponse(
            status_code=404,
            content={"error": f"Feature flag '{flag_name}' not found"}
        )
    
    old_state = feature_flags[flag_name]
    feature_flags[flag_name] = enabled
    
    # If enabling enable_extra_processing, start the gradual ramp
    if flag_name == "enable_extra_processing" and enabled and not old_state:
        extra_processing_ramp_start_time = time.time()
    # If disabling, reset the ramp
    elif flag_name == "enable_extra_processing" and not enabled:
        extra_processing_ramp_start_time = None
    
    return {
        "status": "ok",
        "flag_name": flag_name,
        "enabled": feature_flags[flag_name],
        "message": f"Feature flag '{flag_name}' set to {'enabled' if enabled else 'disabled'}"
    }


# Config endpoints
@app.get("/api/config")
async def list_configs():
    """List all configuration values."""
    return {"configs": configs}


@app.get("/api/config/{key}")
async def get_config(key: str):
    """Get the current value of a configuration key."""
    if key not in configs:
        return JSONResponse(
            status_code=404,
            content={"error": f"Config key '{key}' not found"}
        )
    return {"key": key, "value": configs[key]}


class ConfigValue(BaseModel):
    value: Any


@app.post("/api/config/{key}")
async def set_config(key: str, config_value: ConfigValue):
    """Set a configuration value."""
    global configs
    
    old_value = configs.get(key)
    configs[key] = config_value.value
    
    return {
        "status": "ok",
        "key": key,
        "old_value": old_value,
        "new_value": config_value.value,
        "message": f"Config '{key}' updated"
    }


# Demo state endpoint
@app.get("/api/demo")
async def get_demo_state():
    """Get current demo state (latency, flags, configs) for demo website."""
    global extra_processing_ramp_start_time, extra_processing_ramp_current_ms, extra_processing_ramp_direction, extra_processing_ramp_target_ms, extra_processing_ramp_duration_seconds
    
    # Calculate base latency from actual requests
    base_latency = calculate_p95_latency()
    
    # Calculate ramp latency based on current state
    ramp_latency_ms = 0.0
    
    if extra_processing_ramp_start_time is not None:
        elapsed = time.time() - extra_processing_ramp_start_time
        progress = min(elapsed / extra_processing_ramp_duration_seconds, 1.0)
        
        if extra_processing_ramp_direction == 1:
            # Ramping up: from start value to target
            start_value = extra_processing_ramp_current_ms
            target_value = extra_processing_ramp_target_ms
            ramp_latency_ms = start_value + (target_value - start_value) * progress
        else:
            # Ramping down: from start value to 0
            start_value = extra_processing_ramp_current_ms
            target_value = 0.0
            ramp_latency_ms = start_value + (target_value - start_value) * progress
        
        # If ramp is complete, clean up
        if progress >= 1.0:
            if extra_processing_ramp_direction == -1:
                # Ramp down complete, reset
                extra_processing_ramp_start_time = None
                extra_processing_ramp_current_ms = 0.0
                ramp_latency_ms = 0.0
            else:
                # Ramp up complete, set current to target and clear start time
                extra_processing_ramp_start_time = None
                extra_processing_ramp_current_ms = extra_processing_ramp_target_ms
                ramp_latency_ms = extra_processing_ramp_target_ms
    
    # Add ramp latency if we're actively ramping, or if flag is enabled and ramp is complete
    if extra_processing_ramp_start_time is not None:
        # We're actively ramping (up or down), always show the ramp
        current_latency = base_latency + ramp_latency_ms
    elif feature_flags.get("enable_extra_processing", False):
        # Flag is enabled and ramp is complete, show full target
        current_latency = base_latency + extra_processing_ramp_target_ms
    else:
        # Flag is disabled and no ramp, show base only
        current_latency = base_latency
    
    return {
        "service": service_name,
        "current_p95_latency_ms": round(current_latency, 2),
        "feature_flags": feature_flags,
        "configs": configs,
        "request_count": request_count,
        "status": "healthy"
    }


def calculate_p95_latency() -> float:
    """Calculate p95 latency from recent requests."""
    if len(request_times) < 5:
        return 50.0  # Default baseline
    
    sorted_times = sorted(request_times)
    p95_index = int(len(sorted_times) * 0.95)
    return sorted_times[p95_index]


def calculate_qps() -> float:
    """Calculate requests per second."""
    elapsed = time.time() - start_time
    if elapsed < 1:
        return 10.0  # Default
    return request_count / elapsed


async def report_metrics():
    """Background task to report metrics every 10 seconds."""
    global latency_reset_time, latency_offset_ms, extra_processing_ramp_start_time, extra_processing_ramp_current_ms, extra_processing_ramp_direction, extra_processing_ramp_target_ms, extra_processing_ramp_duration_seconds, feature_flags
    
    async with aiohttp.ClientSession() as session:
        while True:
            try:
                await asyncio.sleep(10)
                
                # Check if latency should be reset
                if latency_reset_time and time.time() >= latency_reset_time:
                    latency_offset_ms = 0.0
                    latency_reset_time = None
                
                # Calculate base metrics
                base_p95_latency = calculate_p95_latency()
                
                # Calculate ramp latency (same logic as get_demo_state)
                ramp_latency_ms = 0.0
                
                if extra_processing_ramp_start_time is not None:
                    elapsed = time.time() - extra_processing_ramp_start_time
                    progress = min(elapsed / extra_processing_ramp_duration_seconds, 1.0)
                    
                    if extra_processing_ramp_direction == 1:
                        # Ramping up
                        start_value = extra_processing_ramp_current_ms
                        target_value = extra_processing_ramp_target_ms
                        ramp_latency_ms = start_value + (target_value - start_value) * progress
                    else:
                        # Ramping down
                        start_value = extra_processing_ramp_current_ms
                        target_value = 0.0
                        ramp_latency_ms = start_value + (target_value - start_value) * progress
                    
                    # If ramp is complete, clean up
                    if progress >= 1.0:
                        if extra_processing_ramp_direction == -1:
                            # Ramp down complete, reset
                            extra_processing_ramp_start_time = None
                            extra_processing_ramp_current_ms = 0.0
                            ramp_latency_ms = 0.0
                        else:
                            # Ramp up complete, set current to target and clear start time
                            extra_processing_ramp_start_time = None
                            extra_processing_ramp_current_ms = extra_processing_ramp_target_ms
                            ramp_latency_ms = extra_processing_ramp_target_ms
                
                # Add ramp latency if we're actively ramping, or if flag is enabled and ramp is complete
                if extra_processing_ramp_start_time is not None:
                    # We're actively ramping (up or down), always show the ramp
                    p95_latency = base_p95_latency + ramp_latency_ms
                elif feature_flags.get("enable_extra_processing", False):
                    # Flag is enabled and ramp is complete, show full target
                    p95_latency = base_p95_latency + extra_processing_ramp_target_ms
                else:
                    # Flag is disabled and no ramp, show base only
                    p95_latency = base_p95_latency
                
                qps = calculate_qps()
                error_rate = 0.0  # Can be made configurable later
                
                # Prepare metrics
                now = datetime.now(timezone.utc)
                metrics = [
                    {
                        "ts": now.isoformat(),
                        "service": service_name,
                        "metric": "p95_latency_ms",
                        "value": p95_latency,
                        "tags": {}
                    },
                    {
                        "ts": now.isoformat(),
                        "service": service_name,
                        "metric": "qps",
                        "value": qps,
                        "tags": {}
                    },
                    {
                        "ts": now.isoformat(),
                        "service": service_name,
                        "metric": "error_rate",
                        "value": error_rate,
                        "tags": {}
                    }
                ]
                
                # Send to API
                async with session.post(
                    f"{api_url}/ingest/metrics",
                    json={"points": metrics},
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as resp:
                    if resp.status == 200:
                        print(f"[{now.isoformat()}] Reported metrics: p95={p95_latency:.1f}ms, qps={qps:.1f}")
                    else:
                        text = await resp.text()
                        print(f"[{now.isoformat()}] Failed to report metrics: {resp.status} - {text}")
                        
            except Exception as e:
                print(f"Error reporting metrics: {e}")
                await asyncio.sleep(10)


@app.on_event("startup")
async def startup():
    """Start background metrics reporting task."""
    global metrics_task, feature_flags, extra_processing_ramp_start_time, extra_processing_ramp_current_ms
    
    # Ensure enable_extra_processing is disabled by default on startup
    feature_flags["enable_extra_processing"] = False
    extra_processing_ramp_start_time = None
    extra_processing_ramp_current_ms = 0.0
    
    metrics_task = asyncio.create_task(report_metrics())
    print(f"Mock service '{service_name}' started. Metrics will be reported to {api_url}")
    print(f"Feature flags initialized: {feature_flags}")


@app.on_event("shutdown")
async def shutdown():
    """Stop background tasks."""
    global metrics_task, latency_ramp_task
    if metrics_task:
        metrics_task.cancel()
        try:
            await metrics_task
        except asyncio.CancelledError:
            pass
    if latency_ramp_task:
        latency_ramp_task.cancel()
        try:
            await latency_ramp_task
        except asyncio.CancelledError:
            pass


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)




