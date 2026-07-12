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

export async function checkHealth(): Promise<{ code: number; status: string }> {
  const res = await fetch(`${API_BASE}/api/v1/health/`);
  if (!res.ok) throw new Error("Health check failed");
  return res.json();
}

export async function uploadResume(file: File): Promise<ResumeUploadResponse> {
  const formData = new FormData();
  formData.append("file", file);

  const send = async (forceRefresh = false) => {
    const user = getAuthInstance().currentUser;
    if (!user) throw new ApiClientError("Not authenticated", "missing_authentication", 401);
    const token = forceRefresh ? await user.getIdToken(true) : await getBearerToken();
    return fetch(`${API_BASE}/api/v1/resumes/upload`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: formData,
    });
  };

  let res = await send();
  if (res.status === 401) res = await send(true);

  if (!res.ok) {
    throw await parseError(res);
  }

  return res.json();
}
