import { expect, test } from "@playwright/test";
import type { DocumentInfo, Message } from "../src/api";

const sessionId = "b25ee02d-2d50-4b47-9258-39af6d5344a2";
const documentId = "ac1f207e-7f20-442b-9ea8-ad78c10c1afe";

test("upload, ask, sources, refusal and persistent history", async ({
  page,
}) => {
  let documents: DocumentInfo[] = [];
  let messages: Message[] = [];
  await page.route("**/api/**", async (route) => {
    const path = new URL(route.request().url()).pathname;
    let response: object = {};
    if (path === "/api/sessions") response = { session_id: sessionId };
    if (path.startsWith("/api/history/"))
      response = { session_id: sessionId, documents, messages };
    if (path === "/api/documents") {
      documents = [
        {
          document_id: documentId,
          session_id: sessionId,
          filename: "proyecto.txt",
          status: "processed",
          chunk_count: 1,
        },
      ];
      response = documents[0];
    }
    if (path === "/api/ask") {
      const question = route.request().postDataJSON().question as string;
      const unknown = question.includes("mundial");
      const answer = unknown
        ? "No encuentro esa información en el documento cargado."
        : "El objetivo es reducir el consumo de agua en un 20%.";
      const sources = unknown
        ? []
        : [{ chunk: 1, text: answer, quote: answer, score: 0.9 }];
      const pair: Message[] = [
        {
          id: `user-${messages.length}`,
          document_id: documentId,
          role: "user",
          content: question,
          sequence: messages.length,
          created_at: new Date().toISOString(),
          sources: [],
        },
        {
          id: `assistant-${messages.length}`,
          document_id: documentId,
          role: "assistant",
          content: answer,
          sequence: messages.length + 1,
          created_at: new Date().toISOString(),
          sources,
        },
      ];
      messages = [...messages, ...pair];
      response = { session_id: sessionId, answer, sources, messages: pair };
    }
    await route.fulfill({ json: response });
  });
  await page.goto("/");
  await expect(page.getByText("Sesión guardada")).toBeVisible();
  await expect(
    page.getByRole("button", { name: "Enviar pregunta" }),
  ).toBeDisabled();
  await page.getByLabel("Seleccionar documento").setInputFiles({
    name: "proyecto.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("El objetivo es reducir el consumo de agua en un 20%."),
  });
  await page.getByRole("button", { name: "Subir documento" }).click();
  await expect(
    page.getByText("Documento procesado correctamente."),
  ).toBeVisible();
  await page
    .getByLabel("Pregunta sobre el documento")
    .fill("¿Cuál es el objetivo?");
  await page.getByRole("button", { name: "Enviar pregunta" }).click();
  await expect(page.locator(".assistant .message-body > p")).toHaveText(/20%/);
  await page.getByText("1 fuente del documento").click();
  await expect(page.locator("blockquote")).toContainText("20%");
  await page.reload();
  await expect(page.locator(".message")).toHaveCount(2);
  await expect(page.getByLabel("Pregunta sobre el documento")).toBeEnabled();
  await page
    .getByLabel("Pregunta sobre el documento")
    .fill("¿Quién ganó el mundial?");
  await page.getByRole("button", { name: "Enviar pregunta" }).click();
  await expect(
    page.getByText("No encuentro esa información en el documento cargado."),
  ).toBeVisible();
  await page.screenshot({
    path: `test-results/chat-${test.info().project.name}.png`,
    fullPage: true,
  });
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth > window.innerWidth,
  );
  expect(overflow).toBe(false);
});

test("network failure keeps saved session and permits retry", async ({
  page,
}) => {
  await page.addInitScript(
    (id) => localStorage.setItem("document-ai-session", id),
    sessionId,
  );
  let attempts = 0;
  await page.route("**/api/history/**", async (route) => {
    attempts++;
    if (attempts === 1) await route.abort();
    else
      await route.fulfill({
        json: { session_id: sessionId, documents: [], messages: [] },
      });
  });
  await page.goto("/");
  await expect(page.getByRole("alert")).toContainText("No pudimos conectar");
  await page.getByRole("button", { name: "Reintentar" }).click();
  await expect(page.getByText("Sesión guardada")).toBeVisible();
  expect(
    await page.evaluate(() => localStorage.getItem("document-ai-session")),
  ).toBe(sessionId);
});

test("failed upload shows an error and preserves the selected file", async ({
  page,
}) => {
  await page.route("**/api/sessions", (route) =>
    route.fulfill({ json: { session_id: sessionId } }),
  );
  await page.route("**/api/documents", (route) =>
    route.fulfill({
      status: 502,
      json: {
        error: {
          code: "AI_PROVIDER_ERROR",
          message: "El proveedor de IA no está disponible.",
        },
      },
    }),
  );
  await page.goto("/");
  await expect(page.getByText("Sesión guardada")).toBeVisible();
  await page.getByLabel("Seleccionar documento").setInputFiles({
    name: "doc.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("contenido"),
  });
  await page.getByRole("button", { name: "Subir documento" }).click();
  await expect(page.getByRole("alert")).toContainText("proveedor de IA");
  await expect(
    page.getByRole("button", { name: "Subir documento" }),
  ).toBeEnabled();
  await expect(
    page.getByRole("button", { name: "Enviar pregunta" }),
  ).toBeDisabled();
});
