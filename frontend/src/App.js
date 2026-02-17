import React from "react";
import { BrowserRouter as Router, Routes, Route, Navigate } from "react-router-dom";

import Homepage from "./pages/Homepage";
import AppPage from "./pages/AppPage";
import PdfPage from "./pages/PdfPage";
import { EvalProvider } from "./context/EvalContext";

function App() {
  return (
    <Router>
      <EvalProvider>
        <Routes>
          <Route path="/" element={<Homepage />} />
          <Route path="/app" element={<AppPage />} />
          <Route path="/app/pdf" element={<PdfPage />} />

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </EvalProvider>
    </Router>
  );
}

export default App;
