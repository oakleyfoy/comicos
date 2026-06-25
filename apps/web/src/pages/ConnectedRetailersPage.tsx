import { Navigate } from "react-router-dom";

/** Legacy route — HTML import only (no credential sync). */
export function ConnectedRetailersPage() {
  return <Navigate to="/connected-retailers/import" replace />;
}
