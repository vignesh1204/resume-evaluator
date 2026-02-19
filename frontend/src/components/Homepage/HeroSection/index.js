import React from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../../Button/CustomButton";
import NoirShell from "../../layout/NoirShell";

const HeroSection = () => {
  const navigate = useNavigate();

  return (
    <NoirShell>
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-4 py-2 text-xs text-white/70">
          <span className="h-2 w-2 rounded-full bg-cyan-300 shadow-[0_0_0_7px_rgba(58,222,255,0.10)]" />
          ATS-style optimization • PDF studio • Diff-aware suggestions
        </div>

        <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-6xl">
          AI-Based resume optimization
        </h1>

        <p className="mt-5 max-w-3xl text-pretty text-base leading-relaxed noir-muted sm:text-lg">
          Score your resume against any job description, auto-apply improvements,
          and generate a clean PDF — with visibility into exactly what changed.
        </p>

        <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
          <CustomButton
            text="Try it now"
            onClick={() => navigate("/app")}
            className="w-56 noir-btn"
          />
          <div className="text-xs noir-muted">
            No signup • Upload PDF • Rescore after edits
          </div>
        </div>

        <div className="mt-14 grid w-full max-w-5xl grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="noir-card-2 rounded-3xl p-5">
            <div className="text-2xl">🧠</div>
            <div className="mt-2 text-sm font-extrabold">Explainable</div>
            <div className="mt-1 text-sm noir-muted">
              Diff-aware suggestions so you can see what changed and why.
            </div>
          </div>
          <div className="noir-card-2 rounded-3xl p-5">
            <div className="text-2xl">🎯</div>
            <div className="mt-2 text-sm font-extrabold">Targeted</div>
            <div className="mt-1 text-sm noir-muted">
              Keyword coverage signals + ATS scoring breakdown.
            </div>
          </div>
          <div className="noir-card-2 rounded-3xl p-5">
            <div className="text-2xl">🧾</div>
            <div className="mt-2 text-sm font-extrabold">PDF Studio</div>
            <div className="mt-1 text-sm noir-muted">
              Preview, reorder sections, then export a polished PDF.
            </div>
          </div>
        </div>
      </div>
    </NoirShell>
  );
};

export default HeroSection;