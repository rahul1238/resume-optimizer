"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiClientError,
  AnalysisDetail,
  AnalysisSummary,
  createAnalysis,
  deleteAnalysis,
  getAnalysis,
  listAnalyses,
} from "@/lib/api";
import styles from "./ResumeAnalysisPanel.module.css";

interface Props {
  resumeId: string;
}

const ANALYSIS_ERRORS: Record<string, string> = {
  ai_provider_not_configured: "Resume analysis is not configured yet.",
  ai_provider_unavailable:
    "The analysis service is temporarily unavailable or has reached its quota. Try again shortly.",
  resume_not_found: "This resume is no longer available. Upload it again to continue.",
  resume_storage_unavailable: "The parsed resume could not be retrieved. Try again shortly.",
  analysis_repository_unavailable:
    "The analysis completed but could not be saved. Please try again.",
  missing_authentication: "Your session has expired. Sign in again to continue.",
  invalid_authentication: "Your session has expired. Sign in again to continue.",
};

function ResultList({ title, items }: { title: string; items: string[] }) {
  if (items.length === 0) return null;
  return (
    <section className={styles.resultSection}>
      <h4>{title}</h4>
      <ul>
        {items.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </section>
  );
}

export default function ResumeAnalysisPanel({ resumeId }: Props) {
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyActionId, setHistoryActionId] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    listAnalyses(resumeId)
      .then((items) => {
        if (active) setHistory(items);
      })
      .catch((caught: unknown) => {
        if (active) {
          setError(caught instanceof ApiClientError
            ? caught.message
            : "Could not load saved analyses.");
        }
      })
      .finally(() => {
        if (active) setHistoryLoading(false);
      });
    return () => { active = false; };
  }, [resumeId]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setLoading(true);
    try {
      const response = await createAnalysis({
        resume_id: resumeId,
        job_description: jobDescription.trim(),
        job_title: jobTitle.trim() || undefined,
        company_name: companyName.trim() || undefined,
      });
      const createdAt = new Date().toISOString();
      const detail: AnalysisDetail = {
        ...response,
        job_title: jobTitle.trim() || null,
        company_name: companyName.trim() || null,
        job_description: jobDescription.trim(),
        match_score: response.result.match_score,
        created_at: createdAt,
      };
      setAnalysis(detail);
      setHistory((previous) => [{
        analysis_id: response.analysis_id,
        resume_id: response.resume_id,
        job_title: detail.job_title,
        company_name: detail.company_name,
        match_score: detail.match_score,
        status: response.status,
        provider: response.provider,
        model: response.model,
        created_at: createdAt,
      }, ...previous]);
    } catch (caught: unknown) {
      const message = caught instanceof ApiClientError
        ? ANALYSIS_ERRORS[caught.code] ?? caught.message
        : "Analysis failed. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const handleOpenAnalysis = async (analysisId: string) => {
    setError(null);
    setHistoryActionId(analysisId);
    try {
      const detail = await getAnalysis(analysisId);
      setAnalysis(detail);
      setJobTitle(detail.job_title ?? "");
      setCompanyName(detail.company_name ?? "");
      setJobDescription(detail.job_description);
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not open this analysis.");
    } finally {
      setHistoryActionId(null);
    }
  };

  const handleDeleteAnalysis = async (item: AnalysisSummary) => {
    if (!window.confirm("Delete this saved analysis?")) return;
    setError(null);
    setHistoryActionId(item.analysis_id);
    try {
      await deleteAnalysis(item.analysis_id);
      setHistory((previous) => previous.filter(
        (entry) => entry.analysis_id !== item.analysis_id,
      ));
      if (analysis?.analysis_id === item.analysis_id) setAnalysis(null);
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not delete this analysis.");
    } finally {
      setHistoryActionId(null);
    }
  };

  const historySection = (
    <section className={styles.historyPanel} aria-labelledby="analysis-history-title">
      <div className={styles.historyHeader}>
        <div>
          <p className={styles.eyebrow}>Previous results</p>
          <h3 id="analysis-history-title">Analysis history</h3>
        </div>
        <span>{history.length}</span>
      </div>
      {historyLoading ? (
        <div className={styles.historyState}>
          <span className="spinner spinner-sm" /> Loading analyses…
        </div>
      ) : history.length === 0 ? (
        <p className={styles.historyState}>No saved analyses for this resume.</p>
      ) : (
        <ul className={styles.historyList}>
          {history.map((item) => (
            <li key={item.analysis_id} className={styles.historyItem}>
              <button
                type="button"
                className={styles.historyOpen}
                onClick={() => handleOpenAnalysis(item.analysis_id)}
                disabled={historyActionId === item.analysis_id}
              >
                <span className={styles.historyScore}>{item.match_score}</span>
                <span className={styles.historyMeta}>
                  <strong>{item.job_title || "Untitled job"}</strong>
                  <small>
                    {item.company_name || "Company not specified"} · {item.created_at
                      ? new Date(item.created_at).toLocaleDateString()
                      : "Saved"}
                  </small>
                </span>
              </button>
              <button
                type="button"
                className={styles.historyDelete}
                onClick={() => handleDeleteAnalysis(item)}
                disabled={historyActionId === item.analysis_id}
                aria-label={`Delete analysis for ${item.job_title || "untitled job"}`}
                title="Delete analysis"
              >
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5" />
                </svg>
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );

  if (analysis) {
    const result = analysis.result;
    return (
      <>
        {historySection}
        <div className={`${styles.panel} animate-slide-up`}>
        <header className={styles.resultHeader}>
          <div className={styles.score} aria-label={`${result.match_score} percent match`}>
            <strong>{result.match_score}</strong>
            <span>Match score</span>
          </div>
          <div className={styles.summary}>
            <p className={styles.eyebrow}>Resume analysis</p>
            <h3>{analysis.job_title || "Job match"}</h3>
            <p>{result.summary}</p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setAnalysis(null)}
          >
            New analysis
          </button>
        </header>

        <div className={styles.resultGrid}>
          <ResultList title="Strengths" items={result.strengths} />
          <ResultList title="Gaps" items={result.gaps} />
          <ResultList title="Recommendations" items={result.recommendations} />
        </div>

        <div className={styles.keywordGrid}>
          <section>
            <h4>Matched keywords</h4>
            <div className={styles.keywords}>
              {result.matched_keywords.length > 0
                ? result.matched_keywords.map((word) => (
                    <span key={word} className={styles.matchedKeyword}>{word}</span>
                  ))
                : <span className={styles.emptyText}>No exact matches identified</span>}
            </div>
          </section>
          <section>
            <h4>Missing keywords</h4>
            <div className={styles.keywords}>
              {result.missing_keywords.length > 0
                ? result.missing_keywords.map((word) => (
                    <span key={word} className={styles.missingKeyword}>{word}</span>
                  ))
                : <span className={styles.emptyText}>No important keywords missing</span>}
            </div>
          </section>
        </div>

        <footer className={styles.resultMeta}>
          Analysis ID {analysis.analysis_id.slice(0, 8)} · {analysis.model}
        </footer>
        </div>
      </>
    );
  }

  return (
    <>
      {historySection}
      <div className={styles.panel}>
      <div className={styles.formHeader}>
        <p className={styles.eyebrow}>Next step</p>
        <h3>Compare with a job</h3>
        <p>Paste the full job description for a more accurate match analysis.</p>
      </div>

      <form className={styles.form} onSubmit={handleSubmit}>
        <div className={styles.optionalFields}>
          <div className="form-group">
            <label className="form-label" htmlFor="job-title">Job title</label>
            <input
              id="job-title"
              className="form-input"
              value={jobTitle}
              onChange={(event) => setJobTitle(event.target.value)}
              maxLength={200}
              placeholder="Backend Engineer"
              disabled={loading}
            />
          </div>
          <div className="form-group">
            <label className="form-label" htmlFor="company-name">Company</label>
            <input
              id="company-name"
              className="form-input"
              value={companyName}
              onChange={(event) => setCompanyName(event.target.value)}
              maxLength={200}
              placeholder="Company name"
              disabled={loading}
            />
          </div>
        </div>

        <div className="form-group">
          <div className={styles.labelRow}>
            <label className="form-label" htmlFor="job-description">Job description</label>
            <span>{jobDescription.length.toLocaleString()} / 30,000</span>
          </div>
          <textarea
            id="job-description"
            className={`form-input ${styles.textarea}`}
            value={jobDescription}
            onChange={(event) => setJobDescription(event.target.value)}
            minLength={100}
            maxLength={30000}
            required
            placeholder="Paste the responsibilities, requirements, qualifications, and preferred skills..."
            disabled={loading}
          />
        </div>

        {error && <div className="alert alert-error" role="alert">{error}</div>}

        <div className={styles.formActions}>
          <span>Minimum 100 characters</span>
          <button
            type="submit"
            className="btn btn-primary"
            disabled={loading || jobDescription.trim().length < 100}
          >
            {loading ? <><span className="spinner spinner-sm" /> Analyzing…</> : "Analyze match"}
          </button>
        </div>
      </form>
      </div>
    </>
  );
}
