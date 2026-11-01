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

function fallbackErrorMessage(status: number) {
  if (status === 409) {
    return "That action conflicts with the assistant's current work. Wait for the current run to finish, then try again.";
  }
  if (status === 405) {
    return "That action isn't available right now. Refresh the page and try again.";
  }
  if (status >= 500) {
    return "Something went wrong on the server. Please try again.";
  }
  return `Request failed (HTTP ${status}). Please try again.`;
}

function errorMessage(status: number, detail: unknown) {
  let message = "";
  if (typeof detail === "string") {
    message = detail.trim();
  } else if (
    detail &&
    typeof detail === "object" &&
    "message" in detail &&
    typeof detail.message === "string"
  ) {
    message = detail.message.trim();
  }

  if (
    status === 409 &&
    (!message || /^(method not allowed|conflict|http 409|409)$/i.test(message))
  ) {
    return fallbackErrorMessage(status);
  }
  if (status === 405) {
    return fallbackErrorMessage(status);
  }
  return message || fallbackErrorMessage(status);
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
    const message = errorMessage(response.status, detail ?? data);
    throw new ApiError(message, response.status, detail);
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
  deleteProject: (id: string) =>
    request<void>(`/api/projects/${id}`, { method: "DELETE" }),
  upload: (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return request<Project>("/api/projects", { method: "POST", body: form });
  },
  createDesign: (
    projectId: string,
    body: {
      rooms: {
        room_id: string;
        fixtures: string[];
        stack_id?: string | null;
      }[];
      shaft_id?: string | null;
      stack?: { x: number; y: number } | null;
      profile_id: string;
    },
  ) => request<DesignState>(`/api/projects/${projectId}/designs`, json(body)),
  design: (id: string) =>
    request<DesignState>(`/api/designs/${id}`),
  deleteDesign: (id: string) =>
    request<void>(`/api/designs/${id}`, { method: "DELETE" }),
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
  updateSheet: (
    designId: string,
    body: {
      preset?: string;
      width_mm?: number;
      height_mm?: number;
      orientation?: string;
      scale?: number;
      include_riser?: boolean;
      include_schedules?: boolean;
    },
  ) =>
    request<DesignState>(`/api/designs/${designId}/sheet`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
};
