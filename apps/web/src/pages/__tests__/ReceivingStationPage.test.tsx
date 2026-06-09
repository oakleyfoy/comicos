import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { ReceivingStationPage } from "../ReceivingStationPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({
    title,
    description,
    actions,
  }: {
    title: string;
    description: string;
    actions?: ReactNode;
  }) => (
    <header>
      <h1>{title}</h1>
      <p>{description}</p>
      {actions ? <div>{actions}</div> : null}
    </header>
  ),
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("ReceivingStationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "createReceivingSession").mockResolvedValue({
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
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:01:00Z",
        started_at: "2026-06-09T15:01:00Z",
        completed_at: null,
        session_notes: null,
        items: [
          {
            id: 10,
            receiving_session_id: 1,
            sequence_index: 0,
            source_filename: "batman.png",
            mime_type: "image/png",
            image_width: 1600,
            image_height: 2400,
            image_sha256: "abc123",
            recognition_bucket: "VERIFIED",
            status: "VERIFIED",
            recognition_confidence: 0.99,
            recognition_snapshot_json: {
              bucket: "VERIFIED",
              confidence: 0.99,
              series: "Batman",
              issue_number: "497",
              variant: "Cover A",
              publisher: "DC",
            },
            candidate_snapshot_json: [
              {
                series: "Batman",
                issue_number: "497",
                variant: "Cover A",
                publisher: "DC",
                confidence: 0.99,
              },
            ],
            selected_candidate_index: null,
            selected_candidate_json: null,
            action_taken: null,
            action_reason: null,
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
    vi.spyOn(apiClient, "confirmReceivingSessionItem").mockResolvedValue({
      session: {
        id: 1,
        status: "COMPLETED",
        total_items: 1,
        verified_items: 0,
        review_items: 0,
        unknown_items: 0,
        confirmed_items: 1,
        skipped_items: 0,
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:02:00Z",
        started_at: "2026-06-09T15:01:00Z",
        completed_at: "2026-06-09T15:02:00Z",
        session_notes: null,
        items: [
          {
            id: 10,
            receiving_session_id: 1,
            sequence_index: 0,
            source_filename: "batman.png",
            mime_type: "image/png",
            image_width: 1600,
            image_height: 2400,
            image_sha256: "abc123",
            recognition_bucket: "VERIFIED",
            status: "CONFIRMED",
            recognition_confidence: 0.99,
            recognition_snapshot_json: {
              bucket: "VERIFIED",
              confidence: 0.99,
              series: "Batman",
              issue_number: "497",
              variant: "Cover A",
              publisher: "DC",
            },
            candidate_snapshot_json: [
              {
                series: "Batman",
                issue_number: "497",
                variant: "Cover A",
                publisher: "DC",
                confidence: 0.99,
              },
            ],
            selected_candidate_index: 0,
            selected_candidate_json: {
              series: "Batman",
              issue_number: "497",
              variant: "Cover A",
              publisher: "DC",
              confidence: 0.99,
            },
            action_taken: "confirm",
            action_reason: null,
            uploaded_at: "2026-06-09T15:01:00Z",
            recognized_at: "2026-06-09T15:01:00Z",
            confirmed_at: "2026-06-09T15:02:00Z",
            skipped_at: null,
            created_at: "2026-06-09T15:01:00Z",
            updated_at: "2026-06-09T15:02:00Z",
          },
        ],
      },
      item: {
        id: 10,
        receiving_session_id: 1,
        sequence_index: 0,
        source_filename: "batman.png",
        mime_type: "image/png",
        image_width: 1600,
        image_height: 2400,
        image_sha256: "abc123",
        recognition_bucket: "VERIFIED",
        status: "CONFIRMED",
        recognition_confidence: 0.99,
        recognition_snapshot_json: {
          bucket: "VERIFIED",
          confidence: 0.99,
          series: "Batman",
          issue_number: "497",
          variant: "Cover A",
          publisher: "DC",
        },
        candidate_snapshot_json: [
          {
            series: "Batman",
            issue_number: "497",
            variant: "Cover A",
            publisher: "DC",
            confidence: 0.99,
          },
        ],
        selected_candidate_index: 0,
        selected_candidate_json: {
          series: "Batman",
          issue_number: "497",
          variant: "Cover A",
          publisher: "DC",
          confidence: 0.99,
        },
        action_taken: "confirm",
        action_reason: null,
        uploaded_at: "2026-06-09T15:01:00Z",
        recognized_at: "2026-06-09T15:01:00Z",
        confirmed_at: "2026-06-09T15:02:00Z",
        skipped_at: null,
        created_at: "2026-06-09T15:01:00Z",
        updated_at: "2026-06-09T15:02:00Z",
      },
    });
    vi.spyOn(apiClient, "getReceivingSessionSummary").mockResolvedValue({
      session: {
        id: 1,
        status: "ACTIVE",
        total_items: 1,
        verified_items: 1,
        review_items: 0,
        unknown_items: 0,
        confirmed_items: 1,
        skipped_items: 0,
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:02:00Z",
        started_at: "2026-06-09T15:01:00Z",
        completed_at: null,
        session_notes: null,
        purchase_order_id: null,
        purchase_mode: null,
        purchase_source_type: null,
        purchase_label: null,
        seller_name: null,
        purchase_date: null,
        amount_paid: null,
        shipping_amount: null,
        tax_amount: null,
        purchase_notes: null,
        allocation_method: null,
        allocation_details_json: {},
        inventory_created_count: 0,
      },
      confirmed_inventory_count: 0,
      inventory_copy_ids: [],
      top_additions: ["Batman #497"],
      order_id: null,
    });
    vi.spyOn(apiClient, "assignReceivingPurchase").mockResolvedValue({
      id: 1,
      status: "ACTIVE",
      total_items: 1,
      verified_items: 1,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 1,
      skipped_items: 0,
      created_at: "2026-06-09T15:00:00Z",
      updated_at: "2026-06-09T15:02:00Z",
      started_at: "2026-06-09T15:01:00Z",
      completed_at: null,
      session_notes: null,
      purchase_order_id: 42,
      purchase_mode: "new",
      purchase_source_type: "FACEBOOK",
      purchase_label: "Facebook Lot",
      seller_name: "Private Seller",
      purchase_date: "2026-06-09",
      amount_paid: "20.00",
      shipping_amount: "0.00",
      tax_amount: "0.00",
      purchase_notes: null,
      allocation_method: "equal",
      allocation_details_json: {},
      inventory_created_count: 0,
    });
    vi.spyOn(apiClient, "completeReceivingSession").mockResolvedValue({
      session: {
        id: 1,
        status: "COMPLETED",
        total_items: 1,
        verified_items: 1,
        review_items: 0,
        unknown_items: 0,
        confirmed_items: 1,
        skipped_items: 0,
        created_at: "2026-06-09T15:00:00Z",
        updated_at: "2026-06-09T15:03:00Z",
        started_at: "2026-06-09T15:01:00Z",
        completed_at: "2026-06-09T15:03:00Z",
        session_notes: null,
        purchase_order_id: 42,
        purchase_mode: "new",
        purchase_source_type: "FACEBOOK",
        purchase_label: "Facebook Lot",
        seller_name: "Private Seller",
        purchase_date: "2026-06-09",
        amount_paid: "20.00",
        shipping_amount: "0.00",
        tax_amount: "0.00",
        purchase_notes: null,
        allocation_method: "equal",
        allocation_details_json: {},
        inventory_created_count: 1,
      },
      confirmed_inventory_count: 1,
      inventory_copy_ids: [100],
      top_additions: ["Batman #497"],
      order_id: 42,
    });
    vi.spyOn(apiClient, "getReceivingSession").mockResolvedValue({
      id: 1,
      status: "COMPLETED",
      total_items: 1,
      verified_items: 1,
      review_items: 0,
      unknown_items: 0,
      confirmed_items: 1,
      skipped_items: 0,
      created_at: "2026-06-09T15:00:00Z",
      updated_at: "2026-06-09T15:03:00Z",
      started_at: "2026-06-09T15:01:00Z",
      completed_at: "2026-06-09T15:03:00Z",
      session_notes: null,
      purchase_order_id: 42,
      purchase_mode: "new",
      purchase_source_type: "FACEBOOK",
      purchase_label: "Facebook Lot",
      seller_name: "Private Seller",
      purchase_date: "2026-06-09",
      amount_paid: "20.00",
      shipping_amount: "0.00",
      tax_amount: "0.00",
      purchase_notes: null,
      allocation_method: "equal",
      allocation_details_json: {},
      inventory_created_count: 1,
      items: [
        {
          id: 10,
          receiving_session_id: 1,
          sequence_index: 0,
          source_filename: "batman.png",
          mime_type: "image/png",
          image_width: 1600,
          image_height: 2400,
          image_sha256: "abc123",
          recognition_bucket: "VERIFIED",
          status: "CONFIRMED",
          recognition_confidence: 0.99,
          recognition_snapshot_json: {
            bucket: "VERIFIED",
            confidence: 0.99,
            series: "Batman",
            issue_number: "497",
            variant: "Cover A",
            publisher: "DC",
          },
          candidate_snapshot_json: [
            {
              series: "Batman",
              issue_number: "497",
              variant: "Cover A",
              publisher: "DC",
              confidence: 0.99,
            },
          ],
          selected_candidate_index: 0,
          selected_candidate_json: {
            series: "Batman",
            issue_number: "497",
            variant: "Cover A",
            publisher: "DC",
            confidence: 0.99,
          },
          inventory_copy_id: 100,
          action_taken: "confirm",
          action_reason: null,
          uploaded_at: "2026-06-09T15:01:00Z",
          recognized_at: "2026-06-09T15:01:00Z",
          confirmed_at: "2026-06-09T15:02:00Z",
          skipped_at: null,
          created_at: "2026-06-09T15:01:00Z",
          updated_at: "2026-06-09T15:03:00Z",
        },
      ],
    });
  });

  it("creates a session, uploads a file, and confirms the queued item", async () => {
    render(
      <MemoryRouter>
        <ReceivingStationPage />
      </MemoryRouter>,
    );

    expect(await screen.findByRole("heading", { name: "Receiving Station" })).toBeInTheDocument();
    const input = screen.getAllByLabelText("Add images")[0] as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3, 4])], "batman.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => {
      expect(screen.getByText("Images Uploaded")).toBeInTheDocument();
      const currentItem = screen.getByRole("heading", { name: "Current Item" }).closest("div");
      expect(currentItem).not.toBeNull();
      if (currentItem) {
        expect(currentItem).toHaveTextContent("Batman #497");
        expect(currentItem).toHaveTextContent("VERIFIED");
      }
      expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument();
    });

    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() => {
      expect(apiClient.confirmReceivingSessionItem).toHaveBeenCalledWith(1, {
        item_id: 10,
        decision: "confirm",
        selected_candidate_index: 0,
      });
    });
  });

  it("opens the completion modal and creates inventory from confirmed books", async () => {
    render(
      <MemoryRouter>
        <ReceivingStationPage />
      </MemoryRouter>,
    );

    const input = screen.getAllByLabelText("Add images")[0] as HTMLInputElement;
    const file = new File([new Uint8Array([1, 2, 3, 4])], "batman.png", { type: "image/png" });
    fireEvent.change(input, { target: { files: [file] } });

    await waitFor(() => expect(screen.getByRole("button", { name: "Confirm" })).toBeInTheDocument());
    fireEvent.click(screen.getByRole("button", { name: "Confirm" }));
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: "Finish Receiving Session" }).some((button) => !button.disabled)).toBe(true),
    );
    const finishButton =
      screen.getAllByRole("button", { name: "Finish Receiving Session" }).find((button) => !button.disabled) ??
      screen.getAllByRole("button", { name: "Finish Receiving Session" })[0];
    fireEvent.click(finishButton);

    expect(await screen.findByText("Receiving Summary")).toBeInTheDocument();
    expect(screen.getByText("Purchase Source")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByText("Cost Allocation")).toBeInTheDocument();
  });
});

