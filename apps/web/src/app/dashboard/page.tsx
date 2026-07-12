"use client";

export const dynamic = "force-dynamic";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useAuth } from "@/context/AuthContext";
import Navbar from "@/components/Navbar";
import ResumeUploader from "@/components/ResumeUploader";
import ResumeResult from "@/components/ResumeResult";
import ResumeAnalysisPanel from "@/components/ResumeAnalysisPanel";
import { ResumeUploadResponse } from "@/lib/api";
import styles from "./page.module.css";

interface HistoryEntry {
  result: ResumeUploadResponse;
  uploadedAt: string;
}

export default function DashboardPage() {
  const { user, loading } = useAuth();
  const router = useRouter();
  const [result, setResult] = useState<ResumeUploadResponse | null>(null);
  const [history, setHistory] = useState<HistoryEntry[]>([]);

  // Redirect if not authenticated
  useEffect(() => {
    if (!loading && !user) {
      router.replace("/login");
    }
  }, [user, loading, router]);

  const handleResult = (r: ResumeUploadResponse) => {
    setResult(r);
    setHistory((prev) => [
      { result: r, uploadedAt: new Date().toLocaleTimeString() },
      ...prev,
    ]);
  };

  const handleReset = () => setResult(null);

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

      <main className={styles.main}>
        <div className="container">
          {/* Header */}
          <div className={styles.pageHeader}>
            <div>
              <h1 className={styles.greeting}>
                Hey, <span className="gradient-text">{firstName}</span> 👋
              </h1>
              <p className={styles.greetingSub}>
                Upload a resume to extract and analyze its contents.
              </p>
            </div>
            {history.length > 0 && (
              <div className={styles.uploadCount}>
                <span className={styles.uploadCountNum}>{history.length}</span>
                <span className={styles.uploadCountLabel}>
                  this session
                </span>
              </div>
            )}
          </div>

          <div className={styles.layout}>
            {/* Main Content */}
            <div className={styles.mainCol}>
              {result ? (
                <>
                  <ResumeResult result={result} onReset={handleReset} />
                  <ResumeAnalysisPanel
                    key={result.resume_id}
                    resumeId={result.resume_id}
                  />
                </>
              ) : (
                <div className={`glass-card ${styles.uploaderCard}`}>
                  <div className={styles.uploaderCardHeader}>
                    <h2 className={styles.uploaderTitle}>Upload Resume</h2>
                    <p className={styles.uploaderSubtitle}>
                      Drag & drop or click to select a PDF or DOCX file
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
                <h3 className={styles.historyTitle}>Upload History</h3>
                {history.length === 0 ? (
                  <div className={styles.historyEmpty}>
                    <div className={styles.historyEmptyIcon}>📂</div>
                    <p>No uploads yet.</p>
                    <p>Upload your first resume to get started.</p>
                  </div>
                ) : (
                  <ul className={styles.historyList}>
                    {history.map((entry, i) => (
                      <li key={entry.result.resume_id} className={styles.historyItem}>
                        <button
                          id={`history-item-${i}`}
                          className={`${styles.historyBtn} ${result?.resume_id === entry.result.resume_id ? styles.historyBtnActive : ""}`}
                          onClick={() => setResult(entry.result)}
                        >
                          <div className={styles.historyItemLeft}>
                            <span className={styles.historyFileIcon}>
                              {entry.result.file_type === "pdf" ? "📄" : "📝"}
                            </span>
                            <div className={styles.historyItemMeta}>
                              <span className={styles.historyFilename}>
                                {entry.result.filename}
                              </span>
                              <span className={styles.historyTime}>
                                {entry.uploadedAt} · {entry.result.character_count.toLocaleString()} chars
                              </span>
                            </div>
                          </div>
                          <span className={`badge badge-${entry.result.file_type}`}>
                            {entry.result.file_type.toUpperCase()}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                )}
              </div>

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
