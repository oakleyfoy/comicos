import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { PrivacyPolicyPage } from "../PrivacyPolicyPage";

describe("PrivacyPolicyPage", () => {
  it("renders the public privacy policy", () => {
    render(
      <MemoryRouter initialEntries={["/privacy"]}>
        <PrivacyPolicyPage />
      </MemoryRouter>,
    );

    expect(screen.getByRole("heading", { name: /Privacy Policy for ComicOS Midtown Sync Helper/i })).toBeInTheDocument();
    expect(screen.getByText(/support@comicosapp.com/i)).toBeInTheDocument();
    expect(screen.getByText("Website:")).toBeInTheDocument();
  });
});
