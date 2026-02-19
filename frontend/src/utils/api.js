const API_BASE = process.env.REACT_APP_API_BASE_URL || "http://127.0.0.1:5001";

async function readError(resp) {
  const txt = await resp.text();
  try {
    const j = JSON.parse(txt);
    return j?.error ? String(j.error) : txt;
  } catch {
    return txt;
  }
}

export async function analyzeResumeMultipart({
  file,
  jobDescription,
  model,
  mode,
  useCache,
}) {
  const fd = new FormData();
  fd.append("resume", file);
  fd.append("job_description", jobDescription);
  if (model) fd.append("model", model);
  if (mode) fd.append("mode", mode);
  fd.append("use_cache", useCache ? "true" : "false");

  const resp = await fetch(`${API_BASE}/analyze_resume`, {
    method: "POST",
    body: fd,
  });

  if (!resp.ok) {
    throw new Error(await readError(resp));
  }
  return await resp.json();
}

export async function scoreResume({
  resumeSkeleton,
  jobDescription,
  model,
  useCache,
}) {
  const resp = await fetch(`${API_BASE}/score_resume`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      resume_skeleton: resumeSkeleton,
      job_description: jobDescription,
      model,
      use_cache: !!useCache,
    }),
  });

  if (!resp.ok) {
    throw new Error(await readError(resp));
  }
  return await resp.json();
}

export async function healthCheck() {
  const resp = await fetch(`${API_BASE}/health`);
  if (!resp.ok) throw new Error(await readError(resp));
  return await resp.json();
}