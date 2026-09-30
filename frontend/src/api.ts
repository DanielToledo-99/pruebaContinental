export type Source = {
  chunk: number;
  text: string;
  quote: string;
  score: number;
};
export type Message = {
  id: string;
  document_id: string;
  role: "user" | "assistant";
  content: string;
  sequence: number;
  created_at: string;
  sources: Source[];
};
export type DocumentInfo = {
  document_id: string;
  session_id: string;
  filename: string;
  status: "processing" | "processed" | "failed";
  chunk_count: number;
};
export type History = {
  session_id: string;
  messages: Message[];
  documents: DocumentInfo[];
};
export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

const base = (import.meta.env.VITE_API_BASE_URL || "/api").replace(/\/$/, "");

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${base}${path}`, {
      ...init,
      signal: AbortSignal.timeout(180_000),
    });
  } catch {
    throw new Error(
      "No pudimos conectar con el servidor. Revisa la conexión y vuelve a intentarlo. Si estabas enviando una pregunta, recarga el historial antes de repetirla.",
    );
  }
  const body = await response.json().catch(() => null);
  if (!response.ok)
    throw new ApiError(
      response.status,
      body?.error?.message || "No se pudo completar la operación.",
    );
  if (!body) throw new Error("El servidor devolvió una respuesta inesperada.");
  return body as T;
}

export const api = {
  createSession: () =>
    request<{ session_id: string }>("/sessions", { method: "POST" }),
  history: (id: string) =>
    request<History>(`/history/${encodeURIComponent(id)}`),
  upload: (sessionId: string, file: File) => {
    const body = new FormData();
    body.append("session_id", sessionId);
    body.append("file", file);
    return request<DocumentInfo>("/documents", { method: "POST", body });
  },
  ask: (sessionId: string, documentId: string, question: string) =>
    request<{ answer: string; sources: Source[]; messages: Message[] }>(
      "/ask",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          document_id: documentId,
          question,
        }),
      },
    ),
};
