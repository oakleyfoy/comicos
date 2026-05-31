import { render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { apiClient } from "../../api/client";
import { RecommendationIntelligenceCertificationPage } from "../RecommendationIntelligenceCertificationPage";

vi.mock("../../components/AppShell", () => ({
  AppShell: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

vi.mock("../../components/PageHeader", () => ({
  PageHeader: ({ title }: { title: string }) => <h1>{title}</h1>,
}));

vi.mock("../../components/StatusBanner", () => ({
  StatusBanner: ({ children }: { children: ReactNode }) => <div>{children}</div>,
}));

describe("RecommendationIntelligenceCertificationPage", () => {
  beforeEach(() => {
    vi.restoreAllMocks();
    vi.spyOn(apiClient, "getRecommendationIntelligenceValidation").mockResolvedValue({
      overall_status: "PASS",
      checks: [{ check_code: "p51_04", title: "V2", status: "PASS", summary: "ok", details_json: {} }],
    });
    vi.spyOn(apiClient, "getRecommendationIntelligenceHealth").mockResolvedValue({
      overall_status: "HEALTHY",
      components: [{ component_code: "v2", title: "V2", health_status: "HEALTHY", summary: "ok", details_json: {} }],
    });
    vi.spyOn(apiClient, "getRecommendationIntelligenceCalibration").mockResolvedValue({
      overall_status: "PASS",
      total_recommendations: 10,
      tier_distribution: { WATCH: 5, BUY: 5 },
      type_distribution: {},
      number_one_count: 2,
      key_issue_in_top_count: 1,
      user_preference_component_active: true,
      score_variance: 12,
      findings: [],
      details_json: {},
    });
    vi.spyOn(apiClient, "getRecommendationIntelligenceSummary").mockResolvedValue({
      total_recommendations_v2: 10,
      must_buy_count: 1,
      strong_buy_count: 2,
      buy_count: 2,
      watch_count: 3,
      pass_count: 2,
      investment_number_one_count: 1,
      start_run_count: 0,
      key_issue_count: 1,
      ratio_variant_count: 0,
      user_preference_match_count: 0,
      average_score: 55,
      readiness_score: 90,
      v1_recommendation_count: 8,
      v2_run_count: 1,
      explanation_count: 10,
      v1_vs_v2_moved_up: 3,
      v1_vs_v2_moved_down: 2,
    });
    vi.spyOn(apiClient, "getRecommendationIntelligenceCertification").mockResolvedValue({
      platform_certified: true,
      certification_status: "APPROVED_FOR_RECOMMENDATION_USE",
      go_live_recommendation: "APPROVED_FOR_RECOMMENDATION_USE",
      readiness_score: 90,
      certification_date: "2026-05-31",
      certification_version: "P51-05",
      validation_status: "PASS",
      health_status: "HEALTHY",
      calibration_status: "PASS",
      certification_notes: ["Certified for advisory use."],
    });
  });

  it("renders certification dashboard", async () => {
    render(
      <MemoryRouter>
        <RecommendationIntelligenceCertificationPage />
      </MemoryRouter>,
    );
    await waitFor(() => {
      expect(screen.getByRole("heading", { name: "Recommendation Intelligence Certification" })).toBeInTheDocument();
    });
    expect(screen.getByText(/Validation/i)).toBeInTheDocument();
    expect(screen.getByText(/APPROVED_FOR_RECOMMENDATION_USE/)).toBeInTheDocument();
  });
});
