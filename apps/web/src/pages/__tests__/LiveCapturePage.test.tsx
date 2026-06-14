import { act, cleanup, render, screen } from "@testing-library/react";
import type { ReactNode, RefObject } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { MobileLiveCapturePage, WebcamLiveCapturePage } from "../LiveCapturePage";

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/live-capture/CameraFeed", async () => {
  const { useEffect } = await import("react");
  return {
    CameraFeed: ({
      videoRef,
      onStreamReady,
    }: {
      videoRef: RefObject<HTMLVideoElement>;
      onStreamReady?: () => void;
    }) => {
      useEffect(() => {
        const video = videoRef.current;
        if (!video) {
          return;
        }
        Object.defineProperty(video, "videoWidth", { value: 1200, configurable: true });
        Object.defineProperty(video, "videoHeight", { value: 1800, configurable: true });
        onStreamReady?.();
      }, [onStreamReady, videoRef]);
      return <video ref={videoRef} data-testid="camera-video" />;
    },
  };
});

beforeEach(() => {
  cleanup();
  intervalCallbacks.length = 0;
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
  vi.spyOn(apiClient, "createReceivingSession").mockResolvedValue({
    id: 1,
    status: "PENDING",
    total_items: 0,
    verified_items: 0,
    review_items: 0,
    unknown_items: 0,
    confirmed_items: 0,
    skipped_items: 0,
    capture_source: "WEBCAM",
    created_at: "2026-06-09T15:00:00Z",
    updated_at: "2026-06-09T15:00:00Z",
    started_at: null,
    completed_at: null,
    session_notes: null,
    live_capture_stats_json: {},
  });
  vi.spyOn(apiClient, "getReceivingSession").mockResolvedValue({
    id: 1,
    status: "ACTIVE",
    total_items: 0,
    verified_items: 0,
    review_items: 0,
    unknown_items: 0,
    confirmed_items: 0,
    skipped_items: 0,
    capture_source: "WEBCAM",
    created_at: "2026-06-09T15:00:00Z",
    updated_at: "2026-06-09T15:00:00Z",
    started_at: "2026-06-09T15:00:00Z",
    completed_at: null,
    session_notes: null,
    live_capture_stats_json: {},
    items: [],
  });
  vi.spyOn(apiClient, "uploadReceivingSessionImages").mockResolvedValue({
    uploaded_count: 1,
    session: {
      id: 1,
      status: "ACTIVE",
      total_items: 1,
      verified_items: 1,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 0,
      skipped_items: 0,
      capture_source: "WEBCAM",
      created_at: "2026-06-09T15:00:00Z",
      updated_at: "2026-06-09T15:01:00Z",
      started_at: "2026-06-09T15:00:00Z",
      completed_at: null,
      session_notes: null,
      live_capture_stats_json: {
        live_capture_frames_received: 1,
        duplicate_frames_suppressed: 0,
        average_recognition_time: 20,
        confirm_rate: 0,
      },
      items: [
        {
          id: 10,
          receiving_session_id: 1,
          sequence_index: 0,
          source_filename: "webcam-frame.jpg",
          mime_type: "image/jpeg",
          image_width: 1200,
          image_height: 1800,
          image_sha256: "abc123",
          capture_source: "WEBCAM",
          frame_fingerprint: "f1",
          frame_sequence_index: 0,
          stable_frame_count: 3,
          recognition_bucket: "VERIFIED",
          status: "VERIFIED",
          recognition_confidence: 0.99,
          recognition_latency_ms: 20,
          capture_started_at: "2026-06-09T15:01:00Z",
          capture_completed_at: "2026-06-09T15:01:00Z",
          recognition_snapshot_json: {
            bucket: "VERIFIED",
            confidence: 0.99,
            series: "Batman",
            issue_number: "497",
          },
          candidate_snapshot_json: [],
          selected_candidate_index: null,
          selected_candidate_json: null,
          duplicate_of_item_id: null,
          duplicate_suppressed: false,
          action_taken: null,
          action_reason: null,
          capture_metadata_json: {},
          uploaded_at: "2026-06-09T15:01:00Z",
          recognized_at: "2026-06-09T15:01:00Z",
          confirmed_at: null,
          skipped_at: null,
          created_at: "2026-06-09T15:01:00Z",
          updated_at: "2026-06-09T15:01:00Z",
        },
      ],
    },
  });
});

const intervalCallbacks: Array<() => void> = [];

describe("WebcamLiveCapturePage", () => {
  it("uploads a stable frame once and suppresses repeats", async () => {
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
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });
    expect(apiClient.createReceivingSession).toHaveBeenCalledTimes(1);
    expect(apiClient.createReceivingSession).toHaveBeenCalledWith({ capture_source: "WEBCAM" });
    expect(intervalCallbacks.length).toBeGreaterThan(0);

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }

    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledWith(
      1,
      expect.any(Array),
      expect.objectContaining({
        capture_source: "WEBCAM",
        stable_frame_count: 3,
      }),
    );
    expect(screen.getByTestId("live-capture-active-camera")).toHaveTextContent("Back Camera");
    expect(screen.getByTestId("live-capture-mode")).toHaveTextContent("WEBCAM");
    expect(screen.getByTestId("live-capture-session")).toHaveTextContent("Session #1");
    expect(screen.getByLabelText(/Selected camera: Back Camera/i)).toBeInTheDocument();
  });

  it("does not upload again while a pending item awaits user action", async () => {
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
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }
    await act(async () => {
      await new Promise((resolve) => setTimeout(resolve, 0));
    });
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);
  });

  it("does not start a second upload while the first upload is in flight", async () => {
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

    let resolveUpload: ((value: Awaited<ReturnType<typeof apiClient.uploadReceivingSessionImages>>) => void) | undefined;
    const uploadDeferred = new Promise<Awaited<ReturnType<typeof apiClient.uploadReceivingSessionImages>>>((resolve) => {
      resolveUpload = resolve;
    });
    vi.spyOn(apiClient, "uploadReceivingSessionImages").mockReturnValue(uploadDeferred);

    render(
      <MemoryRouter>
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);

    await act(async () => {
      resolveUpload?.({
        uploaded_count: 1,
        session: {
          id: 1,
          status: "ACTIVE",
          total_items: 1,
          verified_items: 1,
          review_items: 0,
          unknown_items: 0,
          confirmed_items: 0,
          skipped_items: 0,
          capture_source: "WEBCAM",
          created_at: "2026-06-09T15:00:00Z",
          updated_at: "2026-06-09T15:01:00Z",
          started_at: "2026-06-09T15:00:00Z",
          completed_at: null,
          session_notes: null,
          live_capture_stats_json: {},
          items: [
            {
              id: 10,
              receiving_session_id: 1,
              sequence_index: 0,
              source_filename: "webcam-frame.jpg",
              mime_type: "image/jpeg",
              image_width: 1200,
              image_height: 1800,
              image_sha256: "abc123",
              capture_source: "WEBCAM",
              frame_fingerprint: "f1",
              frame_sequence_index: 0,
              stable_frame_count: 3,
              recognition_bucket: "VERIFIED",
              status: "VERIFIED",
              recognition_confidence: 0.99,
              recognition_latency_ms: 20,
              capture_started_at: "2026-06-09T15:01:00Z",
              capture_completed_at: "2026-06-09T15:01:00Z",
              recognition_snapshot_json: {},
              candidate_snapshot_json: [],
              selected_candidate_index: null,
              selected_candidate_json: null,
              duplicate_of_item_id: null,
              duplicate_suppressed: false,
              action_taken: null,
              action_reason: null,
              capture_metadata_json: {},
              uploaded_at: "2026-06-09T15:01:00Z",
              recognized_at: "2026-06-09T15:01:00Z",
              confirmed_at: null,
              skipped_at: null,
              created_at: "2026-06-09T15:01:00Z",
              updated_at: "2026-06-09T15:01:00Z",
            },
          ],
        },
      });
      await uploadDeferred;
    });
  });

  function reviewItem() {
    return {
      id: 11,
      receiving_session_id: 1,
      sequence_index: 0,
      source_filename: "webcam-frame.jpg",
      mime_type: "image/jpeg",
      image_width: 1200,
      image_height: 1800,
      image_sha256: "rev123",
      capture_source: "WEBCAM",
      frame_fingerprint: "f1",
      frame_sequence_index: 0,
      stable_frame_count: 3,
      recognition_bucket: "REVIEW",
      status: "REVIEW",
      recognition_confidence: 0.88,
      recognition_latency_ms: 20,
      capture_started_at: "2026-06-09T15:01:00Z",
      capture_completed_at: "2026-06-09T15:01:00Z",
      recognition_snapshot_json: {
        bucket: "REVIEW",
        confidence: 0.88,
        series: "Venom",
        issue_number: "7",
        publisher: "Marvel",
        catalog_issue_id: 700,
        winning_source: "catalog_image_fingerprint",
      },
      candidate_snapshot_json: [],
      selected_candidate_index: null,
      selected_candidate_json: null,
      duplicate_of_item_id: null,
      duplicate_suppressed: false,
      action_taken: null,
      action_reason: null,
      capture_metadata_json: {},
      uploaded_at: "2026-06-09T15:01:00Z",
      recognized_at: "2026-06-09T15:01:00Z",
      confirmed_at: null,
      skipped_at: null,
      created_at: "2026-06-09T15:01:00Z",
      updated_at: "2026-06-09T15:01:00Z",
    };
  }

  function mockCanvas() {
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
  }

  it("auto-opens the review modal for a REVIEW capture and pauses further uploads", async () => {
    mockCanvas();
    vi.spyOn(apiClient, "uploadReceivingSessionImages").mockResolvedValue({
      uploaded_count: 1,
      session: {
        id: 1,
        status: "ACTIVE",
        total_items: 1,
        verified_items: 0,
        review_items: 1,
        unknown_items: 0,
        confirmed_items: 0,
        skipped_items: 0,
        capture_source: "WEBCAM",
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:01:00Z",
        started_at: "2026-06-09T15:00:00Z",
        completed_at: null,
        session_notes: null,
        live_capture_stats_json: {},
        items: [reviewItem()],
      },
    } as never);

    render(
      <MemoryRouter>
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }

    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);
    expect(await screen.findByTestId("recognition-review-modal")).toBeInTheDocument();

    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }
    expect(apiClient.uploadReceivingSessionImages).toHaveBeenCalledTimes(1);
  });

  it("cancels the review modal without confirming the item", async () => {
    mockCanvas();
    const confirmSpy = vi.spyOn(apiClient, "confirmReceivingSessionItem");
    vi.spyOn(apiClient, "uploadReceivingSessionImages").mockResolvedValue({
      uploaded_count: 1,
      session: {
        id: 1,
        status: "ACTIVE",
        total_items: 1,
        verified_items: 0,
        review_items: 1,
        unknown_items: 0,
        confirmed_items: 0,
        skipped_items: 0,
        capture_source: "WEBCAM",
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:01:00Z",
        started_at: "2026-06-09T15:00:00Z",
        completed_at: null,
        session_notes: null,
        live_capture_stats_json: {},
        items: [reviewItem()],
      },
    } as never);

    render(
      <MemoryRouter>
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );
    await act(async () => {
      await Promise.resolve();
    });
    for (let index = 0; index < 4; index += 1) {
      await act(async () => {
        intervalCallbacks[0]();
        await Promise.resolve();
      });
    }

    expect(await screen.findByTestId("recognition-review-modal")).toBeInTheDocument();

    await act(async () => {
      screen.getByTestId("review-cancel").click();
      await Promise.resolve();
    });

    expect(screen.queryByTestId("recognition-review-modal")).not.toBeInTheDocument();
    expect(confirmSpy).not.toHaveBeenCalled();
  });

  it("creates a mobile live session with the mobile capture source", async () => {
    render(
      <MemoryRouter>
        <MobileLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(apiClient.createReceivingSession).toHaveBeenCalledTimes(1);
    expect(apiClient.createReceivingSession).toHaveBeenCalledWith({ capture_source: "MOBILE_CAMERA" });
  });

  it("shows a friendly error when the session response is missing an id", async () => {
    vi.spyOn(apiClient, "createReceivingSession").mockResolvedValue({} as never);
    vi.spyOn(apiClient, "getReceivingSession").mockResolvedValue({
      id: 1,
      status: "PENDING",
      total_items: 0,
      verified_items: 0,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 0,
      skipped_items: 0,
      created_at: "2026-06-09T15:00:00Z",
      updated_at: "2026-06-09T15:00:00Z",
      started_at: null,
      completed_at: null,
      session_notes: null,
      live_capture_stats_json: {},
    });

    render(
      <MemoryRouter>
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(screen.getByText(/missing session id/i)).toBeInTheDocument();
  });

  it("starts a fresh session when New session is clicked", async () => {
    const createSpy = vi.spyOn(apiClient, "createReceivingSession");
    const getSpy = vi.spyOn(apiClient, "getReceivingSession");

    render(
      <MemoryRouter>
        <WebcamLiveCapturePage />
      </MemoryRouter>,
    );

    await act(async () => {
      await Promise.resolve();
    });

    expect(createSpy).toHaveBeenCalledTimes(1);

    createSpy.mockResolvedValueOnce({
      id: 99,
      status: "PENDING",
      total_items: 0,
      verified_items: 0,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 0,
      skipped_items: 0,
      capture_source: "WEBCAM",
      created_at: "2026-06-09T16:00:00Z",
      updated_at: "2026-06-09T16:00:00Z",
      started_at: null,
      completed_at: null,
      session_notes: null,
      live_capture_stats_json: {},
    });
    getSpy.mockResolvedValueOnce({
      id: 99,
      status: "ACTIVE",
      total_items: 0,
      verified_items: 0,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 0,
      skipped_items: 0,
      capture_source: "WEBCAM",
      created_at: "2026-06-09T16:00:00Z",
      updated_at: "2026-06-09T16:00:00Z",
      started_at: null,
      completed_at: null,
      session_notes: null,
      items: [],
      live_capture_stats_json: {},
    });

    await act(async () => {
      screen.getByTestId("live-capture-new-session").click();
      await Promise.resolve();
    });

    expect(createSpy).toHaveBeenCalledTimes(2);
    expect(getSpy).toHaveBeenCalledWith(99);
    expect(screen.getByTestId("live-capture-session")).toHaveTextContent("#99");
  });
});
