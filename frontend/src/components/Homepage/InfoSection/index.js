import React from "react";
import { useNavigate } from "react-router-dom";
import CustomButton from "../../Button/CustomButton";

const FeatureRow = ({ reverse = false, eyebrow, title, desc, bullets, cta }) => {
  return (
    <div className="mx-auto max-w-6xl px-6">
      <div
        className={[
          "grid items-center gap-8 py-14",
          "md:grid-cols-2",
          reverse ? "md:[&>*:first-child]:order-2 md:[&>*:last-child]:order-1" : "",
        ].join(" ")}
      >
        {/* Image / visual */}
        <div className="rounded-3xl border border-white/12 bg-white/[0.06] p-4 shadow-soft backdrop-blur-xl">
          <div className="relative overflow-hidden rounded-2xl border border-white/10 bg-[linear-gradient(135deg,rgba(99,102,241,0.22),rgba(16,185,129,0.18))]">
            <div className="absolute inset-0 bg-[radial-gradient(800px_circle_at_20%_20%,rgba(255,255,255,0.14),transparent_45%)]" />
            <div className="relative p-8">
              <div className="text-sm text-white/70">{eyebrow}</div>
              <div className="mt-2 text-2xl font-extrabold tracking-tight">{title}</div>
              <div className="mt-2 text-sm text-white/70 leading-relaxed">
                {desc}
              </div>

              {/* mini “mock UI” */}
              <div className="mt-6 grid grid-cols-2 gap-3">
                <div className="rounded-2xl border border-white/12 bg-black/20 p-4">
                  <div className="text-xs text-white/60">Status</div>
                  <div className="mt-2 inline-flex items-center gap-2 rounded-full border border-emerald-200/25 bg-emerald-300/10 px-3 py-1 text-xs font-semibold text-emerald-100">
                    <span className="h-2 w-2 rounded-full bg-emerald-300" />
                    Ready
                  </div>
                </div>
                <div className="rounded-2xl border border-white/12 bg-black/20 p-4">
                  <div className="text-xs text-white/60">Speed</div>
                  <div className="mt-2 text-lg font-extrabold">Fast</div>
                  <div className="text-xs text-white/60">Evaluate → Preview → Download</div>
                </div>
              </div>

              <div className="mt-6 h-px w-full bg-white/10" />

              <div className="mt-4 grid grid-cols-3 gap-3">
                <div className="rounded-2xl border border-white/12 bg-black/15 p-3 text-xs text-white/70">
                  Keywords
                </div>
                <div className="rounded-2xl border border-white/12 bg-black/15 p-3 text-xs text-white/70">
                  PDF Preview
                </div>
                <div className="rounded-2xl border border-white/12 bg-black/15 p-3 text-xs text-white/70">
                  Clean UI
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Text */}
        <div>
          <div className="inline-flex items-center rounded-full border border-white/12 bg-white/10 px-4 py-2 text-xs text-white/75 shadow-soft backdrop-blur-xl">
            {eyebrow}
          </div>

          <h3 className="mt-4 text-3xl font-extrabold tracking-tight sm:text-4xl">
            {title}
          </h3>

          <p className="mt-4 text-base leading-relaxed text-white/75">
            {desc}
          </p>

          {bullets?.length ? (
            <ul className="mt-6 space-y-3 text-sm text-white/75">
              {bullets.map((b, idx) => (
                <li key={idx} className="flex items-start gap-3">
                  <span className="mt-1 inline-block h-2 w-2 rounded-full bg-emerald-300 shadow-[0_0_0_6px_rgba(110,231,183,0.10)]" />
                  <span className="leading-relaxed">{b}</span>
                </li>
              ))}
            </ul>
          ) : null}

          {cta ? (
            <div className="mt-8">
              {cta}
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
};

const InfoSection = () => {
  const navigate = useNavigate();

  return (
    <section className="w-full">
      {/* subtle divider */}
      <div className="mx-auto max-w-6xl px-6">
        <div className="h-px w-full bg-white/10" />
      </div>

      <FeatureRow
        eyebrow="Step 1"
        title="Evaluate against any job link"
        desc="Paste a job description URL, upload your resume PDF, and get an ATS-style evaluation. If extraction fails, paste the job description text — the flow stays smooth."
        bullets={[
          "Handles blocked job sites with fallback paste mode",
          "Keeps the workflow minimal and focused",
          "Clear status and error messages (no guessing)",
        ]}
        cta={
          <CustomButton
            text="Try the App"
            onClick={() => navigate("/app")}
            className="w-48"
          />
        }
      />

      <div className="mx-auto max-w-6xl px-6">
        <div className="h-px w-full bg-white/10" />
      </div>

      <FeatureRow
        reverse
        eyebrow="Step 2"
        title="See exactly what changed"
        desc="We don’t just spit out a score — you also get a structured list of keywords added and where they were placed, so you can trust the edits."
        bullets={[
          "Keyword pills for quick scanning",
          "Location badges to understand placement",
          "Readable, clean presentation (not walls of text)",
        ]}
      />

      <div className="mx-auto max-w-6xl px-6">
        <div className="h-px w-full bg-white/10" />
      </div>

      <FeatureRow
        eyebrow="Step 3"
        title="Generate a PDF preview and download"
        desc="Once optimized, generate a PDF preview in-app, confirm formatting, and download a clean file name that includes your name and target company."
        bullets={[
          "Built-in preview viewer inside the app",
          "Download enabled only when preview is ready",
          "Feels like a polished product flow",
        ]}
      />

      {/* bottom spacing */}
      <div className="h-10" />
    </section>
  );
};

export default InfoSection;
