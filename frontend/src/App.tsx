import { useEffect, useRef, useState } from "react";
import { FileUp, Loader2, RefreshCw } from "lucide-react";
import { api } from "./api";
import type {
  AgentEvent,
  DesignState,
  Message,
  Profile,
  Project,
} from "./types";
import { ApprovalDialog } from "./components/ApprovalDialog";
import { ChatPanel } from "./components/ChatPanel";
import { MissionControl } from "./components/MissionControl";
import { PlanPreview } from "./components/PlanPreview";
import { SetupPanel } from "./components/SetupPanel";
import { Sidebar } from "./components/Sidebar";
import { Topbar } from "./components/Topbar";

type Toast = { message: string; error?: boolean } | null;

const DEFAULT_PROFILE = "india_nbc_2016";

export default function App() {
  const [loading, setLoading] = useState(true);
  const [provider, setProvider] = useState<{ name: string; model: string } | null>(null);
  const [profiles, setProfiles] = useState<Profile[]>([]);
  const [project, setProject] = useState<Project | null>(null);
  const [design, setDesign] = useState<DesignState | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [busy, setBusy] = useState(false);
  const [toast, setToast] = useState<Toast>(null);
  const [setupRoom, setSetupRoom] = useState<string | null>(null);
  const [setupFixtures, setSetupFixtures] = useState<string[]>(["WC", "BASIN", "SHOWER"]);
  const [setupShaft, setSetupShaft] = useState("");
  const [setupProfile, setSetupProfile] = useState(DEFAULT_PROFILE);
  const [planView, setPlanView] = useState<"design" | "plan">("design");
  const [approvalOpen, setApprovalOpen] = useState(false);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);
  const toastRef = useRef<number | null>(null);
  const mountedRef = useRef(true);

  const activeDesignId = design?.design_id || null;

  function showToast(message: string, error = false) {
    setToast({ message, error });
    if (toastRef.current) window.clearTimeout(toastRef.current);
    toastRef.current = window.setTimeout(() => setToast(null), 4200);
  }

  function closeStreams() {
    esRef.current?.close();
    esRef.current = null;
    if (pollRef.current) {
      window.clearTimeout(pollRef.current);
      pollRef.current = null;
    }
  }

  function resetSetup(current: Project, profileId = DEFAULT_PROFILE) {
    const first = current.rooms.find((room) => room.wet_area) || current.rooms[0];
    setSetupRoom(first?.id || null);
    setSetupFixtures(["WC", "BASIN", "SHOWER"]);
    setSetupShaft(current.shafts[0]?.id || "");
    setSetupProfile(profileId);
    setDesign(null);
    setMessages([]);
    setEvents([]);
    setBusy(false);
    setPlanView("plan");
    setApprovalOpen(false);
    closeStreams();
  }

  async function refreshProject() {
    if (!project) return;
    try {
      const current = await api.project(project.project_id);
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
    setPlanView(data.design ? "design" : "plan");
    setSetupRoom(data.room_id);
    setSetupFixtures(data.fixtures?.length ? data.fixtures : ["WC", "BASIN", "SHOWER"]);
    setSetupShaft(data.stack?.id || project?.shafts[0]?.id || "");
    setSetupProfile(data.profile_id);
    if (data.provider) setProvider({ name: data.provider, model: data.model });
    await refreshProject();
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
              setProvider({ name: job.result.provider, model: job.result.model });
            }
            setBusy(false);
            await refreshDesign(designId);
            await refreshProject();
          } else {
            setBusy(false);
            showToast(job.error || "The agent stopped.", true);
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
          setProvider({ name: String(event.provider), model: String(event.model || "") });
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
      if (event.type === "error") {
        setBusy(false);
        showToast(String(event.message || "Agent error."), true);
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
      let current: Project;
      if (!list.projects.length) {
        current = await api.sample();
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

  async function handleUpload(file: File) {
    if (busy) return;
    setBusy(true);
    try {
      const current = await api.upload(file);
      if (!mountedRef.current) return;
      setProject(current);
      resetSetup(current, profiles[0]?.id || DEFAULT_PROFILE);
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
      showToast("Sample workspace loaded.");
    } catch (error) {
      showToast((error as Error).message, true);
    } finally {
      setBusy(false);
    }
  }

  function handleNewDesign() {
    if (busy || !project) return;
    resetSetup(project, design?.profile_id || setupProfile);
  }

  async function handleStartDesign() {
    if (!project || !setupRoom || !setupFixtures.length || busy) return;
    setBusy(true);
    closeStreams();
    try {
      const created = await api.createDesign(project.project_id, {
        room_id: setupRoom,
        fixtures: setupFixtures,
        shaft_id: setupShaft || null,
        profile_id: setupProfile,
      });
      if (!mountedRef.current || !created.design_id) return;
      setDesign(created);
      setMessages([]);
      setEvents([]);
      setPlanView("design");
      const room = project.rooms.find((item) => item.id === setupRoom);
      const prompt = `Design the drainage for ${room?.name || setupRoom} with ${setupFixtures.join(", ")}. Compare the layouts and explain the warnings.`;
      await refreshProject();
      await sendToDesign(created.design_id, prompt);
    } catch (error) {
      setBusy(false);
      showToast((error as Error).message, true);
    }
  }

  async function handleSelectDesign(id: string) {
    if (busy) return;
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
      showToast("Standard changed. Revalidate before export.");
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
      showToast("Fix applied and the design was revalidated.");
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

  function toggleFixture(fixture: string) {
    setSetupFixtures((previous) =>
      previous.includes(fixture)
        ? previous.filter((item) => item !== fixture)
        : [...previous, fixture],
    );
  }

  const canApprove = Boolean(
    design?.design &&
      !design.stale &&
      design.validation?.length &&
      design.counts.ERROR === 0 &&
      !busy,
  );

  if (loading) {
    return (
      <div className="grid h-full place-items-center bg-slate-950 text-slate-300">
        <div className="text-center">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-gradient-to-br from-blue-600 to-cyan-400 text-lg font-black text-white shadow-xl shadow-blue-900/40">
            F
          </div>
          <div className="mt-3 text-sm font-bold text-white">Flowline</div>
          <div className="mt-1 flex items-center justify-center gap-2 text-[11px] text-slate-500">
            <Loader2 size={12} className="animate-spin" /> Preparing the workspace
          </div>
        </div>
      </div>
    );
  }

  if (!project) {
    return (
      <div className="grid h-full place-items-center bg-slate-50 p-6">
        <div className="w-full max-w-md rounded-2xl border border-slate-200 bg-white p-6 text-center shadow-sm">
          <div className="mx-auto grid h-12 w-12 place-items-center rounded-2xl bg-blue-600 text-lg font-black text-white">
            F
          </div>
          <h1 className="mt-3 text-lg font-bold text-slate-900">Start a workspace</h1>
          <p className="mt-1 text-xs text-slate-500">
            Upload a DXF floor plan or open the sample apartment.
          </p>
          <div className="mt-4 flex justify-center gap-2">
            <label className="flex cursor-pointer items-center gap-1.5 rounded-lg bg-blue-600 px-3 py-2 text-xs font-bold text-white">
              <FileUp size={14} /> Upload DXF
              <input
                type="file"
                accept=".dxf"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) void handleUpload(file);
                  event.target.value = "";
                }}
              />
            </label>
            <button
              type="button"
              onClick={() => void handleSample()}
              className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-bold text-slate-600"
            >
              Open sample
            </button>
          </div>
          <button
            type="button"
            onClick={() => {
              setLoading(true);
              void boot().finally(() => setLoading(false));
            }}
            className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg px-3 py-2 text-[11px] font-semibold text-slate-400 hover:text-slate-600"
          >
            <RefreshCw size={12} /> Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex h-full min-h-0 overflow-hidden bg-slate-50">
      <Sidebar
        project={project}
        activeDesignId={activeDesignId}
        onSelectDesign={(id) => void handleSelectDesign(id)}
        onNewDesign={handleNewDesign}
        onUpload={(file) => void handleUpload(file)}
        onSample={() => void handleSample()}
        provider={provider?.name}
        model={provider?.model}
      />
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar
          project={project}
          design={design}
          profiles={profiles}
          selectedProfile={design?.profile_id || setupProfile}
          onProfile={(id) => void handleProfileChange(id)}
          onApprove={() => setApprovalOpen(true)}
          canApprove={canApprove}
          provider={provider?.name}
          model={provider?.model}
          busy={busy}
        />
        <div className="flex min-h-0 flex-1">
          <main className="flex min-w-0 flex-1 flex-col">
            {design ? (
              <ChatPanel
                design={design}
                messages={messages}
                events={events}
                busy={busy}
                onSend={(content) => {
                  if (design.design_id) void sendToDesign(design.design_id, content);
                }}
                onApplyFix={(fixId) => void handleApplyFix(fixId)}
                onApprove={() => setApprovalOpen(true)}
                canApprove={canApprove}
              />
            ) : (
              <SetupPanel
                project={project}
                profiles={profiles}
                selectedProfile={setupProfile}
                selectedRoom={setupRoom}
                fixtures={setupFixtures}
                shaftId={setupShaft}
                onRoom={setSetupRoom}
                onFixture={toggleFixture}
                onShaft={setSetupShaft}
                onStart={() => void handleStartDesign()}
                busy={busy}
                planView={planView}
                onPlanView={setPlanView}
              />
            )}
          </main>
          {design && (
            <aside className="hidden w-[420px] shrink-0 flex-col gap-3 border-l border-slate-200 bg-slate-50/70 p-4 xl:flex">
              <div className="h-[38vh] min-h-[250px]">
                <PlanPreview
                  project={project}
                  design={design}
                  view={planView}
                  onView={setPlanView}
                  compact
                />
              </div>
              <MissionControl
                design={design}
                events={events}
                busy={busy}
                onApplyFix={(fixId) => void handleApplyFix(fixId)}
              />
            </aside>
          )}
        </div>
      </div>

      <ApprovalDialog
        open={approvalOpen}
        design={design}
        busy={busy}
        onClose={() => setApprovalOpen(false)}
        onApprove={(approver) => void handleApprove(approver)}
      />

      {toast && (
        <div
          className={`fixed bottom-5 right-5 z-[60] max-w-md rounded-xl px-4 py-3 text-xs font-medium text-white shadow-2xl ${
            toast.error ? "bg-red-700" : "bg-slate-900"
          }`}
        >
          {toast.message}
        </div>
      )}
    </div>
  );
}
