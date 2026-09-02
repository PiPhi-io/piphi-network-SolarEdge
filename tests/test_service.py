from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from solar_edge import service as service_module
from solar_edge.schemas import DeviceConfig
from solar_edge.service import SolarEdgeRuntimeService
from solar_edge.solaredge_client import SolarEdgeReading


class FakeRegistry:
    def __init__(self):
        self.states = {}

    def update_state(self, config_id, state, *, device_id):
        self.states[config_id] = {**state, "device_id": device_id}


class FakeClient:
    def __init__(self):
        self.auth_calls = 0
        self.read_calls = []
        self.closed = False

    async def authenticate(self, _config):
        self.auth_calls += 1

    async def read(self, *, include_summary):
        self.read_calls.append(include_summary)
        return SolarEdgeReading(1234567, "Home solar", "Active", None, "W", 3200.0, 1400.0, -1800.0, None, None, today_energy_kwh=12.4)

    async def close(self):
        self.closed = True


def config(config_id="site-one", site_id=1234567):
    return DeviceConfig(id=config_id, site_id=site_id, api_key="secret", poll_interval_seconds=3600)


@pytest.mark.anyio
async def test_service_reuses_client_delivers_telemetry_and_enforces_instance_limit(monkeypatch):
    deliveries = []
    monkeypatch.setattr(service_module, "schedule_telemetry_delivery", lambda **kwargs: deliveries.append(kwargs))
    clients = []

    def factory():
        result = FakeClient()
        clients.append(result)
        return result

    registry = FakeRegistry()
    service = SolarEdgeRuntimeService(
        registry=registry, runtime=SimpleNamespace(process_state=object(), auth=object()),
        telemetry=object(), client_factory=factory,
    )
    entry = {"config_id": "site-one", "device_id": "solaredge-1234567", "container_id": "container-1"}
    await service.configure(config(), entry)
    await service.configure(config(), entry)

    assert len(clients) == 1
    assert clients[0].auth_calls == 1
    assert clients[0].read_calls == [True]
    assert registry.states["site-one"]["grid_power_w"] == -1800.0
    assert deliveries[0]["metrics"]["today_energy_kwh"] == 12.4

    with pytest.raises(HTTPException) as exc_info:
        await service.configure(config("site-two", 7654321), {"config_id": "site-two", "device_id": "solaredge-7654321"})
    assert exc_info.value.status_code == 409
    assert exc_info.value.detail["error"] == "instance_limit_reached"

    await service.close()
    assert clients[0].closed is True
