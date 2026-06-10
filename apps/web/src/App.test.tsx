import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";

import App from "./App";

describe("App routes", () => {
  it("serves the privacy policy without login", async () => {
    render(
      <MemoryRouter initialEntries={["/privacy"]}>
        <App />
      </MemoryRouter>,
    );

    expect(
      await screen.findByRole("heading", { name: /Privacy Policy for ComicOS Midtown Sync Helper/i }),
    ).toBeInTheDocument();
    expect(screen.queryByText(/Sign in to open Collector Home/i)).not.toBeInTheDocument();
  });
});
