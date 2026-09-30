# Verificación de entrega

Ejecutada el 30 de septiembre de 2026 sobre `main` (`a66ea4c`) en un contenedor
Linux: Python 3.12.3, PostgreSQL 16.13 con pgvector 0.6.0, Node.js 22.22 y
Chromium. Las bases se recrearon vacías antes de las pruebas.

## Resultados

| Verificación | Resultado |
| --- | --- |
| GitHub Actions en `main` ([run #4](https://github.com/DanielToledo-99/pruebaContinetal/actions/runs/36747221884)) | **Correcto**: backend y frontend |
| `alembic upgrade head` sobre base vacía | Migración `0001`: 4 tablas y extensión `vector` |
| `alembic check` | Sin diferencias con los modelos |
| pytest sin base de datos (fakes) | 56 passed, 4 skipped |
| pytest con `TEST_DATABASE_URL` (PostgreSQL real) | **60 passed** |
| Ruff, Black, isort | Sin errores (Black: 43 archivos) |
| mypy sobre `app/` | Sin errores (32 archivos) |
| `npm ci` + `npm run build` | TypeScript y Vite correctos |
| ESLint (`--max-warnings 0`) y Prettier | Sin errores ni avisos |
| Playwright con API simulada | **6 passed**, escritorio y móvil |
| `docker compose config --quiet` | Correcto (requiere `.env`) |
| Flujo completo con navegador real, sin API simulada | **Correcto** (detalle abajo) |

La suite emite un aviso de deprecación de Starlette sobre TestClient/httpx, sin
errores de ejecución.

## Flujo completo con la pila real

Navegador Chromium → Vite (proxy `/api`) → FastAPI → PostgreSQL/pgvector, sin
`OPENAI_API_KEY` y con `LLM_PROVIDER=ollama`. El modelo se sustituyó por un
servidor que implementa `/api/embed` y `/api/chat` de Ollama con embeddings de
bolsa de palabras (por eso se usó `RETRIEVAL_MIN_SCORE=0.05`), porque la red del
entorno no permite descargar Ollama.

| Paso | Resultado |
| --- | --- |
| Abrir la aplicación | Sesión creada y guardada |
| Subir `samples/proyecto_agua.txt` | «Documento procesado correctamente», 1 fragmento |
| «¿Cuál es el presupuesto aprobado?» | «El presupuesto aprobado es de 15 000 soles.» con la fuente del fragmento 1 |
| «¿Quién ganó el Mundial de fútbol de 2018?» | «No encuentro esa información en el documento cargado.» |
| Subir un `.pdf` que no es PDF | Error visible: «El contenido del archivo no corresponde a un PDF.» |
| Subir un PDF cifrado con AES y solo contraseña de propietario | Procesado; la pregunta sobre su contenido responde con cita |
| Recargar la página | 6 mensajes y documento activo restaurados |
| Reiniciar el backend y abrir un navegador nuevo en móvil | Conversación recuperada por identificador: 8 mensajes |
| Nueva pregunta en móvil | Respuesta correcta; sin desbordamiento horizontal |
| `POST /ask` solo con sesión y pregunta | Usa el último documento procesado e informa `document_id` |
| `GET /history`, `/docs`, `/health` | Secuencias 0..7 en orden; 200; `{"status":"ok"}` |
| Errores: sesión inexistente, UUID inválido, `.exe` | 404, 422 y 415 con formato `{"error": ...}` |
| Log del backend | Sin errores inesperados |

Con la configuración por defecto (`LLM_PROVIDER=openai`) y sin clave, el backend
avisa al arrancar y la carga devuelve 502 «Configura OPENAI_API_KEY en el backend
para procesar.»; preguntar sin documentos devuelve 409 `NO_PROCESSED_DOCUMENT`.

## Alcance de las pruebas automáticas

- Documentos: PDF/TXT, UTF-8, archivos vacíos, MIME/extensión, tamaño, PDF sin
  texto, PDF con solo contraseña de propietario frente a PDF que exige contraseña,
  límite de texto y chunking con solapamiento.
- Casos de uso: propiedad del documento por sesión, documento por defecto en
  `/ask`, cambio de espacio de embeddings, abstención sin contexto, citas inventadas
  frente a citas con variaciones tipográficas, fallo del proveedor y cargas
  fallidas o canceladas marcadas como `failed`.
- API: formato de errores, errores 500 sin detalles y con CORS, documentación,
  healthcheck, cuerpo grande sin Content-Length y elección de proveedores según
  la configuración.
- Adaptadores: contrato HTTP de OpenAI (salida estructurada, `store=False`, orden
  de embeddings) y de Ollama (JSON schema, lotes de embeddings, respuestas
  inválidas).
- PostgreSQL real: ocho turnos concurrentes (16 mensajes), rollback, aislamiento
  y umbral de búsqueda vectorial, y carga/pregunta/historial por HTTP al recrear
  la aplicación.
- Navegador con API simulada: archivo → pregunta → fuentes → recarga → pregunta
  sin respuesta; recuperación tras fallo de red y reintento de una carga fallida.

## Verificación anterior con Docker

La versión inicial (`550c664`) se verificó en Docker Desktop: `docker compose up
--build -d --wait` con los tres servicios saludables, frontend y proxy `/api/health`
respondiendo, y Playwright contra el frontend servido por Nginx. En este entorno no
hay daemon de Docker, así que **las imágenes no se reconstruyeron con los cambios
actuales**; conviene repetir `docker compose up --build` antes de la entrega.

## Pendiente que requiere configuración del usuario

- **No se ejecutaron llamadas reales a OpenAI ni a modelos reales de Ollama.** Las
  pruebas usan fakes o un servidor simulado y no acreditan la calidad semántica de
  las respuestas. Tras configurar `OPENAI_API_KEY` u Ollama, hacer la prueba manual
  del README con `samples/proyecto_agua.txt` y un PDF con texto seleccionable.
- El umbral de similitud no fue calibrado con un corpus real y depende del modelo
  de embeddings.
- Los controles de grounding reducen alucinaciones, pero una cita válida no
  demuestra que todas las afirmaciones sean correctas.

## Cómo repetir

Desde la raíz, tras copiar `.env.example` a `.env`:

```bash
docker compose config --quiet
docker compose up --build -d --wait
make test-postgres
make lint
```

Desde `frontend/`:

```bash
npm ci
npm run build
npm run lint
npx playwright install chromium
E2E_BASE_URL=http://localhost:3000 npm run test:e2e
```

Los puertos quedan limitados a localhost. Las capturas y traces de Playwright se
guardan en `frontend/test-results/`, excluido de Git. `.env`, `.venv`, `node_modules`
y artefactos de compilación también están excluidos.
