# Document AI Assistant

Asistente para conversar con documentos PDF y TXT, con respuestas fundamentadas en
fragmentos del archivo, citas verificables e historial persistido por sesión.
Desafío Full Stack implementado como un monolito modular.

## Descripción

1. Crea o recupera una sesión.
2. Sube un PDF con texto seleccionable o un TXT UTF-8.
3. El backend extrae texto, lo divide en fragmentos y guarda sus embeddings.
4. Haz una pregunta: el sistema recupera contexto **solo del documento elegido**.
5. Recibe una respuesta con fuentes, o la frase:
   **«No encuentro esa información en el documento cargado.»**
6. Recarga la página o introduce el `session_id` para recuperar la conversación.

La aplicación arranca sin clave de IA. Para procesar archivos y responder realmente
necesita `OPENAI_API_KEY` válida y acceso a los modelos configurados, o bien
`LLM_PROVIDER=ollama` con Ollama local (ver [Modo local con Ollama](#modo-local-con-ollama)).
Las pruebas usan fakes o transporte HTTP simulado y **no consumen OpenAI**.

## Arquitectura

```mermaid
flowchart LR
    UI[React + TypeScript] --> API[FastAPI: rutas y validación]
    API --> UC[Application: casos de uso]
    UC --> D[Domain: entidades y errores]
    UC --> P[Puertos: Repository / UnitOfWork / LLM / Embeddings / VectorStore]
    I[Infraestructura: SQLAlchemy / pgvector / OpenAI / pypdf] -. implementa .-> P
    I --> DB[(PostgreSQL + pgvector)]
    I --> OA[OpenAI u Ollama]
```

Las dependencias apuntan hacia el dominio y la aplicación. Los casos de uso no
importan FastAPI, SQLAlchemy ni OpenAI. `app/main.py` compone las implementaciones.
Las rutas se limitan al transporte HTTP y delegan el trabajo.

```text
backend/
  app/
    domain/                 # dataclasses y excepciones
    application/            # puertos, chunking, grounding y casos de uso
    infrastructure/
      database/             # modelos SQLAlchemy y Unit of Work
      repositories/         # sesiones, documentos e historial
      vector_store/         # búsqueda coseno con pgvector
      document_processing/  # parsers PDF y TXT
      llm/                  # adaptadores OpenAI/Ollama y prompt
    api/                    # rutas, esquemas, DI, middleware y errores
    core/config.py          # Pydantic Settings
    main.py                 # composition root y lifespan
  migrations/               # Alembic: esquema versionado
  tests/{unit,integration}/
  pyproject.toml
  requirements.lock         # versiones verificadas, usadas como constraints
  Dockerfile
frontend/
  src/{App.tsx,api.ts,styles.css}
  e2e/                      # Playwright: escritorio y móvil
  nginx.conf
  Dockerfile
samples/proyecto_agua.txt
docker-compose.yml
.env.example
Makefile
.github/workflows/ci.yml
DECISION_LOG.md
docs/INTERVIEW_GUIDE.md
docs/VERIFICATION.md
```

### Modelo de datos

| Tabla | Campos principales | Relación |
| --- | --- | --- |
| `sessions` | UUID, fecha, próximo número de secuencia | 1:N documentos y mensajes |
| `documents` | UUID, sesión, filename, MIME, fecha, estado, cantidad de chunks, espacio de embeddings | 1:N chunks |
| `document_chunks` | UUID, documento, índice, contenido, vector | Único `(document_id, chunk_index)` |
| `messages` | UUID, sesión, documento, rol, contenido, fecha, secuencia, fuentes JSONB | Único `(session_id, sequence)` |

El historial se ordena por secuencia de confirmación. Un bloqueo breve de la fila
de sesión asigna dos números consecutivos a cada pregunta/respuesta; ambos mensajes
se confirman en una transacción. No se mantiene un bloqueo durante llamadas de IA.

## Tecnologías

- Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2 y asyncpg.
- PostgreSQL 16 + pgvector; migraciones Alembic.
- OpenAI Responses API con salida estructurada y embeddings separados.
- React, TypeScript, Vite, fetch, Lucide y CSS responsive.
- pytest, Ruff, Black, isort, mypy, ESLint y Playwright.
- Docker Compose; Nginx sirve el frontend y redirige `/api` al backend.

## Requisitos

- Docker Engine/Desktop y Docker Compose v2 o superior.
- Una API key de OpenAI para el flujo real de IA.
- Puertos 3000, 8000 y 5432 disponibles.
- Para desarrollo sin contenedores: Python 3.12 y Node.js 22.12 o superior.

## Configuración

```bash
git clone https://github.com/DanielToledo-99/pruebaContinetal.git
cd pruebaContinetal
cp .env.example .env
```

Edita `.env` localmente y completa `OPENAI_API_KEY`. No compartas ese archivo ni
introduzcas la clave en el frontend. `.gitignore` excluye `.env` y sus variantes.

## Variables de entorno

| Variable | Valor de ejemplo / finalidad |
| --- | --- |
| `DATABASE_URL` | `postgresql+asyncpg://postgres:postgres@db:5432/document_ai` |
| `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` | Credenciales locales de ejemplo: `postgres`, `postgres`, `document_ai` |
| `OPENAI_API_KEY` | Vacía en el ejemplo; obligatoria para la IA real |
| `OPENAI_MODEL` | `gpt-4o-mini`, configurable |
| `OPENAI_EMBEDDING_MODEL` | `text-embedding-3-small`, configurable |
| `LLM_PROVIDER` | `openai` (defecto) u `ollama` |
| `EMBEDDING_PROVIDER` | `openai` u `ollama`; si no se define, igual a `LLM_PROVIDER` |
| `OLLAMA_BASE_URL`, `OLLAMA_MODEL`, `OLLAMA_EMBEDDING_MODEL` | `http://host.docker.internal:11434`, `qwen2.5-coder:7b`, `bge-m3` |
| `EMBEDDING_DIMENSIONS` | `1536`; cambiar modelo o dimensión requiere volver a cargar documentos |
| `CORS_ORIGINS` | Orígenes separados por comas; localhost:3000 y localhost:5173 |
| `VITE_API_BASE_URL` | `/api`; se aplica al construir el frontend |
| `MAX_UPLOAD_MB` | `10`; límite de backend, la interfaz permite como máximo 10 MB |
| `MAX_TEXT_CHARS`, `MAX_PDF_PAGES` | `200000` y `200` |
| `CHUNK_SIZE`, `CHUNK_OVERLAP` | `800` y `100` caracteres |
| `RETRIEVAL_TOP_K`, `RETRIEVAL_MIN_SCORE` | `4` y `0.25` |
| `AI_TIMEOUT_SECONDS` | `45` por petición al proveedor, máximo un reintento del SDK |

Si cambias usuario, contraseña o base, actualiza también `DATABASE_URL`. Usa
credenciales de desarrollo únicamente. Docker publica los puertos en `127.0.0.1`.

## Ejecutar con Docker

```bash
docker compose up --build
```

O en segundo plano, esperando los healthchecks:

```bash
docker compose up --build -d --wait
docker compose ps
```

- Frontend: <http://localhost:3000>
- Backend: <http://localhost:8000>
- Swagger: <http://localhost:8000/docs>
- Health: <http://localhost:8000/health>

PostgreSQL debe estar saludable antes del backend. El backend ejecuta
`alembic upgrade head` antes de iniciar FastAPI. El frontend espera al backend.
El volumen `postgres_data` conserva sesiones, mensajes y embeddings entre reinicios.

```bash
docker compose logs --tail=100 backend
docker compose down
```

`down` conserva los datos. Si editas `.env`, aplica el cambio con
`docker compose up -d --build`; un simple `restart` no recarga variables.

## Modo local con Ollama

Permite usar la aplicación sin clave de OpenAI: generación y embeddings corren en
Ollama (versión 0.5 o superior, necesaria para la salida con JSON schema).

```bash
ollama pull qwen2.5-coder:7b   # o el modelo de chat que prefieras
ollama pull bge-m3             # embeddings multilingües
```

En `.env`: `LLM_PROVIDER=ollama` y, en CPU, `AI_TIMEOUT_SECONDS=120`. Compose
mapea `host.docker.internal` al host también en Linux; ahí Ollama debe escuchar en
todas las interfaces (`OLLAMA_HOST=0.0.0.0 ollama serve`). Sin Docker, usa
`OLLAMA_BASE_URL=http://localhost:11434`.

Cambiar de proveedor de embeddings cambia el espacio vectorial: los documentos
cargados con el anterior devuelven 409 y hay que subirlos de nuevo. El umbral
`RETRIEVAL_MIN_SCORE` depende del modelo y conviene recalibrarlo.

## Ejecutar sin Docker

Necesitas PostgreSQL 16 con la extensión pgvector disponible. Puedes ejecutar solo
la base con `docker compose up -d --wait db` y desarrollar las aplicaciones localmente.

Backend, desde la raíz:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
cd backend
pip install -c requirements.lock -e '.[dev]'
export DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/document_ai
alembic upgrade head
uvicorn app.main:app --reload --port 8000
```

El backend lee `.env` en la raíz; la variable exportada sustituye `db` por
`localhost`. Las variables del entorno tienen precedencia sobre el archivo.

Frontend, en otra terminal:

```bash
cd frontend
npm ci
cp .env.example .env
npm run dev
```

Abre <http://localhost:5173>. Vite redirige `/api` a `localhost:8000`.
En Docker Nginx redirige a `backend:8000`, un nombre interno que el navegador
no necesita resolver.

## Tests

Unitarios y HTTP con fakes, sin base ni API externa:

```bash
cd backend
pytest -q
```

Desde la raíz, sin instalar Python local:

```bash
make test
```

Pruebas adicionales contra PostgreSQL real: transacciones, ocho escrituras
simultáneas, aislamiento vectorial y flujo HTTP recuperado tras recrear la app.

```bash
make test-postgres
```

Ese comando usa las credenciales locales de ejemplo y una base separada
`document_ai_test`. Si cambias credenciales, ajusta las URLs del comando o ejecuta
pytest manualmente con `TEST_DATABASE_URL`. La suite rechaza bases cuyo nombre no
termine en `_test`. **Solo la base de pruebas se vacía entre pruebas.**

```bash
cd backend
DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/document_ai_test alembic upgrade head
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/document_ai_test pytest -q
```

Pruebas de navegador con API simulada, en escritorio y móvil:

```bash
cd frontend
npm ci
npx playwright install chromium
npm run test:e2e
```

Para verificar la interfaz servida por Docker:

```bash
E2E_BASE_URL=http://localhost:3000 npm run test:e2e
```

Las pruebas de navegador simulan las respuestas de IA y del API; las pruebas de
PostgreSQL verifican persistencia real. Ninguna de ellas acredita calidad semántica
del modelo real. GitHub Actions ejecuta backend, migraciones, PostgreSQL y frontend.

## Lint

```bash
cd backend
ruff check .
black --check .
isort --check-only .
mypy
```

Frontend:

```bash
cd frontend
npm run lint
npm run build
```

También puedes ejecutar `make lint` desde la raíz, usando Docker.

## Formato

```bash
cd backend
isort .
black .
```

```bash
cd frontend
npx prettier --write src e2e '*.ts' '*.js'
```

## API

| Método | Endpoint | Entrada / salida |
| --- | --- | --- |
| POST | `/sessions` | Crea sesión; devuelve `session_id` (201) |
| POST | `/documents` | Multipart: `session_id` + `file`; devuelve `document_id`, estado, nombre y número de chunks (201) |
| POST | `/ask` | JSON: `session_id`, `question` y `document_id` opcional (por defecto, el último documento procesado de la sesión); devuelve respuesta, documento usado, fuentes y los dos mensajes guardados |
| GET | `/history/{session_id}` | Mensajes ordenados y documentos de la sesión |
| GET | `/health` | Conexión a PostgreSQL |

Crear una sesión:

```bash
curl -X POST http://localhost:8000/sessions
```

Sustituye `SESSION_UUID` y `DOCUMENT_UUID` por los identificadores devueltos:

```bash
curl -X POST http://localhost:8000/documents \
  -F 'session_id=SESSION_UUID' \
  -F 'file=@samples/proyecto_agua.txt;type=text/plain'

curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_UUID","document_id":"DOCUMENT_UUID","question":"¿Cuál es el objetivo principal?"}'

# Sin document_id se usa el último documento procesado de la sesión
curl -X POST http://localhost:8000/ask \
  -H 'Content-Type: application/json' \
  -d '{"session_id":"SESSION_UUID","question":"¿Cuál es el presupuesto?"}'

curl http://localhost:8000/history/SESSION_UUID
```

Errores consistentes:

```json
{"error":{"code":"DOCUMENT_NOT_FOUND","message":"El documento no existe en esta sesión."}}
```

400: documento inválido. 404: sesión/documento inexistente. 409: documento pendiente,
sesión sin documentos procesados o espacio de embeddings distinto. 413: tamaño excesivo. 415: formato no soportado.
422: campos/UUID inválidos. 502: proveedor de IA. 500: fallo interno sin detalles sensibles.

## Flujo RAG

```text
PDF/TXT → validación → extracción → normalización → chunks de 800 caracteres
→ solapamiento de 100 → embeddings por lotes → PostgreSQL/pgvector

Pregunta → embedding → similitud coseno filtrada por document_id
→ top 4 con score ≥ 0.25 → prompt + contexto → respuesta estructurada
→ verificar citas textuales → guardar turno atómicamente → mostrar fuentes
```

El score es similitud coseno, **no una probabilidad ni una garantía de veracidad**.
Los parámetros son una base inicial documentada, no una calibración universal.
Se consultan únicamente los fragmentos del documento seleccionado. Las preguntas
son independientes: el historial se muestra y conserva, pero no se usa como contexto
del LLM. Formula preguntas completas en vez de referencias como «¿y él?».

## Manejo de alucinaciones

- Prompt centralizado en `backend/app/infrastructure/llm/prompts.py`.
- Instrucción explícita de no usar conocimiento externo y tratar documentos como
  datos no confiables, no instrucciones.
- Si no hay contexto relevante, no se llama al LLM: se devuelve la frase de ausencia.
- Salida estructurada con `supported`, `answer` y citas de fragmentos.
- Se comprueba que los números de fragmento existan y las citas aparezcan en ellos
  (sin distinguir mayúsculas, espacios, comillas tipográficas ni puntuación final).
- Una respuesta sin respaldo declarado o con citas inválidas se convierte en la
  frase de ausencia. Las fuentes se guardan con el mensaje para recuperarlas después.

Una cita real puede no justificar toda una conclusión. Estas medidas reducen el
riesgo, pero no prueban entailment semántico ni eliminan toda prompt injection.
La interfaz invita a revisar las fuentes y el límite se explica en el ADR-010.

## Prueba manual completa

1. Configura la clave, levanta Compose y abre el frontend.
2. Sube `samples/proyecto_agua.txt`: debe aparecer «Documento procesado correctamente».
3. Pregunta «¿Cuál es el objetivo principal?»; debe mencionar reducir agua en 20%.
4. Expande las fuentes: la cita debe existir literalmente en el archivo.
5. Pregunta «¿Cuál es el presupuesto?»; debe responder 15 000 soles.
6. Pregunta «¿Quién ganó el Mundial de fútbol de 2018?»; debe devolver la frase de ausencia.
7. Copia el identificador de sesión, recarga y confirma que los mensajes y fuentes siguen allí.
8. Crea otra conversación y usa «Recuperar conversación» con el identificador anterior.
9. Consulta `/history/{session_id}` en Swagger: debe mostrar los turnos en orden.
10. Repite la carga con un PDF con texto seleccionable. Un archivo vacío, un formato
    diferente o un PDF escaneado debe producir un error visible y permitir reintentar.
11. Reinicia backend y frontend y vuelve a recuperar el historial; PostgreSQL lo conserva.

## Decisiones técnicas

Consulta [DECISION_LOG.md](DECISION_LOG.md) para las alternativas, motivos y costes
de cada elección. [La guía de entrevista](docs/INTERVIEW_GUIDE.md) incluye preguntas
y respuestas, un recorrido del código y una demostración de cinco minutos.
El detalle de las verificaciones ejecutadas está en [VERIFICATION.md](docs/VERIFICATION.md).
La [auditoría técnica](docs/AUDITORIA.md) resume bugs corregidos, riesgos pendientes
y una hoja de ruta de escalado.

## Seguridad y observabilidad

Se validan extensión, MIME compatible, firma PDF, UTF-8, archivo vacío, bytes,
páginas y longitud extraída. Se limpia el nombre y nunca se ejecuta el contenido.
No se conserva el archivo original; se guardan metadata, texto y vectores.
La extracción bloqueante se lleva a un hilo. El cuerpo HTTP completo tiene límite
antes del parser multipart, incluso si llega por partes sin Content-Length.

Los logs registran eventos, identificadores y duración del procesamiento, sin
preguntas, respuestas, fragmentos, claves ni cadenas de excepción: los errores
inesperados se registran con tipo y trazas de código, y SQLAlchemy oculta parámetros.
`store=False` se envía en Responses API; esto no sustituye las políticas de retención
del proveedor. El texto de los fragmentos se envía a OpenAI para embeddings y RAG.

No hay autenticación por alcance del desafío. El UUID de sesión permite recuperar
su historial: no debe tratarse como una frontera de autorización. Los puertos se
limitan a localhost y la aplicación no se presenta como servicio multiusuario seguro.

## Limitaciones

- Requiere una clave con saldo/permisos para probar OpenAI realmente, o Ollama local.
- PDF escaneado sin OCR, PDF que exige contraseña para abrirse y DOCX no están
  soportados. Los PDF con solo contraseña de propietario (restricciones) sí.
- Procesamiento síncrono, máximo 10 MB, 200 páginas y 200 000 caracteres por defecto.
- Si el proceso muere durante una carga, puede quedar metadata `processing`; vuelve
  a subir el archivo. No hay worker de recuperación ni reintentos de cargas.
- Timeout de interfaz/proxy de 180 s; cargas muy lentas pueden completarse después.
  Actualiza historial antes de repetir una operación de resultado incierto.
- Sin idempotencia distribuida: un reintento manual puede duplicar una pregunta.
- Búsqueda vectorial exacta, sin índice aproximado; apropiada para documentos pequeños.
- Sin borrado, cuotas, autenticación, OCR, streaming ni preguntas que dependan del historial.
- El umbral necesita evaluación con un corpus representativo; puede causar falsos negativos.

## Mejoras futuras

Evaluaciones de relevancia y fidelidad con documentos reales; recuperación híbrida
léxica/vectorial y reranking; OCR; trabajos de procesamiento con recuperación;
idempotencia; retención/borrado; y autenticación/cuotas si se convierte en producto.
Un índice HNSW se justificaría con mediciones de latencia y un corpus mayor.

## Referencias

- [OpenAI: Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI: embeddings](https://developers.openai.com/api/docs/guides/embeddings)
- [pgvector para SQLAlchemy](https://github.com/pgvector/pgvector-python#sqlalchemy)
- [SQLAlchemy asyncio](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html)
