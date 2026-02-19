// frontend/src/components/AppPage/EvaluatePage.js
import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../Button/CustomButton";
import { useEval } from "../../context/EvalContext";
import { analyzeResumeMultipart } from "../../utils/api";
import NoirShell from "../layout/NoirShell";

// Simulated progress: approaches ~88% over ~60s so we don't hit 100% before the request completes.
const PROGRESS_CAP = 88;
const PROGRESS_TAU = 28; // seconds for ~63% of cap
function progressFromElapsedMs(ms) {
  const s = ms / 1000;
  return Math.min(PROGRESS_CAP, PROGRESS_CAP * (1 - Math.exp(-s / PROGRESS_TAU)));
}

const MODE_OPTIONS = [
  { value: "fast", label: "Fast (cheaper, quicker)" },
  { value: "quality", label: "Quality (more thorough)" },
];

const MODEL_OPTIONS = [
  { value: "gpt-5.1", label: "gpt-5.1 (cheap)" },
  { value: "gpt-5.2", label: "gpt-5.2 (quality)" },
];

function ScoreCard({ title, score }) {
  return (
    <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-4">
      <div className="text-xs text-white/60">{title}</div>
      <div className="mt-1 text-3xl font-extrabold tracking-tight">{score ?? "—"}</div>
    </div>
  );
}

function PillList({ title, items }) {
  if (!items || items.length === 0) return null;
  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="text-sm font-extrabold">{title}</div>
      <div className="mt-3 flex flex-wrap gap-2">
        {items.map((x, i) => (
          <span
            key={`${title}-${i}`}
            className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80"
          >
            {x}
          </span>
        ))}
      </div>
    </div>
  );
}

function RewriteList({ items }) {
  const safeItems = Array.isArray(items) ? items : [];

  if (safeItems.length === 0) return null;

  return (
    <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
      <div className="text-sm font-extrabold">Rewrite suggestions</div>
      <div className="mt-3 space-y-3">
        {safeItems.map((r, i) => (
          <div key={i} className="rounded-xl border border-white/10 bg-white/5 p-3">
            <div className="text-xs text-white/55">{r.target}</div>
            <div className="mt-2">
              <div className="text-xs font-semibold text-white/70">Before</div>
              <div className="mt-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white/85 whitespace-pre-wrap">
                {r.before}
              </div>
            </div>
            <div className="mt-2">
              <div className="text-xs font-semibold text-white/70">After</div>
              <div className="mt-1 rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white/85 whitespace-pre-wrap">
                {r.after}
              </div>
            </div>
            {r.reason && (
              <div className="mt-2 text-xs text-white/60">
                Reason: <span className="text-white/80">{r.reason}</span>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}

export default function EvaluatePage() {
  const navigate = useNavigate();
  const { evalState, setEvalState, resetEval, hasSession } = useEval();

  const [file, setFile] = useState(null);
  const [jd, setJd] = useState(evalState.jobDescription || "");
  const [mode, setMode] = useState(evalState.mode || "fast");
  const [model, setModel] = useState(evalState.model || "gpt-5.1");

  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [analysisProgress, setAnalysisProgress] = useState(null); // 0–100 or null when idle
  const progressIntervalRef = useRef(null);
  const progressStartRef = useRef(null);

  const analysis = evalState.analysis;

  useEffect(() => {
    return () => {
      if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    };
  }, []);

  const canAnalyze = useMemo(() => {
    return !!file && jd.trim().length > 0 && !busy;
  }, [file, jd, busy]);

  const onAnalyze = useCallback(async () => {
    setError(null);
    setBusy(true);
    setAnalysisProgress(0);
    progressStartRef.current = Date.now();

    if (progressIntervalRef.current) clearInterval(progressIntervalRef.current);
    progressIntervalRef.current = setInterval(() => {
      const elapsed = Date.now() - (progressStartRef.current || Date.now());
      setAnalysisProgress((p) => {
        const next = progressFromElapsedMs(elapsed);
        return Math.max(p, Math.round(next));
      });
    }, 400);

    try {
      const result = await analyzeResumeMultipart({
        file,
        jobDescription: jd,
        model,
        mode,
        useCache: true,
      });

      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      setAnalysisProgress(100);
      setTimeout(() => setAnalysisProgress(null), 600);

      const optimizedSkeleton = result?.optimized?.resume || null;
      const originalScore = result?.original?.ats?.score ?? null;
      const optimizedScore = result?.optimized?.ats?.score ?? null;

      const sections = optimizedSkeleton?.sections || [];
      const derivedOrder = sections.map((s) => s.id).filter(Boolean);
      const enabled = derivedOrder.slice();

      setEvalState((prev) => ({
        ...prev,
        jobDescription: jd,
        model,
        mode,
        useCache: true,
        resumeFileName: file?.name || "",
        analysis: result,

        // important: PDF generation should use this canonical optimized skeleton
        resumeCanonical: optimizedSkeleton,

        // editable starts as optimized (user can reorder/toggle)
        editableSkeleton: optimizedSkeleton,

        sectionOrder: derivedOrder,
        enabledSectionIds: enabled,

        rescore: null,

        atsScore: originalScore,
        optimizedAtsScore: optimizedScore,

        // optional
        keywordsSuggested: result?.improvements?.missing_keywords || [],
        generatedFileNameHint: "Resume_Optimized.pdf",
      }));
    } catch (e) {
      if (progressIntervalRef.current) {
        clearInterval(progressIntervalRef.current);
        progressIntervalRef.current = null;
      }
      setAnalysisProgress(null);
      setError(e?.message || "Analyze failed");
    } finally {
      setBusy(false);
    }
  }, [file, jd, model, mode, setEvalState]);

  const originalScore = analysis?.original?.ats?.score ?? null;
  const optimizedScore = analysis?.optimized?.ats?.score ?? null;

  return (
    <NoirShell>
      <div className="mx-auto max-w-6xl px-4 py-8 sm:px-6">
        {/* Session banner */}
        {hasSession && (
          <div className="mb-5 rounded-3xl border border-white/10 bg-white/5 p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div>
                <div className="text-sm font-extrabold">You have a previous session</div>
                <div className="mt-1 text-xs text-white/65">
                  Resume evaluation data was found in this browser.
                </div>
              </div>
              <div className="flex flex-col gap-2 sm:flex-row">
                <button
                  type="button"
                  onClick={() => navigate("/app/pdf")}
                  className="rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/85 hover:bg-white/10"
                >
                  Go to PDF Studio →
                </button>
                <button
                  type="button"
                  onClick={() => {
                    resetEval(); // keep storage, just reset in-memory (it will overwrite)
                    // optional: keep inputs too
                    setJd("");
                    setFile(null);
                  }}
                  className="rounded-2xl border border-white/10 bg-black/30 px-4 py-2 text-sm text-white/85 hover:bg-black/40"
                >
                  Start fresh (keep storage)
                </button>
                <button
                  type="button"
                  onClick={() => {
                    resetEval({ clearStorage: true }); // removes localStorage session
                    setJd("");
                    setFile(null);
                  }}
                  className="rounded-2xl border border-rose-300/20 bg-rose-300/10 px-4 py-2 text-sm text-rose-100 hover:bg-rose-300/15"
                >
                  Clear session
                </button>
              </div>
            </div>
          </div>
        )}

        <div className="rounded-3xl border border-white/10 bg-white/5 p-6">
          <div className="text-2xl font-extrabold tracking-tight">Evaluate your resume</div>
          <div className="mt-2 text-sm text-white/70">
            Upload a PDF + paste a job description. We’ll return parsing + ATS scoring + an optimized version.
          </div>

          <div className="mt-6 grid grid-cols-1 gap-4 lg:grid-cols-2">
            {/* Upload + settings */}
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm font-extrabold">Resume PDF</div>
              <input
                type="file"
                accept="application/pdf"
                onChange={(e) => setFile(e.target.files?.[0] || null)}
                className="mt-3 w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm"
              />
              {file && (
                <div className="mt-2 text-xs text-white/60">
                  Selected: <span className="text-white/85">{file.name}</span>
                </div>
              )}

              <div className="mt-5 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div>
                  <div className="text-xs font-semibold text-white/70">Mode</div>
                  <select
                    value={mode}
                    onChange={(e) => setMode(e.target.value)}
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm"
                  >
                    {MODE_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <div className="text-xs font-semibold text-white/70">Model</div>
                  <select
                    value={model}
                    onChange={(e) => setModel(e.target.value)}
                    className="mt-2 w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm"
                  >
                    {MODEL_OPTIONS.map((o) => (
                      <option key={o.value} value={o.value}>
                        {o.label}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              <div className="mt-5">
                <CustomButton
                  text={busy ? "Analyzing…" : "Analyze"}
                  onClick={onAnalyze}
                  disabled={!canAnalyze}
                  className="w-full noir-btn"
                />
                {analysisProgress != null && (
                  <div className="mt-3">
                    <div className="flex justify-between text-xs text-white/60 mb-1">
                      <span>Progress</span>
                      <span>{analysisProgress}%</span>
                    </div>
                    <div className="h-2 w-full rounded-full bg-white/10 overflow-hidden">
                      <div
                        className="h-full rounded-full bg-cyan-400/90 transition-[width] duration-300 ease-out"
                        style={{ width: `${analysisProgress}%` }}
                      />
                    </div>
                  </div>
                )}
                <div className="mt-2 text-xs text-white/55">
                  Tip: start with <span className="font-semibold">gpt-5.1</span> + fast.
                </div>
              </div>

              {error && (
                <div className="mt-4 rounded-2xl border border-rose-300/30 bg-rose-300/10 p-4 text-rose-100">
                  <div className="font-extrabold">Error</div>
                  <div className="mt-1 text-sm">{error}</div>
                </div>
              )}
            </div>

            {/* JD */}
            <div className="rounded-2xl border border-white/10 bg-black/20 p-4">
              <div className="text-sm font-extrabold">Job description</div>
              <textarea
                value={jd}
                onChange={(e) => setJd(e.target.value)}
                rows={14}
                placeholder="Paste the JD here…"
                className="mt-3 w-full rounded-2xl border border-white/10 bg-black/25 px-4 py-3 text-sm text-white outline-none focus:border-white/20"
              />
              <div className="mt-2 text-xs text-white/55">
                Best results if you paste the full JD (responsibilities + requirements).
              </div>
            </div>
          </div>
        </div>

        {/* Results */}
        {analysis && (
          <div className="mt-6 grid grid-cols-1 gap-6 lg:grid-cols-[1fr_360px]">
            <div className="space-y-4">
              <PillList
                title="Missing keywords"
                items={analysis?.improvements?.missing_keywords?.slice(0, 40) || []}
              />
              <PillList
                title="Priority actions"
                items={analysis?.improvements?.priority_actions || []}
              />
              <RewriteList items={analysis?.improvements?.rewrite_suggestions || []} />
            </div>

            <div className="rounded-3xl border border-white/10 bg-white/5 p-5">
              <div className="text-lg font-extrabold">Scores</div>
              <div className="mt-3 grid grid-cols-1 gap-3">
                <ScoreCard title="Original ATS" score={originalScore} />
                <ScoreCard title="Optimized ATS" score={optimizedScore} />
              </div>

              <div className="mt-5">
                <div className="text-sm font-extrabold">Next</div>
                <div className="mt-1 text-sm text-white/70">
                  Continue to PDF Studio to preview + reorder + download.
                </div>
                <div className="mt-4">
                  <CustomButton
                    text="Continue →"
                    onClick={() => navigate("/app/pdf")}
                    className="w-full noir-btn"
                  />
                </div>
              </div>

              {analysis?.telemetry && (
                <div className="mt-5 rounded-2xl border border-white/10 bg-black/20 p-4 text-xs text-white/65">
                  <div className="font-semibold text-white/75">Telemetry</div>
                  <div className="mt-2 space-y-1">
                    <div>model: {analysis.telemetry.model}</div>
                    <div>mode: {analysis.telemetry.mode}</div>
                    <div>latency_ms: {analysis.telemetry.latency_ms}</div>
                    {analysis.telemetry.estimated_cost_usd != null && (
                      <div>est_cost: ${Number(analysis.telemetry.estimated_cost_usd).toFixed(4)}</div>
                    )}
                    <div>cache_hit: {String(analysis.telemetry.cache_hit)}</div>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </NoirShell>
  );
}