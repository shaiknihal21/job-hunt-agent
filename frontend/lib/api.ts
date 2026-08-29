const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface JobScore {
  score: number;
  skill_match: number;
  experience_match: number;
  location_match: number;
  salary_match: number;
  company_boost: number;
  reasons: string[];
  red_flags: string[];
}

export interface Job {
  id: number;
  external_id: string;
  title: string;
  company: string;
  location: string | null;
  remote: boolean;
  salary_text: string | null;
  description: string | null;
  url: string;
  source: string;
  status: string;
  score: JobScore | null;
}

export interface Profile {
  id: number;
  name: string;
  role: string;
  email: string | null;
  phone: string | null;
  location: string;
  skills: string[];
  target_roles: string[];
  preferred_locations: string[];
}

export interface Application {
  id: number;
  job_id: number;
  profile_id: number;
  resume_id: number | null;
  status: string;
  cover_letter: string | null;
  apply_url: string | null;
  notes: string | null;
  job: Job | null;
}

export interface WeeklyReport {
  period_start: string;
  period_end: string;
  total_discovered: number;
  total_applied: number;
  total_interviews: number;
  total_rejected: number;
  response_rate: number;
  top_missed_jobs: Job[];
}

async function fetchApi<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_URL}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...options?.headers },
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(text || res.statusText);
  }
  return res.json();
}

export const api = {
  getProfile: () => fetchApi<Profile>("/profile"),
  discoverJobs: () => fetchApi<{ discovered: number; ranked: number }>("/jobs/discover", { method: "POST" }),
  getJobs: (minScore?: number) => fetchApi<Job[]>(`/jobs${minScore ? `?min_score=${minScore}` : ""}`),
  getPendingApprovals: () => fetchApi<Job[]>("/approvals/queue"),
  approveJob: (jobId: number, decision: "approve" | "skip") =>
    fetchApi<{ status: string; application_id?: number; summary?: string }>(
      `/approvals/jobs/${jobId}/decide`,
      { method: "POST", body: JSON.stringify({ decision, generate_cover_letter: true }) }
    ),
  submitApplication: (appId: number) =>
    fetchApi<{ status: string }>(`/approvals/applications/${appId}/submit`, { method: "POST" }),
  getApplications: () => fetchApi<Application[]>("/applications"),
  getWeeklyReport: () => fetchApi<WeeklyReport>("/applications/report/weekly"),
  uploadResume: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${API_URL}/profile/resume`, { method: "POST", body: form });
    if (!res.ok) throw new Error(await res.text());
    return res.json();
  },
};
