import { getAuthInstance } from "@/lib/firebase";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export interface ResumeUploadResponse {
  resume_id: string;
  filename: string;
  file_type: "pdf" | "docx";
  page_count: number | null;
  storage_path: string;
  character_count: number;
  text: string;
}

export interface ResumeSummary {
  resume_id: string;
  filename: string;
  file_type: "pdf" | "docx";
  page_count: number | null;
  character_count: number;
  created_at: string | null;
}

export interface ResumeAnalysisResult {
  match_score: number;
  summary: string;
  strengths: string[];
  gaps: string[];
  matched_keywords: string[];
  missing_keywords: string[];
  recommendations: string[];
}

export interface AnalysisCreateRequest {
  resume_id: string;
  job_description: string;
  job_title?: string;
  company_name?: string;
}

export interface AnalysisCreateResponse {
  analysis_id: string;
  resume_id: string;
  status: "completed";
  provider: string;
  model: string;
  result: ResumeAnalysisResult;
}

export interface AnalysisSummary {
  analysis_id: string;
  resume_id: string;
  job_title: string | null;
  company_name: string | null;
  match_score: number;
  status: "completed";
  provider: string;
  model: string;
  created_at: string | null;
}

export interface AnalysisDetail extends AnalysisSummary {
  job_description: string;
  result: ResumeAnalysisResult;
}

export interface BulletRewrite {
  original: string;
  suggested: string;
  reason: string;
}

export interface ResumeImprovementResult {
  optimized_resume_draft: string;
  suggested_summary: string;
  summary_reason: string;
  bullet_rewrites: BulletRewrite[];
  skills_to_emphasize: string[];
  ats_recommendations: string[];
  integrity_notes: string[];
}

export interface ImprovementResponse {
  analysis_id: string;
  resume_id: string;
  provider: string;
  model: string;
  created_at: string | null;
  result: ResumeImprovementResult;
}

interface ApiErrorBody {
  detail?: string | Array<{ msg?: string }>;
  code?: string;
}

export class ApiClientError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message);
    this.name = "ApiClientError";
  }
}

async function getBearerToken(): Promise<string> {
  const user = getAuthInstance().currentUser;
  if (!user) throw new Error("Not authenticated");
  return user.getIdToken();
}

async function parseError(response: Response): Promise<ApiClientError> {
  const body = (await response.json().catch(() => null)) as ApiErrorBody | null;
  const validationMessage = Array.isArray(body?.detail)
    ? body.detail.map((item) => item.msg).filter(Boolean).join(" ")
    : body?.detail;

  return new ApiClientError(
    validationMessage || "An unexpected error occurred.",
    body?.code || `http_${response.status}`,
    response.status,
  );
}

async function authenticatedRequest(
  path: string,
  init?: RequestInit,
): Promise<Response> {
  const send = async (forceRefresh = false) => {
    const user = getAuthInstance().currentUser;
    if (!user) {
      throw new ApiClientError("Not authenticated", "missing_authentication", 401);
    }
    const token = forceRefresh ? await user.getIdToken(true) : await getBearerToken();
    return fetch(`${API_BASE}${path}`, {
      ...init,
      headers: {
        ...init?.headers,
        Authorization: `Bearer ${token}`,
      },
    });
  };

  let response = await send();
  if (response.status === 401) response = await send(true);
  if (!response.ok) throw await parseError(response);
  return response;
}

export async function checkHealth(): Promise<{ code: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/health/`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  const response = await authenticatedRequest("/api/v1/resumes/upload", {
    method: "POST",
    body: formData,
  });
  return response.json();
}

export async function listResumes(): Promise<ResumeSummary[]> {
  const response = await authenticatedRequest("/api/v1/resumes");
  return response.json();
}

export async function getResume(resumeId: string): Promise<ResumeUploadResponse> {
  const response = await authenticatedRequest(
    `/api/v1/resumes/${encodeURIComponent(resumeId)}`,
  );
  return response.json();
}

export async function deleteResume(resumeId: string): Promise<void> {
  await authenticatedRequest(
    `/api/v1/resumes/${encodeURIComponent(resumeId)}`,
    { method: "DELETE" },
  );
}

export async function createAnalysis(
  request: AnalysisCreateRequest,
): Promise<AnalysisCreateResponse> {
  const response = await authenticatedRequest("/api/v1/analyses", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
  return response.json();
}

export async function listAnalyses(resumeId?: string): Promise<AnalysisSummary[]> {
  const query = resumeId ? `?resume_id=${encodeURIComponent(resumeId)}` : "";
  const response = await authenticatedRequest(`/api/v1/analyses${query}`);
  return response.json();
}

export async function getAnalysis(analysisId: string): Promise<AnalysisDetail> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}`,
  );
  return response.json();
}

export async function deleteAnalysis(analysisId: string): Promise<void> {
  await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}`,
    { method: "DELETE" },
  );
}

export async function generateImprovements(
  analysisId: string,
  revision?: {
    current_result: ResumeImprovementResult;
    feedback: string[];
  },
): Promise<ImprovementResponse> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/improvements`,
    {
      method: "POST",
      headers: revision ? { "Content-Type": "application/json" } : undefined,
      body: revision ? JSON.stringify(revision) : undefined,
    },
  );
  return response.json();
}

export async function saveImprovements(
  analysisId: string,
  result: ResumeImprovementResult,
): Promise<ImprovementResponse> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/improvements`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ result }),
    },
  );
  return response.json();
}

export async function downloadResumeExport(
  analysisId: string,
  format: "pdf" | "docx",
  options: { mode?: "ats" | "preserve"; targetPages?: 1 | 2 } = {},
): Promise<void> {
  const query = new URLSearchParams({
    target_pages: String(options.targetPages ?? 1),
  });
  if (format === "docx") query.set("mode", options.mode ?? "ats");
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/export/${format}?${query}`,
  );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  link.download = `optimized-resume.${format}`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
