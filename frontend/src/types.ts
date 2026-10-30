export type Health = {
  ready: boolean;
  provider?: string;
  model?: string;
  error?: string;
  profiles?: string[];
};

export type Profile = {
  id: string;
  name: string;
  region: string;
  status: string;
  disclaimer: string;
  sources: string[];
};

export type Room = {
  id: string;
  name: string | null;
  area_m2: number;
  width_mm: number;
  height_mm: number;
  wet_area: boolean;
  closed: boolean;
};

export type Shaft = {
  id: string;
  x: number;
  y: number;
  width_mm: number;
  depth_mm: number;
};

export type DesignSummary = {
  design_id: string;
  room_id?: string;
  profile_id?: string;
  layout_id?: string | null;
  status: string;
  counts?: Counts;
  approved?: boolean;
};

export type ProjectSummary = {
  project_id: string;
  name: string;
  units: string;
  designs: number;
  rooms: number;
  updated_at: number;
};

export type Project = {
  project_id: string;
  name: string;
  units: string;
  source_scale: number;
  warnings: string[];
  rooms: Room[];
  doors: { id: string; x: number; y: number; width_mm: number }[];
  shafts: Shaft[];
  designs: DesignSummary[];
  svg: string;
  created_at: number;
  updated_at: number;
};

export type Counts = {
  PASS: number;
  WARNING: number;
  ERROR: number;
};

export type Candidate = {
  id: string;
  pattern: string;
  score: number;
  violations: string[];
  rationale_hint: string;
  selected: boolean;
};

export type Issue = {
  rule_id: string;
  severity: "PASS" | "WARNING" | "ERROR";
  message: string;
  source: string;
  measured?: number | string | null;
  required?: number | string | null;
  affected?: Record<string, unknown>;
  fix_ids?: string[];
};

export type Fix = {
  id: string;
  kind: string;
  description: string;
};

export type PlanStep = {
  id: string;
  label: string;
  status: "pending" | "active" | "done" | "skipped" | "error";
};

export type Decision = {
  kind: string;
  at?: number;
  [key: string]: unknown;
};

export type Fixture = {
  id: string;
  type: string;
  position: { x: number; y: number };
  rotation_deg?: number;
};

export type Pipe = {
  id: string;
  from_node: string;
  to_node: string;
  system: string;
  diameter_mm: number;
  slope?: number | null;
  points: { x: number; y: number }[];
};

export type Design = {
  id: string;
  room_id: string;
  profile_id: string;
  layout_id?: string | null;
  fixtures: Fixture[];
  pipes: Pipe[];
  stack: { id: string; position: { x: number; y: number }; diameter_mm: number };
  rationale?: string | null;
  assumptions?: string[];
};

export type DesignState = {
  design_id: string | null;
  project_id: string;
  room_id: string | null;
  fixtures: string[];
  stack: { id: string; position: { x: number; y: number }; diameter_mm: number } | null;
  profile_id: string;
  profile_name: string;
  disclaimer: string;
  provider: string;
  model: string;
  stopped_reason?: string | null;
  final_answer: string;
  counts: Counts;
  issues: Issue[];
  fixes: Fix[];
  candidates: Candidate[];
  design: Design | null;
  validation: Issue[];
  decisions: Decision[];
  plan: PlanStep[];
  stale: boolean;
  applied_fixes: string[];
  exported_path?: string | null;
  approved: boolean;
  svg: string;
  download_url?: string | null;
  messages?: Message[];
  events?: AgentEvent[];
};

export type Message = {
  id: string;
  role: "user" | "assistant" | string;
  content: string;
  turn_id?: string | null;
  created_at?: number;
};

export type AgentEvent = {
  type: string;
  seq?: number;
  turn_id?: string | null;
  at?: number;
  [key: string]: any;
};

export type Job = {
  job_id: string;
  status: string;
  done: boolean;
  error?: string | null;
  result?: DesignState | null;
};
