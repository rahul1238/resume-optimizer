"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Navbar from "@/components/Navbar";
import ResumeUploader from "@/components/ResumeUploader";
import ResumeResult from "@/components/ResumeResult";
import ResumeAnalysisPanel from "@/components/ResumeAnalysisPanel";
import {
  ApiClientError,
  deleteResume,
  getResume,
  listResumes,
  ResumeSummary,
  ResumeUploadResponse,
} from "@/lib/api";
import styles from "./page.module.css";

interface HistoryEntry {
  resume: ResumeSummary;
}

export default function DashboardPage() {
  const { user, loading, error: authError } = useAuth();
  const router = useRouter();
  const [result, setResult] = useState<ResumeUploadResponse | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);
  const [resumesLoading, setResumesLoading] = useState(true);
  const [resumeActionId, setResumeActionId] = useState<string | null>(null);
  const [resumeError, setResumeError] = useState<string | null>(null);

  // Redirect if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  useEffect(() => {
    if (!user) return;
    let active = true;
    listResumes()
      .then((resumes) => {
        if (active) setHistory(resumes.map((resume) => ({ resume })));
      })
      .catch((error: unknown) => {
        if (active) {
          setResumeError(
            error instanceof ApiClientError
              ? error.message
              : "Could not load saved resumes.",
          );
        }
      })
      .finally(() => {
        if (active) setResumesLoading(false);
      });
    return () => { active = false; };
  }, [user]);

  const handleResult = (r: ResumeUploadResponse) => {
    setResult(r);
    const summary: ResumeSummary = {
      resume_id: r.resume_id,
      title: r.title,
      tags: r.tags,
      filename: r.filename,
      file_type: r.file_type,
      page_count: r.page_count,
      character_count: r.character_count,
      created_at: new Date().toISOString(),
    };
    setHistory((previous) => [
      { resume: summary },
      ...previous.filter((entry) => entry.resume.resume_id !== r.resume_id),
    ]);
  };

  const handleReset = () => setResult(null);

  const handleSelectResume = async (resumeId: string) => {
    setResumeError(null);
    setResumeActionId(resumeId);
    try {
      setResult(await getResume(resumeId));
    } catch (error: unknown) {
      setResumeError(
        error instanceof ApiClientError ? error.message : "Could not load this resume.",
      );
    } finally {
      setResumeActionId(null);
    }
  };

  const handleDeleteResume = async (resume: ResumeSummary) => {
    if (!window.confirm(`Delete ${resume.filename} and all of its analyses?`)) return;
    setResumeError(null);
    setResumeActionId(resume.resume_id);
    try {
      await deleteResume(resume.resume_id);
      setHistory((previous) => previous.filter(
        (entry) => entry.resume.resume_id !== resume.resume_id,
      ));
      if (result?.resume_id === resume.resume_id) setResult(null);
    } catch (error: unknown) {
      setResumeError(
        error instanceof ApiClientError
          ? error.message
          : "Could not reach the API to delete this resume. Check that the backend is running.",
      );
    } finally {
      setResumeActionId(null);
    }
  };

  if (loading) {
    return (
      <div className={styles.loadingPage}>
        <div className="spinner spinner-lg" />
        <p>Loading…</p>
      </div>
    );
  }

  if (!user) return null;

  const firstName = user.displayName?.split(" ")[0] ?? user.email?.split("@")[0] ?? "there";

  return (
    <div className={styles.page}>
      <Navbar />

      <main className={`${styles.main} ${result ? styles.mainActive : ""}`}>
        <div className={`container ${result ? styles.workspaceContainer : ""}`}>
          {/* Header */}
          {!result && <div className={styles.pageHeader}>
            <div>
              <h1 className={styles.greeting}>
                Hey, <span className="gradient-text">{firstName}</span> 👋
              </h1>
              <p className={styles.greetingSub}>
                Select your master resume, then create a focused version for each job.
              </p>
            </div>
            {history.length > 0 && (
              <div className={styles.uploadCount}>
                <span className={styles.uploadCountNum}>{history.length}</span>
                <span className={styles.uploadCountLabel}>
                  master {history.length === 1 ? "source" : "sources"}
                </span>
              </div>
            )}
          </div>}

          <div className={`${styles.layout} ${result ? styles.layoutActive : ""}`}>
            {/* Main Content */}
            <div className={styles.mainCol}>
              {result ? (
                <>
                  <ResumeResult result={result} onReset={handleReset} />
                  <ResumeAnalysisPanel
                    key={result.resume_id}
                    resumeId={result.resume_id}
                    sourceFileType={result.file_type}
                  />
                </>
              ) : (
                <div className={`glass-card ${styles.uploaderCard}`}>
                  <div className={styles.uploaderCardHeader}>
                    <h2 className={styles.uploaderTitle}>Upload Master Resume</h2>
                    <p className={styles.uploaderSubtitle}>
                      Include every verified skill, project, and experience
                    </p>
                  </div>
                  <div className={styles.uploaderCardBody}>
                    <ResumeUploader onResult={handleResult} />
                  </div>
                </div>
              )}
            </div>

            {/* Sidebar — Upload History */}
            <aside className={styles.sidebar}>
              <div className={`glass-card ${styles.historyCard}`}>
                <h3 className={styles.historyTitle}>Master Resume Sources</h3>
                {resumesLoading ? (
                  <div className={styles.historyLoading}>
                    <span className="spinner spinner-sm" /> Loading resumes…
                  </div>
                ) : history.length === 0 ? (
                  <div className={styles.historyEmpty}>
                    <div className={styles.historyEmptyIcon}>📂</div>
                    <p>No uploads yet.</p>
                    <p>Upload your complete career resume to get started.</p>
                  </div>
                ) : (
                  <ul className={styles.historyList}>
                    {history.map((entry, i) => (
                      <li key={entry.resume.resume_id} className={styles.historyItem}>
                        <button
                          id={`history-item-${i}`}
                          className={`${styles.historyBtn} ${result?.resume_id === entry.resume.resume_id ? styles.historyBtnActive : ""}`}
                          onClick={() => handleSelectResume(entry.resume.resume_id)}
                          disabled={resumeActionId === entry.resume.resume_id}
                        >
                          <div className={styles.historyItemLeft}>
                            <span className={styles.historyFileIcon}>
                              {entry.resume.file_type === "pdf" ? "📄" : "📝"}
                            </span>
                            <div className={styles.historyItemMeta}>
                              <span className={styles.historyFilename}>
                                {entry.resume.title || entry.resume.filename}
                              </span>
                              <span className={styles.historyTime}>
                                {entry.resume.created_at
                                  ? new Date(entry.resume.created_at).toLocaleDateString()
                                  : "Saved"} · {entry.resume.character_count.toLocaleString()} chars
                              </span>
                              {entry.resume.tags.length > 0 && (
                                <span className={styles.historyTime}>
                                  {entry.resume.tags.join(" · ")}
                                </span>
                              )}
                            </div>
                          </div>
                        </button>
                        <button
                          type="button"
                          className={styles.deleteBtn}
                          onClick={() => handleDeleteResume(entry.resume)}
                          disabled={resumeActionId === entry.resume.resume_id}
                          aria-label={`Delete ${entry.resume.filename}`}
                          title="Delete resume"
                        >
                          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                            <path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5" />
                          </svg>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

              {(resumeError || authError) && (
                <div className="alert alert-error" role="alert">
                  {resumeError || authError}
                </div>
              )}

              {/* Quick Stats card (if result exists) */}
              {result && (
                <div className={`glass-card ${styles.quickStats} animate-fade-in`}>
                  <h4 className={styles.quickStatsTitle}>Current Resume</h4>
                  <div className={styles.quickStatsList}>
                    <div className={styles.quickStat}>
                      <span className={styles.quickStatLabel}>File type</span>
                      <span className={`badge badge-${result.file_type}`}>{result.file_type.toUpperCase()}</span>
                    </div>
                    {result.page_count !== null && (
                      <div className={styles.quickStat}>
                        <span className={styles.quickStatLabel}>Pages</span>
                        <span className={styles.quickStatValue}>{result.page_count}</span>
                      </div>
                    )}
                    <div className={styles.quickStat}>
                      <span className={styles.quickStatLabel}>Words</span>
                      <span className={styles.quickStatValue}>
                        {result.text.trim().split(/\s+/).length.toLocaleString()}
                      </span>
                    </div>
                    <div className={styles.quickStat}>
                      <span className={styles.quickStatLabel}>Characters</span>
                      <span className={styles.quickStatValue}>{result.character_count.toLocaleString()}</span>
                    </div>
                  </div>
                </div>
              )}
            </aside>
          </div>
        </div>
      </main>
    </div>
  );
}
