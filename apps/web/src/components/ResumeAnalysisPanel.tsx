"use client";

import { FormEvent, useState } from "react";
import {
  ApiClientError,
  AnalysisCreateResponse,
  createAnalysis,
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
  const [analysis, setAnalysis] = useState<AnalysisCreateResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      setAnalysis(response);
    } catch (caught: unknown) {
      const message = caught instanceof ApiClientError
        ? ANALYSIS_ERRORS[caught.code] ?? caught.message
        : "Analysis failed. Please try again.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  if (analysis) {
    const result = analysis.result;
    return (
      <div className={`${styles.panel} animate-slide-up`}>
        <header className={styles.resultHeader}>
          <div className={styles.score} aria-label={`${result.match_score} percent match`}>
            <strong>{result.match_score}</strong>
            <span>Match score</span>
          </div>
          <div className={styles.summary}>
            <p className={styles.eyebrow}>Resume analysis</p>
            <h3>{jobTitle || "Job match"}</h3>
            <p>{result.summary}</p>
          </div>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setAnalysis(null)}
          >
            Edit job
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
    );
  }

  return (
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
  );
}
