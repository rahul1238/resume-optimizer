"use client";

import { useState } from "react";
import { ResumeUploadResponse } from "@/lib/api";
import styles from "./ResumeResult.module.css";

interface Props {
  result: ResumeUploadResponse;
  onReset: () => void;
}

export default function ResumeResult({ result, onReset }: Props) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(result.text);
      setCopyError(false);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 2000);
    } catch {
      setCopyError(true);
    }
  };

  return (
    <div className={`${styles.wrapper} animate-slide-up`}>
      {/* Header */}
      <div className={styles.header}>
        <div className={styles.titleRow}>
          <div className={styles.fileIcon}>
            {result.file_type === "pdf" ? "📄" : "📝"}
          </div>
          <div className={styles.fileMeta}>
            <h3 className={styles.filename}>{result.filename}</h3>
            <div className={styles.badges}>
              <span className={`badge badge-${result.file_type}`}>
                {result.file_type.toUpperCase()}
              </span>
              <span className="badge badge-success">✓ Parsed</span>
            </div>
          </div>
          <button
            id="upload-another-btn"
            onClick={onReset}
            className={`btn btn-ghost btn-sm ${styles.resetBtn}`}
          >
            Upload another
          </button>
        </div>

        {/* Stats */}
        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.statValue}>{result.character_count.toLocaleString()}</span>
            <span className={styles.statLabel}>Characters</span>
          </div>
          {result.page_count !== null && (
            <div className={styles.stat}>
              <span className={styles.statValue}>{result.page_count}</span>
              <span className={styles.statLabel}>{result.page_count === 1 ? "Page" : "Pages"}</span>
            </div>
          )}
          <div className={styles.stat}>
            <span className={styles.statValue}>
              {result.text.trim().split(/\s+/).length.toLocaleString()}
            </span>
            <span className={styles.statLabel}>Words</span>
          </div>
          <div className={`${styles.stat} ${styles.idStat}`}>
            <span className={styles.statValue} title={result.resume_id}>
              {result.resume_id.slice(0, 8)}…
            </span>
            <span className={styles.statLabel}>Resume ID</span>
          </div>
        </div>
      </div>

      {/* Extracted Text */}
      <div className={styles.textSection}>
        <div className={styles.textHeader}>
          <h4 className={styles.textTitle}>Extracted Text</h4>
          <button
            id="copy-text-btn"
            onClick={handleCopy}
            className={`btn btn-ghost btn-sm ${styles.copyBtn}`}
          >
            {copied ? (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
                  <polyline points="20 6 9 17 4 12" />
                </svg>
                Copied!
              </>
            ) : (
              <>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                </svg>
                Copy text
              </>
            )}
          </button>
        </div>
        <pre className={styles.textContent}>{result.text}</pre>
        {copyError && (
          <p className={styles.copyError} role="alert">
            Could not copy the text. Select it manually and try again.
          </p>
        )}
      </div>
    </div>
  );
}
