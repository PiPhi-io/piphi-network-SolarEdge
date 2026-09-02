# PiPhi Network SolarEdge

Read-only SolarEdge Monitoring integration built with `piphi-runtime-kit-python` and the `piphi-network-create` cloud-polling scaffold.

It provides live solar production, home consumption, signed grid import/export, optional battery power/state of charge, production totals, Core telemetry, a manual refresh command, and two sandboxed dashboard widgets.

> SolarEdge says Monitoring API V1 will be deprecated on November 1, 2026. This release remains draft/unverified until the SolarEdge ONE V2 OAuth contract is validated. See [the API/library research](docs/solaredge-library-research.md).

## Configure

In SolarEdge Monitoring, enable API access and obtain the numeric Site ID and API key. PiPhi stores the API key as a secret.

```json
{
  "id": "home-solar",
  "site_id": 1234567,
  "api_key": "replace-with-your-api-key",
  "alias": "Home solar",
  "poll_interval_seconds": 900,
  "summary_interval_seconds": 3600
}
```

The minimum intervals deliberately preserve room under SolarEdge's documented 300-request daily quota.

## Develop and verify

```bash
pdm install -G dev
pdm run pytest
pdm run python scripts/validate.py
```

Widget projects live under `widgets/`. In either widget directory:

```bash
npm install
npm run build
npm test
npm run validate
npm run conformance
```

The Python suite includes vendor-response normalization, quota-conscious service lifecycle, shared runtime conformance fixtures, and a direct PiPhi Core manifest normalization/validation test.

## Run

```bash
pdm run uvicorn solar_edge.main:app --reload --port 8090
```

The runtime exposes `/health`, `/diagnostics`, `/discover`, `/config`, `/config/sync`, `/deconfigure`, `/ui-config`, `/state`, `/contract`, `/entities`, `/events`, `/telemetry/example`, and `/command`.

## Docker

```bash
docker build -t piphinetwork/piphi-network-solaredge:0.1.0 .
docker run --rm -p 8090:8090 piphinetwork/piphi-network-solaredge:0.1.0
```
