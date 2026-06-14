import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { describe, expect, it } from "vitest";

import { visibleNavGroups } from "./appNavigation";

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
      "/pull-lists",
      "/foc-dashboard",
      "/marketplace-opportunities",
      "/buy-opportunities",
      "/future-pull-list",
      "/dashboard",
      "/collection-gaps",
      "/collection-valuation-dashboard",
      "/key-issues",
      "/imports",
      "/imports/email",
      "/orders/import",
      "/sell-queue",
      "/storage-dashboard",
      "/storage-locations",
      "/inventory-locator",
      "/grading-queue",
      "/grading-intelligence",
      "/listing-drafts",
      "/listings",
      "/selling-analytics",
      "/discovery-dashboard",
      "/discovery-opportunities",
      "/mobile-scan",
      "/portfolio-analytics",
      "/daily-briefing",
      "/weekly-briefing",
      "/platform-certification",
      "/production-readiness",
      "/collector-profile",
      "/collector-budget",
      "/workflow-health",
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

  it("shows P95-04 live capture routes in the Scanner sidebar group", () => {
    const scanner = visibleNavGroups(true).find((g) => g.id === "scanner");
    expect(scanner?.title).toBe("Scanner");
    const labels = scanner?.links.map((l) => l.label) ?? [];
    expect(labels).toEqual(["Webcam Receiving", "Mobile Receiving", "Convention Scan"]);
    const paths = scanner?.links.map((l) => l.to) ?? [];
    expect(paths).toEqual(["/receiving/live", "/receiving/mobile", "/convention-scan"]);
  });

  it("hides legacy phase pages from the sidebar", () => {
    const labels = visibleNavGroups(true).flatMap((g) => g.links.map((l) => l.label));
    const hidden = [
      "Grading Platform",
      "Release Intelligence",
      "Box Contents",
      "Assignment",
      "Collection insights",
      "Purchase Budget",
    ];
    for (const label of hidden) {
      expect(labels, `${label} should not appear in sidebar`).not.toContain(label);
    }
  });
});
