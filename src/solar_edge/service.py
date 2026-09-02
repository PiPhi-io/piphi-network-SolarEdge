from __future__ import annotations

import asyncio
from collections.abc import Callable
from contextlib import suppress
from dataclasses import dataclass
from time import monotonic
from typing import Any

from fastapi import HTTPException
from piphi_runtime_kit_python import schedule_telemetry_delivery

from .schemas import DeviceConfig
from .solaredge_client import MonitoringApiClient, SolarEdgeClient, SolarEdgeReading


@dataclass(slots=True)
class ActiveSession:
    config: DeviceConfig
    client: SolarEdgeClient
    entry: dict[str, Any]
    credentials_key: tuple[int, str]
    last_summary_poll: float = 0.0


class SolarEdgeRuntimeService:
    """Own one quota-conscious SolarEdge client and polling task."""

    def __init__(self, *, registry, runtime, telemetry, client_factory: Callable[[], SolarEdgeClient] = MonitoringApiClient):
        self.registry = registry
        self.runtime = runtime
        self.telemetry = telemetry
        self.client_factory = client_factory
        self._active: ActiveSession | None = None
        self._poll_task: asyncio.Task[None] | None = None
        self._lock = asyncio.Lock()

    @property
    def active_config_id(self) -> str | None:
        return str(self._active.entry["config_id"]) if self._active else None

    async def configure(self, config: DeviceConfig, entry: dict[str, Any]) -> None:
        async with self._lock:
            if self.active_config_id is not None and self.active_config_id != str(entry["config_id"]):
                raise HTTPException(status_code=409, detail={"error": "instance_limit_reached", "message": "This release supports one SolarEdge site per runtime.", "maximum_instances": 1})
            key = (config.site_id, config.secret_api_key())
            if self._active and self._active.credentials_key == key:
                self._active.config = config
                self._active.entry = entry
                return
            await self._stop_locked()
            client = self.client_factory()
            try:
                await client.authenticate(config)
                self._active = ActiveSession(config=config, client=client, entry=entry, credentials_key=key)
                await self._refresh_locked(force_summary=True)
            except Exception:
                await client.close()
                self._active = None
                raise
            self._poll_task = asyncio.create_task(self._poll_loop(), name="solaredge-poller")

    async def refresh(self, *, force_summary: bool = True) -> dict[str, Any]:
        async with self._lock:
            if self._active is None:
                raise HTTPException(status_code=409, detail="SolarEdge is not configured")
            return await self._refresh_locked(force_summary=force_summary)

    async def remove(self, config_id: str) -> bool:
        async with self._lock:
            if self.active_config_id != str(config_id):
                return False
            await self._stop_locked()
            return True

    async def close(self) -> None:
        async with self._lock:
            await self._stop_locked()

    async def _stop_locked(self) -> None:
        task, self._poll_task = self._poll_task, None
        if task is not None and task is not asyncio.current_task():
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        if self._active is not None:
            await self._active.client.close()
        self._active = None

    async def _poll_loop(self) -> None:
        while self._active is not None:
            active = self._active
            await asyncio.sleep(active.config.poll_interval_seconds)
            try:
                async with self._lock:
                    if self._active is not active:
                        return
                    await self._refresh_locked(force_summary=False)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.registry.update_state(str(active.entry["config_id"]), {"connected": False, "error": str(exc)}, device_id=str(active.entry["device_id"]))

    async def _refresh_locked(self, *, force_summary: bool) -> dict[str, Any]:
        assert self._active is not None
        active = self._active
        now = monotonic()
        include_summary = force_summary or now - active.last_summary_poll >= active.config.summary_interval_seconds
        reading = await active.client.read(include_summary=include_summary)
        if include_summary:
            active.last_summary_poll = now
        state = reading_to_state(reading)
        config_id, device_id = str(active.entry["config_id"]), str(active.entry["device_id"])
        self.registry.update_state(config_id, state, device_id=device_id)
        schedule_telemetry_delivery(
            process_state=self.runtime.process_state, telemetry_client=self.telemetry,
            auth_context=self.runtime.auth, config_id=config_id, device_id=device_id,
            container_id=active.entry.get("container_id"),
            metrics={key: value for key, value in state.items() if isinstance(value, (bool, int, float))},
            units=TELEMETRY_UNITS,
        )
        return state


TELEMETRY_UNITS = {
    "production_power_w": "W", "consumption_power_w": "W", "grid_power_w": "W",
    "battery_power_w": "W", "battery_soc_percent": "%", "today_energy_kwh": "kWh",
    "month_energy_kwh": "kWh", "year_energy_kwh": "kWh", "lifetime_energy_kwh": "kWh",
}


def reading_to_state(reading: SolarEdgeReading) -> dict[str, Any]:
    return {
        "connected": True, "site_id": reading.site_id, "site_name": reading.site_name,
        "site_status": reading.site_status, "last_update": reading.last_update,
        "production_power_w": reading.production_power_w,
        "consumption_power_w": reading.consumption_power_w, "grid_power_w": reading.grid_power_w,
        "battery_power_w": reading.battery_power_w, "battery_soc_percent": reading.battery_soc_percent,
        "today_energy_kwh": reading.today_energy_kwh, "month_energy_kwh": reading.month_energy_kwh,
        "year_energy_kwh": reading.year_energy_kwh, "lifetime_energy_kwh": reading.lifetime_energy_kwh,
        "lifetime_revenue": reading.lifetime_revenue,
    }
