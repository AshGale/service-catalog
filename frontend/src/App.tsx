import { useState, useEffect, useCallback, useRef } from "react";

// ── Types ──────────────────────────────────────────────────────────────────

interface Service {
  service_name: string;
  owner: string | null;
  lifecycle: string | null;
  last_updated: string | null;
  metadata: Record<string, unknown> | null;
}

interface Deps {
  dependsOn: string[];
  providesApis: string[];
}

interface AskEntry {
  q: string;
  a: string;
  context: number;
}

// Mermaid is loaded dynamically from CDN at runtime
declare global {
  interface Window {
    mermaid?: {
      initialize: (config: Record<string, unknown>) => void;
      render: (id: string, code: string) => Promise<{ svg: string }>;
    };
  }
}

// ── Theme: Industrial terminal aesthetic ───────────────────────────────────

const theme = {
  bg: "#0a0c0f",
  surface: "#12151a",
  surfaceRaised: "#181c23",
  border: "#252a33",
  borderActive: "#3d8c40",
  text: "#c8cdd5",
  textMuted: "#6b7280",
  textDim: "#3d4451",
  accent: "#3d8c40",
  accentGlow: "rgba(61,140,64,0.15)",
  accentText: "#5cb85f",
  danger: "#c0392b",
  warn: "#d4a017",
  tagBg: "#1a2418",
  tagBorder: "#2d4a2f",
} as const;

const font = {
  mono: "'IBM Plex Mono', 'Fira Code', 'SF Mono', monospace",
  display: "'IBM Plex Sans Condensed', 'Arial Narrow', sans-serif",
} as const;

// ── Shared styles ──────────────────────────────────────────────────────────

const baseInput: React.CSSProperties = {
  background: theme.surface,
  border: `1px solid ${theme.border}`,
  color: theme.text,
  fontFamily: font.mono,
  fontSize: "13px",
  padding: "10px 14px",
  borderRadius: "4px",
  outline: "none",
  width: "100%",
  boxSizing: "border-box",
  transition: "border-color 0.2s",
};

// ── Tiny typed fetch wrapper ───────────────────────────────────────────────

const API = "/api";

async function apiFetch<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const res = await fetch(`${API}${path}`, opts);
  if (!res.ok) {
    const body = (await res.json().catch(() => ({}))) as { detail?: string };
    throw new Error(body.detail ?? `${res.status} ${res.statusText}`);
  }
  return res.json() as Promise<T>;
}

// ── Components ────────────────────────────────────────────────────────────

function Indicator({ status }: { status: string | null }) {
  const colors: Record<string, string> = {
    production: theme.accent,
    staging: theme.warn,
    experimental: theme.danger,
    deprecated: theme.textDim,
  };
  const c = (status && colors[status]) || theme.textMuted;
  return (
    <span
      style={{
        display: "inline-block",
        width: 8,
        height: 8,
        borderRadius: "50%",
        background: c,
        boxShadow: `0 0 6px ${c}`,
        marginRight: 8,
        flexShrink: 0,
      }}
    />
  );
}

function Tag({ children }: { children: React.ReactNode }) {
  return (
    <span
      style={{
        display: "inline-block",
        padding: "2px 8px",
        fontSize: 11,
        fontFamily: font.mono,
        background: theme.tagBg,
        border: `1px solid ${theme.tagBorder}`,
        borderRadius: 3,
        color: theme.accentText,
        marginRight: 6,
        marginBottom: 4,
      }}
    >
      {children}
    </span>
  );
}

function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <div
      style={{
        fontSize: 10,
        fontFamily: font.mono,
        color: theme.textDim,
        textTransform: "uppercase",
        letterSpacing: "0.12em",
        marginBottom: 8,
        marginTop: 20,
      }}
    >
      {children}
    </div>
  );
}

function EmptyState({ icon, message }: { icon: string; message: string }) {
  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        height: 300,
        color: theme.textDim,
        fontFamily: font.mono,
        fontSize: 13,
        gap: 12,
      }}
    >
      <span style={{ fontSize: 32, opacity: 0.4 }}>{icon}</span>
      <span>{message}</span>
    </div>
  );
}

// ── Service List Panel ─────────────────────────────────────────────────────

interface ServiceListProps {
  services: Service[];
  selected: string | null;
  onSelect: (name: string) => void;
  loading: boolean;
}

function ServiceList({ services, selected, onSelect, loading }: ServiceListProps) {
  const [filter, setFilter] = useState("");
  const filtered = services.filter(
    (s) =>
      s.service_name.toLowerCase().includes(filter.toLowerCase()) ||
      (s.owner ?? "").toLowerCase().includes(filter.toLowerCase())
  );

  return (
    <div
      style={{
        width: 320,
        minWidth: 320,
        borderRight: `1px solid ${theme.border}`,
        display: "flex",
        flexDirection: "column",
        height: "100%",
      }}
    >
      {/* Search */}
      <div style={{ padding: "16px 16px 12px" }}>
        <input
          type="text"
          placeholder="filter services…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          style={{ ...baseInput, fontSize: 12 }}
          onFocus={(e) => (e.currentTarget.style.borderColor = theme.borderActive)}
          onBlur={(e) => (e.currentTarget.style.borderColor = theme.border)}
        />
      </div>

      {/* List */}
      <div style={{ flex: 1, overflowY: "auto", padding: "0 8px 16px" }}>
        {loading ? (
          <EmptyState icon="⟳" message="loading catalog…" />
        ) : filtered.length === 0 ? (
          <EmptyState icon="∅" message="no services found" />
        ) : (
          filtered.map((svc) => {
            const active = selected === svc.service_name;
            return (
              <button
                key={svc.service_name}
                onClick={() => onSelect(svc.service_name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  width: "100%",
                  padding: "10px 12px",
                  marginBottom: 2,
                  background: active ? theme.accentGlow : "transparent",
                  border: "1px solid",
                  borderColor: active ? theme.borderActive : "transparent",
                  borderRadius: 4,
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s",
                  fontFamily: font.mono,
                }}
                onMouseEnter={(e) => {
                  if (!active) e.currentTarget.style.background = theme.surfaceRaised;
                }}
                onMouseLeave={(e) => {
                  if (!active) e.currentTarget.style.background = "transparent";
                }}
              >
                <Indicator status={svc.lifecycle} />
                <div style={{ minWidth: 0 }}>
                  <div
                    style={{
                      fontSize: 13,
                      color: active ? theme.accentText : theme.text,
                      fontWeight: active ? 600 : 400,
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                    }}
                  >
                    {svc.service_name}
                  </div>
                  <div style={{ fontSize: 11, color: theme.textMuted, marginTop: 2 }}>
                    {svc.owner ?? "unowned"} · {svc.lifecycle ?? "unknown"}
                  </div>
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Count */}
      <div
        style={{
          padding: "10px 16px",
          borderTop: `1px solid ${theme.border}`,
          fontSize: 11,
          fontFamily: font.mono,
          color: theme.textDim,
        }}
      >
        {filtered.length} service{filtered.length !== 1 ? "s" : ""}
      </div>
    </div>
  );
}

// ── Detail Panel ───────────────────────────────────────────────────────────

type DetailTab = "overview" | "diagram" | "dependencies";

function DetailPanel({ serviceName }: { serviceName: string | null }) {
  const [data, setData] = useState<Service | null>(null);
  const [tags, setTags] = useState<string[]>([]);
  const [deps, setDeps] = useState<Deps | null>(null);
  const [diagram, setDiagram] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [tab, setTab] = useState<DetailTab>("overview");

  useEffect(() => {
    if (!serviceName) return;
    setLoading(true);
    setTab("overview");
    Promise.all([
      apiFetch<Service>(`/services/${serviceName}`),
      apiFetch<string[]>(`/services/${serviceName}/tags`).catch(() => [] as string[]),
      apiFetch<Deps>(`/services/${serviceName}/deps`).catch(() => null),
      apiFetch<{ mermaid: string | null }>(`/services/${serviceName}/diagram`).catch(() => ({
        mermaid: null,
      })),
    ]).then(([svc, t, d, dia]) => {
      setData(svc);
      setTags(t);
      setDeps(d);
      setDiagram(dia?.mermaid ?? null);
      setLoading(false);
    });
  }, [serviceName]);

  if (!serviceName) return <EmptyState icon="←" message="select a service to inspect" />;
  if (loading) return <EmptyState icon="⟳" message="loading…" />;
  if (!data) return <EmptyState icon="!" message="failed to load service" />;

  const tabs: DetailTab[] = ["overview", "diagram", "dependencies"];

  return (
    <div style={{ flex: 1, overflowY: "auto", padding: 24 }}>
      {/* Header */}
      <div style={{ marginBottom: 24 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 6 }}>
          <Indicator status={data.lifecycle} />
          <h2
            style={{
              margin: 0,
              fontFamily: font.display,
              fontSize: 22,
              fontWeight: 700,
              color: theme.text,
              letterSpacing: "-0.02em",
            }}
          >
            {data.service_name}
          </h2>
        </div>
        <div style={{ fontFamily: font.mono, fontSize: 12, color: theme.textMuted }}>
          {data.owner ?? "unowned"} · {data.lifecycle ?? "unknown"} · updated{" "}
          {data.last_updated?.split(".")[0] ?? "—"}
        </div>
      </div>

      {/* Tabs */}
      <div
        style={{
          display: "flex",
          gap: 0,
          borderBottom: `1px solid ${theme.border}`,
          marginBottom: 20,
        }}
      >
        {tabs.map((t) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            style={{
              padding: "8px 18px",
              fontFamily: font.mono,
              fontSize: 12,
              color: tab === t ? theme.accentText : theme.textMuted,
              background: "none",
              border: "none",
              borderBottom: `2px solid ${tab === t ? theme.accent : "transparent"}`,
              cursor: "pointer",
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              transition: "all 0.15s",
            }}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Tab content */}
      {tab === "overview" && (
        <div>
          {tags.length > 0 && (
            <>
              <SectionLabel>tags</SectionLabel>
              <div style={{ display: "flex", flexWrap: "wrap" }}>
                {tags.map((t) => (
                  <Tag key={t}>{t}</Tag>
                ))}
              </div>
            </>
          )}
          {data.metadata && (
            <>
              <SectionLabel>metadata</SectionLabel>
              <pre
                style={{
                  fontFamily: font.mono,
                  fontSize: 12,
                  color: theme.textMuted,
                  background: theme.surface,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 4,
                  padding: 14,
                  overflowX: "auto",
                  margin: 0,
                }}
              >
                {JSON.stringify(data.metadata, null, 2)}
              </pre>
            </>
          )}
        </div>
      )}

      {tab === "diagram" && (
        <div>
          {diagram ? (
            <>
              <SectionLabel>architecture · mermaid</SectionLabel>
              <pre
                style={{
                  fontFamily: font.mono,
                  fontSize: 12,
                  color: theme.accentText,
                  background: theme.surface,
                  border: `1px solid ${theme.border}`,
                  borderRadius: 4,
                  padding: 16,
                  overflowX: "auto",
                  margin: 0,
                  lineHeight: 1.7,
                }}
              >
                {diagram}
              </pre>
              <MermaidPreview code={diagram} />
            </>
          ) : (
            <EmptyState icon="◇" message="no diagram embedded in this service" />
          )}
        </div>
      )}

      {tab === "dependencies" && (
        <div>
          {(deps?.dependsOn?.length ?? 0) > 0 && (
            <>
              <SectionLabel>depends on</SectionLabel>
              {deps!.dependsOn.map((d) => (
                <div
                  key={d}
                  style={{ fontFamily: font.mono, fontSize: 13, color: theme.text, padding: "6px 0" }}
                >
                  <span style={{ color: theme.danger, marginRight: 8 }}>→</span>
                  {d}
                </div>
              ))}
            </>
          )}
          {(deps?.providesApis?.length ?? 0) > 0 && (
            <>
              <SectionLabel>provides apis</SectionLabel>
              {deps!.providesApis.map((a) => (
                <div
                  key={a}
                  style={{ fontFamily: font.mono, fontSize: 13, color: theme.text, padding: "6px 0" }}
                >
                  <span style={{ color: theme.accentText, marginRight: 8 }}>←</span>
                  {a}
                </div>
              ))}
            </>
          )}
          {!(deps?.dependsOn?.length) && !(deps?.providesApis?.length) && (
            <EmptyState icon="◇" message="no dependencies declared" />
          )}
        </div>
      )}
    </div>
  );
}

// ── Mermaid live preview (loaded from CDN) ─────────────────────────────────

function MermaidPreview({ code }: { code: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const [svg, setSvg] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!code) return;
    let cancelled = false;

    (async () => {
      try {
        if (!window.mermaid) {
          await new Promise<void>((res, rej) => {
            const script = document.createElement("script");
            script.src =
              "https://cdnjs.cloudflare.com/ajax/libs/mermaid/10.9.1/mermaid.min.js";
            script.async = true;
            script.onload = () => res();
            script.onerror = () => rej(new Error("Failed to load mermaid"));
            document.head.appendChild(script);
          });
          window.mermaid!.initialize({
            startOnLoad: false,
            theme: "dark",
            themeVariables: {
              darkMode: true,
              primaryColor: theme.surfaceRaised,
              primaryBorderColor: theme.accent,
              primaryTextColor: theme.text,
              lineColor: theme.accent,
              secondaryColor: theme.surface,
              tertiaryColor: theme.bg,
            },
          });
        }

        const id = `mermaid-${Date.now()}`;
        const { svg: rendered } = await window.mermaid!.render(id, code);
        if (!cancelled) {
          setSvg(rendered);
          setError(null);
        }
      } catch (err) {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : "Render failed");
          setSvg(null);
        }
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [code]);

  if (error) {
    return (
      <div
        style={{
          marginTop: 12,
          padding: 12,
          fontFamily: font.mono,
          fontSize: 11,
          color: theme.danger,
          background: "rgba(192,57,43,0.08)",
          border: `1px solid rgba(192,57,43,0.2)`,
          borderRadius: 4,
        }}
      >
        render error: {error}
      </div>
    );
  }

  if (!svg) return null;

  return (
    <div
      ref={ref}
      style={{
        marginTop: 16,
        padding: 20,
        background: theme.surface,
        border: `1px solid ${theme.border}`,
        borderRadius: 4,
        overflowX: "auto",
      }}
      dangerouslySetInnerHTML={{ __html: svg }}
    />
  );
}

// ── Ask Panel (RAG) ────────────────────────────────────────────────────────

function AskPanel() {
  const [question, setQuestion] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<AskEntry[]>([]);

  const handleAsk = useCallback(async () => {
    if (!question.trim()) return;
    setLoading(true);
    setError(null);
    try {
      const res = await apiFetch<{ answer: string; context_count: number }>("/ask", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question: question.trim() }),
      });
      const entry: AskEntry = { q: question.trim(), a: res.answer, context: res.context_count };
      setHistory((h) => [entry, ...h]);
      setQuestion("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }, [question]);

  return (
    <div style={{ padding: 24, maxWidth: 720 }}>
      <SectionLabel>ask the catalog</SectionLabel>
      <div style={{ display: "flex", gap: 10, marginBottom: 20, marginTop: 8 }}>
        <input
          type="text"
          placeholder="e.g. Which services depend on Kafka?"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && handleAsk()}
          style={{ ...baseInput, flex: 1 }}
          onFocus={(e) => (e.currentTarget.style.borderColor = theme.borderActive)}
          onBlur={(e) => (e.currentTarget.style.borderColor = theme.border)}
        />
        <button
          onClick={handleAsk}
          disabled={loading || !question.trim()}
          style={{
            padding: "10px 22px",
            fontFamily: font.mono,
            fontSize: 12,
            background: loading ? theme.surfaceRaised : theme.accent,
            color: loading ? theme.textMuted : "#fff",
            border: "none",
            borderRadius: 4,
            cursor: loading ? "wait" : "pointer",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            transition: "all 0.15s",
            whiteSpace: "nowrap",
          }}
        >
          {loading ? "thinking…" : "ask"}
        </button>
      </div>

      {error && (
        <div
          style={{
            padding: 12,
            fontFamily: font.mono,
            fontSize: 12,
            color: theme.danger,
            background: "rgba(192,57,43,0.08)",
            border: `1px solid rgba(192,57,43,0.2)`,
            borderRadius: 4,
            marginBottom: 16,
          }}
        >
          {error}
        </div>
      )}

      {history.map((entry, i) => (
        <div
          key={i}
          style={{ marginBottom: 20, animation: i === 0 ? "fadeIn 0.3s ease" : undefined }}
        >
          <div
            style={{ fontFamily: font.mono, fontSize: 12, color: theme.textMuted, marginBottom: 8 }}
          >
            <span style={{ color: theme.accentText }}>❯</span> {entry.q}
          </div>
          <div
            style={{
              fontFamily: font.mono,
              fontSize: 13,
              color: theme.text,
              background: theme.surface,
              border: `1px solid ${theme.border}`,
              borderRadius: 4,
              padding: 16,
              lineHeight: 1.65,
              whiteSpace: "pre-wrap",
            }}
          >
            {entry.a}
          </div>
          <div
            style={{ fontFamily: font.mono, fontSize: 10, color: theme.textDim, marginTop: 6 }}
          >
            {entry.context} context doc{entry.context !== 1 ? "s" : ""} used
          </div>
        </div>
      ))}

      {history.length === 0 && !loading && (
        <EmptyState icon="◈" message="ask a question about your architecture" />
      )}
    </div>
  );
}

// ── Ingest Panel ───────────────────────────────────────────────────────────

function IngestPanel({ onIngested }: { onIngested: () => void }) {
  const [dragging, setDragging] = useState(false);
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFile = async (file: File | undefined) => {
    if (!file) return;
    setStatus("uploading…");
    setError(null);

    const form = new FormData();
    form.append("file", file);

    try {
      const res = await apiFetch<{ ingested: string[] }>("/ingest", {
        method: "POST",
        body: form,
      });
      setStatus(`ingested: ${res.ingested.join(", ")}`);
      onIngested();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unknown error");
      setStatus(null);
    }
  };

  return (
    <div style={{ padding: 24, maxWidth: 520 }}>
      <SectionLabel>ingest catalog-info.yaml</SectionLabel>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => {
          e.preventDefault();
          setDragging(false);
          handleFile(e.dataTransfer.files[0]);
        }}
        onClick={() => inputRef.current?.click()}
        style={{
          marginTop: 12,
          border: `2px dashed ${dragging ? theme.accent : theme.border}`,
          borderRadius: 6,
          padding: 40,
          textAlign: "center",
          fontFamily: font.mono,
          fontSize: 13,
          color: dragging ? theme.accentText : theme.textMuted,
          cursor: "pointer",
          transition: "all 0.2s",
          background: dragging ? theme.accentGlow : "transparent",
        }}
      >
        drop a catalog-info.yaml here
        <br />
        <span style={{ fontSize: 11, color: theme.textDim }}>or click to browse</span>
        <input
          ref={inputRef}
          type="file"
          accept=".yaml,.yml"
          style={{ display: "none" }}
          onChange={(e) => handleFile(e.target.files?.[0])}
        />
      </div>

      {status && (
        <div
          style={{ marginTop: 14, fontFamily: font.mono, fontSize: 12, color: theme.accentText }}
        >
          ✓ {status}
        </div>
      )}
      {error && (
        <div style={{ marginTop: 14, fontFamily: font.mono, fontSize: 12, color: theme.danger }}>
          ✗ {error}
        </div>
      )}
    </div>
  );
}

// ── App ────────────────────────────────────────────────────────────────────

type View = "catalog" | "ask" | "ingest";

export default function App() {
  const [services, setServices] = useState<Service[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [view, setView] = useState<View>("catalog");
  const [loading, setLoading] = useState(true);

  const fetchServices = useCallback(() => {
    setLoading(true);
    apiFetch<Service[]>("/services")
      .then(setServices)
      .catch(() => setServices([]))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    fetchServices();
  }, [fetchServices]);

  const navItems: { key: View; label: string }[] = [
    { key: "catalog", label: "catalog" },
    { key: "ask", label: "ask" },
    { key: "ingest", label: "ingest" },
  ];

  return (
    <div
      style={{
        background: theme.bg,
        color: theme.text,
        fontFamily: font.mono,
        height: "100vh",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      }}
    >
      {/* Top bar */}
      <header
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          padding: "0 20px",
          height: 48,
          borderBottom: `1px solid ${theme.border}`,
          flexShrink: 0,
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
          <span
            style={{
              fontFamily: font.display,
              fontSize: 15,
              fontWeight: 700,
              letterSpacing: "-0.03em",
              color: theme.accentText,
            }}
          >
            ▣ SERVICE CATALOG
          </span>
          <span
            style={{
              fontSize: 10,
              color: theme.textDim,
              border: `1px solid ${theme.border}`,
              padding: "2px 6px",
              borderRadius: 3,
            }}
          >
            v1.0
          </span>
        </div>

        <nav style={{ display: "flex", gap: 2 }}>
          {navItems.map((n) => (
            <button
              key={n.key}
              onClick={() => setView(n.key)}
              style={{
                padding: "6px 16px",
                fontFamily: font.mono,
                fontSize: 11,
                color: view === n.key ? theme.accentText : theme.textMuted,
                background: view === n.key ? theme.accentGlow : "transparent",
                border: `1px solid ${view === n.key ? theme.borderActive : "transparent"}`,
                borderRadius: 4,
                cursor: "pointer",
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                transition: "all 0.15s",
              }}
            >
              {n.label}
            </button>
          ))}
        </nav>
      </header>

      {/* Body */}
      <main style={{ flex: 1, display: "flex", overflow: "hidden" }}>
        {view === "catalog" && (
          <>
            <ServiceList
              services={services}
              selected={selected}
              onSelect={setSelected}
              loading={loading}
            />
            <DetailPanel serviceName={selected} />
          </>
        )}
        {view === "ask" && <AskPanel />}
        {view === "ingest" && <IngestPanel onIngested={fetchServices} />}
      </main>

      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=IBM+Plex+Sans+Condensed:wght@400;700&display=swap');
        * { margin: 0; padding: 0; box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: ${theme.bg}; }
        ::-webkit-scrollbar-thumb { background: ${theme.border}; border-radius: 3px; }
        ::-webkit-scrollbar-thumb:hover { background: ${theme.textDim}; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(6px); } to { opacity: 1; transform: translateY(0); } }
      `}</style>
    </div>
  );
}
