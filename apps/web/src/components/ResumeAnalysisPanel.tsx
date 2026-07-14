"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiClientError,
  AnalysisDetail,
  AnalysisSummary,
  calculateKeywordCoverage,
  createAnalysis,
  deleteAnalysis,
  downloadResumeExport,
  getAnalysis,
  generateImprovements,
  ImprovementResponse,
  KeywordCoverage,
  listAnalyses,
  saveImprovements,
} from "@/lib/api";
import styles from "./ResumeAnalysisPanel.module.css";

interface Props {
  resumeId: string;
  sourceFileType: "pdf" | "docx";
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

export default function ResumeAnalysisPanel({ resumeId, sourceFileType }: Props) {
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyActionId, setHistoryActionId] = useState<string | null>(null);
  const [improvement, setImprovement] = useState<ImprovementResponse | null>(null);
  const [improvementLoading, setImprovementLoading] = useState(false);
  const [improvementSaving, setImprovementSaving] = useState(false);
  const [improvementSaved, setImprovementSaved] = useState(false);
  const [exporting, setExporting] = useState<"pdf" | "docx" | null>(null);
  const [exportMode, setExportMode] = useState<"ats" | "preserve">("ats");
  const [targetPages, setTargetPages] = useState<1 | 2>(1);
  const [improvementFeedback, setImprovementFeedback] = useState<Record<string, string>>({});
  const [coverage, setCoverage] = useState<KeywordCoverage | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
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

  useEffect(() => {
    if (!analysis || !improvement?.result.optimized_resume_draft.trim()) {
      return;
    }
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      setCoverageLoading(true);
      calculateKeywordCoverage(
        analysis.analysis_id,
        improvement.result.optimized_resume_draft,
        controller.signal,
      )
        .then(setCoverage)
        .catch((caught: unknown) => {
          if (!(caught instanceof DOMException && caught.name === "AbortError")) {
            setCoverage(null);
          }
        })
        .finally(() => {
          if (!controller.signal.aborted) setCoverageLoading(false);
        });
    }, 400);
    return () => {
      window.clearTimeout(timer);
      controller.abort();
    };
  }, [analysis, improvement?.result.optimized_resume_draft]);

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
      setImprovement(null);
      setImprovementFeedback({});
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
      setImprovement(null);
      setImprovementFeedback({});
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

  const handleGenerateImprovements = async (revise = false) => {
    if (!analysis) return;
    setError(null);
    setImprovementLoading(true);
    try {
      const feedback = Object.entries(improvementFeedback)
        .filter(([, value]) => value.trim())
        .map(([section, value]) => {
          if (section.startsWith("question-") && improvement) {
            const index = Number(section.slice("question-".length));
            const question = improvement.result.clarification_questions[index];
            if (question) return `Answer to "${question.question}": ${value.trim()}`;
          }
          return `${section}: ${value.trim()}`;
        });
      const response = await generateImprovements(
        analysis.analysis_id,
        revise && improvement
          ? { current_result: improvement.result, feedback }
          : undefined,
      );
      setImprovement(response);
      setImprovementSaved(true);
      setImprovementFeedback({});
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? ANALYSIS_ERRORS[caught.code] ?? caught.message
        : "Could not generate resume improvements.");
    } finally {
      setImprovementLoading(false);
    }
  };

  const updateImprovementFeedback = (key: string, value: string) => {
    setImprovementFeedback((previous) => ({ ...previous, [key]: value }));
  };

  const updateClarificationAnswer = (index: number, value: string) => {
    updateImprovementFeedback(`question-${index}`, value);
    setImprovementSaved(false);
    setImprovement((current) => current ? {
      ...current,
      result: {
        ...current.result,
        clarification_questions: current.result.clarification_questions.map(
          (question, itemIndex) => itemIndex === index
            ? {
                ...question,
                answer: value,
                status: value.trim() ? "answered" : "unanswered",
              }
            : question,
        ),
      },
    } : current);
  };

  const replaceFirst = (source: string, current: string, replacement: string) => {
    if (!current || !source.includes(current)) return source;
    return source.replace(current, replacement);
  };

  const updateAtomicChange = (index: number, value: string) => {
    setImprovementSaved(false);
    setImprovement((current) => current ? {
      ...current,
      result: {
        ...current.result,
        optimized_resume_draft: replaceFirst(
          current.result.optimized_resume_draft,
          current.result.change_set[index].suggested,
          value,
        ),
        change_set: current.result.change_set.map((change, itemIndex) => (
          itemIndex === index ? { ...change, suggested: value } : change
        )),
        bullet_rewrites: current.result.bullet_rewrites.map((rewrite) => (
          rewrite.original === current.result.change_set[index].original
            ? { ...rewrite, suggested: value }
            : rewrite
        )),
      },
    } : current);
  };

  const reviewAtomicChange = (
    index: number,
    status: "accepted" | "rejected",
  ) => {
    setImprovementSaved(false);
    setImprovement((current) => {
      if (!current) return current;
      const selected = current.result.change_set[index];
      const from = status === "accepted" ? selected.original : selected.suggested;
      const to = status === "accepted" ? selected.suggested : selected.original;
      return {
        ...current,
        result: {
          ...current.result,
          optimized_resume_draft: replaceFirst(
            current.result.optimized_resume_draft,
            from,
            to,
          ),
          suggested_summary: selected.change_type === "summary" && status === "accepted"
            ? selected.suggested
            : current.result.suggested_summary,
          bullet_rewrites: current.result.bullet_rewrites.map((rewrite) => (
            rewrite.original === selected.original
              ? {
                  ...rewrite,
                  suggested: status === "accepted" ? selected.suggested : rewrite.original,
                }
              : rewrite
          )),
          change_set: current.result.change_set.map((change, itemIndex) => (
            itemIndex === index ? { ...change, status } : change
          )),
        },
      };
    });
  };

  const updateOptimizedDraft = (value: string) => {
    setImprovementSaved(false);
    setImprovement((current) => current ? {
      ...current,
      result: { ...current.result, optimized_resume_draft: value },
    } : current);
  };

  const handleSaveImprovements = async () => {
    if (!analysis || !improvement) return;
    setError(null);
    setImprovementSaving(true);
    try {
      setImprovement(await saveImprovements(
        analysis.analysis_id,
        improvement.result,
      ));
      setImprovementSaved(true);
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not save the edited resume draft.");
    } finally {
      setImprovementSaving(false);
    }
  };

  const handleExport = async (format: "pdf" | "docx") => {
    if (!analysis || !improvement) return;
    setError(null);
    setExporting(format);
    try {
      if (!improvementSaved) {
        const saved = await saveImprovements(
          analysis.analysis_id,
          improvement.result,
        );
        setImprovement(saved);
        setImprovementSaved(true);
      }
      await downloadResumeExport(analysis.analysis_id, format, {
        mode: exportMode,
        targetPages,
      });
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : `Could not download the ${format.toUpperCase()} resume.`);
    } finally {
      setExporting(null);
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

        <section className={styles.improvementPanel}>
          <div className={styles.improvementHeader}>
            <div>
              <p className={styles.eyebrow}>Targeted editing</p>
              <h3>Resume improvements</h3>
            </div>
            {improvement && (
              <div className={styles.coverageSummary} aria-live="polite">
                <strong>
                  {coverageLoading ? "…" : coverage
                    ? `${coverage.coverage_score}%`
                    : "N/A"}
                </strong>
                <span>Keyword coverage</span>
              </div>
            )}
            {!improvement && (
              <button
                type="button"
                className="btn btn-primary btn-sm"
                onClick={() => handleGenerateImprovements(false)}
                disabled={improvementLoading}
              >
                {improvementLoading
                  ? <><span className="spinner spinner-sm" /> Generating…</>
                  : "Generate improvements"}
              </button>
            )}
          </div>

          {error && (
            <div className={`alert alert-error ${styles.improvementAlert}`} role="alert">
              {error}
            </div>
          )}

          {improvement ? (
            <div className={styles.improvementBody}>
              {coverage && (
                <section className={styles.coverageBar}>
                  <div>
                    <strong>{coverage.covered_keywords.length}</strong>
                    <span>Covered</span>
                  </div>
                  <div>
                    <strong>{coverage.missing_keywords.length}</strong>
                    <span>Missing</span>
                  </div>
                  <p>
                    Deterministic phrase coverage from the saved job keywords.
                    No AI call is used.
                  </p>
                </section>
              )}
              <section className={styles.suggestionBlock}>
                <div className={styles.draftHeading}>
                  <div>
                    <h4>Complete optimized draft</h4>
                    <p>Edit this draft directly. Manual saves do not call Gemini.</p>
                  </div>
                  <div className={styles.draftActions}>
                    <label className={styles.exportOption}>
                      <span>Layout</span>
                      <select
                        className="form-input"
                        value={exportMode}
                        onChange={(event) => setExportMode(
                          event.target.value as "ats" | "preserve",
                        )}
                        disabled={exporting !== null}
                      >
                        <option value="ats">ATS optimized</option>
                        <option value="preserve" disabled={sourceFileType !== "docx"}>
                          Preserve original DOCX
                        </option>
                      </select>
                    </label>
                    <label className={styles.exportOption}>
                      <span>Target</span>
                      <select
                        className="form-input"
                        value={targetPages}
                        onChange={(event) => setTargetPages(
                          Number(event.target.value) as 1 | 2,
                        )}
                        disabled={exporting !== null || exportMode === "preserve"}
                      >
                        <option value={1}>1 page</option>
                        <option value={2}>2 pages</option>
                      </select>
                    </label>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={handleSaveImprovements} disabled={improvementSaving || !improvement.result.optimized_resume_draft.trim()}>
                      {improvementSaving ? "Saving…" : improvementSaved ? "Saved" : "Save draft"}
                    </button>
                    <button type="button" className="btn btn-ghost btn-sm" onClick={() => handleExport("docx")} disabled={exporting !== null || !improvement.result.optimized_resume_draft.trim()}>
                      {exporting === "docx" ? "Preparing…" : "Download DOCX"}
                    </button>
                    <button type="button" className="btn btn-primary btn-sm" onClick={() => handleExport("pdf")} disabled={exporting !== null || !improvement.result.optimized_resume_draft.trim()} title="PDF always uses the ATS-optimized layout">
                      {exporting === "pdf" ? "Preparing…" : "Download PDF"}
                    </button>
                  </div>
                </div>
                <textarea
                  className={`form-input ${styles.draftEditor}`}
                  value={improvement.result.optimized_resume_draft}
                  onChange={(event) => updateOptimizedDraft(event.target.value)}
                  maxLength={50000}
                  aria-label="Edit complete optimized resume draft"
                />
              </section>

              {improvement.result.clarification_questions.length > 0 && (
                <section className={styles.suggestionBlock}>
                  <div className={styles.reviewHeading}>
                    <div>
                      <h4>Confirm your experience</h4>
                      <p>Answers are used as context when you regenerate.</p>
                    </div>
                    <span>{improvement.result.clarification_questions.length}</span>
                  </div>
                  <div className={styles.clarifications}>
                    {improvement.result.clarification_questions.map((question, index) => (
                      <label key={question.question_id || `${question.requirement}-${index}`} className={styles.clarification}>
                        <span>{question.requirement}</span>
                        <strong>{question.question}</strong>
                        <textarea
                          className="form-input"
                          value={improvementFeedback[`question-${index}`] ?? question.answer}
                          onChange={(event) => updateClarificationAnswer(
                            index,
                            event.target.value,
                          )}
                          maxLength={1000}
                          placeholder="Describe only experience you actually have"
                        />
                      </label>
                    ))}
                  </div>
                </section>
              )}

              {improvement.result.change_set.length > 0 && (
                <section className={styles.suggestionBlock}>
                  <div className={styles.reviewHeading}>
                    <div>
                      <h4>Review proposed changes</h4>
                      <p>Accept, edit, or reject each change before export.</p>
                    </div>
                    <span>
                      {improvement.result.change_set.filter(
                        (change) => change.status === "proposed",
                      ).length} pending
                    </span>
                  </div>
                  <div className={styles.rewrites}>
                    {improvement.result.change_set.map((change, index) => (
                      <article
                        key={change.change_id || `${change.original}-${index}`}
                        className={`${styles.rewrite} ${styles[`change_${change.status}`]}`}
                      >
                        <div className={styles.changeMeta}>
                          <span>{change.target_section || change.change_type}</span>
                          <span>{Math.round(change.confidence * 100)}% confidence</span>
                        </div>
                        {change.original && (
                          <p><span>Original</span>{change.original}</p>
                        )}
                        <div className={styles.rewriteEditor}>
                          <span>Suggested</span>
                          <textarea
                            className="form-input"
                            value={change.suggested}
                            onChange={(event) => updateAtomicChange(index, event.target.value)}
                            maxLength={1500}
                            aria-label={`Edit proposed change ${index + 1}`}
                          />
                        </div>
                        <small>{change.reason}</small>
                        {change.evidence.length > 0 && (
                          <div className={styles.evidence}>
                            <span>Evidence</span>
                            <p>{change.evidence.join(" · ")}</p>
                          </div>
                        )}
                        {change.requires_confirmation && (
                          <p className={styles.confirmationNote}>Confirm this claim before accepting.</p>
                        )}
                        <div className={styles.changeActions}>
                          <button
                            type="button"
                            className="btn btn-ghost btn-sm"
                            onClick={() => reviewAtomicChange(index, "rejected")}
                            disabled={change.status === "rejected"}
                          >
                            Reject
                          </button>
                          <button
                            type="button"
                            className="btn btn-primary btn-sm"
                            onClick={() => reviewAtomicChange(index, "accepted")}
                            disabled={change.status === "accepted"}
                          >
                            {change.requires_confirmation ? "Confirm and accept" : "Accept"}
                          </button>
                        </div>
                      </article>
                    ))}
                  </div>
                </section>
              )}

              <div className={styles.improvementGrid}>
                <ResultList title="ATS recommendations" items={improvement.result.ats_recommendations} />
                <ResultList title="Skills to emphasize" items={improvement.result.skills_to_emphasize} />
                <ResultList title="Integrity notes" items={improvement.result.integrity_notes} />
              </div>

              <div className={styles.revisionActions}>
                <label className={styles.feedbackField}>
                  <span>General feedback</span>
                  <textarea
                    className="form-input"
                    value={improvementFeedback.general ?? ""}
                    onChange={(event) => updateImprovementFeedback("general", event.target.value)}
                    maxLength={1000}
                    placeholder="Add instructions that apply to the complete improvement draft"
                  />
                </label>
                <button
                  type="button"
                  className="btn btn-primary"
                  onClick={() => handleGenerateImprovements(true)}
                  disabled={improvementLoading}
                >
                  {improvementLoading
                    ? <><span className="spinner spinner-sm" /> Regenerating…</>
                    : "Regenerate with edits"}
                </button>
              </div>
            </div>
          ) : (
            <p className={styles.improvementEmpty}>
              Generate evidence-based rewrites using this resume and job description.
            </p>
          )}
        </section>
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
