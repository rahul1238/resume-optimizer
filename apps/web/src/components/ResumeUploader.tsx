"use client";

import { useState, useRef, DragEvent, ChangeEvent, KeyboardEvent } from "react";
import { ApiClientError, uploadResume, ResumeUploadResponse } from "@/lib/api";
import styles from "./ResumeUploader.module.css";

interface Props {
  onResult: (result: ResumeUploadResponse) => void;
}

const ERROR_MESSAGES: Record<string, string> = {
  unsupported_resume_format: "Only PDF and DOCX files are supported.",
  resume_too_large: "File must be under 5 MB.",
  empty_resume: "The file appears to be empty.",
  unreadable_resume: "Unable to read this file. It may be corrupted.",
  resume_text_not_found: "No readable text found in this resume.",
  resume_storage_unavailable: "Storage is temporarily unavailable. Please try again.",
  missing_authentication: "You must be signed in to upload.",
  invalid_authentication: "Your session has expired. Please sign in again.",
};

export default function ResumeUploader({ onResult }: Props) {
  const [isDragging, setIsDragging] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [tags, setTags] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File) => {
    setError(null);

    // Client-side validation
    const ext = file.name.split(".").pop()?.toLowerCase();
    if (ext !== "pdf" && ext !== "docx") {
      setError("Only PDF and DOCX files are supported.");
      return;
    }
    if (file.size > 5 * 1024 * 1024) {
      setError("File must be under 5 MB.");
      return;
    }

    setIsUploading(true);

    try {
      const result = await uploadResume(file, {
        title,
        tags: tags.split(",").map((tag) => tag.trim()).filter(Boolean),
      });
      onResult(result);
    } catch (err: unknown) {
      const msg = err instanceof ApiClientError
        ? ERROR_MESSAGES[err.code] ?? err.message
        : "Upload failed. Please try again.";
      setError(msg);
    } finally {
      setIsUploading(false);
    }
  };

  const onDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) handleFile(file);
  };

  const onDragOver = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = () => setIsDragging(false);

  const onDropzoneKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (!isUploading && (event.key === "Enter" || event.key === " ")) {
      event.preventDefault();
      inputRef.current?.click();
    }
  };

  const onInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
    e.target.value = "";
  };

  return (
    <div className={styles.wrapper}>
      <div className={styles.profileFields}>
        <label>
          <span>Resume name</span>
          <input
            className="form-input"
            value={title}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="Master full-stack resume"
            maxLength={120}
            disabled={isUploading}
          />
        </label>
        <label>
          <span>Tags <small>optional, comma separated</small></span>
          <input
            className="form-input"
            value={tags}
            onChange={(event) => setTags(event.target.value)}
            placeholder="backend, platform, senior"
            maxLength={250}
            disabled={isUploading}
          />
        </label>
      </div>
      <div
        id="resume-dropzone"
        className={`${styles.dropzone} ${isDragging ? styles.dragging : ""} ${isUploading ? styles.uploading : ""}`}
        onDrop={onDrop}
        onDragOver={onDragOver}
        onDragLeave={onDragLeave}
        onClick={() => !isUploading && inputRef.current?.click()}
        role="button"
        tabIndex={0}
        aria-label="Upload master resume"
        onKeyDown={onDropzoneKeyDown}
        aria-disabled={isUploading}
      >
        <input
          ref={inputRef}
          type="file"
          id="resume-file-input"
          accept=".pdf,.docx"
          className={styles.hiddenInput}
          onChange={onInputChange}
          disabled={isUploading}
        />

        {isUploading ? (
          <div className={styles.uploadingState}>
            <div className={styles.uploadIcon}>
              <div className="spinner spinner-lg" />
            </div>
            <p className={styles.uploadingText}>Parsing your resume…</p>
            <p className={styles.uploadingHint}>This can take a few seconds.</p>
          </div>
        ) : (
          <div className={styles.idleState}>
            <div className={styles.uploadIcon}>
              <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
                <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
                <polyline points="17 8 12 3 7 8" />
                <line x1="12" y1="3" x2="12" y2="15" />
              </svg>
            </div>
            <p className={styles.dropText}>
              <strong>Drop your master resume here</strong> or click to browse
            </p>
            <p className={styles.hint}>PDF or DOCX · Max 5 MB</p>
            <div className={styles.formats}>
              <span className="badge badge-pdf">PDF</span>
              <span className="badge badge-docx">DOCX</span>
            </div>
          </div>
        )}
      </div>

      {error && (
        <div className={`alert alert-error animate-fade-in ${styles.errorAlert}`} role="alert">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" style={{ flexShrink: 0, marginTop: 2 }}>
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="8" x2="12" y2="12" />
            <line x1="12" y1="16" x2="12.01" y2="16" />
          </svg>
          {error}
        </div>
      )}
    </div>
  );
}
