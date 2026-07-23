"use client";

import { useEffect, useState } from "react";
import { Check, Copy, FileText, RefreshCw, X } from "lucide-react";
import { ResumeUploadResponse } from "@/lib/api";
import styles from "./ResumeResult.module.css";

interface Props {
  result: ResumeUploadResponse;
  onReset: () => void;
}

export default function ResumeResult({ result, onReset }: Props) {
  const [copied, setCopied] = useState(false);
  const [copyError, setCopyError] = useState(false);
  const [sourceOpen, setSourceOpen] = useState(false);

  useEffect(() => {
    if (!sourceOpen) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setSourceOpen(false);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [sourceOpen]);

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
      <div className={styles.header}>
        <div className={styles.identity}>
          <span className={styles.fileIcon} aria-hidden="true">
            <FileText size={18} strokeWidth={1.9} />
          </span>
          <div className={styles.fileMeta}>
            <h3 className={styles.filename}>{result.filename}</h3>
            <p>
              <span>Master resume</span>
              <span>{result.file_type.toUpperCase()}</span>
              <span className={styles.parsed}><Check size={12} /> Parsed</span>
            </p>
          </div>
        </div>

        <div className={styles.stats}>
          <div className={styles.stat}>
            <strong>{result.text.trim().split(/\s+/).length.toLocaleString()}</strong>
            <span>words</span>
          </div>
          {result.page_count !== null && (
            <div className={styles.stat}>
              <strong>{result.page_count}</strong>
              <span>{result.page_count === 1 ? "page" : "pages"}</span>
            </div>
          )}
          <div className={styles.stat}>
            <strong>{result.character_count.toLocaleString()}</strong>
            <span>characters</span>
          </div>
        </div>

        <div className={styles.actions}>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={() => setSourceOpen(true)}
          >
            <FileText size={15} />
            Source
          </button>
          <button
            id="upload-another-btn"
            onClick={onReset}
            className="btn btn-ghost btn-sm"
          >
            <RefreshCw size={15} />
            Change resume
          </button>
        </div>
      </div>

      {sourceOpen && (
        <div className={styles.modalBackdrop} onMouseDown={() => setSourceOpen(false)}>
          <section
            className={styles.sourceModal}
            role="dialog"
            aria-modal="true"
            aria-labelledby="resume-source-title"
            onMouseDown={(event) => event.stopPropagation()}
          >
            <header className={styles.modalHeader}>
              <div>
                <p>Parsed master resume</p>
                <h2 id="resume-source-title">{result.filename}</h2>
              </div>
              <button
                type="button"
                className={styles.iconButton}
                onClick={() => setSourceOpen(false)}
                aria-label="Close source text"
                title="Close"
              >
                <X size={18} />
              </button>
            </header>
            <div className={styles.textToolbar}>
              <span>{result.character_count.toLocaleString()} characters</span>
              <button
                id="copy-text-btn"
                onClick={handleCopy}
                className="btn btn-ghost btn-sm"
              >
                {copied ? <Check size={14} /> : <Copy size={14} />}
                {copied ? "Copied" : "Copy text"}
              </button>
            </div>
            <pre className={styles.textContent}>{result.text}</pre>
            {copyError && (
              <p className={styles.copyError} role="alert">
                Could not copy the text. Select it manually and try again.
              </p>
            )}
          </section>
        </div>
      )}
    </div>
  );
}
