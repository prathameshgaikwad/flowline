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

export type PlumbingRole =
  | "bathroom"
  | "powder"
  | "kitchen"
  | "balcony"
  | "utility"
  | "wash_area"
  | "none";

export type DetectedFixture = {
  id: string;
  type: string;
  room_id?: string | null;
  x: number;
  y: number;
  width_mm: number;
  depth_mm: number;
  block_name?: string | null;
  layer?: string;
  source: string;
  confidence: number;
};

export type Room = {
  id: string;
  name: string | null;
  area_m2: number;
  width_mm: number;
  height_mm: number;
  wet_area: boolean;
  plumbing_role: PlumbingRole;
  default_fixtures: string[];
  fixture_hints: string[];
  fixtures?: DetectedFixture[];
  default_stack_id: string | null;
  closed: boolean;
};

export type Shaft = {
  id: string;
  name?: string | null;
  x: number;
  y: number;
  width_mm: number;
  depth_mm: number;
  services: string[];
  source: string;
  confidence: number;
};

export type Stack = {
  id: string;
  x: number;
  y: number;
  diameter_mm: number;
  shaft_id?: string | null;
};

export type WaterSource = {
  id: string;
  x: number;
  y: number;
  shaft_id?: string | null;
};

export type DesignSummary = {
  design_id: string;
  room_id?: string;
  room_ids?: string[];
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
  stacks: Stack[];
  water_sources: WaterSource[];
  detected_fixtures: DetectedFixture[];
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
  room_id?: string | null;
  position: { x: number; y: number };
  rotation_deg?: number;
  source?: string;
  source_fixture_id?: string | null;
};

export type Pipe = {
  id: string;
  room_id?: string | null;
  from_node: string;
  to_node: string;
  system: string;
  diameter_mm: number;
  slope?: number | null;
  points: { x: number; y: number }[];
};

export type SupplyPipe = {
  id: string;
  from_node: string;
  to_node: string;
  system: string;
  diameter_mm: number;
  material: string;
  insulated?: boolean;
  points: { x: number; y: number }[];
};

export type PlumbingItem = {
  id: string;
  type: string;
  position: { x: number; y: number };
  tag?: string | null;
  system?: string | null;
  size?: string | null;
  notes?: string | null;
};

export type SheetSpec = {
  preset: string;
  width_mm: number;
  height_mm: number;
  orientation: string;
  scale: number;
  title: string;
  sheet_number: string;
  revision: string;
  drawn_by: string;
  checked_by: string;
  include_riser: boolean;
  include_schedules: boolean;
  notes: string[];
};

export type DrawingCheck = {
  rule_id: string;
  severity: "PASS" | "WARNING" | "ERROR";
  message: string;
  affected?: Record<string, unknown>;
};

export type RoomPlan = {
  room_id: string;
  fixture_types: string[];
  layout_id: string | null;
  stack_id: string;
  water_source_id?: string | null;
  rationale: string | null;
};

export type Design = {
  id: string;
  room_id: string;
  room_ids?: string[];
  room_plans?: RoomPlan[];
  profile_id: string;
  layout_id?: string | null;
  fixtures: Fixture[];
  pipes: Pipe[];
  vent_pipes?: Pipe[];
  supply_pipes?: SupplyPipe[];
  plumbing_items?: PlumbingItem[];
  stack: { id: string; position: { x: number; y: number }; diameter_mm: number };
  stacks?: { id: string; position: { x: number; y: number }; diameter_mm: number }[];
  vent_stack?: { id: string; position: { x: number; y: number }; diameter_mm: number } | null;
  vent_stacks?: { id: string; position: { x: number; y: number }; diameter_mm: number }[];
  water_source?: {
    id: string;
    position: { x: number; y: number };
    pressure_kpa: number;
    heater: boolean;
    heater_capacity_l: number;
    material: string;
  } | null;
  water_sources?: WaterSource[];
  sheet?: SheetSpec;
  rationale?: string | null;
  assumptions?: string[];
};

export type DesignState = {
  design_id: string | null;
  project_id: string;
  room_id: string | null;
  room_ids?: string[];
  room_plans?: RoomPlan[];
  fixtures_by_room?: { room_id: string; fixtures: string[] }[];
  fixtures: string[];
  stack: { id: string; position: { x: number; y: number }; diameter_mm: number } | null;
  stacks?: { id: string; position: { x: number; y: number }; diameter_mm: number }[];
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
  vent_pipes?: Pipe[];
  supply_pipes?: SupplyPipe[];
  plumbing_items?: PlumbingItem[];
  vent_stack?: { id: string; position: { x: number; y: number }; diameter_mm: number } | null;
  water_source?: {
    id: string;
    position: { x: number; y: number };
    pressure_kpa: number;
    heater: boolean;
    heater_capacity_l: number;
    material: string;
  } | null;
  water_sources?: WaterSource[];
  sheet?: SheetSpec | null;
  drawing_review?: DrawingCheck[];
  sheet_ready?: boolean;
  sheet_pages?: number;
  sheet_svg_url?: string | null;
  sheet_pdf_url?: string | null;
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
