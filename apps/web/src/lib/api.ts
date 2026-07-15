import { getAuthInstance } from "@/lib/firebase";

const API_BASE = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000"
).replace(/\/$/, "");

export interface ResumeUploadResponse {
  resume_id: string;
  title: string;
  tags: string[];
  filename: string;
  file_type: "pdf" | "docx";
  page_count: number | null;
  storage_path: string;
  character_count: number;
  text: string;
}

export interface ResumeSummary {
  resume_id: string;
  title: string;
  tags: string[];
  filename: string;
  file_type: "pdf" | "docx";
  page_count: number | null;
  character_count: number;
  created_at: string | null;
}

export interface ATSCheck {
  check_id: string;
  label: string;
  status: "pass" | "warning" | "fail";
  detail: string;
}

export interface ATSScan {
  score: number;
  checks: ATSCheck[];
  recommendations: string[];
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

export interface KeywordCoverage {
  coverage_score: number;
  covered_keywords: string[];
  missing_keywords: string[];
}

export interface BulletRewrite {
  original: string;
  suggested: string;
  reason: string;
}

export interface StructuredResumeSection {
  section_id: string;
  heading: string;
  items: string[];
}

export interface StructuredResumeDocument {
  schema_version: number;
  header: string[];
  sections: StructuredResumeSection[];
}

export interface ResumeChange {
  change_id: string;
  change_type: "summary" | "bullet" | "skill" | "section";
  status: "proposed" | "accepted" | "rejected";
  target_section: string;
  original: string;
  suggested: string;
  reason: string;
  evidence: string[];
  confidence: number;
  requires_confirmation: boolean;
}

export interface ClarificationQuestion {
  question_id: string;
  requirement: string;
  question: string;
  target_section: string;
  integration_mode: "modify_existing" | "add_new_line" | null;
  status: "unanswered" | "answered" | "skipped";
  answer: string;
}

export interface TailoringDecision {
  decision_id: string;
  content_type: "skill" | "experience_bullet" | "project" | "employment";
  source_text: string;
  action: "include" | "condense" | "omit";
  relevance: "required" | "recommended" | "supporting" | "irrelevant";
  reason: string;
  matched_requirements: string[];
}

export interface ResumeImprovementResult {
  optimized_resume_draft: string;
  suggested_summary: string;
  summary_reason: string;
  bullet_rewrites: BulletRewrite[];
  skills_to_emphasize: string[];
  ats_recommendations: string[];
  integrity_notes: string[];
  structured_resume: StructuredResumeDocument | null;
  change_set: ResumeChange[];
  clarification_questions: ClarificationQuestion[];
  tailoring_decisions: TailoringDecision[];
}

export interface ImprovementResponse {
  analysis_id: string;
  resume_id: string;
  provider: string;
  model: string;
  created_at: string | null;
  updated_at: string | null;
  company_name: string | null;
  role_name: string | null;
  application_date: string | null;
  revision: number;
  layout: ResumeLayoutSettings;
  result: ResumeImprovementResult;
}

export interface ResumeLayoutSettings {
  page_format: "a4" | "letter";
  heading_font: "sans" | "serif";
  body_font: "sans" | "serif";
  heading_size: number;
  body_size: number;
  name_size: number;
  line_spacing: number;
  margin_top: number;
  margin_right: number;
  margin_bottom: number;
  margin_left: number;
  section_spacing: number;
  heading_content_spacing: number;
  block_spacing: number;
}

export interface BulletOptimizationProposal {
  proposal_id: string;
  section_id: string;
  group_index: number;
  entry_label: string;
  item_indices: number[];
  original_bullets: string[];
  proposed_bullets: string[];
  target_count: number;
  mode: "prioritize" | "consolidate" | "expand";
  protected_keywords: string[];
  lost_keywords: string[];
  rationale: string;
  can_apply: boolean;
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

export async function uploadResume(
  file: File,
  profile: { title?: string; tags?: string[] } = {},
): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);
  if (profile.title?.trim()) formData.append("title", profile.title.trim());
  if (profile.tags?.length) formData.append("tags", profile.tags.join(","));
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

export async function scanResumeATS(
  resumeId: string,
  signal?: AbortSignal,
): Promise<ATSScan> {
  const response = await authenticatedRequest(
    `/api/v1/resumes/${encodeURIComponent(resumeId)}/ats-scan`,
    { signal },
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

export async function calculateKeywordCoverage(
  analysisId: string,
  draft: string,
  signal?: AbortSignal,
): Promise<KeywordCoverage> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/coverage`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft }),
      signal,
    },
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

export async function saveImprovementLayout(
  analysisId: string,
  layout: ResumeLayoutSettings,
): Promise<ImprovementResponse> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/improvements/layout`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ layout }),
    },
  );
  return response.json();
}

export async function proposeBulletOptimization(
  analysisId: string,
  request: {
    section_id: string;
    group_index: number;
    target_count: number;
    mode: "prioritize" | "consolidate" | "expand";
  },
): Promise<BulletOptimizationProposal> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/improvements/bullets`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(request),
    },
  );
  return response.json();
}

export async function getResumePdfPreview(
  analysisId: string,
  draft: string,
  layout: ResumeLayoutSettings,
  signal?: AbortSignal,
): Promise<{ blob: Blob; pageCount: number }> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/preview/pdf`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ draft, layout }),
      signal,
    },
  );
  return {
    blob: await response.blob(),
    pageCount: Number(response.headers.get("X-Resume-Page-Count") ?? 1),
  };
}

export async function downloadResumeExport(
  analysisId: string,
): Promise<void> {
  const response = await authenticatedRequest(
    `/api/v1/analyses/${encodeURIComponent(analysisId)}/export/pdf`,
  );
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement("a");
  link.href = url;
  const disposition = response.headers.get("Content-Disposition") ?? "";
  const filename = disposition.match(/filename="?([^";]+)"?/i)?.[1];
  link.download = filename ?? "Tailored_Resume.pdf";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
