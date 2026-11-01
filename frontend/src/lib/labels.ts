import type { Counts, DesignState, Project, SheetSpec } from "../types";

export type Tone = "neutral" | "accent" | "success" | "warning" | "danger";

const stepLabels: Record<string, string> = {
  inspect: "Reading the drawing",
  layouts: "Exploring layout options",
  select: "Choosing the best fit",
  route: "Routing the drains",
  services: "Routing water and vent",
  sheet: "Preparing the sheet",
  validate: "Checking against code",
  fix: "Tidying up the details",
  explain: "Writing up the result",
};

export function humanStep(id: string, fallback: string) {
  return stepLabels[id] || fallback;
}

const toolLabels: Record<string, string> = {
  inspect_plan: "Read the drawing",
  list_layout_options: "Explored layout options",
  plan_room_layouts: "Planned room layouts",
  select_layout: "Chose a layout",
  route_drainage: "Routed the drains",
  route_services: "Routed water and vents",
  prepare_sheet: "Prepared the sheet",
  set_sheet_options: "Updated the sheet",
  review_drawing: "Reviewed the drawing",
  validate_design: "Ran a code check",
  apply_fix: "Applied a fix",
  set_fixtures: "Updated the fixtures",
  compare_layouts: "Compared layouts",
  get_design_state: "Read the design state",
  explain_design: "Wrote the summary",
  export_dxf: "Exported the DXF",
};

export function humanTool(name: string) {
  return toolLabels[name] || name.replaceAll("_", " ");
}

export function toolSummary(name: string, output?: Record<string, any>): string {
  if (!output) return "Working…";
  if (output.error) return String(output.error);
  if (name === "inspect_plan")
    return `${plural(output.rooms?.length ?? 0, "room")} · ${plural(
      output.shafts?.length ?? 0,
      "shaft",
    )}`;
  if (name === "list_layout_options")
    return plural(output.count ?? 0, "layout option");
  if (name === "select_layout")
    return `${output.layout_id ?? "layout"} · ${output.pattern ?? ""}`;
  if (name === "route_drainage")
    return plural(output.count ?? 0, "branch pipe");
  if (name === "route_services") return "Water, vent, and equipment routed";
  if (name === "prepare_sheet") return "Construction sheet ready";
  if (name === "set_sheet_options") return "Sheet settings updated";
  if (name === "review_drawing") {
    const counts = output.counts || {};
    return `${plural(counts.ERROR ?? 0, "error")} · ${plural(
      counts.WARNING ?? 0,
      "warning",
    )}`;
  }
  if (name === "validate_design" || name === "apply_fix") {
    const counts = output.counts || {};
    return `${counts.PASS ?? 0} passed · ${plural(
      counts.WARNING ?? 0,
      "warning",
    )} · ${plural(counts.ERROR ?? 0, "error")}`;
  }
  if (name === "compare_layouts")
    return `${plural(output.candidates?.length ?? 0, "layout")} compared`;
  if (name === "get_design_state") return "Design state";
  if (name === "set_fixtures")
    return `${output.fixtures?.join(", ") ?? "fixtures"} selected`;
  if (name === "explain_design") return "Summary ready";
  return "Done";
}

export function displayIssues(design: DesignState | null) {
  return (design?.issues || []).filter(
    (issue) => issue.rule_id !== "PROFILE_STATUS",
  );
}

export function displayCounts(design: DesignState | null): Counts {
  const issues = displayIssues(design);
  return {
    PASS: design?.counts?.PASS || 0,
    WARNING: issues.filter((issue) => issue.severity === "WARNING").length,
    ERROR: issues.filter((issue) => issue.severity === "ERROR").length,
  };
}

export function designStatus(design: DesignState | null, busy: boolean): {
  label: string;
  tone: Tone;
  pulse: boolean;
} {
  if (busy) return { label: "Designing…", tone: "accent", pulse: true };
  if (!design?.design)
    return {
      label: design?.design_id ? "No layout" : "Setup",
      tone: design?.design_id ? "warning" : "neutral",
      pulse: false,
    };
  if (design.approved)
    return { label: "Approved", tone: "success", pulse: false };
  if (design.stale)
    return { label: "Recheck needed", tone: "warning", pulse: false };
  const counts = displayCounts(design);
  if (counts.ERROR > 0)
    return {
      label: `Needs fixes · ${counts.ERROR}`,
      tone: "danger",
      pulse: false,
    };
  if (counts.WARNING > 0)
    return {
      label: `${counts.WARNING} ${
        counts.WARNING === 1 ? "warning" : "warnings"
      }`,
      tone: "warning",
      pulse: false,
    };
  if (design.validation?.length)
    return { label: "Ready to review", tone: "success", pulse: false };
  return { label: "Needs checks", tone: "neutral", pulse: false };
}

export function summaryStatusLabel(status: string) {
  switch (status) {
    case "approved":
      return "Approved";
    case "validated":
      return "Ready";
    case "drafted":
      return "Draft";
    case "needs_fix":
      return "Needs a fix";
    case "stale":
      return "Recheck needed";
    case "setup":
      return "Setup";
    case "missing":
      return "Missing";
    default:
      return status.replaceAll("_", " ");
  }
}

export function summaryStatusTone(status: string): Tone {
  switch (status) {
    case "approved":
    case "validated":
      return "success";
    case "needs_fix":
      return "danger";
    case "stale":
      return "warning";
    case "drafted":
      return "accent";
    default:
      return "neutral";
  }
}

export function plumbingRoleLabel(role: string | null | undefined) {
  return (
    {
      bathroom: "Bathroom",
      powder: "Toilet / powder",
      kitchen: "Kitchen",
      balcony: "Balcony",
      utility: "Utility",
      wash_area: "Wash area",
      none: "Other room",
    }[role || "none"] || "Room"
  );
}

export function roomNameFor(project: Project | null, roomId?: string | null) {
  if (!project || !roomId) return "Bathroom";
  const room = project.rooms.find((item) => item.id === roomId);
  return room?.name || `Room ${roomId.replace(/^R-?/i, "")}`;
}

export function plumbingAreasLabel(
  project: Project | null,
  roomIds: string[] | null | undefined,
) {
  const ids = roomIds?.filter(Boolean) || [];
  if (!ids.length) return "Plumbing design";
  const names = ids.map((roomId) => roomNameFor(project, roomId));
  if (names.length === 1) return names[0];
  if (names.length === 2) return `${names[0]} + ${names[1]}`;
  return `${names.length} plumbing areas`;
}

export function drawingName(project: Project) {
  const base = project.name.replace(/\.dxf$/i, "").replaceAll("_", " ");
  return base.charAt(0).toUpperCase() + base.slice(1);
}

export function selectedLayout(design: DesignState | null) {
  if (!design) return null;
  return (
    design.candidates.find((candidate) => candidate.selected) ||
    design.candidates[0] ||
    null
  );
}

export function countsText(counts: Counts | undefined) {
  if (!counts) return "No checks yet";
  return `${counts.PASS} passed · ${counts.WARNING} warnings · ${counts.ERROR} errors`;
}

export function plural(count: number, singular: string, pluralForm?: string) {
  return `${count} ${count === 1 ? singular : pluralForm || `${singular}s`}`;
}

const fixtureNames: Record<string, string> = {
  WC: "Toilet",
  BASIN: "Basin",
  SHOWER: "Shower",
  FLOOR_DRAIN: "Floor drain",
  KITCHEN_SINK: "Kitchen sink",
};

export function fixtureName(type: string) {
  return fixtureNames[type] || type.replaceAll("_", " ").toLowerCase();
}

export function friendlyProfileName(name?: string | null) {
  if (!name) return "";
  return name.replace(/\s*\(POC\)\s*/i, "").trim();
}

export function compactProfileName(name?: string | null) {
  const friendly = friendlyProfileName(name);
  if (!friendly) return "";
  return friendly
    .replace("India - ", "India · ")
    .replace(" / IS 1742", "")
    .replace("US - ", "US · ");
}

export function drawingCounts(design: DesignState | null): Counts {
  const checks = design?.drawing_review || [];
  return {
    PASS: checks.filter((check) => check.severity === "PASS").length,
    WARNING: checks.filter((check) => check.severity === "WARNING").length,
    ERROR: checks.filter((check) => check.severity === "ERROR").length,
  };
}

export function sheetSizeLabel(sheet?: SheetSpec | null) {
  if (!sheet) return "No sheet";
  const preset = sheet.preset === "CUSTOM" ? "Custom" : sheet.preset.replace("ANSI_", "ANSI ");
  return `${preset} ${sheet.orientation}`;
}
