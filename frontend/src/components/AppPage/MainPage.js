import React, { useEffect, useMemo, useState } from 'react';
import pdfToText from 'react-pdftotext';

import CustomButton from '../Button/CustomButton';
import DragNDrop from '../DragNDrop/DragNDrop';

import './MainPage.css';

const MainPage = () => {
  const [uploadedFile, setUploadedFile] = useState(null);
  const [jobDescLink, setJobDescLink] = useState('');

  // paste JD fallback
  const [showPasteJd, setShowPasteJd] = useState(false);
  const [pastedJdText, setPastedJdText] = useState('');

  // loading states
  const [isEvaluating, setIsEvaluating] = useState(false);
  const [isGeneratingPdf, setIsGeneratingPdf] = useState(false);

  // outputs
  const [updatedResumeJson, setUpdatedResumeJson] = useState(null);
  const [keywordsAdded, setKeywordsAdded] = useState([]);

  // PDF preview state
  const [pdfPreviewUrl, setPdfPreviewUrl] = useState(null);
  const [pdfBlob, setPdfBlob] = useState(null);

  const [error, setError] = useState(null);

  useEffect(() => {
    return () => {
      if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
    };
  }, [pdfPreviewUrl]);

  const getCompanyFromUrl = (url) => {
    try {
      const host = new URL(url).hostname.replace('www.', '');
      const base = host.split('.')[0] || 'Company';
      return base.charAt(0).toUpperCase() + base.slice(1);
    } catch {
      return 'Company';
    }
  };

  const getNameFromUpdatedJson = (json) => {
    if (!json) return 'Resume';
    if (json.resume && json.resume.name) return String(json.resume.name).trim().split(' ')[0] || 'Resume';
    if (json.name) return String(json.name).trim().split(' ')[0] || 'Resume';
    return 'Resume';
  };

  const downloadFileName = useMemo(() => {
    const name = getNameFromUpdatedJson(updatedResumeJson);
    const company = getCompanyFromUrl(jobDescLink);
    return `${name}_${company}_Optimized.pdf`;
  }, [updatedResumeJson, jobDescLink]);

  const resetPdfPreview = () => {
    if (pdfPreviewUrl) window.URL.revokeObjectURL(pdfPreviewUrl);
    setPdfPreviewUrl(null);
    setPdfBlob(null);
  };

  const onClickEvalBtn = async () => {
    setIsEvaluating(true);
    setError(null);

    setUpdatedResumeJson(null);
    setKeywordsAdded([]);
    resetPdfPreview();

    try {
      if (!uploadedFile) throw new Error('Please upload a resume PDF.');
      if (!jobDescLink.trim()) throw new Error('Please enter a job description link.');

      const resumeText = await pdfToText(uploadedFile);
      const resumeJson = { raw_text: resumeText };

      let jdText = '';
      const extractResp = await fetch('http://localhost:5000/extract', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ job_description_link: jobDescLink }),
      });

      if (extractResp.ok) {
        const extractData = await extractResp.json();
        jdText = extractData.job_description || '';
        setShowPasteJd(false);
      } else if (extractResp.status === 422) {
        const errData = await extractResp.json().catch(() => ({}));
        setShowPasteJd(true);

        if (!pastedJdText.trim()) {
          throw new Error(
            errData.warning ||
              'Could not extract job description from the link. Please paste the job description text.'
          );
        }
        jdText = pastedJdText.trim();
      } else {
        const errText = await extractResp.text();
        throw new Error(`JD extraction failed (${extractResp.status}): ${errText}`);
      }

      const evalResp = await fetch('http://localhost:5000/evaluate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          resume_json: resumeJson,
          job_description_link: jobDescLink,
          job_description_text: jdText,
        }),
      });

      if (!evalResp.ok) {
        const errText = await evalResp.text();
        throw new Error(`Server error (${evalResp.status}): ${errText}`);
      }

      const evalData = await evalResp.json();
      setUpdatedResumeJson(evalData.updated_resume_json || null);
      setKeywordsAdded(evalData.keywords_added || []);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsEvaluating(false);
    }
  };

  const onClickGeneratePdfBtn = async () => {
    setIsGeneratingPdf(true);
    setError(null);

    resetPdfPreview();

    try {
      if (!updatedResumeJson) {
        throw new Error('No updated resume data found. Click Evaluate first.');
      }

      const resp = await fetch('http://localhost:5000/generate_pdf', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ updated_resume_json: updatedResumeJson }),
      });

      if (!resp.ok) {
        const errText = await resp.text();
        throw new Error(`PDF generation failed (${resp.status}): ${errText}`);
      }

      const blob = await resp.blob();
      const url = window.URL.createObjectURL(blob);

      setPdfBlob(blob);
      setPdfPreviewUrl(url);
    } catch (err) {
      setError(err.message);
    } finally {
      setIsGeneratingPdf(false);
    }
  };

  const onClickDownloadBtn = () => {
    try {
      if (!pdfBlob || !pdfPreviewUrl) throw new Error('Generate the PDF preview first.');
      const a = document.createElement('a');
      a.href = pdfPreviewUrl;
      a.download = downloadFileName;
      document.body.appendChild(a);
      a.click();
      a.remove();
    } catch (err) {
      setError(err.message);
    }
  };

  const canEvaluate = !!uploadedFile && !!jobDescLink.trim() && !isEvaluating && !isGeneratingPdf;
  const canGeneratePdf = !!updatedResumeJson && !isGeneratingPdf && !isEvaluating;
  const canDownload = !!pdfPreviewUrl && !!pdfBlob && !isGeneratingPdf && !isEvaluating;

  const statusText = useMemo(() => {
    if (isEvaluating) return 'Evaluating resume…';
    if (isGeneratingPdf) return 'Generating PDF preview…';
    if (pdfPreviewUrl) return 'PDF preview ready.';
    if (updatedResumeJson) return 'Updated resume ready. Generate a PDF preview.';
    return 'Upload your resume and paste a job link to begin.';
  }, [isEvaluating, isGeneratingPdf, pdfPreviewUrl, updatedResumeJson]);

  return (
    <div className="body">
      <div className="topbar">
        <div className="brand">
          <div className="brand-title">Resume Evaluator</div>
          <div className="brand-subtitle">Optimize your resume for a job link and preview the updated PDF.</div>
        </div>
        <div className="status-pill" aria-live="polite">
          <span className={`dot ${isEvaluating || isGeneratingPdf ? 'dot-live' : ''}`} />
          {statusText}
        </div>
      </div>

      <div className="layout">
        {/* LEFT */}
        <div className="left-panel">
          <div className="card">
            <div className="card-header">
              <h2>Inputs</h2>
              <p>Enter a job link, upload a resume, then evaluate.</p>
            </div>

            <div className="field">
              <label className="label">Job description link</label>
              <textarea
                type="text"
                placeholder="Paste job link here (e.g., careers page URL)…"
                className="jd-input"
                value={jobDescLink}
                onChange={(e) => setJobDescLink(e.target.value)}
              />
              <div className="helper">
                If the link can’t be extracted, you’ll be asked to paste the job description text.
              </div>
            </div>

            {showPasteJd && (
              <div className="field">
                <label className="label">Paste job description text</label>
                <textarea
                  placeholder="We couldn't extract the JD from the link. Paste the full job description text here…"
                  className="jd-paste"
                  value={pastedJdText}
                  onChange={(e) => setPastedJdText(e.target.value)}
                />
              </div>
            )}

            <div className="field">
              <label className="label">Resume PDF</label>
              <div className="dropwrap">
                {/* Reduced by ~25% */}
                <DragNDrop width="490px" height="285px" setDroppedFile={setUploadedFile} />
              </div>
              <div className="helper">
                {uploadedFile ? (
                  <span>
                    Selected: <strong>{uploadedFile.name}</strong>
                  </span>
                ) : (
                  <span>Drag and drop a PDF, or click to select.</span>
                )}
              </div>
            </div>

            <div className="actions">
              <div className="actions-row">
                <CustomButton
                  text={isEvaluating ? 'Evaluating…' : 'Evaluate'}
                  disabled={!canEvaluate}
                  onClick={onClickEvalBtn}
                />
                <CustomButton
                  text={isGeneratingPdf ? 'Generating…' : 'Generate PDF Preview'}
                  disabled={!canGeneratePdf}
                  onClick={onClickGeneratePdfBtn}
                />
              </div>
              <div className="actions-note">
                Step 1: Evaluate → Step 2: Generate PDF Preview → Step 3: Download
              </div>
            </div>

            {error && (
              <div className="alert" role="alert">
                <div className="alert-title">Something went wrong</div>
                <div className="alert-text">{error}</div>
                <details className="alert-details">
                  <summary>Troubleshooting tips</summary>
                  <ul>
                    <li>Check Flask logs for LaTeX compile errors</li>
                    <li>Some job sites block extraction — paste JD text and try again</li>
                    <li>Ensure template files exist in backend/templates</li>
                  </ul>
                </details>
              </div>
            )}
          </div>

          <div className="card card-compact">
            <div className="card-header compact">
              <h2>Keywords Added</h2>
              <p>What we inserted and where.</p>
            </div>

            {keywordsAdded && keywordsAdded.length > 0 ? (
              <div className="keywords-list">
                {keywordsAdded.map((k, idx) => (
                  <div className="keyword-row" key={idx}>
                    <div className="keyword-pill">{k.keyword}</div>
                    <div className="keyword-meta">
                      <span className="badge">{k.location}</span>
                      <span className="where">{k.where}</span>
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="empty">Evaluate to see keywords added for this job.</div>
            )}
          </div>
        </div>

        {/* RIGHT */}
        <div className="right-panel">
          <div className="card preview-card">
            <div className="card-header preview-header">
              <div>
                <h2>PDF Preview</h2>
                <p>Generate the PDF to preview it here.</p>
              </div>
              <div className="filechip" title={downloadFileName}>
                {downloadFileName}
              </div>
            </div>

            <div className="preview-body">
              {pdfPreviewUrl ? (
                <iframe title="Resume Preview" src={pdfPreviewUrl} className="pdf-frame" />
              ) : (
                <div className="preview-placeholder">
                  <div className="placeholder-title">No preview yet</div>
                  <div className="placeholder-text">
                    Click <strong>Generate PDF Preview</strong> after evaluation.
                  </div>
                </div>
              )}
            </div>

            <div className="preview-footer">
              <CustomButton text="Download Updated Resume" disabled={!canDownload} onClick={onClickDownloadBtn} />
              <div className="footer-help">Download becomes available after the preview is generated.</div>
            </div>
          </div>

          <div className="hint-card">
            <div className="hint-title">Pro tip</div>
            <div className="hint-text">
              If a job site blocks extraction, paste the job description text manually. It improves reliability.
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default MainPage;
