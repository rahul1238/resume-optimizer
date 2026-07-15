"use client";

import { FormEvent, useEffect, useState } from "react";
import {
  ApiClientError,
  ATSScan,
  BulletOptimizationProposal,
  AnalysisDetail,
  AnalysisSummary,
  calculateKeywordCoverage,
  createAnalysis,
  deleteAnalysis,
  downloadResumeExport,
  getResumePdfPreview,
  getAnalysis,
  generateImprovements,
  ImprovementResponse,
  KeywordCoverage,
  listAnalyses,
  proposeBulletOptimization,
  ResumeLayoutSettings,
  scanResumeATS,
  saveImprovementLayout,
  saveImprovements,
  StructuredResumeDocument,
} from "@/lib/api";
import styles from "./ResumeAnalysisPanel.module.css";

interface Props {
  resumeId: string;
}

const ANALYSIS_ERRORS: Record<string, string> = {
  ai_provider_not_configured: "Resume analysis is not configured yet.",
  ai_provider_unavailable:
    "The analysis service is temporarily unavailable or has reached its quota. Try again shortly.",
  ai_provider_quota_exceeded:
    "Gemini's free-tier quota is exhausted across the available models. Try again after the quota resets.",
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

function LayoutNumber({
  label,
  value,
  min,
  max,
  step,
  onChange,
}: {
  label: string;
  value: number;
  min: number;
  max: number;
  step: number;
  onChange: (value: number) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input
        className="form-input"
        type="number"
        value={value}
        min={min}
        max={max}
        step={step}
        onChange={(event) => {
          const next = event.currentTarget.valueAsNumber;
          if (Number.isFinite(next)) {
            onChange(Math.min(max, Math.max(min, next)));
          }
        }}
      />
    </label>
  );
}

interface BulletGroup {
  groupIndex: number;
  entryLabel: string;
  itemIndices: number[];
  bullets: string[];
}

function bulletGroups(items: string[]): BulletGroup[] {
  const groups: BulletGroup[] = [];
  let entryLabel = "Entry";
  let index = 0;
  while (index < items.length) {
    if (!/^\s*[-*•]\s+/.test(items[index])) {
      entryLabel = items[index];
      index += 1;
      continue;
    }
    const itemIndices: number[] = [];
    const bullets: string[] = [];
    while (index < items.length && /^\s*[-*•]\s+/.test(items[index])) {
      itemIndices.push(index);
      bullets.push(items[index]);
      index += 1;
    }
    groups.push({
      groupIndex: groups.length,
      entryLabel,
      itemIndices,
      bullets,
    });
  }
  return groups;
}

function serializeResume(document: StructuredResumeDocument): string {
  const sections = document.sections.map((section) => (
    [section.heading, ...section.items].join("\n")
  ));
  return [...document.header, ...sections].join("\n\n");
}

export default function ResumeAnalysisPanel({ resumeId }: Props) {
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [jobDescription, setJobDescription] = useState("");
  const [atsScan, setAtsScan] = useState<ATSScan | null>(null);
  const [atsLoading, setAtsLoading] = useState(true);
  const [atsError, setAtsError] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalysisDetail | null>(null);
  const [history, setHistory] = useState<AnalysisSummary[]>([]);
  const [historyLoading, setHistoryLoading] = useState(true);
  const [historyActionId, setHistoryActionId] = useState<string | null>(null);
  const [improvement, setImprovement] = useState<ImprovementResponse | null>(null);
  const [improvementLoading, setImprovementLoading] = useState(false);
  const [improvementSaving, setImprovementSaving] = useState(false);
  const [improvementSaved, setImprovementSaved] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [layoutSaving, setLayoutSaving] = useState(false);
  const [bulletProposal, setBulletProposal] = useState<BulletOptimizationProposal | null>(null);
  const [bulletLoadingKey, setBulletLoadingKey] = useState<string | null>(null);
  const [bulletSettings, setBulletSettings] = useState<Record<string, {
    targetCount: number;
    mode: "prioritize" | "consolidate" | "expand";
  }>>({});
  const [draftView, setDraftView] = useState<"preview" | "edit">("preview");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewPageCount, setPreviewPageCount] = useState<number | null>(null);
  const [previewRevision, setPreviewRevision] = useState(0);
  const [improvementFeedback, setImprovementFeedback] = useState<Record<string, string>>({});
  const [coverage, setCoverage] = useState<KeywordCoverage | null>(null);
  const [coverageLoading, setCoverageLoading] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    scanResumeATS(resumeId, controller.signal)
      .then(setAtsScan)
      .catch((caught: unknown) => {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setAtsError(caught instanceof ApiClientError
            ? caught.message
            : "Could not run the generic ATS scan.");
        }
      })
      .finally(() => {
        if (!controller.signal.aborted) setAtsLoading(false);
      });
    return () => controller.abort();
  }, [resumeId]);

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

  useEffect(() => {
    const draft = improvement?.result.optimized_resume_draft.trim();
    const layout = improvement?.layout;
    if (!analysis || !draft || !layout) {
      return;
    }

    const controller = new AbortController();
    let objectUrl: string | null = null;
    const timer = window.setTimeout(async () => {
      setPreviewLoading(true);
      setPreviewError(null);
      try {
        const preview = await getResumePdfPreview(
          analysis.analysis_id,
          draft,
          layout,
          controller.signal,
        );
        objectUrl = URL.createObjectURL(preview.blob);
        setPreviewUrl(objectUrl);
        setPreviewPageCount(preview.pageCount);
      } catch (caught: unknown) {
        if (!(caught instanceof DOMException && caught.name === "AbortError")) {
          setPreviewError(caught instanceof ApiClientError
            ? caught.message
            : "Could not render the resume preview.");
        }
      } finally {
        if (!controller.signal.aborted) setPreviewLoading(false);
      }
    }, 900);

    return () => {
      window.clearTimeout(timer);
      controller.abort();
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [
    analysis,
    improvement?.result.optimized_resume_draft,
    improvement?.layout,
    previewRevision,
  ]);

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

  const handleGenerateImprovements = async (
    revise = false,
    supplementalFeedback: string[] = [],
  ) => {
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
        })
        .concat(supplementalFeedback);
      const response = await generateImprovements(
        analysis.analysis_id,
        revise && improvement
          ? { current_result: improvement.result, feedback }
          : undefined,
      );
      setImprovement(response);
      setImprovementSaved(true);
      setImprovementFeedback({});
      setDraftView("preview");
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

  const updateBulletSetting = (
    key: string,
    currentCount: number,
    update: Partial<{
      targetCount: number;
      mode: "prioritize" | "consolidate" | "expand";
    }>,
  ) => {
    setBulletSettings((previous) => {
      const existing = previous[key] ?? {
        targetCount: currentCount > 1 ? currentCount - 1 : 2,
        mode: "prioritize",
      } as const;
      return {
        ...previous,
        [key]: { ...existing, ...update },
      };
    });
  };

  const handleBulletProposal = async (
    sectionId: string,
    group: BulletGroup,
  ) => {
    if (!analysis) return;
    const key = `${sectionId}:${group.groupIndex}`;
    const setting = bulletSettings[key] ?? {
      targetCount: group.bullets.length > 1 ? group.bullets.length - 1 : 2,
      mode: "prioritize" as const,
    };
    setBulletLoadingKey(key);
    setError(null);
    try {
      setBulletProposal(await proposeBulletOptimization(analysis.analysis_id, {
        section_id: sectionId,
        group_index: group.groupIndex,
        target_count: setting.targetCount,
        mode: setting.mode,
      }));
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? ANALYSIS_ERRORS[caught.code] ?? caught.message
        : "Could not create the bullet proposal.");
    } finally {
      setBulletLoadingKey(null);
    }
  };

  const applyBulletProposal = () => {
    if (!bulletProposal?.can_apply) return;
    setImprovementSaved(false);
    setImprovement((current) => {
      const document = current?.result.structured_resume;
      if (!current || !document) return current;
      const replacedIndices = new Set(bulletProposal.item_indices);
      const firstIndex = Math.min(...bulletProposal.item_indices);
      const sections = document.sections.map((section) => {
        if (section.section_id !== bulletProposal.section_id) return section;
        const items: string[] = [];
        section.items.forEach((item, index) => {
          if (index === firstIndex) items.push(...bulletProposal.proposed_bullets);
          if (!replacedIndices.has(index)) items.push(item);
        });
        return { ...section, items };
      });
      const updatedDocument = { ...document, sections };
      return {
        ...current,
        result: {
          ...current.result,
          structured_resume: updatedDocument,
          optimized_resume_draft: serializeResume(updatedDocument),
          change_set: [
            ...current.result.change_set,
            {
              change_id: bulletProposal.proposal_id,
              change_type: "bullet" as const,
              status: "accepted" as const,
              target_section: bulletProposal.entry_label.slice(0, 120),
              original: bulletProposal.original_bullets.join("\n").slice(0, 1500),
              suggested: bulletProposal.proposed_bullets.join("\n").slice(0, 1500),
              reason: bulletProposal.rationale.slice(0, 500),
              evidence: bulletProposal.original_bullets.slice(0, 5),
              confidence: 0.9,
              requires_confirmation: false,
            },
          ].slice(-30),
        },
      };
    });
    setBulletProposal(null);
  };

  const updateLayout = <K extends keyof ResumeLayoutSettings>(
    key: K,
    value: ResumeLayoutSettings[K],
  ) => {
    setImprovement((current) => current ? {
      ...current,
      layout: { ...current.layout, [key]: value },
    } : current);
  };

  const handleSaveLayout = async () => {
    if (!analysis || !improvement) return;
    setLayoutSaving(true);
    setError(null);
    try {
      const currentResult = improvement.result;
      const saved = await saveImprovementLayout(
        analysis.analysis_id,
        improvement.layout,
      );
      setImprovement({ ...saved, result: currentResult });
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not save the resume layout.");
    } finally {
      setLayoutSaving(false);
    }
  };

  const handleSaveImprovements = async () => {
    if (!analysis || !improvement) return;
    setError(null);
    setImprovementSaving(true);
    try {
      const currentLayout = improvement.layout;
      const saved = await saveImprovements(
        analysis.analysis_id,
        improvement.result,
      );
      setImprovement({ ...saved, layout: currentLayout });
      setImprovementSaved(true);
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not save the edited resume draft.");
    } finally {
      setImprovementSaving(false);
    }
  };

  const handleExport = async () => {
    if (!analysis || !improvement) return;
    setError(null);
    setExporting(true);
    try {
      const saved = await saveImprovements(
        analysis.analysis_id,
        improvement.result,
      );
      const withLayout = await saveImprovementLayout(
        analysis.analysis_id,
        improvement.layout,
      );
      setImprovement({ ...withLayout, result: saved.result });
      setImprovementSaved(true);
      await downloadResumeExport(analysis.analysis_id);
    } catch (caught: unknown) {
      setError(caught instanceof ApiClientError
        ? caught.message
        : "Could not download the PDF resume.");
    } finally {
      setExporting(false);
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

  const atsSection = (
    <section className={styles.atsPanel} aria-labelledby="generic-ats-title">
      <div className={styles.atsHeader}>
        <div>
          <p className={styles.eyebrow}>Generic scan</p>
          <h3 id="generic-ats-title">ATS readiness</h3>
        </div>
        {atsScan && (
          <div className={styles.atsScore} aria-label={`${atsScan.score} percent ATS ready`}>
            <strong>{atsScan.score}</strong>
            <span>/100</span>
          </div>
        )}
      </div>
      {atsLoading ? (
        <div className={styles.historyState}>
          <span className="spinner spinner-sm" /> Scanning resume…
        </div>
      ) : atsError ? (
        <p className={styles.atsError}>{atsError}</p>
      ) : atsScan ? (
        <div className={styles.atsBody}>
          <ul className={styles.atsChecks}>
            {atsScan.checks.map((check) => (
              <li key={check.check_id} className={styles[`ats_${check.status}`]}>
                <div>
                  <strong>{check.label}</strong>
                  <span>{check.status}</span>
                </div>
                <p>{check.detail}</p>
              </li>
            ))}
          </ul>
        </div>
      ) : null}
    </section>
  );

  if (analysis) {
    const result = analysis.result;
    return (
      <div className={styles.analysisWorkspace}>
        <aside className={styles.workspaceColumn} aria-label="Analysis history">
          {atsSection}
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
        </aside>

        <section className={`${styles.workspaceColumn} ${styles.editorColumn}`} aria-label="Resume change review">
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
              {improvement.result.structured_resume && (
                <section className={styles.bulletControlBlock}>
                  <div className={styles.reviewHeading}>
                    <div>
                      <h4>Bullet count</h4>
                      <p>Create a proposal for one role or project at a time.</p>
                    </div>
                  </div>
                  <div className={styles.bulletGroups}>
                    {improvement.result.structured_resume.sections
                      .filter((section) => {
                        const heading = section.heading.toLowerCase();
                        return heading.includes("experience") || heading.includes("project");
                      })
                      .flatMap((section) => bulletGroups(section.items).map((group) => {
                        const key = `${section.section_id}:${group.groupIndex}`;
                        const setting = bulletSettings[key] ?? {
                          targetCount: group.bullets.length > 1
                            ? group.bullets.length - 1
                            : 2,
                          mode: "prioritize" as const,
                        };
                        const proposal = bulletProposal?.section_id === section.section_id
                          && bulletProposal.group_index === group.groupIndex
                          ? bulletProposal
                          : null;
                        return (
                          <article key={key} className={styles.bulletGroup}>
                            <div className={styles.bulletGroupHeader}>
                              <div>
                                <strong>{group.entryLabel}</strong>
                                <span>{group.bullets.length} current bullets</span>
                              </div>
                              <div className={styles.bulletControls}>
                                <label>
                                  <span>Target</span>
                                  <input
                                    className="form-input"
                                    type="number"
                                    min={1}
                                    max={12}
                                    value={setting.targetCount}
                                    onChange={(event) => updateBulletSetting(
                                      key,
                                      group.bullets.length,
                                      {
                                        targetCount: Math.min(
                                          12,
                                          Math.max(1, event.currentTarget.valueAsNumber || 1),
                                        ),
                                        mode: event.currentTarget.valueAsNumber
                                          > group.bullets.length
                                          ? "expand"
                                          : setting.mode === "expand"
                                            ? "prioritize"
                                            : setting.mode,
                                      },
                                    )}
                                  />
                                </label>
                                <label>
                                  <span>Method</span>
                                  <select
                                    className="form-input"
                                    value={setting.mode}
                                    onChange={(event) => updateBulletSetting(
                                      key,
                                      group.bullets.length,
                                      {
                                        mode: event.target.value as
                                          | "prioritize"
                                          | "consolidate"
                                          | "expand",
                                      },
                                    )}
                                  >
                                    <option value="prioritize">Prioritize</option>
                                    <option value="consolidate">Consolidate</option>
                                    <option value="expand">Expand</option>
                                  </select>
                                </label>
                                <button
                                  type="button"
                                  className="btn btn-ghost btn-sm"
                                  onClick={() => handleBulletProposal(section.section_id, group)}
                                  disabled={bulletLoadingKey !== null
                                    || setting.targetCount === group.bullets.length}
                                >
                                  {bulletLoadingKey === key ? "Generating…" : "Propose"}
                                </button>
                              </div>
                            </div>
                            {proposal && (
                              <div className={styles.bulletProposal}>
                                <p>{proposal.rationale}</p>
                                <ul>
                                  {proposal.proposed_bullets.map((bullet, index) => (
                                    <li key={`${proposal.proposal_id}:${index}`}>
                                      {bullet.replace(/^\s*[-*•]\s+/, "")}
                                    </li>
                                  ))}
                                </ul>
                                {proposal.lost_keywords.length > 0 && (
                                  <div className={styles.keywordWarning} role="alert">
                                    Missing protected keywords: {proposal.lost_keywords.join(", ")}
                                  </div>
                                )}
                                <div className={styles.proposalActions}>
                                  <button
                                    type="button"
                                    className="btn btn-ghost btn-sm"
                                    onClick={() => setBulletProposal(null)}
                                  >
                                    Dismiss
                                  </button>
                                  <button
                                    type="button"
                                    className="btn btn-primary btn-sm"
                                    onClick={applyBulletProposal}
                                    disabled={!proposal.can_apply}
                                  >
                                    Apply proposal
                                  </button>
                                </div>
                              </div>
                            )}
                          </article>
                        );
                      }))}
                  </div>
                </section>
              )}
              {improvement.result.tailoring_decisions.length > 0 && (
                <section className={styles.selectionBlock}>
                  <div className={styles.reviewHeading}>
                    <div>
                      <h4>Content selected for this role</h4>
                      <p>The master resume remains unchanged.</p>
                    </div>
                    <span>
                      {improvement.result.tailoring_decisions.filter(
                        (decision) => decision.action === "omit",
                      ).length} omitted
                    </span>
                  </div>
                  <div className={styles.selectionGroups}>
                    {(["include", "condense", "omit"] as const).map((action) => {
                      const decisions = improvement.result.tailoring_decisions.filter(
                        (decision) => decision.action === action,
                      );
                      if (decisions.length === 0) return null;
                      return (
                        <details key={action} className={styles.selectionGroup}>
                          <summary>
                            <span>{action === "include" ? "Included" : action === "condense" ? "Condensed" : "Omitted"}</span>
                            <strong>{decisions.length}</strong>
                          </summary>
                          <div className={styles.selectionList}>
                            {decisions.map((decision) => (
                              <article key={decision.decision_id}>
                                <div className={styles.changeMeta}>
                                  <span>{decision.content_type.replace("_", " ")}</span>
                                  <span>{decision.relevance}</span>
                                </div>
                                <p>{decision.source_text}</p>
                                <small>{decision.reason}</small>
                                {decision.matched_requirements.length > 0 && (
                                  <div className={styles.decisionRequirements}>
                                    {decision.matched_requirements.map((requirement) => (
                                      <span key={requirement}>{requirement}</span>
                                    ))}
                                  </div>
                                )}
                              </article>
                            ))}
                          </div>
                        </details>
                      );
                    })}
                  </div>
                </section>
              )}
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
        </section>

        <aside className={`${styles.workspaceColumn} ${styles.draftColumn}`} aria-label="Tailored resume draft">
          <section className={styles.draftPanel}>
            {improvement ? (
              <>
                <div className={styles.draftHeading}>
                  <div>
                    <p className={styles.eyebrow}>Tailored resume</p>
                    <h3>Editable draft</h3>
                    <p>Manual edits do not call Gemini.</p>
                  </div>
                  {previewPageCount && (
                    <span className={styles.pageCount}>
                      {previewPageCount} {previewPageCount === 1 ? "page" : "pages"}
                    </span>
                  )}
                </div>
                <div className={styles.draftCommands}>
                  <div className={styles.viewToggle} aria-label="Resume view">
                    <button
                      type="button"
                      className={draftView === "preview" ? styles.viewToggleActive : ""}
                      onClick={() => setDraftView("preview")}
                      aria-pressed={draftView === "preview"}
                    >
                      Preview
                    </button>
                    <button
                      type="button"
                      className={draftView === "edit" ? styles.viewToggleActive : ""}
                      onClick={() => setDraftView("edit")}
                      aria-pressed={draftView === "edit"}
                    >
                      Edit
                    </button>
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={handleSaveImprovements} disabled={improvementSaving || !improvement.result.optimized_resume_draft.trim()}>
                    {improvementSaving ? "Saving…" : improvementSaved ? "Saved" : "Save draft"}
                  </button>
                  <button type="button" className="btn btn-primary btn-sm" onClick={handleExport} disabled={exporting || !improvement.result.optimized_resume_draft.trim()}>
                    {exporting ? "Preparing…" : "Download PDF"}
                  </button>
                </div>
                <details className={styles.layoutPanel}>
                  <summary>Layout and typography</summary>
                  <div className={styles.layoutGrid}>
                    <label><span>Page</span><select className="form-input" value={improvement.layout.page_format} onChange={(event) => updateLayout("page_format", event.target.value as "a4" | "letter")}><option value="a4">A4</option><option value="letter">Letter</option></select></label>
                    <label><span>Body font</span><select className="form-input" value={improvement.layout.body_font} onChange={(event) => updateLayout("body_font", event.target.value as "sans" | "serif")}><option value="sans">Sans serif</option><option value="serif">Serif</option></select></label>
                    <label><span>Heading font</span><select className="form-input" value={improvement.layout.heading_font} onChange={(event) => updateLayout("heading_font", event.target.value as "sans" | "serif")}><option value="sans">Sans serif</option><option value="serif">Serif</option></select></label>
                    <LayoutNumber label="Body size" value={improvement.layout.body_size} min={9.5} max={12} step={0.5} onChange={(value) => updateLayout("body_size", value)} />
                    <LayoutNumber label="Heading size" value={improvement.layout.heading_size} min={10} max={15} step={0.5} onChange={(value) => updateLayout("heading_size", value)} />
                    <LayoutNumber label="Name size" value={improvement.layout.name_size} min={14} max={22} step={1} onChange={(value) => updateLayout("name_size", value)} />
                    <LayoutNumber label="Line spacing" value={improvement.layout.line_spacing} min={1.05} max={1.5} step={0.05} onChange={(value) => updateLayout("line_spacing", value)} />
                    <LayoutNumber label="Top margin" value={improvement.layout.margin_top} min={0.35} max={1.2} step={0.05} onChange={(value) => updateLayout("margin_top", value)} />
                    <LayoutNumber label="Right margin" value={improvement.layout.margin_right} min={0.35} max={1.2} step={0.05} onChange={(value) => updateLayout("margin_right", value)} />
                    <LayoutNumber label="Bottom margin" value={improvement.layout.margin_bottom} min={0.35} max={1.2} step={0.05} onChange={(value) => updateLayout("margin_bottom", value)} />
                    <LayoutNumber label="Left margin" value={improvement.layout.margin_left} min={0.35} max={1.2} step={0.05} onChange={(value) => updateLayout("margin_left", value)} />
                    <LayoutNumber label="Section gap" value={improvement.layout.section_spacing} min={2} max={16} step={1} onChange={(value) => updateLayout("section_spacing", value)} />
                    <LayoutNumber label="Heading gap" value={improvement.layout.heading_content_spacing} min={1} max={10} step={0.5} onChange={(value) => updateLayout("heading_content_spacing", value)} />
                    <LayoutNumber label="Block gap" value={improvement.layout.block_spacing} min={0} max={10} step={0.5} onChange={(value) => updateLayout("block_spacing", value)} />
                  </div>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={handleSaveLayout} disabled={layoutSaving}>
                    {layoutSaving ? "Saving…" : "Save layout"}
                  </button>
                </details>
                {draftView === "preview" ? (
                  <div className={styles.previewFrame} aria-live="polite">
                    {previewUrl && (
                      <iframe
                        src={`${previewUrl}#toolbar=1&navpanes=0&view=FitH`}
                        title="Formatted tailored resume preview"
                      />
                    )}
                    {previewLoading && (
                      <div className={styles.previewStatus}>
                        <span className="spinner spinner-sm" /> Rendering formatted resume…
                      </div>
                    )}
                    {!previewLoading && previewError && (
                      <div className={styles.previewStatus} role="alert">
                        <p>{previewError}</p>
                        <button
                          type="button"
                          className="btn btn-ghost btn-sm"
                          onClick={() => setPreviewRevision((value) => value + 1)}
                        >
                          Retry preview
                        </button>
                      </div>
                    )}
                  </div>
                ) : (
                  <textarea
                    className={`form-input ${styles.draftEditor}`}
                    value={improvement.result.optimized_resume_draft}
                    onChange={(event) => updateOptimizedDraft(event.target.value)}
                    maxLength={50000}
                    aria-label="Edit complete optimized resume draft"
                  />
                )}
              </>
            ) : (
              <p className={styles.improvementEmpty}>
                Generate improvements to open the tailored draft.
              </p>
            )}
          </section>
        </aside>
      </div>
    );
  }

  return (
    <>
      {atsSection}
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
