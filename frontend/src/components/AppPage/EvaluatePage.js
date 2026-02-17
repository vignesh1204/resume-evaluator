import React, { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import pdfToText from "react-pdftotext";

import DragNDrop from "../DragNDrop/DragNDrop";
import CustomButton from "../Button/CustomButton";
import { useEval } from "../../context/EvalContext";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://localhost:5000";

const getCompanyFromUrl = (url) => {
  try {
    const host = new URL(url).hostname.replace("www.", "");
    const base = host.split(".")[0] || "Company";
    return base.charAt(0).toUpperCase() + base.slice(1);
  } catch {
    return "Company";
  }
};

const getNameFromUpdatedJson = (json) => {
  if (!json) return "Resume";
  if (json.resume && json.resume.name) return String(json.resume.name).trim().split(" ")[0] || "Resume";
  if (json.name) return String(json.name).trim().split(" ")[0] || "Resume";
  return "Resume";
};

const PriorityPill = ({ priority }) => {
  const cls =
    priority === "High"
      ? "border-red-200/25 bg-red-300/10 text-red-100"
      : priority === "Medium"
      ? "border-amber-200/25 bg-amber-300/10 text-amber-100"
      : "border-emerald-200/25 bg-emerald-300/10 text-emerald-100";

  return (
    <span className={`shrink-0 rounded-full border px-3 py-1 text-xs font-semibold ${cls}`}>
      {priority || "Info"}
    </span>
  );
};

const EvaluatePage = () => {
  const navigate = useNavigate();
  const { evalState, setEvalState } = useEval();

  const [uploadedFile, setUploadedFile] = useState(null);

  const [jdMode, setJdMode] = useState("link"); // "link" | "text"
  const [jobDescLink, setJobDescLink] = useState("");
  const [jobDescText, setJobDescText] = useState("");

  const [isEvaluating, setIsEvaluating] = useState(false);
  const [error, setError] = useState(null);

  const hasResult = evalState?.atsScore !== null && evalState?.atsScore !== undefined;

  const canEvaluate = useMemo(() => {
    if (isEvaluating) return false;
    if (!uploadedFile) return false;
    if (jdMode === "link") return !!jobDescLink.trim();
    return !!jobDescText.trim();
  }, [isEvaluating, uploadedFile, jdMode, jobDescLink, jobDescText]);

  const onClickEvaluate = async () => {
    setError(null);
    setIsEvaluating(true);

    try {
      if (!uploadedFile) throw new Error("Please upload a resume PDF.");
      if (jdMode === "link" && !jobDescLink.trim()) throw new Error("Please paste a job link.");
      if (jdMode === "text" && !jobDescText.trim()) throw new Error("Please paste the job description text.");

      const resumeText = await pdfToText(uploadedFile);
      const resumeJson = { raw_text: resumeText };

      const payload = {
        resume_json: resumeJson,
        job_description_link: jdMode === "link" ? jobDescLink.trim() : "",
        job_description_text: jdMode === "text" ? jobDescText.trim() : "",
        keyword_suggestions_max: 10,
        changes_max: 5,
      };

      const resp = await fetch(`${API_BASE}/evaluate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`Server error (${resp.status}): ${errText}`);
      }

      const data = await resp.json();

      const atsScore = data.ats_score ?? null;
      const optimizedAtsScore = data.optimized_ats_score ?? null;
      const changes = Array.isArray(data.changes) ? data.changes.slice(0, 5) : [];
      const keywordsSuggested = Array.isArray(data.keywords_suggested) ? data.keywords_suggested.slice(0, 10) : [];

      // IMPORTANT: canonical resume used by PdfPage
      const resumeCanonical = data.optimized_resume_canonical ?? null;

      const company = getCompanyFromUrl(jobDescLink);
      const name = getNameFromUpdatedJson(resumeCanonical?.header ? { resume: { name: resumeCanonical.header.name } } : null);
      const fileNameHint = `${name}_${company}_Optimized.pdf`;

      setEvalState({
        jobDescLink: jobDescLink.trim(),
        jobDescText: jobDescText.trim(),
        atsScore,
        optimizedAtsScore,
        changes,
        keywordsSuggested,
        resumeCanonical,
        generatedFileNameHint: fileNameHint,
        sectionOrder: [], // will be derived in PdfPage
        enabledSectionIds: [], // optional
      });
    } catch (e) {
      setError(e.message || "Evaluation failed.");
    } finally {
      setIsEvaluating(false);
    }
  };

  const onClickGoPdf = () => {
    if (!evalState?.resumeCanonical) {
      setError("No optimized resume data found. Please evaluate first.");
      return;
    }
    navigate("/app/pdf");
  };

  return (
    <div className="min-h-screen w-full bg-[radial-gradient(1200px_circle_at_10%_10%,rgba(124,255,178,0.18),transparent_40%),radial-gradient(900px_circle_at_90%_20%,rgba(99,102,241,0.25),transparent_45%),linear-gradient(to_bottom_right,#0b1220,#070a12)] text-white">
      {/* Top bar */}
      <div className="sticky top-0 z-50 border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/15 shadow-soft">
              <span className="text-lg">📈</span>
            </div>
            <div className="min-w-0">
              <div className="truncate text-xl font-extrabold tracking-tight">ATS Evaluation</div>
              <div className="text-sm text-white/70">Upload + compare against a job description.</div>
            </div>
          </div>

          <div className="flex items-center justify-between gap-3 sm:justify-end">
            <div className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/10 px-4 py-2 text-xs text-white/75">
              <span className={`h-2 w-2 rounded-full ${isEvaluating ? "bg-emerald-300" : "bg-white/50"}`} />
              {isEvaluating ? "Evaluating…" : hasResult ? "Evaluation ready" : "Waiting for inputs"}
            </div>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        {!hasResult ? (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[1fr_420px]">
            {/* Inputs */}
            <div className="rounded-3xl border border-white/12 bg-white/[0.08] p-5 shadow-soft backdrop-blur-xl sm:p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                <div className="min-w-0">
                  <h1 className="text-2xl font-extrabold tracking-tight sm:text-3xl">Evaluate your resume</h1>
                  <p className="mt-2 text-sm text-white/70">
                    Upload a PDF + provide either a job link or the job description text.
                  </p>
                </div>
                <div className="w-fit rounded-2xl border border-white/12 bg-black/20 px-3 py-2 text-xs text-white/70">
                  Output: score + 5 fixes
                </div>
              </div>

              {/* JD Mode toggle */}
              <div className="mt-6">
                <div className="text-sm font-semibold text-white/90">Job description input</div>
                <div className="mt-3 inline-flex w-full rounded-2xl border border-white/12 bg-black/20 p-1 sm:w-auto">
                  <button
                    className={[
                      "flex-1 rounded-xl px-4 py-2 text-sm transition sm:flex-none",
                      jdMode === "link" ? "bg-white/10 text-white" : "text-white/70 hover:text-white",
                    ].join(" ")}
                    onClick={() => setJdMode("link")}
                    type="button"
                  >
                    Paste link
                  </button>
                  <button
                    className={[
                      "flex-1 rounded-xl px-4 py-2 text-sm transition sm:flex-none",
                      jdMode === "text" ? "bg-white/10 text-white" : "text-white/70 hover:text-white",
                    ].join(" ")}
                    onClick={() => setJdMode("text")}
                    type="button"
                  >
                    Paste text
                  </button>
                </div>
              </div>

              {/* JD inputs */}
              {jdMode === "link" ? (
                <div className="mt-4">
                  <label className="text-sm font-semibold text-white/90">Job link</label>
                  <textarea
                    placeholder="Paste job link here…"
                    className="mt-2 h-12 w-full resize-none rounded-2xl border border-white/12 bg-black/25 px-4 py-3 text-sm text-white outline-none placeholder:text-white/50 focus:border-white/25"
                    value={jobDescLink}
                    onChange={(e) => setJobDescLink(e.target.value)}
                  />
                  <div className="mt-2 text-xs text-white/60">
                    Some sites block extraction — if that happens, switch to “Paste text”.
                  </div>
                </div>
              ) : (
                <div className="mt-4">
                  <label className="text-sm font-semibold text-white/90">Job description text</label>
                  <textarea
                    placeholder="Paste the full job description text here…"
                    className="mt-2 h-44 w-full resize-y rounded-2xl border border-white/12 bg-black/25 px-4 py-3 text-sm text-white outline-none placeholder:text-white/50 focus:border-white/25 sm:h-52"
                    value={jobDescText}
                    onChange={(e) => setJobDescText(e.target.value)}
                  />
                </div>
              )}

              {/* Resume upload */}
              <div className="mt-6">
                <label className="text-sm font-semibold text-white/90">Resume PDF</label>
                <div className="mt-2 rounded-3xl border border-white/12 bg-black/15 p-3">
                  <div className="flex justify-center">
                    {/* Responsive: let DragNDrop fill width on small screens */}
                    <div className="w-full max-w-[520px]">
                      <DragNDrop width="100%" height="260px" setDroppedFile={setUploadedFile} />
                    </div>
                  </div>
                </div>
                <div className="mt-2 text-xs text-white/65">
                  {uploadedFile ? (
                    <>
                      Selected: <span className="font-semibold text-white">{uploadedFile.name}</span>
                    </>
                  ) : (
                    "Drag and drop a PDF, or click to select."
                  )}
                </div>
              </div>

              {/* Evaluate button */}
              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
                <CustomButton
                  text={isEvaluating ? "Evaluating…" : "Evaluate"}
                  disabled={!canEvaluate}
                  onClick={onClickEvaluate}
                  className="w-full sm:w-44"
                />
                <div className="text-xs text-white/60">
                  We’ll show your ATS score + the top 5 changes to improve it.
                </div>
              </div>

              {error && (
                <div className="mt-5 rounded-2xl border border-red-300/40 bg-red-200/90 p-4 text-red-950">
                  <div className="font-extrabold">Something went wrong</div>
                  <div className="mt-1 text-sm leading-relaxed">{error}</div>
                </div>
              )}
            </div>

            {/* Side card */}
            <div className="rounded-3xl border border-white/12 bg-white/[0.06] p-5 shadow-soft backdrop-blur-xl sm:p-6">
              <div className="text-sm font-extrabold">What you’ll get</div>
              <div className="mt-4 space-y-3 text-sm text-white/75">
                <div className="flex items-start gap-3">
                  <span className="mt-1 h-2 w-2 rounded-full bg-emerald-300" />
                  Big ATS score that’s easy to compare across jobs
                </div>
                <div className="flex items-start gap-3">
                  <span className="mt-1 h-2 w-2 rounded-full bg-emerald-300" />
                  5 prioritized fixes (keywords, bullets, formatting, etc.)
                </div>
                <div className="flex items-start gap-3">
                  <span className="mt-1 h-2 w-2 rounded-full bg-emerald-300" />
                  Keyword suggestions (up to 10) for the optimized PDF step
                </div>
              </div>
            </div>
          </div>
        ) : (
          // Results view
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[380px_1fr]">
            {/* Score */}
            <div className="rounded-3xl border border-white/12 bg-white/[0.08] p-5 shadow-soft backdrop-blur-xl sm:p-6">
              <div className="text-sm text-white/70">ATS Score</div>
              <div className="mt-2 text-5xl font-extrabold tracking-tight sm:text-6xl">
                {evalState.atsScore ?? "—"}
              </div>
              <div className="mt-2 text-sm text-white/70">
                Higher is better. Improve score by applying the suggested changes + keywords.
              </div>

              <div className="mt-6 rounded-2xl border border-white/12 bg-black/20 p-4">
                <div className="text-xs text-white/60">Suggested keywords (top)</div>
                <div className="mt-3 flex flex-wrap gap-2">
                  {(evalState.keywordsSuggested || []).slice(0, 10).map((k, i) => (
                    <span
                      key={i}
                      className="rounded-full border border-white/12 bg-white/10 px-3 py-1 text-xs text-white/80"
                    >
                      {k}
                    </span>
                  ))}
                  {(!evalState.keywordsSuggested || evalState.keywordsSuggested.length === 0) && (
                    <span className="text-xs text-white/60">No keyword suggestions returned.</span>
                  )}
                </div>
              </div>

              <div className="mt-6">
                <CustomButton
                  text="Generate optimized PDF"
                  onClick={onClickGoPdf}
                  disabled={!evalState.resumeCanonical}
                  className="w-full"
                />
                <div className="mt-2 text-xs text-white/60">
                  Next: choose keyword count (3–10) → generate preview → download.
                </div>
              </div>

              {error && (
                <div className="mt-5 rounded-2xl border border-red-300/40 bg-red-200/90 p-4 text-red-950">
                  <div className="font-extrabold">Something went wrong</div>
                  <div className="mt-1 text-sm leading-relaxed">{error}</div>
                </div>
              )}
            </div>

            {/* Changes list */}
            <div className="rounded-3xl border border-white/12 bg-white/[0.08] p-5 shadow-soft backdrop-blur-xl sm:p-6">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
                <div className="min-w-0">
                  <h2 className="text-xl font-extrabold tracking-tight sm:text-2xl">
                    Top 5 changes to improve your ATS match
                  </h2>
                  <p className="mt-2 text-sm text-white/70">
                    Keyword alignment is highest priority. Fix these before regenerating your PDF.
                  </p>
                </div>
                <div className="w-fit rounded-2xl border border-white/12 bg-black/20 px-3 py-2 text-xs text-white/70">
                  {Array.isArray(evalState.changes) ? evalState.changes.length : 0} items
                </div>
              </div>

              <div className="mt-5 space-y-3">
                {(evalState.changes || []).slice(0, 5).map((c, idx) => (
                  <div key={idx} className="rounded-2xl border border-white/10 bg-black/20 p-4 sm:p-5">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="min-w-0">
                        <div className="text-xs text-white/60">{c.type || "Recommendation"}</div>
                        <div className="mt-1 text-base font-extrabold text-white sm:text-lg">
                          {c.title || `Change #${idx + 1}`}
                        </div>
                      </div>
                      <PriorityPill priority={c.priority || (idx === 0 ? "High" : "Medium")} />
                    </div>

                    <div className="mt-3 text-sm text-white/75 leading-relaxed">
                      {c.detail || c.description || "No details provided."}
                    </div>
                  </div>
                ))}

                {(!evalState.changes || evalState.changes.length === 0) && (
                  <div className="rounded-2xl border border-dashed border-white/15 bg-black/15 p-5 text-sm text-white/70">
                    No changes returned by the evaluator. Check your backend `/evaluate` response format.
                  </div>
                )}
              </div>

              <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:gap-4">
                <button
                  type="button"
                  className="w-full rounded-2xl border border-white/12 bg-white/10 px-4 py-2 text-sm text-white/80 hover:bg-white/15 transition sm:w-auto"
                  onClick={() => {
                    setEvalState({
                      jobDescLink: "",
                      jobDescText: "",
                      atsScore: null,
                      optimizedAtsScore: null,
                      changes: [],
                      keywordsSuggested: [],
                      resumeCanonical: null,
                      generatedFileNameHint: "Resume_Optimized.pdf",
                      sectionOrder: [],
                      enabledSectionIds: [],
                    });
                  }}
                >
                  Start over
                </button>
                <div className="text-xs text-white/60">
                  Want to test against another job? Start over and re-evaluate.
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default EvaluatePage;
