import { render, screen, waitFor } from "@testing-library/react";

import type { ReactNode } from "react";

import { MemoryRouter } from "react-router-dom";

import { beforeEach, describe, expect, it, vi } from "vitest";



import { apiClient } from "../../api/client";

import { GradingValidationPage } from "../GradingValidationPage";



vi.mock("../../components/AppShell", () => ({

  AppShell: ({ children }: { children: ReactNode }) => <div data-testid="app-shell">{children}</div>,

}));



vi.mock("../../components/PageHeader", () => ({

  PageHeader: ({ title, description }: { title: string; description: string }) => (

    <header>

      <h1>{title}</h1>

      <p>{description}</p>

    </header>

  ),

}));



vi.mock("../../components/StatusBanner", () => ({

  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,

}));



describe("GradingValidationPage", () => {

  beforeEach(() => {

    vi.restoreAllMocks();

    vi.spyOn(apiClient, "getGradingValidationDashboard").mockResolvedValue({

      prediction_accuracy: {

        validation_count: 2,

        average_variance: 0.2,

        accuracy_score: 0.9,

      },

      calibration_metrics: [

        {

          id: 1,

          metric_date: "2026-05-30",

          grading_scale: "PSA",

          total_predictions: 2,

          average_variance: 0.2,

          accuracy_score: 0.9,

          created_at: "2026-05-30T12:00:00Z",

        },

      ],

      drift_summary: {

        event_count: 0,

        average_drift_score: 0,

        latest_drift_type: null,

      },

      reliability_metrics: [

        {

          id: 1,

          metric_uuid: "rel-1",

          reliability_type: "SYSTEM_RELIABILITY",

          metric_score: 0.85,

          measured_at: "2026-05-30T12:00:00Z",

        },

      ],

      recommendation_outcomes: [

        {

          id: 1,

          outcome_uuid: "out-1",

          recommendation_id: 1,

          prediction_id: 1,

          outcome_type: "RECOMMENDATION_REVIEWED",

          outcome_score: 0.36,

          created_at: "2026-05-30T12:00:00Z",

        },

      ],

      agent_activity: [

        {

          id: 1,

          agent_code: "grade_validation",

          execution_uuid: "exec-1",

          status: "COMPLETED",

          started_at: "2026-05-30T12:00:00Z",

          completed_at: "2026-05-30T12:00:01Z",

          duration_ms: 40,

          created_at: "2026-05-30T12:00:00Z",

        },

      ],

    });

  });



  it("renders grading validation dashboard", async () => {

    render(

      <MemoryRouter>

        <GradingValidationPage />

      </MemoryRouter>,

    );



    await waitFor(() => {

      expect(screen.getByRole("heading", { name: "Grading Validation" })).toBeInTheDocument();

    });



    expect(screen.getAllByText("Prediction Accuracy").length).toBeGreaterThan(0);

    expect(screen.getAllByText("Calibration Metrics").length).toBeGreaterThan(0);

    expect(screen.getByText("Drift Metrics")).toBeInTheDocument();

    expect(screen.getAllByText("Reliability Metrics").length).toBeGreaterThan(0);

    expect(screen.getAllByText("Recommendation Outcomes").length).toBeGreaterThan(0);

    expect(screen.getByText("Agent Activity")).toBeInTheDocument();

  });

});

