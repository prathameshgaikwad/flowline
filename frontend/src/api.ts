import type {
  DesignState,
  Health,
  Job,
  Profile,
  Project,
  ProjectSummary,
} from "./types";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(message: string, status: number, detail: unknown) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, options);
  const text = await response.text();
  let data: any = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!response.ok) {
    const detail = data.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail?.message || JSON.stringify(detail || data);
    throw new ApiError(message || `HTTP ${response.status}`, response.status, detail);
  }
  return data as T;
}

const json = (body: unknown): RequestInit => ({
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request<Health>("/api/health"),
  profiles: () => request<{ profiles: Profile[] }>("/api/profiles"),
  projects: () => request<{ projects: ProjectSummary[] }>("/api/projects"),
  sample: (name = "apartment") =>
    request<Project>(`/api/projects/sample?name=${name}`, { method: "POST" }),
  project: (id: string) => request<Project>(`/api/projects/${id}`),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Project>("/api/projects", { method: "POST", body: form });
  },
  createDesign: (
    projectId: string,
    body: {
      room_id: string;
      fixtures: string[];
      shaft_id?: string | null;
      profile_id: string;
    },
  ) => request<DesignState>(`/api/projects/${projectId}/designs`, json(body)),
  design: (id: string) =>
    request<DesignState>(`/api/designs/${id}`),
  sendMessage: (id: string, content: string) =>
    request<{ job_id: string; design_id: string; provider: string; model: string }>(
      `/api/designs/${id}/messages`,
      json({ content }),
    ),
  job: (id: string) => request<Job>(`/api/jobs/${id}`),
  fix: (designId: string, fixId: string) =>
    request<DesignState>(`/api/designs/${designId}/fix`, json({ fix_id: fixId })),
  approve: (designId: string, approver_name: string) =>
    request<DesignState>(
      `/api/designs/${designId}/approve`,
      json({ approver_name }),
    ),
  setProfile: (designId: string, profile_id: string) =>
    request<DesignState>(`/api/designs/${designId}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ profile_id }),
    }),
};
