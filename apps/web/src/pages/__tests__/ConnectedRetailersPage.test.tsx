import { render } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { ConnectedRetailersPage } from "../ConnectedRetailersPage";

describe("ConnectedRetailersPage", () => {
  it("redirects to the HTML import flow", () => {
    render(
      <MemoryRouter initialEntries={["/connected-retailers"]}>
        <Routes>
          <Route path="/connected-retailers" element={<ConnectedRetailersPage />} />
          <Route path="/connected-retailers/import" element={<div>import page</div>} />
        </Routes>
      </MemoryRouter>,
    );

    expect(document.body.textContent).toContain("import page");
  });
});
