import React from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../../Button/CustomButton";

const HeroSection = () => {
  const navigate = useNavigate();

  const onClickTryBtn = () => {
    navigate("/app");
  };

  return (
    <div className="min-h-screen w-full bg-[radial-gradient(1200px_circle_at_10%_10%,rgba(124,255,178,0.18),transparent_40%),radial-gradient(900px_circle_at_90%_20%,rgba(99,102,241,0.25),transparent_45%),linear-gradient(to_bottom_right,#0b1220,#070a12)] text-white">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col items-center justify-center px-6 py-16 text-center">
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/10 px-4 py-2 text-xs text-white/75 shadow-soft backdrop-blur-xl">
          <span className="h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_0_6px_rgba(110,231,183,0.12)]" />
          ATS-style optimization • PDF preview • Keywords injected
        </div>

        <h1 className="text-balance text-4xl font-extrabold tracking-tight sm:text-6xl">
          AI-Powered Resume Scoring Tool
        </h1>

        <p className="mt-5 max-w-3xl text-pretty text-base leading-relaxed text-white/75 sm:text-lg">
          Quickly evaluate your resume against any job description and get actionable feedback —
          powered by smart AI.
        </p>

        <div className="mt-9 flex flex-col items-center gap-3 sm:flex-row">
          <CustomButton text="Try it now" onClick={onClickTryBtn} className="w-56" />
          <div className="text-xs text-white/55">
            No signup • Upload PDF • Download optimized version
          </div>
        </div>

        {/* Feature cards */}
        <div className="mt-14 grid w-full max-w-5xl grid-cols-1 gap-4 sm:grid-cols-3">
          <div className="rounded-3xl border border-white/12 bg-white/[0.06] p-5 shadow-soft backdrop-blur-xl">
            <div className="text-2xl">⚡</div>
            <div className="mt-2 text-sm font-extrabold">Fast workflow</div>
            <div className="mt-1 text-sm text-white/70">
              Evaluate → Generate preview → Download. Clean and simple.
            </div>
          </div>
          <div className="rounded-3xl border border-white/12 bg-white/[0.06] p-5 shadow-soft backdrop-blur-xl">
            <div className="text-2xl">🎯</div>
            <div className="mt-2 text-sm font-extrabold">Targeted keywords</div>
            <div className="mt-1 text-sm text-white/70">
              See exactly what keywords were added and where they went.
            </div>
          </div>
          <div className="rounded-3xl border border-white/12 bg-white/[0.06] p-5 shadow-soft backdrop-blur-xl">
            <div className="text-2xl">🧾</div>
            <div className="mt-2 text-sm font-extrabold">PDF preview</div>
            <div className="mt-1 text-sm text-white/70">
              Generate a polished PDF preview before downloading.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default HeroSection;
