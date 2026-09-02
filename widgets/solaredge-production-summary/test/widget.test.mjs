import test from "node:test";
import assert from "node:assert/strict";
import manifest from "../widget.manifest.json" with { type: "json" };
import { validateWidgetManifest } from "piphi-network-widget-sdk/manifest";

test("manifest is publishable", () => {
  assert.equal(validateWidgetManifest(manifest).filter((item) => item.severity === "error").length, 0);
});
