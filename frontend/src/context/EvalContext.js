import React, { createContext, useContext, useMemo, useState } from "react";

const EvalContext = createContext(null);

export const EvalProvider = ({ children }) => {
  const [evalState, setEvalState] = useState({
    jobDescLink: "",
    jobDescText: "",
    atsScore: null,
    optimizedAtsScore: null,
    changes: [],
    keywordsSuggested: [],
    updatedResumeJson: null,
    generatedFileNameHint: "Resume_Optimized.pdf",
    sectionOrder: [],
  });


  const value = useMemo(() => ({ evalState, setEvalState }), [evalState]);

  return <EvalContext.Provider value={value}>{children}</EvalContext.Provider>;
};

export const useEval = () => {
  const ctx = useContext(EvalContext);
  if (!ctx) throw new Error("useEval must be used within EvalProvider");
  return ctx;
};
