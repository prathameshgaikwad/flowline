import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";
import { CheckCircle2, TriangleAlert, X } from "lucide-react";
import { api } from "./api";
import type {
  AgentEvent,
  DesignState,
  DesignSummary,
  Message,
  Profile,
  Project,
  ProjectSummary,
} from "./types";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { ChatPanel } from "./components/ChatPanel";
import { DesignCanvas } from "./components/DesignCanvas";
import { DeleteDesignDialog } from "./components/DeleteDesignDialog";
import { DeleteProjectDialog } from "./components/DeleteProjectDialog";
import { DetailsDrawer } from "./components/DetailsDrawer";
import type { DetailsTab } from "./components/DetailsDrawer";
import { FullscreenPlan } from "./components/FullscreenPlan";
import { HomePage } from "./components/HomePage";
import { Logo } from "./components/Logo";
import { NewDesignPanel } from "./components/NewDesignPanel";
import type { SetupRoomSelection } from "./components/RoomSelectionList";
import { SheetCanvas } from "./components/SheetCanvas";
import type { SheetUpdate } from "./components/SheetCanvas";
import { StartScreen } from "./components/StartScreen";
import { StatusPill } from "./components/StatusPill";
import { StudioHeader } from "./components/StudioHeader";
import {
  cx,
  SegmentedControl,
  Skeleton,
} from "./components/ui";
import { designStatus } from "./lib/labels";
import { useSplitPane } from "./hooks/useSplitPane";

type Toast = { id: number; message: string; error?: boolean } | null;

const DEFAULT_PROFILE = "india_nbc_2016";
const CHECK_PROMPT =
  "Validate the current design against the active standard. Do not change the layout.";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [provider, setProvider] = useState<{ name: string; model: string } | null>(
    null,
  );
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [projects, setProjects] = useState<ProjectSummary[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [design, setDesign] = useState<DesignState | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const [setupRooms, setSetupRooms] = useState<SetupRoomSelection[]>([]);
  const [activeSetupRoomId, setActiveSetupRoomId] = useState<string | null>(
    null,
  );
  const [setupStack, setSetupStack] = useState<{ x: number; y: number } | null>(
    null,
  );
  const [pickingStack, setPickingStack] = useState(false);
  const [setupProfile, setSetupProfile] = useState(DEFAULT_PROFILE);
  const [canvasView, setCanvasView] = useState<"design" | "source" | "sheet">("source");
  const [sheetPage, setSheetPage] = useState(1);
  const [sheetSvg, setSheetSvg] = useState<string | null>(null);
  const [sheetLoading, setSheetLoading] = useState(false);
  const [sheetError, setSheetError] = useState<string | null>(null);
  const [sheetRetry, setSheetRetry] = useState(0);
  const [sheetUpdating, setSheetUpdating] = useState(false);
  const [mobilePane, setMobilePane] = useState<"plan" | "assistant">("plan");
  const [approvalOpen, setApprovalOpen] = useState(false);
  const [blankWorkspace, setBlankWorkspace] = useState(false);
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [detailsTab, setDetailsTab] = useState<DetailsTab>("design");
  const [fullscreen, setFullscreen] = useState(false);
  const [deleteDesignTarget, setDeleteDesignTarget] =
    useState<DesignSummary | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [deleteProjectTarget, setDeleteProjectTarget] =
    useState<ProjectSummary | null>(null);
  const [deleteProjectBusy, setDeleteProjectBusy] = useState(false);
  const [deleteProjectError, setDeleteProjectError] =
    useState<string | null>(null);
  const [view, setView] = useState<"workspace" | "home">("workspace");
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);
  const toastRef = useRef<number | null>(null);
  const mountedRef = useRef(true);
  const autoViewRef = useRef<string | null>(null);
  const splitContainerRef = useRef<HTMLDivElement>(null);
  const split = useSplitPane(splitContainerRef);

  function showToast(message: string, error = false) {
    setToast({ id: Date.now(), message, error });
    if (toastRef.current) window.clearTimeout(toastRef.current);
    toastRef.current = window.setTimeout(() => setToast(null), 4200);
  }

  function focusWorkspaceTrigger() {
    window.requestAnimationFrame(() => {
      document
        .querySelector<HTMLElement>('[data-testid="workspace-trigger"]')
        ?.focus();
    });
  }

  function focusHomeMain() {
    window.requestAnimationFrame(() => {
      document.querySelector<HTMLElement>("#home-main")?.focus();
    });
  }

  function handleOpenHome() {
    setBlankWorkspace(false);
    setApprovalOpen(false);
    setDetailsOpen(false);
    setFullscreen(false);
    setDeleteDesignTarget(null);
    setDeleteError(null);
    setDeleteProjectTarget(null);
    setDeleteProjectError(null);
    setView("home");
  }

  function handleResumeWorkspace() {
    setView("workspace");
    if (project && !design && project.designs.length) {
      void loadDesignById(project.designs.at(-1)!.design_id, false);
    }
  }

  function closeStreams() {
    esRef.current?.close();
    esRef.current = null;
    if (pollRef.current) {
      window.clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  function setupRoomDraft(
    current: Project,
    roomId: string,
  ): SetupRoomSelection {
    const room = current.rooms.find((item) => item.id === roomId);
    return {
      roomId,
      fixtures: [...(room?.default_fixtures || [])],
      stackId:
        room?.default_stack_id || current.stacks[0]?.id || "",
    };
  }

  function defaultSetupRooms(current: Project) {
    return current.rooms
      .filter((room) => room.plumbing_role !== "none")
      .map((room) => setupRoomDraft(current, room.id));
  }

  function resetSetup(current: Project, profileId = DEFAULT_PROFILE) {
    const rooms = defaultSetupRooms(current);
    setSetupRooms(rooms);
    setActiveSetupRoomId(rooms[0]?.roomId || null);
    setSetupStack(null);
    setPickingStack(false);
    setSetupProfile(profileId);
    setDesign(null);
    setMessages([]);
    setEvents([]);
    setBusy(false);
    setCanvasView("source");
    setSheetPage(1);
    setSheetSvg(null);
    setSheetLoading(false);
    setSheetError(null);
    setSheetRetry(0);
    setMobilePane("assistant");
    setApprovalOpen(false);
    setBlankWorkspace(false);
    setDetailsOpen(false);
    setFullscreen(false);
    setDeleteDesignTarget(null);
    setDeleteBusy(false);
    setDeleteError(null);
    autoViewRef.current = null;
    closeStreams();
  }

  async function refreshProjects() {
    try {
      const list = await api.projects();
      if (mountedRef.current) setProjects(list.projects);
    } catch {
      // The workspace still works with the current project.
    }
  }

  async function refreshProject(projectId?: string) {
    const id = projectId || project?.project_id;
    if (!id) return;
    try {
      const current = await api.project(id);
      if (mountedRef.current) setProject(current);
    } catch {
      // Keep the current view; the next action will surface the error.
    }
  }

  async function loadDesignById(id: string, surfaceError = true) {
    let data: DesignState;
    try {
      data = await api.design(id);
    } catch (error) {
      if (surfaceError) showToast((error as Error).message, true);
      setDesign(null);
      return;
    }
    if (!mountedRef.current) return;
    setDesign(data);
    setMessages(data.messages || []);
    setEvents(data.events || []);
    setCanvasView(data.design ? "design" : "source");
    setSheetPage(1);
    setSheetSvg(null);
    setSheetError(null);
    setMobilePane("plan");
    autoViewRef.current = data.design ? data.design_id : null;
    const loadedRooms: SetupRoomSelection[] =
      data.room_plans?.map((plan) => ({
        roomId: plan.room_id,
        fixtures: plan.fixture_types,
        stackId: plan.stack_id,
      })) ||
      data.fixtures_by_room?.map((item) => ({
        roomId: item.room_id,
        fixtures: item.fixtures,
        stackId: data.stack?.id || "",
      })) ||
      (data.room_id
        ? [
            {
              roomId: data.room_id,
              fixtures: data.fixtures,
              stackId: data.stack?.id || "",
            },
          ]
        : []);
    setSetupRooms(loadedRooms);
    setActiveSetupRoomId(loadedRooms[0]?.roomId || null);
    setSetupStack(null);
    setPickingStack(false);
    setSetupProfile(data.profile_id);
    setBlankWorkspace(false);
    setDetailsOpen(false);
    setFullscreen(false);
    if (data.provider) setProvider({ name: data.provider, model: data.model });
    await refreshProject(data.project_id);
  }

  async function refreshDesign(id: string) {
    try {
      const data = await api.design(id);
      if (!mountedRef.current) return;
      setDesign(data);
      setMessages(data.messages || []);
      setEvents(data.events || []);
      if (data.provider) setProvider({ name: data.provider, model: data.model });
    } catch (error) {
      showToast((error as Error).message, true);
    }
  }

  async function refreshDesignState(id: string) {
    try {
      const data = await api.design(id);
      if (!mountedRef.current) return;
      setDesign(data);
      if (data.provider) setProvider({ name: data.provider, model: data.model });
      const current = await api.project(data.project_id);
      if (mountedRef.current) setProject(current);
    } catch {
      // The final snapshot will correct the state if this fetch races the turn.
    }
  }

  function schedulePoll(jobId: string, designId: string) {
    if (pollRef.current) window.clearTimeout(pollRef.current);
    pollRef.current = window.setTimeout(async () => {
      try {
        const job = await api.job(jobId);
        if (!mountedRef.current) return;
        if (job.done) {
          if (job.result) {
            setDesign(job.result);
            if (job.result.provider) {
              setProvider({
                name: job.result.provider,
                model: job.result.model,
              });
            }
            setBusy(false);
            await refreshDesign(designId);
            await refreshProject();
          } else {
            setBusy(false);
            showToast(job.error || "The assistant stopped.", true);
          }
          closeStreams();
        } else {
          schedulePoll(jobId, designId);
        }
      } catch (error) {
        setBusy(false);
        showToast((error as Error).message, true);
      }
    }, 1200);
  }

  function subscribe(jobId: string, designId: string) {
    closeStreams();
    const source = new EventSource(`/api/jobs/${jobId}/events`);
    esRef.current = source;
    source.onmessage = (message) => {
      let event: AgentEvent;
      try {
        event = JSON.parse(message.data);
      } catch {
        return;
      }
      if (!mountedRef.current) return;
      if (event.type === "snapshot") {
        setDesign(event as unknown as DesignState);
        if (event.provider) {
          setProvider({
            name: String(event.provider),
            model: String(event.model || ""),
          });
        }
        setBusy(false);
        closeStreams();
        void refreshDesign(designId);
        void refreshProject();
        return;
      }
      setEvents((previous) => {
        if (event.seq && previous.some((item) => item.seq === event.seq)) {
          return previous;
        }
        return [...previous, event];
      });
      if (
        event.type === "tool_result" &&
        [
          "select_layout",
          "route_drainage",
          "route_services",
          "prepare_sheet",
          "set_sheet_options",
          "review_drawing",
          "validate_design",
          "apply_fix",
        ].includes(String(event.tool))
      ) {
        void refreshDesignState(designId);
      }
      if (event.type === "error") {
        setBusy(false);
        showToast(String(event.message || "Assistant error."), true);
        closeStreams();
      }
    };
    source.onerror = () => {
      source.close();
      schedulePoll(jobId, designId);
    };
  }

  async function sendToDesign(designId: string, content: string) {
    if (busy) return;
    setBusy(true);
    closeStreams();
    try {
      const started = await api.sendMessage(designId, content);
      if (!mountedRef.current) return;
      setMessages((previous) => [
        ...previous,
        {
          id: `local-${started.job_id}`,
          role: "user",
          content,
          turn_id: started.job_id,
        },
      ]);
      setProvider({ name: started.provider, model: started.model });
      subscribe(started.job_id, designId);
    } catch (error) {
      setBusy(false);
      showToast((error as Error).message, true);
    }
  }

  async function boot() {
    try {
      let health = null;
      try {
        health = await api.health();
        if (health.ready && health.provider) {
          setProvider({ name: health.provider, model: health.model || "" });
        }
      } catch (error) {
        showToast((error as Error).message, true);
      }
      let loadedProfiles: Profile[] = [];
      try {
        const response = await api.profiles();
        loadedProfiles = response.profiles || [];
        setProfiles(loadedProfiles);
      } catch {
        // The setup still works with the default profile id.
      }
      const list = await api.projects();
      setProjects(list.projects);
      let current: Project;
      if (!list.projects.length) {
        current = await api.sample();
        await refreshProjects();
      } else {
        current = await api.project(list.projects[0].project_id);
      }
      if (!mountedRef.current) return;
      setProject(current);
      const profileId =
        loadedProfiles[0]?.id || current.designs[0]?.profile_id || DEFAULT_PROFILE;
      resetSetup(current, profileId);
      const latest = current.designs.at(-1);
      if (latest) {
        await loadDesignById(latest.design_id, false);
      }
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      if (mountedRef.current) setLoading(false);
    }
  }

  useEffect(() => {
    mountedRef.current = true;
    void boot();
    return () => {
      mountedRef.current = false;
      closeStreams();
      if (toastRef.current) window.clearTimeout(toastRef.current);
    };
    // Bootstrap once.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (
      design?.design &&
      design.design_id &&
      autoViewRef.current !== design.design_id
    ) {
      autoViewRef.current = design.design_id;
      setCanvasView("design");
    }
  }, [design?.design, design?.design_id]);

  useEffect(() => {
    if (canvasView === "sheet" && !design?.sheet_ready) {
      setCanvasView(design ? "design" : "source");
    }
  }, [canvasView, design]);

  useEffect(() => {
    if (
      canvasView !== "sheet" ||
      !design?.design_id ||
      !design.sheet_ready
    ) {
      setSheetSvg(null);
      return;
    }
    let cancelled = false;
    setSheetLoading(true);
    setSheetError(null);
    fetch(`/api/designs/${design.design_id}/sheet.svg?page=${sheetPage}`)
      .then(async (response) => {
        if (!response.ok) {
          throw new Error((await response.text()) || `HTTP ${response.status}`);
        }
        return response.text();
      })
      .then((text) => {
        if (!cancelled) setSheetSvg(text);
      })
      .catch((error: Error) => {
        if (!cancelled) {
          const message =
            error instanceof TypeError ||
            /failed to fetch|networkerror/i.test(error.message)
              ? "The sheet preview could not be loaded. Try again."
              : error.message || "Could not render the sheet.";
          setSheetError(message);
        }
      })
      .finally(() => {
        if (!cancelled) setSheetLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [
    canvasView,
    design?.design_id,
    design?.sheet_ready,
    design?.sheet?.preset,
    design?.sheet?.orientation,
    design?.sheet?.scale,
    design?.sheet?.width_mm,
    design?.sheet?.height_mm,
    sheetPage,
    sheetRetry,
  ]);

  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      const target = event.target;
      if (
        !(target instanceof HTMLElement) ||
        target.closest("input, textarea, select, [contenteditable='true']")
      ) {
        return;
      }
      if (
        event.key.toLowerCase() === "f" &&
        !event.metaKey &&
        !event.ctrlKey &&
        !event.altKey &&
        !fullscreen &&
        !detailsOpen &&
        !approvalOpen &&
        !deleteDesignTarget &&
        view === "workspace"
      ) {
        event.preventDefault();
        setFullscreen(true);
      }
    }
    window.addEventListener("keydown", handleShortcut);
    return () => window.removeEventListener("keydown", handleShortcut);
  }, [approvalOpen, deleteDesignTarget, detailsOpen, fullscreen, view]);

  useEffect(() => {
    document.title =
      view === "home"
        ? "Flowline — Drawing library"
        : "Flowline — Bathroom design studio";
    if (view === "workspace") {
      window.requestAnimationFrame(() => {
        splitContainerRef.current?.focus({ preventScroll: true });
      });
    }
  }, [view]);

  function handleViewSheet() {
    if (!design?.sheet_ready) {
      showToast("Prepare the sheet first.", true);
      return;
    }
    setSheetPage(1);
    setCanvasView("sheet");
    setMobilePane("plan");
    setDetailsOpen(false);
    setFullscreen(false);
  }

  async function handleUpdateSheet(body: SheetUpdate) {
    if (!design?.design_id || sheetUpdating) return;
    setSheetUpdating(true);
    try {
      const updated = await api.updateSheet(design.design_id, body);
      setDesign(updated);
      setSheetPage(1);
      setSheetSvg(null);
      showToast("Sheet updated.");
      await refreshProject();
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setSheetUpdating(false);
    }
  }

  async function handleUpload(file: File) {
    if (busy) return;
    setBusy(true);
    try {
      const current = await api.upload(file);
      if (!mountedRef.current) return;
      setProject(current);
      resetSetup(current, profiles[0]?.id || DEFAULT_PROFILE);
      setView("workspace");
      await refreshProjects();
      showToast("Drawing loaded.");
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function handleSample() {
    if (busy) return;
    setBusy(true);
    try {
      const current = await api.sample();
      if (!mountedRef.current) return;
      setProject(current);
      resetSetup(current, profiles[0]?.id || DEFAULT_PROFILE);
      setView("workspace");
      await refreshProjects();
      showToast("Sample apartment loaded.");
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function handleOpenProject(id: string) {
    if (busy) return;
    try {
      const current = await api.project(id);
      if (!mountedRef.current) return;
      setProject(current);
      setBlankWorkspace(false);
      setView("workspace");
      resetSetup(current, current.designs[0]?.profile_id || DEFAULT_PROFILE);
      setBusy(true);
      const latest = current.designs.at(-1);
      if (latest) await loadDesignById(latest.design_id, false);
      await refreshProjects();
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function handleNewDesign() {
    if (!project) return;
    if (busy) {
      showToast("Wait for the current run to finish.", true);
      return;
    }
    closeStreams();
    resetSetup(project, setupProfile);
    setView("workspace");
    setBlankWorkspace(true);
    setDesign(null);
    setMessages([]);
    setEvents([]);
    setBusy(false);
    setCanvasView("source");
    setSheetPage(1);
    setSheetSvg(null);
    setSheetError(null);
    setApprovalOpen(false);
    setDetailsOpen(false);
    setFullscreen(false);
    setPickingStack(false);
    setMobilePane("assistant");
    autoViewRef.current = null;
  }

  function handleUseCurrentDrawing() {
    if (!project) return;
    setView("workspace");
    resetSetup(project, setupProfile);
  }

  function handleBackToWorkspace() {
    if (!project) return;
    setBlankWorkspace(false);
    setView("workspace");
    const latest = project.designs.at(-1);
    if (latest) {
      void loadDesignById(latest.design_id, false);
    } else {
      resetSetup(project, setupProfile);
    }
  }

  function handleRequestDeleteDesign(target: DesignSummary) {
    setDeleteError(null);
    setApprovalOpen(false);
    setDetailsOpen(false);
    setFullscreen(false);
    setDeleteDesignTarget(target);
  }

  async function handleConfirmDeleteDesign() {
    if (!project || !deleteDesignTarget || deleteBusy) return;
    const target = deleteDesignTarget;
    const projectId = project.project_id;
    const wasCurrent = design?.design_id === target.design_id;
    const localProject: Project = {
      ...project,
      designs: project.designs.filter(
        (item) => item.design_id !== target.design_id,
      ),
    };

    setDeleteBusy(true);
    setDeleteError(null);
    try {
      await api.deleteDesign(target.design_id);
    } catch (error) {
      setDeleteError((error as Error).message);
      setDeleteBusy(false);
      return;
    }

    setDeleteDesignTarget(null);
    setDeleteBusy(false);
    setProject(localProject);
    focusWorkspaceTrigger();
    showToast("Design deleted.");
    void refreshProjects();

    if (wasCurrent) {
      closeStreams();
      setDesign(null);
      setMessages([]);
      setEvents([]);
      setCanvasView("source");
      setSheetPage(1);
      setSheetSvg(null);
      setSheetError(null);
      setDetailsOpen(false);
      setFullscreen(false);
      setApprovalOpen(false);
      setMobilePane("assistant");
      setBusy(false);
      autoViewRef.current = null;
    }

    try {
      const updated = await api.project(projectId);
      if (!mountedRef.current) return;
      setProject(updated);
      if (wasCurrent) {
        const latest = updated.designs.at(-1);
        if (latest) {
          await loadDesignById(latest.design_id, false);
        } else {
          resetSetup(updated, setupProfile);
        }
      }
    } catch {
      if (wasCurrent && !localProject.designs.length) {
        resetSetup(localProject, setupProfile);
      }
      showToast("Design deleted, but the workspace could not refresh.", true);
    }
  }

  function handleRequestDeleteProject(target: ProjectSummary) {
    setDeleteProjectError(null);
    setDeleteProjectTarget(target);
  }

  async function handleConfirmDeleteProject() {
    if (!deleteProjectTarget || deleteProjectBusy) return;
    const target = deleteProjectTarget;
    const wasCurrent = project?.project_id === target.project_id;

    setDeleteProjectBusy(true);
    setDeleteProjectError(null);
    try {
      await api.deleteProject(target.project_id);
    } catch (error) {
      setDeleteProjectError((error as Error).message);
      setDeleteProjectBusy(false);
      return;
    }

    setDeleteProjectTarget(null);
    setDeleteProjectBusy(false);
    setProjects((current) =>
      current.filter((item) => item.project_id !== target.project_id),
    );

    if (wasCurrent) {
      closeStreams();
      setProject(null);
      setDesign(null);
      setMessages([]);
      setEvents([]);
      setCanvasView("source");
      setSheetPage(1);
      setSheetSvg(null);
      setSheetError(null);
      setDetailsOpen(false);
      setFullscreen(false);
      setApprovalOpen(false);
      setDeleteDesignTarget(null);
      setBusy(false);
      autoViewRef.current = null;
    }

    setView("home");
    focusHomeMain();
    showToast("Drawing deleted.");
    void refreshProjects();
  }

  async function handleStartDesign() {
    if (
      !project ||
      !setupRooms.length ||
      setupRooms.some((item) => !item.fixtures.length) ||
      busy
    ) {
      return;
    }
    setView("workspace");
    setBlankWorkspace(false);
    if (!setupStack && !project.stacks.length) {
      showToast("Place a drain stack on the plan first.", true);
      return;
    }
    setBusy(true);
    setPickingStack(false);
    setMobilePane("assistant");
    closeStreams();
    try {
      const created = await api.createDesign(project.project_id, {
        rooms: setupRooms.map((item) => ({
          room_id: item.roomId,
          fixtures: item.fixtures,
          stack_id: setupStack ? null : item.stackId || null,
        })),
        stack: setupStack,
        profile_id: setupProfile,
      });
      if (!mountedRef.current || !created.design_id) return;
      setDesign(created);
      setMessages([]);
      setEvents([]);
      setCanvasView("source");
      const roomText = setupRooms
        .map((item) => {
          const room = project.rooms.find((candidate) => candidate.id === item.roomId);
          return `${room?.name || item.roomId} with ${item.fixtures.join(", ")}`;
        })
        .join("; ");
      const prompt = `Design the plumbing for ${roomText}. Compare the layouts and explain the warnings.`;
      await refreshProject();
      await refreshProjects();
      await sendToDesign(created.design_id, prompt);
    } catch (error) {
      setBusy(false);
      showToast((error as Error).message, true);
    }
  }

  async function handleSelectDesign(id: string) {
    if (busy) return;
    setBlankWorkspace(false);
    closeStreams();
    await loadDesignById(id);
  }

  async function handleProfileChange(profileId: string) {
    if (busy) return;
    setSetupProfile(profileId);
    if (!design?.design_id) return;
    try {
      const updated = await api.setProfile(design.design_id, profileId);
      setDesign(updated);
      showToast("Code standard updated. Run the checks again.");
      await refreshProject();
    } catch (error) {
      showToast((error as Error).message, true);
    }
  }

  async function handleApplyFix(fixId: string) {
    if (busy || !design?.design_id) return;
    setBusy(true);
    try {
      const updated = await api.fix(design.design_id, fixId);
      setDesign(updated);
      setDetailsOpen(false);
      showToast("Fix applied and the design was rechecked.");
      await refreshProject();
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  async function handleApprove(approver: string) {
    if (!design?.design_id) return;
    setBusy(true);
    try {
      const updated = await api.approve(design.design_id, approver);
      setDesign(updated);
      showToast("Approved. The DXF is ready to download.");
      await refreshProject();
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function handleRunChecks() {
    if (!design?.design_id || busy) return;
    setDetailsOpen(false);
    void sendToDesign(design.design_id, CHECK_PROMPT);
  }

  function handleOpenDetails(tab: DetailsTab) {
    setDetailsTab(tab);
    setDetailsOpen(true);
  }

  function handleToggleStackPick() {
    const next = !pickingStack;
    setPickingStack(next);
    setCanvasView("source");
    if (next) setMobilePane("plan");
  }

  function handlePickStack(point: { x: number; y: number }) {
    setSetupStack(point);
    setPickingStack(false);
    showToast(`Drain stack placed at ${point.x.toFixed(0)}, ${point.y.toFixed(0)} mm.`);
  }

  function handleClearStack() {
    setSetupStack(null);
    setPickingStack(false);
  }

  function toggleSetupRoom(roomId: string) {
    if (!project) return;
    setSetupRooms((previous) => {
      const existing = previous.find((item) => item.roomId === roomId);
      if (existing) {
        const next = previous.filter((item) => item.roomId !== roomId);
        setActiveSetupRoomId((active) =>
          active === roomId ? next[0]?.roomId || null : active,
        );
        return next;
      }
      setActiveSetupRoomId(roomId);
      return [...previous, setupRoomDraft(project, roomId)];
    });
  }

  function selectAllPlumbingRooms() {
    if (!project) return;
    const defaults = defaultSetupRooms(project);
    setSetupRooms((previous) => {
      const existing = new Map(previous.map((item) => [item.roomId, item]));
      const plumbingIds = new Set(defaults.map((item) => item.roomId));
      return [
        ...defaults.map((item) => existing.get(item.roomId) || item),
        ...previous.filter((item) => !plumbingIds.has(item.roomId)),
      ];
    });
    setActiveSetupRoomId((active) => active || defaults[0]?.roomId || null);
  }

  function toggleSetupFixture(roomId: string, fixture: string) {
    setSetupRooms((previous) =>
      previous.map((item) =>
        item.roomId === roomId
          ? {
              ...item,
              fixtures: item.fixtures.includes(fixture)
                ? item.fixtures.filter((value) => value !== fixture)
                : [...item.fixtures, fixture],
            }
          : item,
      ),
    );
  }

  function setSetupRoomStack(roomId: string, stackId: string) {
    setSetupRooms((previous) =>
      previous.map((item) =>
        item.roomId === roomId ? { ...item, stackId } : item,
      ),
    );
  }

  const canApprove = Boolean(design?.design && !busy);

  if (loading) {
    return <StudioSkeleton />;
  }

  if (view === "home") {
    return (
      <>
        <HomePage
          projects={projects}
          project={project}
          design={design}
          busy={busy}
          onResume={handleResumeWorkspace}
          onOpenProject={(id) => void handleOpenProject(id)}
          onDeleteProject={handleRequestDeleteProject}
          onUpload={(file) => void handleUpload(file)}
          onSample={() => void handleSample()}
        />
        <DeleteProjectDialog
          project={deleteProjectTarget}
          current={
            Boolean(project) &&
            deleteProjectTarget?.project_id === project?.project_id
          }
          running={Boolean(
            busy &&
              project?.project_id === deleteProjectTarget?.project_id,
          )}
          busy={deleteProjectBusy}
          error={deleteProjectError}
          onClose={() => {
            if (deleteProjectBusy) return;
            setDeleteProjectTarget(null);
            setDeleteProjectError(null);
            focusHomeMain();
          }}
          onConfirm={() => void handleConfirmDeleteProject()}
        />
        <AppToast toast={toast} onDismiss={() => setToast(null)} />
      </>
    );
  }

  if (!project) {
    return (
      <>
        <StartScreen
          project={null}
          projects={projects}
          blank={false}
          busy={busy}
          onHome={handleOpenHome}
          onUpload={(file) => void handleUpload(file)}
          onSample={() => void handleSample()}
          onOpenProject={(id) => void handleOpenProject(id)}
          onRetry={() => {
            setLoading(true);
            void boot().finally(() => setLoading(false));
          }}
        />
        <AppToast toast={toast} onDismiss={() => setToast(null)} />
      </>
    );
  }

  if (blankWorkspace) {
    return (
      <>
        <StartScreen
          project={project}
          projects={projects}
          blank
          busy={busy}
          onHome={handleOpenHome}
          onUpload={(file) => void handleUpload(file)}
          onSample={() => void handleSample()}
          onUseCurrent={handleUseCurrentDrawing}
          onOpenProject={(id) => void handleOpenProject(id)}
          onBack={handleBackToWorkspace}
          onRetry={() => void boot()}
        />
        <AppToast toast={toast} onDismiss={() => setToast(null)} />
      </>
    );
  }

  const activeProfile = design?.profile_id || setupProfile;
  const selectedRooms =
    design?.room_ids ||
    design?.room_plans?.map((plan) => plan.room_id) ||
    setupRooms.map((room) => room.roomId);
  const activeStatus = designStatus(design, busy);

  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-canvas">
      <a href="#main-workspace" className="skip-link">
        Skip to workspace
      </a>
      <p className="status-live" role="status" aria-live="polite">
        {activeStatus.label}
        {busy ? ". Assistant is working." : ""}
      </p>
      <StudioHeader
        project={project}
        projects={projects}
        design={design}
        profiles={profiles}
        selectedProfile={activeProfile}
        onProfile={(id) => void handleProfileChange(id)}
        onApprove={() => setApprovalOpen(true)}
        canApprove={canApprove}
        busy={busy}
        provider={provider?.name}
        model={provider?.model}
        onSelectDesign={(id) => void handleSelectDesign(id)}
        onDeleteDesign={handleRequestDeleteDesign}
        onOpenHome={handleOpenHome}
        onNewDesign={handleNewDesign}
        onUpload={(file) => void handleUpload(file)}
        onSample={() => void handleSample()}
        onOpenProject={(id) => void handleOpenProject(id)}
        onOpenDetails={() => handleOpenDetails("design")}
      />

      <div className="flex shrink-0 items-center gap-2 border-b border-line bg-surface px-3 py-2 lg:hidden">
        <SegmentedControl
          label="Workspace view"
          className="w-full flex-1 [&>button]:flex-1"
          value={mobilePane}
          onChange={(value) => setMobilePane(value)}
          options={[
            { value: "plan", label: design ? "Plan" : "Source plan" },
            { value: "assistant", label: design ? "Assistant" : "Setup" },
          ]}
        />
        {design && (
          <span className="sm:hidden">
            <StatusPill design={design} busy={busy} />
          </span>
        )}
      </div>

      <main
        id="main-workspace"
        ref={splitContainerRef}
        tabIndex={-1}
        aria-busy={busy}
        className="flex min-h-0 flex-1 flex-col focus:outline-none lg:flex-row"
      >
        <h1 className="sr-only">Flowline bathroom plumbing design workspace</h1>
        <div
          id="plan-pane"
          className={cx(
            "relative min-h-0 min-w-0 flex-1 flex-col lg:shrink-0 lg:grow-0 lg:basis-[var(--split)]",
            mobilePane === "plan" ? "flex" : "hidden lg:flex",
          )}
          style={{ "--split": `${split.percent}%` } as CSSProperties}
        >
          {canvasView === "sheet" ? (
            <SheetCanvas
              svg={sheetSvg}
              loading={sheetLoading}
              error={sheetError}
              page={sheetPage}
              pages={design?.sheet_pages || 1}
              sheet={design?.sheet || null}
              updating={sheetUpdating}
              onPage={setSheetPage}
              onBack={() => setCanvasView("design")}
              onUpdateSheet={(body) => void handleUpdateSheet(body)}
              onRetry={() => setSheetRetry((value) => value + 1)}
            />
          ) : (
            <DesignCanvas
              project={project}
              design={design}
              view={canvasView}
              onView={(view) => setCanvasView(view)}
              busy={busy}
              selectedRooms={selectedRooms}
              onToggleRoom={design ? undefined : toggleSetupRoom}
              stackPoint={setupStack}
              pickingStack={pickingStack}
              onPickStack={handlePickStack}
              onCancelStackPick={() => setPickingStack(false)}
              onToggleFullscreen={design ? () => setFullscreen(true) : undefined}
              sheetReady={Boolean(design?.sheet_ready)}
              onOpenSheet={handleViewSheet}
            />
          )}
        </div>

        <div
          role="separator"
          aria-orientation="vertical"
          aria-label="Resize plan and assistant"
          aria-controls="plan-pane assistant-pane"
          aria-valuemin={46}
          aria-valuemax={72}
          aria-valuenow={Math.round(split.percent)}
          aria-valuetext={`${Math.round(split.percent)} percent for plan`}
          tabIndex={0}
          onPointerDown={split.startDrag}
          onDoubleClick={split.reset}
          onKeyDown={split.onKeyDown}
          className={cx(
            "group hidden w-2 shrink-0 cursor-col-resize items-center justify-center border-x border-line bg-surface transition hover:bg-accent-soft lg:flex",
            split.dragging && "bg-accent-soft",
          )}
          data-testid="splitter"
        >
          <div
            className={cx(
              "h-10 w-0.5 rounded-full bg-line-strong transition group-hover:bg-accent",
              split.dragging && "bg-accent",
            )}
          />
        </div>

        <aside
          id="assistant-pane"
          className={cx(
            "min-h-0 min-w-0 flex-1 flex-col overflow-hidden",
            mobilePane === "assistant" ? "flex" : "hidden lg:flex",
          )}
        >
          {design ? (
            <ChatPanel
              design={design}
              messages={messages}
              events={events}
              busy={busy}
              onSend={(content) => {
                if (design.design_id) void sendToDesign(design.design_id, content);
              }}
              onOpenDetails={handleOpenDetails}
              onOpenFullscreen={() => setFullscreen(true)}
              onOpenSheet={handleViewSheet}
              onApprove={() => setApprovalOpen(true)}
            />
          ) : (
            <NewDesignPanel
              project={project}
              profiles={profiles}
              selectedProfile={setupProfile}
              selections={setupRooms}
              activeRoomId={activeSetupRoomId}
              onToggleRoom={toggleSetupRoom}
              onActivateRoom={setActiveSetupRoomId}
              onSelectAll={selectAllPlumbingRooms}
              onFixture={toggleSetupFixture}
              onStack={setSetupRoomStack}
              onProfile={(id) => void handleProfileChange(id)}
              onStart={() => void handleStartDesign()}
              busy={busy}
              stackPoint={setupStack}
              pickingStack={pickingStack}
              onToggleStackPick={handleToggleStackPick}
              onClearStack={handleClearStack}
            />
          )}
        </aside>
      </main>

      {fullscreen && (
        <FullscreenPlan
          project={project}
          design={design}
          view={canvasView === "sheet" ? "design" : canvasView}
          onView={(view) => setCanvasView(view)}
          busy={busy}
          selectedRooms={selectedRooms}
          onToggleRoom={design ? undefined : toggleSetupRoom}
          stackPoint={setupStack}
          pickingStack={pickingStack}
          onPickStack={handlePickStack}
          onCancelStackPick={() => setPickingStack(false)}
          onClose={() => setFullscreen(false)}
          onHome={handleOpenHome}
        />
      )}

      <DetailsDrawer
        open={detailsOpen}
        tab={detailsTab}
        onTab={setDetailsTab}
        design={design}
        project={project}
        events={events}
        busy={busy}
        onClose={() => setDetailsOpen(false)}
        onApplyFix={(fixId) => void handleApplyFix(fixId)}
        onRunChecks={handleRunChecks}
        onViewSheet={handleViewSheet}
      />

      <ApprovalDialog
        open={approvalOpen}
        design={design}
        busy={busy}
        onClose={() => setApprovalOpen(false)}
        onApprove={(approver) => void handleApprove(approver)}
      />

      <DeleteDesignDialog
        design={deleteDesignTarget}
        project={project}
        running={Boolean(
          busy && design?.design_id === deleteDesignTarget?.design_id,
        )}
        busy={deleteBusy}
        error={deleteError}
        onClose={() => {
          if (deleteBusy) return;
          setDeleteDesignTarget(null);
          setDeleteError(null);
          focusWorkspaceTrigger();
        }}
        onConfirm={() => void handleConfirmDeleteDesign()}
      />

      <AppToast toast={toast} onDismiss={() => setToast(null)} />
    </div>
  );
}

function AppToast({
  toast,
  onDismiss,
}: {
  toast: Toast;
  onDismiss: () => void;
}) {
  if (!toast) return null;
  const Icon = toast.error ? TriangleAlert : CheckCircle2;
  return (
    <div
      key={toast.id}
      role={toast.error ? "alert" : "status"}
      aria-live={toast.error ? "assertive" : "polite"}
      aria-atomic="true"
      className={cx(
        "fixed bottom-[calc(1rem+env(safe-area-inset-bottom))] left-3 right-3 z-[70] flex items-start gap-3 overflow-hidden rounded-overlay border bg-raised/95 p-3 pr-2 text-label shadow-float backdrop-blur animate-slide-in sm:left-auto sm:right-6 sm:w-[380px] sm:max-w-[calc(100vw-3rem)] lg:bottom-6",
        toast.error ? "border-danger-line" : "border-line",
      )}
      data-testid="toast"
    >
      <span
        className={cx(
          "absolute inset-y-0 left-0 w-1",
          toast.error ? "bg-danger" : "bg-success",
        )}
        aria-hidden="true"
      />
      <span
        className={cx(
          "grid h-9 w-9 shrink-0 place-items-center rounded-full",
          toast.error
            ? "bg-danger-soft text-danger"
            : "bg-success-soft text-success",
        )}
        aria-hidden="true"
      >
        <Icon size={17} />
      </span>
      <div className="min-w-0 flex-1 pt-0.5">
        <div
          className={cx(
            "text-[10px] font-semibold uppercase tracking-[0.12em]",
            toast.error ? "text-danger" : "text-success",
          )}
        >
          {toast.error ? "Action failed" : "Done"}
        </div>
        <p className="mt-0.5 text-ui leading-relaxed text-ink-soft">
          {toast.message}
        </p>
      </div>
      <button
        type="button"
        onClick={onDismiss}
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full text-muted transition hover:bg-sunken hover:text-ink"
        aria-label="Dismiss notification"
      >
        <X size={15} />
      </button>
      <span
        className={cx(
          "toast-progress absolute bottom-0 left-1 right-0 h-0.5 origin-left",
          toast.error ? "bg-danger/60" : "bg-success/60",
        )}
        aria-hidden="true"
      />
    </div>
  );
}

function StudioSkeleton() {
  return (
    <div className="flex h-full min-h-0 flex-col overflow-hidden bg-canvas">
      <p className="status-live" role="status" aria-live="polite">
        Loading your Flowline workspace.
      </p>
      <header className="flex h-[60px] shrink-0 items-center gap-3 border-b border-line bg-surface px-4">
        <Logo size={30} withWord />
        <div className="ml-2 flex min-w-0 flex-1 flex-col gap-1.5">
          <Skeleton className="h-3.5 w-32" />
          <Skeleton className="h-2.5 w-48" />
        </div>
        <Skeleton className="hidden h-8 w-32 rounded-full sm:block" />
        <Skeleton className="hidden h-9 w-24 lg:block" />
      </header>
      <div className="flex min-h-0 flex-1">
        <div className="hidden min-w-0 flex-1 flex-col gap-4 p-6 sm:flex">
          <Skeleton className="h-10 w-64" />
          <div className="grid min-h-0 flex-1 place-items-center">
            <Skeleton className="aspect-[4/3] w-[72%] rounded-card" />
          </div>
          <Skeleton className="h-11 w-56" />
        </div>
        <div className="flex w-full flex-col gap-4 border-l border-line bg-surface p-5 lg:w-[38%]">
          <Skeleton className="h-5 w-36" />
          <Skeleton className="h-3.5 w-full" />
          <Skeleton className="h-3.5 w-4/5" />
          <Skeleton className="mt-3 h-40 w-full rounded-card" />
          <Skeleton className="h-24 w-full rounded-card" />
        </div>
      </div>
    </div>
  );
}
