import { act, render, screen } from "@testing-library/react";
import type { ReactNode, RefObject } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ConventionScanPage } from "../ConventionScanPage";

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/live-capture/CameraFeed", async () => {
  const { useEffect } = await import("react");
  return {
    CameraFeed: ({ videoRef }: { videoRef: RefObject<HTMLVideoElement> }) => {
      useEffect(() => {
        const video = videoRef.current;
        if (!video) {
          return;
        }
        Object.defineProperty(video, "videoWidth", { value: 1200, configurable: true });
        Object.defineProperty(video, "videoHeight", { value: 1800, configurable: true });
      }, [videoRef]);
      return <video ref={videoRef} data-testid="camera-video" />;
    },
  };
});

beforeEach(() => {
  vi.restoreAllMocks();
  Object.defineProperty(navigator, "mediaDevices", {
    value: {
      enumerateDevices: vi.fn().mockResolvedValue([
        { kind: "videoinput", deviceId: "camera-1", label: "Back Camera" },
      ]),
    },
    configurable: true,
  });
  vi.spyOn(window, "setInterval").mockImplementation(((callback: TimerHandler) => {
    intervalCallbacks.push(callback as () => void);
    return 1 as unknown as number;
  }) as typeof window.setInterval);
  vi.spyOn(window, "clearInterval").mockImplementation(() => undefined);
  vi.spyOn(apiClient, "getInventorySummary").mockResolvedValue({
    total_copies: 12,
    in_hand_copies: 10,
    ordered_not_received_copies: 1,
    preordered_copies: 1,
    cancelled_copies: 0,
    total_cost_basis: "120.00",
    total_current_fmv: "180.00",
    total_unrealized_gain_loss: "60.00",
    raw_count: 8,
    graded_count: 4,
    hold_count: 6,
    sell_count: 6,
  });
  vi.spyOn(apiClient, "identifyComicFromImage").mockResolvedValue({
    status: "success",
    bucket: "VERIFIED",
    confidence: 0.99,
    series: "Batman",
    issue_number: "497",
    variant: "Cover A",
    publisher: "DC",
    release_date: "1993-07-01",
    cover_image_url: "https://example.com/batman.jpg",
    candidate_count: 1,
    candidates: [],
    metrics: {},
  });
  vi.spyOn(apiClient, "collectorScan").mockResolvedValue({
    identification: {
      confidence: "0.99",
      requires_manual_review: false,
      scan_source: "manual_entry",
      normalized_barcode: "Batman #497",
      book: {
        title: "Batman",
        series_name: "Batman",
        issue_number: "497",
      },
      storage_entity: null,
    },
    book_intelligence: {
      ownership: {
        owned: true,
        total_copies: 2,
        graded_copies: 1,
        raw_copies: 1,
        inventory_copy_ids: [10, 11],
      },
      fmv: {
        authoritative_fmv: 42,
        confidence_score: 0.87,
      },
      recommendation: {
        recommendation: "HOLD",
        conviction_score: 0.91,
        confidence_score: 0.81,
        rationale: "Key issue with strong demand.",
        source_system: "collector_scan",
      },
      grading: {},
      storage: { locations: [] },
      action_card: { action: "HOLD", reasons: ["Strong issue", "Collector demand"] },
    },
    collection_completion: {
      label: "Batman",
      owned_issue_count: 2,
      known_issue_count: 12,
      completion_percent: 0.75,
      missing_issue_numbers: ["498", "499"],
      suggested_next_purchases: ["Batman #498"],
      scanned_issue_is_missing: false,
      gap_completion_opportunity: true,
    },
    spec_opportunity: null,
    action_card: { action: "HOLD", reasons: ["Strong issue", "Collector demand"] },
    price_assessment: null,
    personalization: null,
  } as never);
});

const intervalCallbacks: Array<() => void> = [];

describe("ConventionScanPage", () => {
  it("looks up convention scans and shows collection intelligence", async () => {
    const originalCreateElement = document.createElement.bind(document);
    const fakeCanvas = {
      width: 0,
      height: 0,
      getContext: () => ({
        drawImage: vi.fn(),
        getImageData: () => ({ data: new Uint8ClampedArray(16 * 16 * 4).fill(1) }),
      }),
      toBlob: (callback: BlobCallback) => callback(new Blob(["frame"], { type: "image/jpeg" })),
    };
    vi.spyOn(document, "createElement").mockImplementation(((tagName: string) => {
      if (tagName === "canvas") {
        return fakeCanvas as never;
      }
      return originalCreateElement(tagName);
    }) as typeof document.createElement);

    render(
      <MemoryRouter>
        <ConventionScanPage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(apiClient.getInventorySummary).toHaveBeenCalledTimes(1);
    expect(intervalCallbacks.length).toBeGreaterThan(0);

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }

    expect(apiClient.identifyComicFromImage).toHaveBeenCalledTimes(1);
    expect(apiClient.collectorScan).toHaveBeenCalledWith({ manual_entry: "Batman #497" });
    expect(screen.getAllByText("HOLD").length).toBeGreaterThan(0);
    expect(screen.getByText("Batman #497")).toBeInTheDocument();
    expect(screen.getByText("Owned")).toBeInTheDocument();
    vi.restoreAllMocks();
  });
});
