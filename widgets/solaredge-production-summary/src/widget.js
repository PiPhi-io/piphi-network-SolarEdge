import { getInjectedPiPhiWidgetHost } from "piphi-network-widget-sdk";

const host = getInjectedPiPhiWidgetHost();
const root = document.querySelector("#piphi-widget-root") || document.body;
const context = await host.getContext();
const title = await host.translate("widget.title");
const periods = [["today_energy_kwh", "Today"], ["month_energy_kwh", "Month"], ["year_energy_kwh", "Year"], ["lifetime_energy_kwh", "Lifetime"]];

root.innerHTML = `
  <style>
    :root { color-scheme: light dark; font: 14px/1.4 system-ui, sans-serif; }
    main { box-sizing: border-box; min-height: 240px; padding: 18px; color: CanvasText; background: Canvas; }
    h2 { margin: 0 0 14px; font-size: 1rem; }
    .totals { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
    .total { border: 1px solid color-mix(in srgb, CanvasText 16%, transparent); border-radius: 12px; padding: 12px; }
    strong { display: block; color: #17a768; font-size: clamp(1.1rem, 5vw, 1.8rem); font-variant-numeric: tabular-nums; }
    small, [role=status] { opacity: .68; }
  </style>
  <main dir="${context.localization?.direction || "ltr"}">
    <h2>${escapeHtml(title)}</h2>
    <section class="totals" aria-label="Production totals">
      ${periods.map(([key, label]) => `<div class="total"><small>${label}</small><strong data-key="${key}">—</strong><small>kWh</small></div>`).join("")}
    </section>
    <p role="status">loading</p>
  </main>`;

const status = root.querySelector("[role=status]");
const stop = await host.subscribeState({ capabilityIds: periods.map(([key]) => key) }, (event) => {
  status.textContent = event.status || event.kind;
  if (event.kind !== "snapshot" && event.kind !== "point") return;
  const state = event.data?.primaryState || event.data?.state || event.data?.value || event.data || {};
  for (const node of root.querySelectorAll("[data-key]")) {
    const value = Number(state[node.dataset.key]);
    if (Number.isFinite(value)) node.textContent = new Intl.NumberFormat(undefined, { maximumFractionDigits: 1 }).format(value);
  }
});

window.addEventListener("pagehide", stop, { once: true });
await host.ready({ height: 260 });

function escapeHtml(value) {
  return String(value).replace(/[&<>'"]/g, (character) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" })[character]);
}
