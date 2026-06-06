import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { NAV_GROUPS, visibleNavGroups } from "./appNavigation";

const manifestPath = join(dirname(fileURLToPath(import.meta.url)), "../../../../config/nav-route-smoke.manifest.json");

type ManifestRoute = { path: string; apis: string[] };

function loadManifest(): ManifestRoute[] {
  const raw = readFileSync(manifestPath, "utf-8");
  return (JSON.parse(raw) as { routes: ManifestRoute[] }).routes;
}

describe("nav route smoke manifest", () => {
  it("lists an API path for every priority nav route in the manifest", () => {
    const manifestPaths = new Set(loadManifest().map((r) => r.path));
    const priorityPaths = [
      "/collector-home",
      "/daily-actions",
      "/collector-command-center",
      "/notifications",
      "/daily-briefing",
      "/workflow-health",
      "/pull-lists",
      "/foc-dashboard",
      "/marketplace-opportunities",
      "/future-pull-list",
      "/dashboard",
      "/collection-valuation-dashboard",
      "/key-issues",
      "/sell-queue",
      "/storage-dashboard",
      "/discovery-feed",
      "/mobile-scan",
    ];
    for (const path of priorityPaths) {
      expect(manifestPaths.has(path), `missing manifest entry for ${path}`).toBe(true);
    }
  });

  it("every visible nav link is either in the manifest or marked hiddenFromNav", () => {
    const manifestPaths = new Set(loadManifest().map((r) => r.path));
    for (const group of visibleNavGroups(true)) {
      for (const link of group.links) {
        if (link.hiddenFromNav || link.requiresOpsAdmin) {
          continue;
        }
        expect(
          manifestPaths.has(link.to),
          `nav link ${link.label} (${link.to}) needs manifest entry or hiddenFromNav`,
        ).toBe(true);
      }
    }
  });
});
