import React, { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../Button/CustomButton";
import { useEval } from "../../context/EvalContext";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://localhost:5000";

const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

const SECTION_LABELS = {
  summary: "Summary",
  skills: "Skills",
  experience: "Experience",
  education: "Education",
  projects: "Projects",
  certifications: "Certifications",
  awards: "Awards",
  publications: "Publications",
  volunteering: "Volunteering",
  leadership: "Leadership",
  activities: "Activities",
  additional: "Additional",
};

const prettifyKey = (key) =>
  SECTION_LABELS[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());

function deriveSectionOrderFromCanonical(resumeCanonical) {
  if (!resumeCanonical || !Array.isArray(resumeCanonical.sections)) return [];
  return resumeCanonical.sections
    .map((s) => (s?.id ? String(s.id) : ""))
    .filter((id) => id.trim().length > 0);
}

const ScorePill = ({ label, value, tone = "neutral" }) => {
  const toneCls =
    tone === "good"
      ? "border-emerald-200/25 bg-emerald-300/10 text-emerald-100"
      : tone === "warn"
      ? "border-amber-200/25 bg-amber-300/10 text-amber-100"
      : "border-white/12 bg-white/10 text-white/80";

  return (
    <div className={`rounded-2xl border px-4 py-3 ${toneCls}`}>
      <div className="text-xs opacity-80">{label}</div>
      <div className="mt-1 text-2xl font-extrabold tracking-tight">{value ?? "—"}</div>
    </div>
  );
};

const PdfPage = () => {
  const navigate = useNavigate();
  const { evalState, setEvalState } = useEval();

  const [keywordCount, setKeywordCount] = useState(5);
  const [touched, setTouched] = useState(false);

  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);

  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);
  const [error, setError] = useState(null);

  // section ordering + selection
  const [sectionOrder, setSectionOrder] = useState([]);
  const [enabledMap, setEnabledMap] = useState({});
  const dragIndexRef = useRef(null);

  const timerRef = useRef(null);

  const hasEval = !!evalState?.resumeCanonical;

  useEffect(() => {
    if (!hasEval) return;

    const derived = deriveSectionOrderFromCanonical(evalState.resumeCanonical);

    const savedOrder = evalState?.sectionOrder;
    const finalOrder = Array.isArray(savedOrder) && savedOrder.length > 0 ? savedOrder : derived;
    setSectionOrder(finalOrder);

    // default: all checked
    const savedEnabled = evalState?.enabledSectionIds;
    if (Array.isArray(savedEnabled) && savedEnabled.length > 0) {
      const m = {};
      finalOrder.forEach((id) => {
        m[id] = savedEnabled.includes(id);
      });
      setEnabledMap(m);
    } else {
      const m = {};
      finalOrder.forEach((id) => (m[id] = true));
      setEnabledMap(m);
    }
  }, [hasEval, evalState.resumeCanonical]);

  useEffect(() => {
    return () => {
      if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [pdfPreviewUrl]);

  const validKeywordCount = useMemo(() => {
    const n = Number(keywordCount);
    return Number.isInteger(n) && n >= 3 && n <= 10;
  }, [keywordCount]);

  const fileName = evalState?.generatedFileNameHint || "Resume_Optimized.pdf";

  const baseScore = evalState?.atsScore ?? null;
  const optimizedScore = evalState?.optimizedAtsScore ?? null;

  const scoreTone = useMemo(() => {
    if (optimizedScore == null) return "neutral";
    if (optimizedScore >= 80) return "good";
    if (optimizedScore >= 65) return "warn";
    return "neutral";
  }, [optimizedScore]);

  const scoreDelta = useMemo(() => {
    if (baseScore == null || optimizedScore == null) return null;
    const d = Number(optimizedScore) - Number(baseScore);
    if (!Number.isFinite(d)) return null;
    return d;
  }, [baseScore, optimizedScore]);

  const resetPreview = () => {
    if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewUrl(null);
    setPdfBlob(null);
  };

  const startFakeProgress = () => {
    setProgress(8);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setProgress((p) => {
        if (p >= 92) return p;
        const bump = p < 60 ? 6 : p < 80 ? 3 : 1;
        return clamp(p + bump, 0, 92);
      });
    }, 450);
  };

  const stopFakeProgress = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  };

  // reorder helpers
  const moveItem = (from, to) => {
    setSectionOrder((prev) => {
      const arr = [...prev];
      const [item] = arr.splice(from, 1);
      arr.splice(to, 0, item);
      return arr;
    });
  };

  const onDragStart = (index) => {
    dragIndexRef.current = index;
  };

  const onDragOver = (e) => {
    e.preventDefault();
  };

  const onDrop = (dropIndex) => {
    const fromIndex = dragIndexRef.current;
    if (fromIndex == null || fromIndex === dropIndex) return;
    moveItem(fromIndex, dropIndex);
    dragIndexRef.current = null;
  };

  const onClickUp = (index) => {
    if (index <= 0) return;
    moveItem(index, index - 1);
  };

  const onClickDown = (index) => {
    if (index >= sectionOrder.length - 1) return;
    moveItem(index, index + 1);
  };

  const onClickGenerate = async () => {
    setError(null);
    setIsGenerating(true);
    resetPreview();
    startFakeProgress();

    try {
      if (!hasEval) throw new Error("No evaluation data found. Go back and evaluate first.");

      const enabledSectionIds = sectionOrder.filter((id) => enabledMap[id] !== false);
      if (enabledSectionIds.length === 0) {
        throw new Error("Select at least one section to include in the PDF.");
      }

      setEvalState((prev) => ({
        ...prev,
        sectionOrder,
        enabledSectionIds,
      }));

      const payload = {
        resume_canonical: evalState.resumeCanonical,
        keyword_count: Number(keywordCount),
        keywords_suggested: evalState.keywordsSuggested || [],
        section_order: sectionOrder,
        enabled_section_ids: enabledSectionIds,
      };

      const resp = await fetch(`${API_BASE}/generate_pdf`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`PDF generation failed (${resp.status}): ${errText}`);
      }

      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);

      stopFakeProgress();
      setProgress(100);

      setPdfBlob(blob);
      setPdfPreviewUrl(url);
    } catch (e) {
      stopFakeProgress();
      setProgress(0);
      setError(e.message || "PDF generation failed.");
    } finally {
      setIsGenerating(false);
    }
  };

  const onClickDownload = () => {
    try {
      if (!pdfBlob || !pdfPreviewUrl) throw new Error("Generate the PDF preview first.");
      const a = document.createElement("a");
      a.href = pdfPreviewUrl;
      a.download = fileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      setError(e.message);
    }
  };

  const keywordInputValue = keywordCount === null ? "" : String(keywordCount);

  const canGenerate = hasEval && validKeywordCount && !isGenerating;

  return (
    <div className="min-h-screen w-full bg-[radial-gradient(1200px_circle_at_10%_10%,rgba(124,255,178,0.18),transparent_40%),radial-gradient(900px_circle_at_90%_20%,rgba(99,102,241,0.25),transparent_45%),linear-gradient(to_bottom_right,#0b1220,#070a12)] text-white">
      {/* Top bar */}
      <div className="sticky top-0 z-50 border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl bg-white/10 ring-1 ring-white/15 shadow-soft">
              <span className="text-lg">🧾</span>
            </div>
            <div className="min-w-0">
              <div className="truncate text-xl font-extrabold tracking-tight">Generate optimized PDF</div>
              <div className="text-sm text-white/70">
                Keyword count + reorder + select sections → generate → preview → download.
              </div>
            </div>
          </div>

          <button
            type="button"
            className="w-full rounded-2xl border border-white/12 bg-white/10 px-4 py-2 text-sm text-white/80 hover:bg-white/15 transition sm:w-auto"
            onClick={() => navigate("/app")}
          >
            ← Back to evaluation
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        {!hasEval ? (
          <div className="rounded-3xl border border-white/12 bg-white/[0.08] p-5 shadow-soft backdrop-blur-xl sm:p-6">
            <div className="text-lg font-extrabold">No evaluation found</div>
            <div className="mt-2 text-sm text-white/70">Please go back and run the evaluation first.</div>
            <div className="mt-6">
              <CustomButton text="Go to /app" onClick={() => navigate("/app")} className="w-full sm:w-40" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[460px_1fr]">
            {/* Left panel */}
            <div className="rounded-3xl border border-white/12 bg-white/[0.08] p-5 shadow-soft backdrop-blur-xl sm:p-6">
              <div className="text-sm font-extrabold">Trust check</div>
              <div className="mt-2 text-sm text-white/70">
                Optimized ATS score helps you trust the generated resume.
              </div>

              <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-2">
                <ScorePill label="Original ATS score" value={baseScore} tone="neutral" />
                <ScorePill label="Optimized ATS score" value={optimizedScore} tone={scoreTone} />
              </div>

              {scoreDelta != null && (
                <div className="mt-3 rounded-2xl border border-white/12 bg-black/20 px-4 py-3 text-sm text-white/75">
                  Change:{" "}
                  <span className={`font-extrabold ${scoreDelta >= 0 ? "text-emerald-200" : "text-red-200"}`}>
                    {scoreDelta >= 0 ? `+${scoreDelta}` : `${scoreDelta}`}
                  </span>{" "}
                  points
                </div>
              )}

              {/* Keyword count */}
              <div className="mt-7">
                <div className="text-sm font-extrabold">Keyword injection</div>
                <div className="mt-2 text-sm text-white/70">
                  Select how many keywords to add (min 3, max 10). Default is 5.
                </div>

                <div className="mt-4">
                  <label className="text-sm font-semibold text-white/90">Number of keywords (3–10)</label>
                  <input
                    type="number"
                    min={3}
                    max={10}
                    value={keywordInputValue}
                    onChange={(e) => {
                      setTouched(true);
                      const v = e.target.value;
                      if (v === "") {
                        setKeywordCount(null);
                        return;
                      }
                      setKeywordCount(Number(v));
                    }}
                    className="mt-2 w-full rounded-2xl border border-white/12 bg-black/25 px-4 py-3 text-sm text-white outline-none focus:border-white/25"
                  />
                  {!validKeywordCount && touched && (
                    <div className="mt-2 text-xs text-red-200">Enter a number between 3 and 10.</div>
                  )}
                </div>
              </div>

              {/* Section reorder + checkboxes */}
              <div className="mt-7">
                <div className="text-sm font-extrabold">Sections</div>
                <div className="mt-2 text-sm text-white/70">
                  Drag to reorder. Toggle checkboxes to include/exclude sections in the PDF.
                </div>

                <div className="mt-4 rounded-2xl border border-white/12 bg-black/20 p-3">
                  {sectionOrder.length === 0 ? (
                    <div className="p-3 text-sm text-white/60">No sections detected.</div>
                  ) : (
                    <div className="space-y-2">
                      {sectionOrder.map((key, idx) => (
                        <div
                          key={key}
                          draggable
                          onDragStart={() => onDragStart(idx)}
                          onDragOver={onDragOver}
                          onDrop={() => onDrop(idx)}
                          className="group flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2"
                          title="Drag to reorder"
                        >
                          <div className="flex min-w-0 items-center gap-3">
                            <div className="cursor-grab select-none rounded-lg border border-white/10 bg-black/20 px-2 py-1 text-xs text-white/70">
                              ↕
                            </div>
                            <div className="min-w-0">
                              <div className="truncate text-sm font-semibold text-white/90">
                                {prettifyKey(key)}
                              </div>
                              <div className="truncate text-xs text-white/55">{key}</div>
                            </div>
                          </div>

                          <div className="flex items-center gap-2">
                            {/* checkbox */}
                            <input
                              type="checkbox"
                              className="h-4 w-4 accent-emerald-300"
                              checked={enabledMap[key] !== false}
                              onChange={(e) =>
                                setEnabledMap((prev) => ({ ...prev, [key]: e.target.checked }))
                              }
                              title="Include section"
                            />

                            <button
                              type="button"
                              onClick={() => onClickUp(idx)}
                              disabled={idx === 0}
                              className="rounded-lg border border-white/12 bg-black/20 px-2 py-1 text-xs text-white/75 hover:bg-black/30 disabled:opacity-40"
                              title="Move up"
                            >
                              ↑
                            </button>
                            <button
                              type="button"
                              onClick={() => onClickDown(idx)}
                              disabled={idx === sectionOrder.length - 1}
                              className="rounded-lg border border-white/12 bg-black/20 px-2 py-1 text-xs text-white/75 hover:bg-black/30 disabled:opacity-40"
                              title="Move down"
                            >
                              ↓
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <div className="mt-2 text-xs text-white/55">
                  Tip: use Up/Down buttons if drag feels finicky on mobile.
                </div>
              </div>

              {/* Generate button */}
              <div className="mt-7">
                <CustomButton
                  text={isGenerating ? "Generating…" : "Generate PDF"}
                  disabled={!canGenerate}
                  onClick={onClickGenerate}
                  className="w-full"
                />
                <div className="mt-2 text-xs text-white/60">Button enables only when keyword count is valid.</div>
              </div>

              {isGenerating && (
                <div className="mt-6">
                  <div className="flex items-center justify-between text-xs text-white/70">
                    <span>Generating PDF…</span>
                    <span>{progress}%</span>
                  </div>
                  <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                    <div
                      className="h-full rounded-full bg-emerald-300/80 transition-[width] duration-300"
                      style={{ width: `${progress}%` }}
                    />
                  </div>
                </div>
              )}

              {error && (
                <div className="mt-5 rounded-2xl border border-red-300/40 bg-red-200/90 p-4 text-red-950">
                  <div className="font-extrabold">Something went wrong</div>
                  <div className="mt-1 text-sm leading-relaxed">{error}</div>
                </div>
              )}
            </div>

            {/* Right panel: preview */}
            <div className="overflow-hidden rounded-3xl border border-white/12 bg-white/[0.08] shadow-soft backdrop-blur-xl">
              <div className="flex flex-col gap-3 border-b border-white/10 bg-black/15 p-5 sm:flex-row sm:items-center sm:justify-between sm:p-6">
                <div>
                  <div className="text-lg font-extrabold">PDF Preview</div>
                  <div className="mt-1 text-sm text-white/70">Generate to preview the optimized resume.</div>
                </div>
                <div
                  className="max-w-full rounded-full border border-white/12 bg-black/25 px-4 py-2 text-xs text-white/70 sm:max-w-[420px]"
                  title={fileName}
                >
                  <span className="block truncate">{fileName}</span>
                </div>
              </div>

              {/* Responsive iframe height */}
              <div className="bg-white h-[520px] sm:h-[640px] lg:h-[720px]">
                {pdfPreviewUrl ? (
                  <iframe title="Resume Preview" src={pdfPreviewUrl} className="h-full w-full border-0" />
                ) : (
                  <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-slate-900">
                    <div className="text-4xl">📄</div>
                    <div className="text-lg font-extrabold">No preview yet</div>
                    <div className="max-w-[520px] text-sm text-slate-700">
                      Choose keyword count + reorder/toggle sections, then click{" "}
                      <span className="font-bold">Generate PDF</span>.
                    </div>
                  </div>
                )}
              </div>

              <div className="border-t border-white/10 bg-black/15 p-5 sm:p-6">
                <CustomButton
                  text="Download PDF"
                  disabled={!pdfPreviewUrl || !pdfBlob || isGenerating}
                  onClick={onClickDownload}
                  className="w-full sm:w-44"
                />
                <div className="mt-2 text-xs text-white/60">Download enables after preview is generated.</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default PdfPage;
