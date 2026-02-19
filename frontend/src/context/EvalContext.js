// frontend/src/context/EvalContext.js
import React, { createContext, useContext, useEffect, useMemo, useState } from "react";

const EvalContext = createContext(null);

const STORAGE_KEY = "resume_evaluator_eval_state_v1";

// Keep only JSON-safe data here (no File objects, no Blobs, no functions).
const DEFAULT_STATE = {
  // user inputs
  jobDescription: "",
  model: "gpt-5.1",
  mode: "fast",
  useCache: true,

  // last analysis response
  analysis: null,

  // canonical skeleton used for PDF generation (optimized)
  resumeCanonical: null,

  // editable skeleton for rescore/edit flow (typically starts from optimized)
  editableSkeleton: null,

  // pdf/editor preferences
  sectionOrder: [],
  enabledSectionIds: [],

  // scoring after edits
  rescore: null,

  // convenience display fields
  resumeFileName: "",
  generatedFileNameHint: "Resume_Optimized.pdf",

  // optional: keywords list used for PDF generation (if your UI uses it)
  keywordsSuggested: [],
  atsScore: null,
  optimizedAtsScore: null,
};

function safeParse(jsonStr) {
  try {
    return JSON.parse(jsonStr);
  } catch {
    return null;
  }
}

function sanitizeStateForStorage(state) {
  // Ensure nothing non-serializable sneaks in
  // (your state should already be safe, but this keeps it robust)
  return {
    ...DEFAULT_STATE,
    ...state,
  };
}

export function EvalProvider({ children }) {
  const [evalState, setEvalState] = useState(() => {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? safeParse(raw) : null;
    return parsed ? { ...DEFAULT_STATE, ...parsed } : { ...DEFAULT_STATE };
  });

  // Persist on every change
  useEffect(() => {
    try {
      const clean = sanitizeStateForStorage(evalState);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(clean));
    } catch {
      // ignore storage quota errors etc.
    }
  }, [evalState]);

  const hasSession = useMemo(() => {
    // Consider it a session if we have analysis OR a canonical skeleton
    return !!(evalState?.analysis || evalState?.resumeCanonical || evalState?.editableSkeleton);
  }, [evalState]);

  const resetEval = ({ clearStorage = false } = {}) => {
    setEvalState({ ...DEFAULT_STATE });
    if (clearStorage) {
      try {
        window.localStorage.removeItem(STORAGE_KEY);
      } catch {
        // ignore
      }
    }
  };

  const value = useMemo(
    () => ({
      evalState,
      setEvalState,
      resetEval,
      hasSession,
    }),
    [evalState, hasSession]
  );

  return <EvalContext.Provider value={value}>{children}</EvalContext.Provider>;
}

export function useEval() {
  const ctx = useContext(EvalContext);
  if (!ctx) throw new Error("useEval must be used within EvalProvider");
  return ctx;
}