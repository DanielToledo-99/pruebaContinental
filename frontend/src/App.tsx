import { useCallback, useEffect, useRef, useState } from "react";
import type { ChangeEvent, FormEvent, KeyboardEvent } from "react";
import {
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Check,
  CheckCircle2,
  ChevronDown,
  Copy,
  FileText,
  History as HistoryIcon,
  LoaderCircle,
  MessageSquare,
  Plus,
  ShieldCheck,
  Sparkles,
  Upload,
  X,
} from "lucide-react";
import { api, ApiError } from "./api";
import type { DocumentInfo, History, Message, Source } from "./api";

const SESSION_KEY = "document-ai-session";
const DOCUMENT_KEY = "document-ai-document";
const suggestions = [
  "¿Cuál es el objetivo principal?",
  "Resume los puntos más importantes.",
  "¿Qué conclusiones presenta?",
];
const uuidPattern =
  /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
const readSaved = (key: string) => {
  try {
    return localStorage.getItem(key) || "";
  } catch {
    return "";
  }
};

export default function App() {
  const [sessionId, setSessionId] = useState("");
  const [documents, setDocuments] = useState<DocumentInfo[]>([]);
  const [activeId, setActiveId] = useState("");
  const [messages, setMessages] = useState<Message[]>([]);
  const [file, setFile] = useState<File | null>(null);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState<"loading" | "upload" | "ask" | null>(
    "loading",
  );
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [dragging, setDragging] = useState(false);
  const [restoreId, setRestoreId] = useState("");
  const [showRestore, setShowRestore] = useState(false);
  const [copied, setCopied] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const textarea = useRef<HTMLTextAreaElement>(null);
  const bottom = useRef<HTMLDivElement>(null);
  const initialized = useRef(false);
  const active = documents.find((doc) => doc.document_id === activeId);
  const ready = active?.status === "processed";

  const save = (key: string, value: string) => {
    try {
      localStorage.setItem(key, value);
    } catch {
      setNotice(
        "El navegador no permite guardar la sesión. Copia su identificador para recuperarla después.",
      );
    }
  };

  const applyHistory = useCallback((history: History) => {
    setSessionId(history.session_id);
    setMessages(history.messages);
    setDocuments(history.documents);
    const saved = readSaved(DOCUMENT_KEY);
    const selected =
      history.documents.find(
        (doc) => doc.document_id === saved && doc.status === "processed",
      ) || history.documents.filter((doc) => doc.status === "processed").at(-1);
    setActiveId(selected?.document_id || "");
    save(SESSION_KEY, history.session_id);
  }, []);

  const initialize = useCallback(async () => {
    setBusy("loading");
    setError("");
    try {
      const saved = readSaved(SESSION_KEY);
      if (saved && uuidPattern.test(saved)) {
        try {
          applyHistory(await api.history(saved));
          return;
        } catch (err) {
          if (!(err instanceof ApiError && err.status === 404)) throw err;
          setNotice(
            "La sesión guardada ya no existe. Creamos una nueva para ti.",
          );
        }
      }
      const session = await api.createSession();
      applyHistory({ ...session, messages: [], documents: [] });
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }, [applyHistory]);

  useEffect(() => {
    if (!initialized.current) {
      initialized.current = true;
      void initialize();
    }
  }, [initialize]);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [messages, busy]);

  function chooseFile(selected?: File) {
    if (!selected || busy) return;
    setError("");
    setNotice("");
    if (!/\.(pdf|txt|docx)$/i.test(selected.name)) {
      setError("Selecciona un archivo PDF, TXT o Word (.docx).");
      return;
    }
    if (selected.size === 0) {
      setError("El archivo está vacío.");
      return;
    }
    if (selected.size > 10 * 1024 * 1024) {
      setError("El tamaño máximo es 10 MB.");
      return;
    }
    setFile(selected);
  }

  async function upload(event: FormEvent) {
    event.preventDefault();
    if (!file || !sessionId || busy) return;
    setBusy("upload");
    setError("");
    setNotice("");
    try {
      const document = await api.upload(sessionId, file);
      setDocuments((current) => [...current, document]);
      setActiveId(document.document_id);
      save(DOCUMENT_KEY, document.document_id);
      setFile(null);
      if (fileInput.current) fileInput.current.value = "";
      setNotice("Documento procesado correctamente.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function ask(event: FormEvent) {
    event.preventDefault();
    const text = question.trim();
    if (!text || !ready || busy) return;
    setBusy("ask");
    setError("");
    setNotice("");
    try {
      const result = await api.ask(sessionId, activeId, text);
      setMessages((current) => [...current, ...result.messages]);
      setQuestion("");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
      requestAnimationFrame(() => textarea.current?.focus());
    }
  }

  async function newSession() {
    if (busy) return;
    setBusy("loading");
    setError("");
    setNotice("");
    try {
      const session = await api.createSession();
      applyHistory({ ...session, messages: [], documents: [] });
      setFile(null);
      setQuestion("");
      setShowRestore(false);
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function restore(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    if (!uuidPattern.test(restoreId.trim())) {
      setError("Introduce un identificador de sesión válido.");
      return;
    }
    setBusy("loading");
    setError("");
    setNotice("");
    try {
      applyHistory(await api.history(restoreId.trim()));
      setQuestion("");
      setFile(null);
      setShowRestore(false);
      setNotice("Conversación recuperada.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function refreshHistory() {
    if (!sessionId || busy) return;
    setBusy("loading");
    setError("");
    try {
      applyHistory(await api.history(sessionId));
      setNotice("Historial actualizado.");
    } catch (err) {
      setError(errorText(err));
    } finally {
      setBusy(null);
    }
  }

  async function copySession() {
    try {
      await navigator.clipboard.writeText(sessionId);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      setError(
        "No se pudo copiar. Selecciona y copia el identificador de sesión manualmente.",
      );
    }
  }

  function onQuestionKey(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (
      event.key === "Enter" &&
      !event.shiftKey &&
      !event.nativeEvent.isComposing
    ) {
      event.preventDefault();
      event.currentTarget.form?.requestSubmit();
    }
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="/"
          aria-label="Document AI Assistant, inicio"
        >
          <span className="brand-mark">
            <BookOpen size={23} />
          </span>
          <span>
            Document<span className="brand-ai">AI</span>
            <small>DE TUS DOCUMENTOS A RESPUESTAS</small>
          </span>
        </a>
        <div className="workspace-label">TU ESPACIO DE TRABAJO</div>
        <div className="nav-active">
          <MessageSquare size={18} /> Asistente de documentos <span>01</span>
        </div>
        <button
          className="new-session"
          onClick={() => void newSession()}
          disabled={!!busy}
        >
          <Plus size={17} /> Nueva conversación
        </button>
        <section className="document-panel" aria-labelledby="document-heading">
          <div className="section-label">
            <h2 id="document-heading">DOCUMENTOS</h2>
            <span>
              {documents
                .filter((doc) => doc.status === "processed")
                .length.toString()
                .padStart(2, "0")}
            </span>
          </div>
          {documents
            .filter((doc) => doc.status === "processed")
            .map((doc) => (
              <button
                key={doc.document_id}
                disabled={!!busy}
                onClick={() => {
                  setActiveId(doc.document_id);
                  save(DOCUMENT_KEY, doc.document_id);
                }}
                className={`document-item ${doc.document_id === activeId ? "selected" : ""}`}
              >
                <FileText size={20} />
                <span>
                  <strong>{doc.filename}</strong>
                  <small>
                    {doc.chunk_count} fragmentos · Listo para consultar
                  </small>
                </span>
                {doc.document_id === activeId && <Check size={15} />}
              </button>
            ))}
          {!documents.some((doc) => doc.status === "processed") && (
            <p className="no-documents">
              Tu próximo hallazgo empieza
              <br />
              con un documento.
            </p>
          )}
          <form onSubmit={upload}>
            <label
              className={`dropzone ${dragging ? "dragging" : ""} ${busy ? "disabled" : ""}`}
              onDragOver={(event) => {
                event.preventDefault();
                if (!busy) setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                chooseFile(event.dataTransfer.files[0]);
              }}
            >
              <input
                ref={fileInput}
                type="file"
                accept=".pdf,.txt,.docx,application/pdf,text/plain,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                disabled={!!busy || !sessionId}
                onChange={(event: ChangeEvent<HTMLInputElement>) =>
                  chooseFile(event.target.files?.[0])
                }
                aria-label="Seleccionar documento"
              />
              <span className="upload-symbol">
                <Upload size={20} />
              </span>
              <strong>{file ? file.name : "Añade un documento"}</strong>
              <span>
                Arrastra aquí o <u>selecciona un archivo</u>
              </span>
              <small>PDF, TXT o Word (.docx) · Máximo 10 MB</small>
            </label>
            <button
              className="upload-button"
              disabled={!file || !!busy || !sessionId}
            >
              {busy === "upload" ? (
                <>
                  <LoaderCircle size={16} className="spin" /> Procesando
                  documento...
                </>
              ) : (
                <>
                  Subir documento <ArrowUp size={16} />
                </>
              )}
            </button>
          </form>
          {documents.some((doc) => doc.status !== "processed") && (
            <p className="muted-small">
              Hay cargas que no se completaron. Puedes volver a subir el
              archivo.
            </p>
          )}
        </section>
        <div className="sidebar-bottom">
          <div className="session-label">
            <span className={`status-dot ${sessionId ? "" : "offline"}`} />
            {busy === "loading"
              ? "Conectando sesión"
              : sessionId
                ? "Sesión guardada"
                : "Sin conexión"}
          </div>
          {sessionId && (
            <div className="session-id">
              <code title={sessionId}>{sessionId}</code>
              <button
                aria-label="Copiar identificador de sesión"
                onClick={() => void copySession()}
              >
                {copied ? <Check size={15} /> : <Copy size={15} />}
              </button>
            </div>
          )}
          <button
            className="restore-button"
            onClick={() => setShowRestore(!showRestore)}
            disabled={!!busy}
          >
            <HistoryIcon size={16} /> Recuperar conversación{" "}
            <ChevronDown size={14} />
          </button>
          {showRestore && (
            <form className="restore-form" onSubmit={restore}>
              <label htmlFor="restore">Identificador de sesión</label>
              <input
                id="restore"
                value={restoreId}
                onChange={(event) => setRestoreId(event.target.value)}
                placeholder="Pega el identificador"
              />
              <button disabled={!!busy || !restoreId.trim()}>
                Recuperar <ArrowRight size={14} />
              </button>
            </form>
          )}
          <div className="private-note">
            <ShieldCheck size={15} />
            <span>
              Respuestas basadas en tus archivos.
              <br />
              Tú conservas el contexto.
            </span>
          </div>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <span className="breadcrumb">
              Espacio de trabajo <span>/</span>
            </span>
            <h1>Document AI Assistant</h1>
          </div>
          <span className="context-badge">
            <span className="status-dot" /> Contexto del documento
          </span>
        </header>
        <div className="conversation-top">
          <div>
            <span className="eyebrow">MENOS BÚSQUEDA, MÁS CLARIDAD</span>
            <h2>
              Conversa con tus documentos<span>.</span>
            </h2>
            <p>Pregunta, descubre y encuentra la fuente de cada respuesta.</p>
          </div>
          <span className="workspace-icon">
            <Sparkles size={23} />
          </span>
        </div>

        {error && (
          <div className="alert error" role="alert">
            <span>{error}</span>
            {!sessionId && !busy && (
              <button onClick={() => void initialize()}>Reintentar</button>
            )}
            <button aria-label="Cerrar error" onClick={() => setError("")}>
              <X size={16} />
            </button>
          </div>
        )}
        {notice && (
          <div className="alert success" role="status">
            <CheckCircle2 size={17} />
            <span>{notice}</span>
            <button aria-label="Cerrar aviso" onClick={() => setNotice("")}>
              <X size={16} />
            </button>
          </div>
        )}

        <section className="chat-panel" aria-label="Conversación">
          <div className="chat-toolbar">
            <span>
              <span className="status-dot" />
              {active ? active.filename : "Tu conversación"}
            </span>
            <div>
              <span className="toolbar-status">
                {busy === "upload"
                  ? "Procesando"
                  : ready
                    ? "Documento listo"
                    : "Esperando documento"}
              </span>
              {sessionId && (
                <button
                  title="Actualizar historial"
                  aria-label="Actualizar historial"
                  disabled={!!busy}
                  onClick={() => void refreshHistory()}
                >
                  <HistoryIcon size={17} />
                </button>
              )}
            </div>
          </div>
          <div
            className="messages"
            role="log"
            aria-live="polite"
            aria-relevant="additions"
          >
            {messages.length === 0 && (
              <div className="welcome">
                <div className="welcome-art">
                  <div className="art-ring" />
                  <div className="art-file">
                    <FileText size={48} strokeWidth={1.1} />
                    <span>
                      <Sparkles size={20} />
                    </span>
                  </div>
                  <span className="art-dot one" />
                  <span className="art-dot two" />
                </div>
                <span className="welcome-kicker">
                  TU DOCUMENTO TIENE LAS RESPUESTAS
                </span>
                <h3>
                  {busy === "loading"
                    ? "Preparando tu espacio..."
                    : ready
                      ? "¿Qué quieres descubrir?"
                      : "Una nueva forma de leer."}
                </h3>
                <p>
                  {ready
                    ? "Haz tu primera pregunta. Buscaré la información en el documento y te mostraré las fuentes."
                    : "Sube un documento y deja que las preguntas te guíen. Las respuestas estarán conectadas a su contenido."}
                </p>
                <div className="welcome-steps">
                  <span>
                    <b>1</b> Sube tu archivo
                  </span>
                  <ArrowRight size={14} />
                  <span>
                    <b>2</b> Haz una pregunta
                  </span>
                  <ArrowRight size={14} />
                  <span>
                    <b>3</b> Explora las fuentes
                  </span>
                </div>
              </div>
            )}
            {messages.map((message) => (
              <article className={`message ${message.role}`} key={message.id}>
                <div className="avatar">
                  {message.role === "assistant" ? <Sparkles size={16} /> : "TÚ"}
                </div>
                <div className="message-body">
                  <div className="message-meta">
                    <strong>
                      {message.role === "assistant" ? "Document AI" : "Tú"}
                    </strong>
                    <time dateTime={message.created_at}>
                      {new Date(message.created_at).toLocaleTimeString("es", {
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </time>
                  </div>
                  <p>{message.content}</p>
                  {message.sources.length > 0 && (
                    <Sources
                      sources={message.sources}
                      filename={
                        documents.find(
                          (doc) => doc.document_id === message.document_id,
                        )?.filename || "Documento"
                      }
                    />
                  )}
                </div>
              </article>
            ))}
            {busy === "ask" && (
              <div className="thinking" role="status">
                <LoaderCircle className="spin" size={17} />
                <span>Consultando documento...</span>
              </div>
            )}
            <div ref={bottom} />
          </div>
          <div className="composer-area">
            {messages.length === 0 && (
              <div className="suggestions">
                {suggestions.map((suggestion) => (
                  <button
                    key={suggestion}
                    disabled={!ready || !!busy}
                    onClick={() => {
                      setQuestion(suggestion);
                      textarea.current?.focus();
                    }}
                  >
                    {suggestion} <ArrowRight size={13} />
                  </button>
                ))}
              </div>
            )}
            <form
              className={`composer ${ready ? "" : "inactive"}`}
              onSubmit={ask}
            >
              <label className="sr-only" htmlFor="question">
                Pregunta sobre el documento
              </label>
              <textarea
                ref={textarea}
                id="question"
                rows={2}
                maxLength={2000}
                value={question}
                onChange={(event) => setQuestion(event.target.value)}
                onKeyDown={onQuestionKey}
                disabled={!ready || !!busy}
                placeholder={
                  ready
                    ? "¿Qué te gustaría saber sobre este documento?"
                    : "Sube un documento para empezar a conversar..."
                }
              />
              <div className="composer-footer">
                <span>
                  <FileText size={14} />
                  {active ? active.filename : "Ningún documento seleccionado"}
                </span>
                <div>
                  <small>
                    {question.length > 1800
                      ? `${question.length}/2000`
                      : "↵ para enviar"}
                  </small>
                  <button
                    type="submit"
                    aria-label="Enviar pregunta"
                    disabled={!ready || !question.trim() || !!busy}
                  >
                    {busy === "ask" ? (
                      <LoaderCircle size={18} className="spin" />
                    ) : (
                      <ArrowUp size={19} />
                    )}
                  </button>
                </div>
              </div>
            </form>
            <p className="grounding-note">
              <ShieldCheck size={13} /> Si la información no está en el
              documento, te lo diré. Revisa las fuentes.
            </p>
          </div>
        </section>
        <footer className="page-footer">
          <span>LECTURA CON CONTEXTO. RESPUESTAS CON FUENTES.</span>
          <span>
            PDF, TXT & DOCX <ArrowDown size={12} />
          </span>
        </footer>
      </main>
    </div>
  );
}

function Sources({
  sources,
  filename,
}: {
  sources: Source[];
  filename: string;
}) {
  const count = sources.reduce(
    (total, source) => total + Math.max(source.quotes.length, 1),
    0,
  );
  return (
    <details className="sources">
      <summary>
        <BookOpen size={14} />
        <span>
          {count} {count === 1 ? "cita" : "citas"} · {filename}
        </span>
        <ChevronDown size={14} />
      </summary>
      {sources.map((source) => (
        <div className="source" key={source.chunk}>
          <span className="source-label">FRAGMENTO {source.chunk}</span>
          {source.quotes.map((quote) => (
            <blockquote key={quote}>{quote}</blockquote>
          ))}
          <details className="source-context">
            <summary>Ver el fragmento completo</summary>
            <p>{highlight(source.text, source.quotes)}</p>
          </details>
        </div>
      ))}
    </details>
  );
}

// Marks each quote inside its fragment; quotes are exact excerpts whose
// whitespace may differ from the fragment, and " […] " joins elided parts.
function highlight(text: string, quotes: string[]) {
  const pattern = quotes
    .flatMap((quote) => quote.split(" […] "))
    .map((part) =>
      part
        .split(/\s+/)
        .filter(Boolean)
        .map((word) => word.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"))
        .join("\\s+"),
    )
    .filter(Boolean)
    .join("|");
  if (!pattern) return text;
  return text
    .split(new RegExp(`(${pattern})`, "i"))
    .map((part, index) => (index % 2 ? <mark key={index}>{part}</mark> : part));
}

function errorText(error: unknown) {
  return error instanceof Error
    ? error.message
    : "Ocurrió un error inesperado.";
}
