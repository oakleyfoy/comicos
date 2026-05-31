import { render, screen, waitFor } from "@testing-library/react";

import type { ReactNode } from "react";

import { MemoryRouter } from "react-router-dom";

import { beforeEach, describe, expect, it, vi } from "vitest";



import { apiClient } from "../../api/client";

import { GradingPlatformPage } from "../GradingPlatformPage";



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



describe("GradingPlatformPage", () => {

  beforeEach(() => {

    vi.restoreAllMocks();

    vi.spyOn(apiClient, "getGradingPlatformSummary").mockResolvedValue({

      condition_summary: {

        analysis_count: 1,

        profile_count: 1,

        average_condition_score: 88,

        average_quality_score: 90,

      },

      prediction_summary: {

        prediction_count: 1,

        average_confidence: 0.72,

        recent_predictions: [],

      },

      recommendation_summary: {

        recommendation_count: 1,

        average_priority: 0.81,

        recent_recommendations: [],

      },

      roi_summary: {

        roi_analysis_count: 1,

        average_roi_percent: 25,

        recent_roi: [],

      },

      calibration_summary: {

        validation_count: 1,

        calibration_metric_count: 1,

        average_accuracy_score: 0.95,

        recent_calibration: [],

      },

      reliability_summary: {

        reliability_metric_count: 1,

        drift_event_count: 0,

        average_reliability_score: 0.85,

        recent_reliability: [],

      },

      top_grading_candidates: [

        {

          id: 1,

          recommendation_uuid: "rec-1",

          prediction_id: 1,

          inventory_copy_id: null,

          recommendation_type: "GRADE",

          title: "Advisory grade candidate",

          description: "Manual review only.",

          confidence_score: 0.72,

          priority_score: 0.81,

          recommendation_status: "OPEN",

          created_at: "2026-05-30T12:00:00Z",

        },

      ],

    });

    vi.spyOn(apiClient, "getGradingPlatformHealth").mockResolvedValue({

      overall_status: "HEALTHY",

      components: [

        {

          component_code: "validation_health",

          title: "Validation Health",

          health_status: "HEALTHY",

          summary: "1 validation record.",

          details_json: {},

        },

      ],

    });

    vi.spyOn(apiClient, "getGradingPlatformValidation").mockResolvedValue({

      overall_status: "PASS",

      platform_certified: true,

      checks: [

        {

          check_code: "condition_intelligence",

          title: "Condition Intelligence",

          status: "PASS",

          summary: "ok",

          details_json: {},

        },

        {

          check_code: "grade_predictions",

          title: "Grade Predictions",

          status: "PASS",

          summary: "ok",

          details_json: {},

        },

        {

          check_code: "grading_recommendations",

          title: "Grading Recommendations",

          status: "PASS",

          summary: "ok",

          details_json: {},

        },

        {

          check_code: "grading_validation",

          title: "Grading Validation",

          status: "PASS",

          summary: "ok",

          details_json: {},

        },

      ],

    });

    vi.spyOn(apiClient, "getGradingPlatformCertification").mockResolvedValue({

      platform_certified: true,

      validation_status: "PASS",

      health_status: "HEALTHY",

      summary: "Certified",

      go_live_recommendation: "APPROVED_FOR_PERSONAL_USE",

      certification_notes: ["Ready for personal production use."],

    });

  });



  it("renders grading platform dashboard", async () => {

    render(

      <MemoryRouter>

        <GradingPlatformPage />

      </MemoryRouter>,

    );



    await waitFor(() => {

      expect(screen.getByRole("heading", { name: "Grading Platform" })).toBeInTheDocument();

    });



    expect(screen.getByText("Certification Status")).toBeInTheDocument();

    expect(screen.getByText("Condition Intelligence Status")).toBeInTheDocument();

    expect(screen.getByText("Prediction Status")).toBeInTheDocument();

    expect(screen.getByText("Top Grading Candidates")).toBeInTheDocument();

  });

});

