import { Navigate, Outlet, useLocation } from "react-router-dom";

import { useAuth } from "../auth/AuthContext";

export function OpsProtectedRoute() {
  const { isAuthenticated, isLoading, isOpsAdmin } = useAuth();
  const location = useLocation();

  if (isLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 text-slate-200">
        Loading operations workspace...
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace state={{ from: location }} />;
  }

  if (!isOpsAdmin) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Outlet />;
}
