export const API = process.env.NEXT_PUBLIC_API_URL ?? 'http://localhost:3001';

export const STATUSES = ['saved', 'applied', 'interview', 'offer', 'rejected'] as const;
export type Status = (typeof STATUSES)[number];

export const STATUS_LABEL: Record<Status, string> = {
  saved: 'Saved',
  applied: 'Applied',
  interview: 'Interview',
  offer: 'Offer',
  rejected: 'Rejected',
};

export interface Application {
  id: string;
  company: string;
  title: string;
  status: Status;
  jobDescription: string | null;
  notes: string | null;
  url: string | null;
  createdAt: string;
  updatedAt: string;
}

export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}

// MVP choice: the JWT lives in localStorage. It is simple, but readable by any
// script on the page. Before a public launch, consider httpOnly cookies.
const TOKEN_KEY = 'jt_token';
export const getToken = () => (typeof window === 'undefined' ? null : window.localStorage.getItem(TOKEN_KEY));
export const setToken = (t: string) => window.localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => window.localStorage.removeItem(TOKEN_KEY);

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const isForm = typeof FormData !== 'undefined' && init.body instanceof FormData;
  let res: Response;
  try {
    res = await fetch(`${API}${path}`, {
      ...init,
      headers: {
        ...(isForm ? {} : { 'Content-Type': 'application/json' }),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...init.headers,
      },
    });
  } catch {
    throw new ApiError('Cannot reach the server. Is the backend running?', 0);
  }

  if (!res.ok) {
    let message = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      message = Array.isArray(body.message) ? body.message.join(', ') : (body.message ?? message);
    } catch {
      /* keep default message */
    }
    throw new ApiError(message, res.status);
  }
  return res.json() as Promise<T>;
}

type Credentials = { email: string; password: string };

export const register = (c: Credentials) =>
  request<{ accessToken: string }>('/auth/register', { method: 'POST', body: JSON.stringify(c) });

export const login = (c: Credentials) =>
  request<{ accessToken: string }>('/auth/login', { method: 'POST', body: JSON.stringify(c) });

export const listApplications = () => request<Application[]>('/applications');

export const createApplication = (data: { company: string; title: string; jobDescription?: string }) =>
  request<Application>('/applications', { method: 'POST', body: JSON.stringify(data) });

export const updateApplication = (id: string, data: Partial<Pick<Application, 'status' | 'company' | 'title' | 'notes' | 'jobDescription'>>) =>
  request<Application>(`/applications/${id}`, { method: 'PATCH', body: JSON.stringify(data) });

export const deleteApplication = (id: string) => request<{ deleted: boolean }>(`/applications/${id}`, { method: 'DELETE' });

export interface Resume {
  id: string;
  filename: string;
  charCount: number;
  preview: string;
  createdAt: string;
}

export const MAX_UPLOAD_MB = 4;

export const listResumes = () => request<Resume[]>('/resumes');

export const uploadResume = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return request<Resume>('/resumes', { method: 'POST', body: form });
};

export const deleteResume = (id: string) => request<{ deleted: boolean }>(`/resumes/${id}`, { method: 'DELETE' });

export interface Evidence {
  line: string;
  line_number: number;
}

export type MatcherChoice = 'keyword' | 'tfidf' | 'llm';

export interface RequirementResult {
  requirement: string;
  supported: boolean;
  evidence: Evidence[];
  importance?: 'required' | 'preferred' | null; // TF-IDF and AI matchers
  note?: string | null; // TF-IDF: how it matched. AI: written by the model, not verified
}

export interface MatchResult {
  id: string;
  applicationId: string;
  resumeId: string | null;
  resumeFilename: string;
  matcher: string;
  score: number;
  result: {
    requirements: RequirementResult[];
    missing: string[];
    meta?: { ungrounded?: number | null; usage?: Record<string, number> | null; docSimilarity?: number | null };
  };
  createdAt: string;
}

export const runMatch = (applicationId: string, resumeId: string, matcher: MatcherChoice = 'keyword') =>
  request<MatchResult>(`/applications/${applicationId}/matches`, {
    method: 'POST',
    body: JSON.stringify({ resumeId, matcher }),
  });

export const listMatches = (applicationId: string) => request<MatchResult[]>(`/applications/${applicationId}/matches`);
