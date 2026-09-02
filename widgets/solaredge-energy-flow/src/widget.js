import { getInjectedPiPhiWidgetHost } from "piphi-network-widget-sdk";

const host = getInjectedPiPhiWidgetHost();
const root = document.querySelector("#piphi-widget-root") || document.body;
const context = await host.getContext();
const title = await host.translate("widget.title");

root.innerHTML = `
  <style>
    :root { color-scheme: light dark; font: 14px/1.4 system-ui, sans-serif; }
    main { box-sizing: border-box; min-height: 280px; padding: 18px; color: CanvasText; background: Canvas; }
    h2 { margin: 0 0 18px; font-size: 1rem; }
    .flow { display: grid; grid-template-columns: repeat(3, 1fr); gap: 10px; }
    .node { border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 14px; padding: 14px 10px; text-align: center; }
    .solar { color: #17a768; } .grid.import { color: #dc6d2b; } .grid.export { color: #1877c9; }
    strong { display: block; margin-top: 5px; font-size: clamp(1.15rem, 5vw, 2rem); font-variant-numeric: tabular-nums; }
    .battery { margin-top: 12px; } small, [role=status] { opacity: .68; }
  </style>
  <main dir="${context.localization?.direction || "ltr"}">
    <h2>${escapeHtml(title)}</h2>
    <section class="flow" aria-label="Current power flow">
      <div class="node solar"><small>Solar</small><strong data-key="production_power_w">—</strong><small>W</small></div>
      <div class="node"><small>Home</small><strong data-key="consumption_power_w">—</strong><small>W</small></div>
      <div class="node grid"><small data-grid-label>Grid</small><strong data-key="grid_power_w">—</strong><small>W</small></div>
    </section>
    <div class="node battery" hidden><small>Battery</small><strong data-key="battery_power_w">—</strong><small>W · <span data-key="battery_soc_percent">—</span>%</small></div>
    <p role="status">loading</p>
  </main>`;

const status = root.querySelector("[role=status]");
const stop = await host.subscribeState(
  { capabilityIds: ["production_power_w", "consumption_power_w", "grid_power_w", "battery_power_w", "battery_soc_percent"] },
  (event) => {
    status.textContent = event.status || event.kind;
    if (event.kind !== "snapshot" && event.kind !== "point") return;
    const state = event.data?.primaryState || event.data?.state || event.data?.value || event.data || {};
    for (const node of root.querySelectorAll("[data-key]")) {
      const value = state[node.dataset.key];
      if (value !== undefined && value !== null) node.textContent = formatNumber(Math.abs(Number(value)));
    }
    const grid = Number(state.grid_power_w);
    const gridNode = root.querySelector(".grid");
    gridNode?.classList.toggle("import", grid > 0);
    gridNode?.classList.toggle("export", grid < 0);
    const gridLabel = root.querySelector("[data-grid-label]");
    if (gridLabel && Number.isFinite(grid)) gridLabel.textContent = grid < 0 ? "Grid export" : "Grid import";
    root.querySelector(".battery").hidden = state.battery_power_w == null && state.battery_soc_percent == null;
  },
);

window.addEventListener("pagehide", stop, { once: true });
await host.ready({ height: 300 });

function formatNumber(value) {
  return Number.isFinite(value) ? new Intl.NumberFormat(undefined, { maximumFractionDigits: 0 }).format(value) : "—";
}
function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}
