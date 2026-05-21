import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Homepage from "./pages/Homepage";
import AppPage from "./pages/AppPage";
import PdfPage from "./pages/PdfPage";
import AuthCallback from "./pages/AuthCallback";
import { EvalProvider } from "./context/EvalContext";
import { AuthProvider, useAuth } from "./context/AuthContext";
import Header from "./components/layout/Header";

function ProtectedRoute({ children }) {
  const { user, loading } = useAuth();
  if (loading) return null;
  if (!user) return <Navigate to="/" replace />;
  return children;
}

function App() {
  return (
    <Router>
      <AuthProvider>
        <EvalProvider>
          <Header />
          <Routes>
            <Route path="/" element={<Homepage />} />
            <Route path="/app" element={<ProtectedRoute><AppPage /></ProtectedRoute>} />
            <Route path="/app/pdf" element={<ProtectedRoute><PdfPage /></ProtectedRoute>} />
            <Route path="/auth/callback" element={<AuthCallback />} />

            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </EvalProvider>
      </AuthProvider>
    </Router>
  );
}

export default App;
