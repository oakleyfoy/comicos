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

  it("shows Add Comics with simplified user intake routes", () => {
    const addComics = visibleNavGroups(false).find((g) => g.id === "acquire");
    expect(addComics?.title).toBe("Add Comics");
    const labels = addComics?.links.map((l) => l.label) ?? [];
    expect(labels).toEqual([
      "Import retailer orders",
      "Phone Photo",
      "Import folder",
      "GPT Comic Read",
      "Manual Entry",
    ]);
    const paths = addComics?.links.map((l) => l.to) ?? [];
    expect(paths).toEqual([
      "/connected-retailers/import",
      "/add-comics/photo",
      "/add-comics/import-folder",
      "/add-comics/gpt-read",
      "/add-comics/manual",
    ]);
  });

  it("hides scanner and internal tools from non-admin navigation", () => {
    const groups = visibleNavGroups(false);
    expect(groups.find((g) => g.id === "scanner")).toBeUndefined();
    expect(groups.find((g) => g.id === "internal-tools")).toBeUndefined();
    const labels = groups.flatMap((g) => g.links.map((l) => l.label));
    expect(labels).not.toContain("Acquisitions");
    expect(labels).not.toContain("+ New Acquisition");
    expect(labels).not.toContain("Webcam Receiving");
  });

  it("shows P95-04 live capture and intake tools in Admin / Internal Tools for ops admins", () => {
    const internal = visibleNavGroups(true).find((g) => g.id === "internal-tools");
    expect(internal?.title).toBe("Admin / Internal Tools");
    const labels = internal?.links.map((l) => l.label) ?? [];
    expect(labels).toContain("Webcam Receiving");
    expect(labels).toContain("Mobile Receiving");
    expect(labels).toContain("Convention Scan");
    expect(labels).toContain("Scan Intake");
    expect(labels).not.toContain("Acquisitions");
    expect(labels).not.toContain("+ New Acquisition");
    const paths = internal?.links.map((l) => l.to) ?? [];
    expect(paths).toEqual(
      expect.arrayContaining(["/receiving/live", "/receiving/mobile", "/convention-scan"]),
    );
  });

  it("lists discovery intake routes under Reports instead of a Discovery group", () => {
    expect(visibleNavGroups(true).find((g) => g.id === "discovery")).toBeUndefined();
    const reports = visibleNavGroups(true).find((g) => g.id === "reports");
    const labels = reports?.links.map((l) => l.label) ?? [];
    expect(labels).toEqual(
      expect.arrayContaining([
        "Discovery Dashboard",
        "Discovery Opportunities",
        "Discovery Watchlists",
        "Discovery Alerts",
        "Release Lifecycle",
        "Discovery Analytics",
      ]),
    );
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
