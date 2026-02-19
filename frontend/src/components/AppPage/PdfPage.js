import React, { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../Button/CustomButton";
import { useEval } from "../../context/EvalContext";
import NoirShell from "../layout/NoirShell";

const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:5001";
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));

const prettify = (key) =>
  String(key || "")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());

function deriveSectionOrderFromCanonical(resumeCanonical) {
  if (!resumeCanonical || !Array.isArray(resumeCanonical.sections)) return [];
  return resumeCanonical.sections.map((s) => String(s?.id || "")).filter((id) => id.trim());
}

function tokenizeWithWhitespace(s) {
  return String(s || "").match(/\S+|\s+/g) || [];
}

function buildInlineDiff(beforeText, afterText) {
  const a = tokenizeWithWhitespace(beforeText);
  const b = tokenizeWithWhitespace(afterText);
  const m = a.length;
  const n = b.length;
  const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0));

  for (let i = m - 1; i >= 0; i -= 1) {
    for (let j = n - 1; j >= 0; j -= 1) {
      if (a[i] === b[j]) dp[i][j] = dp[i + 1][j + 1] + 1;
      else dp[i][j] = Math.max(dp[i + 1][j], dp[i][j + 1]);
    }
  }

  const ops = [];
  let i = 0;
  let j = 0;
  while (i < m && j < n) {
    if (a[i] === b[j]) {
      ops.push({ kind: "equal", text: a[i] });
      i += 1;
      j += 1;
    } else if (dp[i + 1][j] >= dp[i][j + 1]) {
      ops.push({ kind: "del", text: a[i] });
      i += 1;
    } else {
      ops.push({ kind: "add", text: b[j] });
      j += 1;
    }
  }
  while (i < m) {
    ops.push({ kind: "del", text: a[i] });
    i += 1;
  }
  while (j < n) {
    ops.push({ kind: "add", text: b[j] });
    j += 1;
  }
  return ops;
}

const Modal = ({ open, onClose, children }) => {
  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && onClose?.();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-[999]">
      <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
      <div className="absolute inset-0 p-3 sm:p-6">
        <div className="noir-card noir-grain relative mx-auto h-full max-w-6xl overflow-hidden rounded-3xl">
          <div className="flex items-center justify-between border-b border-white/10 bg-black/20 px-4 py-3">
            <div className="text-sm font-extrabold">Preview</div>
            <button
              onClick={onClose}
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-1 text-xs text-white/80 hover:bg-white/10"
            >
              Close (Esc)
            </button>
          </div>
          <div className="h-[calc(100%-48px)] bg-white">{children}</div>
        </div>
      </div>
    </div>
  );
};

export default function PdfPage() {
  const navigate = useNavigate();
  const { evalState, setEvalState } = useEval();

  const [isGenerating, setIsGenerating] = useState(false);
  const [progress, setProgress] = useState(0);

  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);
  const [error, setError] = useState(null);

  const [sectionOrder, setSectionOrder] = useState([]);
  const [enabledMap, setEnabledMap] = useState({});
  const dragIndexRef = useRef(null);

  const [isFullPreview, setIsFullPreview] = useState(false);
  const timerRef = useRef(null);

  const hasEval = !!evalState?.resumeCanonical;

  const rewriteSuggestions = evalState?.analysis?.improvements?.rewrite_suggestions || [];
  const keywordsSuggested = evalState?.analysis?.improvements?.missing_keywords || [];
  const [suggestionDrafts, setSuggestionDrafts] = useState([]);
  const [editingSuggestions, setEditingSuggestions] = useState([]);

  useEffect(() => {
    if (!hasEval) return;

    const derived = deriveSectionOrderFromCanonical(evalState.resumeCanonical);
    const savedOrder = evalState?.sectionOrder;
    const finalOrder = Array.isArray(savedOrder) && savedOrder.length > 0 ? savedOrder : derived;
    setSectionOrder(finalOrder);

    const savedEnabled = evalState?.enabledSectionIds;
    if (Array.isArray(savedEnabled) && savedEnabled.length > 0) {
      const m = {};
      finalOrder.forEach((id) => (m[id] = savedEnabled.includes(id)));
      setEnabledMap(m);
    } else {
      const m = {};
      finalOrder.forEach((id) => (m[id] = true));
      setEnabledMap(m);
    }
  }, [hasEval, evalState.resumeCanonical]);

  useEffect(() => {
    const rows = Array.isArray(rewriteSuggestions) ? rewriteSuggestions : [];
    setSuggestionDrafts(rows.map((r) => r?.after || ""));
    setEditingSuggestions(rows.map(() => false));
  }, [rewriteSuggestions]);

  useEffect(() => {
    return () => {
      if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [pdfPreviewUrl]);

  const resetPreview = () => {
    if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewUrl(null);
    setPdfBlob(null);
  };

  // “real” looking progress during network call
  const startProgress = () => {
    setProgress(5);
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = setInterval(() => {
      setProgress((p) => {
        if (p >= 92) return p;
        const bump = p < 55 ? 6 : p < 80 ? 3 : 1;
        return clamp(p + bump, 0, 92);
      });
    }, 420);
  };
  const stopProgress = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    timerRef.current = null;
  };

  const moveItem = (from, to) => {
    setSectionOrder((prev) => {
      const arr = [...prev];
      const [item] = arr.splice(from, 1);
      arr.splice(to, 0, item);
      return arr;
    });
  };

  const onDragStart = (index) => (dragIndexRef.current = index);
  const onDragOver = (e) => e.preventDefault();
  const onDrop = (dropIndex) => {
    const fromIndex = dragIndexRef.current;
    if (fromIndex == null || fromIndex === dropIndex) return;
    moveItem(fromIndex, dropIndex);
    dragIndexRef.current = null;
  };

  const onClickGenerate = async () => {
    setError(null);
    setIsGenerating(true);
    resetPreview();
    startProgress();

    try {
      if (!hasEval) throw new Error("No evaluation found. Go back and run evaluation first.");

      const enabledSectionIds = sectionOrder.filter((id) => enabledMap[id] !== false);
      if (enabledSectionIds.length === 0) throw new Error("Select at least one section.");

      setEvalState((prev) => ({ ...prev, sectionOrder, enabledSectionIds }));

      const payload = {
        resume_canonical: evalState.resumeCanonical, // optimized skeleton (always)
        keywords_suggested: keywordsSuggested,       // ✅ inject ALL
        keyword_count: keywordsSuggested.length,     // keep for compatibility if backend expects it
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

      stopProgress();
      setProgress(100);
      setPdfBlob(blob);
      setPdfPreviewUrl(url);
    } catch (e) {
      stopProgress();
      setProgress(0);
      setError(e?.message || "PDF generation failed.");
    } finally {
      setIsGenerating(false);
    }
  };

  const onClickDownload = () => {
    try {
      if (!pdfBlob || !pdfPreviewUrl) throw new Error("Generate the PDF preview first.");
      const a = document.createElement("a");
      a.href = pdfPreviewUrl;
      a.download = evalState?.generatedFileNameHint || "Resume_Optimized.pdf";
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (e) {
      setError(e?.message || "Download failed.");
    }
  };

  const canGenerate = hasEval && !isGenerating;

  return (
    <NoirShell>
      {/* Top bar */}
      <div className="sticky top-0 z-50 border-b border-white/10 bg-black/20 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl flex-col gap-3 px-4 py-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 shrink-0 place-items-center rounded-2xl border border-white/10 bg-white/5">
              <span className="text-lg">🧾</span>
            </div>
            <div className="min-w-0">
              <div className="truncate text-xl font-extrabold tracking-tight">PDF Studio</div>
              <div className="text-sm noir-muted">Optimized content is auto-applied.</div>
            </div>
          </div>

          <button
            type="button"
            className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-2 text-sm text-white/80 hover:bg-white/10 transition sm:w-auto"
            onClick={() => navigate("/app")}
          >
            ← Back
          </button>
        </div>
      </div>

      <div className="mx-auto max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
        {!hasEval ? (
          <div className="noir-card rounded-3xl p-6">
            <div className="text-lg font-extrabold">No evaluation found</div>
            <div className="mt-2 text-sm noir-muted">Please go back and run evaluation first.</div>
            <div className="mt-6">
              <CustomButton text="Go to /app" onClick={() => navigate("/app")} className="w-full sm:w-40 noir-btn" />
            </div>
          </div>
        ) : (
          <div className="grid grid-cols-1 gap-6 lg:grid-cols-[420px_1fr]">
            {/* Left: controls + changes */}
            <div className="space-y-6">
              {/* Section order (keep, but compact) */}
              <div className="noir-card rounded-3xl p-5 sm:p-6">
                <div className="text-sm font-extrabold">Sections</div>
                <div className="mt-2 text-sm noir-muted">Drag to reorder. Toggle to include.</div>

                <div className="mt-4 rounded-2xl border border-white/10 bg-black/25 p-3">
                  <div className="space-y-2">
                    {sectionOrder.map((key, idx) => (
                      <div
                        key={key}
                        draggable
                        onDragStart={() => onDragStart(idx)}
                        onDragOver={onDragOver}
                        onDrop={() => onDrop(idx)}
                        className="flex items-center justify-between gap-3 rounded-xl border border-white/10 bg-white/5 px-3 py-2"
                      >
                        <div className="min-w-0">
                          <div className="truncate text-sm font-semibold text-white/90">{prettify(key)}</div>
                          <div className="truncate text-xs noir-muted">{key}</div>
                        </div>

                        <div className="flex items-center gap-2">
                          <input
                            type="checkbox"
                            className="h-4 w-4 accent-cyan-300"
                            checked={enabledMap[key] !== false}
                            onChange={(e) => setEnabledMap((prev) => ({ ...prev, [key]: e.target.checked }))}
                            title="Include section"
                          />
                          <button
                            type="button"
                            onClick={() => idx > 0 && moveItem(idx, idx - 1)}
                            disabled={idx === 0}
                            className="rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/75 hover:bg-black/40 disabled:opacity-40"
                          >
                            ↑
                          </button>
                          <button
                            type="button"
                            onClick={() => idx < sectionOrder.length - 1 && moveItem(idx, idx + 1)}
                            disabled={idx === sectionOrder.length - 1}
                            className="rounded-lg border border-white/10 bg-black/30 px-2 py-1 text-xs text-white/75 hover:bg-black/40 disabled:opacity-40"
                          >
                            ↓
                          </button>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>

              {/* Diffs (compact, no target labels) */}
              {rewriteSuggestions.length > 0 && (
                <div className="noir-card rounded-3xl p-5 sm:p-6">
                  <div className="flex items-center justify-between">
                    <div className="text-sm font-extrabold">Changes applied</div>
                    <div className="text-xs noir-muted">{rewriteSuggestions.length} edits</div>
                  </div>
                  <div className="mt-2 text-xs noir-muted">
                    Red strikethrough = removed, Yellow = replaced, Green = added.
                  </div>

                  <div className="mt-4 space-y-3">
                    {rewriteSuggestions.slice(0, 10).map((r, i) => (
                      <div key={i} className="rounded-2xl border border-white/10 bg-black/20 p-4">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-xs text-white/55">{r.target}</div>
                          <button
                            type="button"
                            onClick={() =>
                              setEditingSuggestions((prev) => {
                                const next = [...prev];
                                next[i] = !next[i];
                                return next;
                              })
                            }
                            className="rounded-md border border-white/15 bg-black/30 px-2 py-1 text-[11px] font-semibold text-white/80 hover:bg-black/40"
                          >
                            {editingSuggestions[i] ? "Done" : "Edit"}
                          </button>
                        </div>
                        <div className="mt-2">
                          {editingSuggestions[i] ? (
                            <textarea
                              value={suggestionDrafts[i] || ""}
                              onChange={(e) =>
                                setSuggestionDrafts((prev) => {
                                  const next = [...prev];
                                  next[i] = e.target.value;
                                  return next;
                                })
                              }
                              rows={4}
                              className="w-full rounded-xl border border-white/10 bg-black/25 px-3 py-2 text-sm text-white/90 outline-none focus:border-white/20"
                            />
                          ) : (
                            <div className="rounded-xl border border-white/10 bg-black/20 px-3 py-2 text-sm text-white/85 whitespace-pre-wrap">
                              {buildInlineDiff(r.before || "", suggestionDrafts[i] || "").map((part, idx, arr) => {
                                if (part.kind === "equal") return <span key={idx}>{part.text}</span>;
                                if (part.kind === "del") {
                                  return (
                                    <span key={idx} className="text-rose-300 line-through decoration-rose-300/90">
                                      {part.text}
                                    </span>
                                  );
                                }
                                const prevKind = idx > 0 ? arr[idx - 1].kind : "";
                                const nextKind = idx < arr.length - 1 ? arr[idx + 1].kind : "";
                                const isReplacement = prevKind === "del" || nextKind === "del";
                                return (
                                  <span
                                    key={idx}
                                    className={
                                      isReplacement ? "bg-amber-300/30 text-amber-100" : "bg-emerald-400/25 text-emerald-100"
                                    }
                                  >
                                    {part.text}
                                  </span>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      </div>
                    ))}
                    {rewriteSuggestions.length > 10 && (
                      <div className="text-xs noir-muted">Showing first 10. (We can add “Show more” later.)</div>
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Right: generate + preview */}
            <div className="space-y-6">
              <div className="noir-card rounded-3xl p-5 sm:p-6">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-extrabold">Generate</div>
                    <div className="mt-1 text-sm noir-muted">
                      Uses the optimized resume + injects all missing keywords.
                    </div>
                  </div>
                  <span className="rounded-full border border-emerald-200/20 bg-emerald-300/10 px-3 py-1 text-xs text-emerald-100">
                    Auto-applied ✓
                  </span>
                </div>

                <div className="mt-5">
                  <CustomButton
                    text={isGenerating ? "Generating…" : "Generate PDF"}
                    disabled={!canGenerate}
                    onClick={onClickGenerate}
                    className="w-full noir-btn"
                  />
                </div>

                {isGenerating && (
                  <div className="mt-5">
                    <div className="flex items-center justify-between text-xs text-white/70">
                      <span>Working…</span>
                      <span>{progress}%</span>
                    </div>
                    <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10">
                      <div
                        className="h-full rounded-full bg-cyan-300/80 transition-[width] duration-300"
                        style={{ width: `${progress}%` }}
                      />
                    </div>
                  </div>
                )}

                {error && (
                  <div className="mt-5 rounded-2xl border border-rose-300/30 bg-rose-300/10 p-4 text-rose-100">
                    <div className="font-extrabold">Error</div>
                    <div className="mt-1 text-sm leading-relaxed">{error}</div>
                  </div>
                )}
              </div>

              <div className="noir-card rounded-3xl overflow-hidden">
                <div className="border-b border-white/10 bg-black/20 p-5 sm:p-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div>
                      <div className="text-lg font-extrabold">Preview</div>
                      <div className="mt-1 text-sm noir-muted">Generate to preview the final optimized PDF.</div>
                    </div>

                    <div className="flex items-center gap-2">
                      <button
                        type="button"
                        onClick={() => setIsFullPreview(true)}
                        disabled={!pdfPreviewUrl}
                        className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-xs text-white/80 hover:bg-white/10 disabled:opacity-40"
                      >
                        Fullscreen
                      </button>
                    </div>
                  </div>
                </div>

                <div className="bg-white h-[60vh] sm:h-[68vh] lg:h-[720px]">
                  {pdfPreviewUrl ? (
                    <iframe title="Resume Preview" src={pdfPreviewUrl} className="h-full w-full border-0" />
                  ) : (
                    <div className="flex h-full flex-col items-center justify-center gap-2 px-6 text-center text-slate-900">
                      <div className="text-4xl">📄</div>
                      <div className="text-lg font-extrabold">No preview yet</div>
                      <div className="max-w-[520px] text-sm text-slate-700">
                        Click <span className="font-bold">Generate PDF</span> to preview the optimized resume.
                      </div>
                    </div>
                  )}
                </div>

                <div className="border-t border-white/10 bg-black/20 p-5 sm:p-6">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <CustomButton
                      text="Download PDF"
                      disabled={!pdfPreviewUrl || !pdfBlob || isGenerating}
                      onClick={onClickDownload}
                      className="w-full sm:w-48 noir-btn"
                    />
                    <div className="text-xs noir-muted">Download enabled after preview.</div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        )}

        <Modal open={isFullPreview} onClose={() => setIsFullPreview(false)}>
          {pdfPreviewUrl ? (
            <iframe title="Resume Preview Full" src={pdfPreviewUrl} className="h-full w-full border-0" />
          ) : (
            <div className="grid h-full place-items-center text-slate-900">
              <div>No preview available.</div>
            </div>
          )}
        </Modal>
      </div>
    </NoirShell>
  );
}