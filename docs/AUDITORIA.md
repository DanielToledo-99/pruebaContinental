# Auditoría técnica

Fecha: 30 de septiembre de 2026. Alcance: todo el repositorio (backend, frontend,
infraestructura, CI y documentación) en el commit `550c664`, más las correcciones
de esta rama.

## Resumen

La base es sólida: capas bien separadas, transacciones correctas (no se retienen
conexiones durante las llamadas de IA y el turno pregunta/respuesta es atómico),
validación de archivos cuidadosa y buena cobertura de pruebas, incluida PostgreSQL
real. Con una `OPENAI_API_KEY` válida el flujo principal funciona.

Se encontraron tres problemas que impedían que funcionara o que se integrara:

1. **CI en rojo**: `black --check` fallaba en `ollama_provider.py`
   ([run del commit inicial](https://github.com/DanielToledo-99/pruebaContinetal/actions/runs/36744613275)).
2. **El modo Ollama no funcionaba sin clave de OpenAI**: `LLM_PROVIDER=ollama` solo
   cambiaba la generación; los embeddings seguían en OpenAI, así que toda carga
   fallaba con 502 «Configura OPENAI_API_KEY». Se reprodujo con el servidor real.
3. **Ollama inaccesible desde Docker en Linux**: `host.docker.internal` no existe
   allí sin `extra_hosts`.

Los tres están corregidos en esta rama, junto con otros cinco bugs. Quedan mejoras
de escalado, UX y calidad de RAG, priorizadas al final.

## Cumplimiento del desafío

Contraste con `Desafio_Tecnico_Musache_Fullstack_CIE_LAB.docx`.

| Requisito | Estado | Evidencia |
| --- | --- | --- |
| `POST /ask` con pregunta e identificador de sesión | Cumple | `document_id` ahora es opcional: sin él se usa el último documento procesado de la sesión. Antes era obligatorio y una llamada con solo sesión y pregunta devolvía 422. |
| Cargar un documento como fuente | Cumple | `POST /documents` (PDF y TXT). |
| `GET /history/{session_id}` | Cumple | Mensajes ordenados por secuencia, con fuentes y documentos. |
| Validación y errores HTTP consistentes | Cumple | Formato `{"error": {"code", "message"}}`, códigos 400/404/409/413/415/422/500/502. |
| Responder con el contenido del documento | Cumple | RAG con pgvector filtrado por documento. |
| Indicar cuando el documento no contiene la respuesta | Cumple | Frase fija de ausencia; citas verificadas en el fragmento. |
| LLM externo o local, documentado | Cumple | OpenAI u Ollama (modo local corregido en esta rama), documentados en README y DECISION_LOG. |
| Streaming o carga simple | Cumple | Carga simple (ADR-008). |
| SPA: cargar documento y preguntar | Cumple | React + TypeScript. |
| Estado de la solicitud: cargando, completada, error | Cumple | Indicadores de carga, avisos y alertas con reintento. |
| Historial por sesión en la interfaz | Cumple | Se restaura al recargar o con el identificador de sesión. |
| Capas Domain / Application / Infrastructure | Cumple | Más API como capa de transporte. |
| Tipado fuerte y Pydantic | Cumple | Pydantic v2 en API y configuración; mypy sin errores y en CI desde esta rama. |
| Lógica separada de infraestructura y proveedor de IA | Cumple | Puertos `Protocol`; los casos de uso no importan FastAPI, SQLAlchemy ni SDKs. |
| Manejo de errores con excepciones | Cumple | Jerarquía `ApplicationError` y manejadores centralizados. |
| Historial persistido en base de datos | Cumple | PostgreSQL con migraciones Alembic. |
| Pruebas unitarias y de integración (pytest) | Cumple | 60 tests, incluida PostgreSQL real; Playwright en el frontend. |
| Ruff/Flake8, Black e isort | Cumple | En CI; Black fallaba en `main` y está corregido. |
| Sin secretos en el código | Cumple | Variables de entorno y `SecretStr`; revisado todo el historial de Git: solo aparece `test-key` en tests. |
| Dockerfile y docker-compose.yml | Cumple | Backend, frontend (Nginx) y PostgreSQL con healthchecks. No se pudo ejecutar Compose en este entorno. |
| Código en un repositorio GitHub | **Acción necesaria** | El repositorio es **privado**: hay que hacerlo público o invitar a los evaluadores. |
| README.md completo | Cumple | Descripción, requisitos, entorno, Docker, pruebas, API y limitaciones. |
| DECISION_LOG.md | Cumple | 12 ADR con alternativas y motivos. |
| Documentar lo pendiente | Cumple | Limitaciones y mejoras en README y este informe. |
| Opcional: despliegue gratuito | No hecho | Antes de exponerla haría falta autenticación y límite de peticiones (ver Seguridad). |

## Qué se verificó

| Verificación | Original | Tras los cambios |
| --- | --- | --- |
| pytest con fakes | 40 passed, 4 skipped | 56 passed, 4 skipped |
| pytest con PostgreSQL 16 + pgvector real | 44 passed | **60 passed** |
| Ruff / isort / `alembic check` | Correcto | Correcto |
| mypy sobre `app/` | 7 errores (no estaba configurado) | Correcto, añadido a CI |
| Black | **1 archivo con errores** | Correcto |
| `npm run build` / `npm run lint` | Correcto | Correcto |
| Prettier | 1 archivo sin formato | Correcto |
| Playwright (escritorio y móvil) | 6 passed | 6 passed |
| Servidor real sin clave, `LLM_PROVIDER=ollama` | **Carga falla (502)** | Flujo completo correcto* |

\* Con un servidor que imita la API de Ollama (`/api/embed`, `/api/chat`), porque
la red de este entorno bloquea la descarga de Ollama. Se comprobó carga, respuesta
con cita verificada, abstención ante una pregunta ajena e historial ordenado.

**No verificado aquí:** `docker compose` (no hay daemon de Docker), llamadas reales
a OpenAI (no hay clave) y modelos reales de Ollama. Los tests nuevos de cada
corrección fallan con el código original y pasan con el corregido.

## Qué falta para que funcione

Con los cambios de esta rama:

1. Copiar `.env.example` a `.env`: Compose falla si no existe.
2. Elegir proveedor:
   - **OpenAI**: completar `OPENAI_API_KEY` con una clave con saldo.
   - **Ollama local**: `LLM_PROVIDER=ollama`, `ollama pull bge-m3` y el modelo de
     chat; en Linux arrancar Ollama con `OLLAMA_HOST=0.0.0.0`; en CPU subir
     `AI_TIMEOUT_SECONDS` a 120. Ollama 0.5 o superior.
3. `docker compose up --build -d --wait` y abrir <http://localhost:3000>.
4. Hacer la prueba manual del README con un modelo real: los tests usan fakes y
   no acreditan la calidad de las respuestas.

Al arrancar, el backend ahora registra qué proveedores usa (`ai_providers ...`) y
avisa si hace falta `OPENAI_API_KEY` y no está definida.

## Bugs corregidos en esta rama

| # | Severidad | Problema | Corrección |
| --- | --- | --- | --- |
| 1 | Alta | CI rojo por formato Black. | Formato aplicado. |
| 2 | Alta | Embeddings siempre en OpenAI: sin clave no se procesa ningún documento, aunque `LLM_PROVIDER=ollama`. | `OllamaEmbeddingProvider` (`/api/embed`, lotes de 16, validación de dimensión y valores). `EMBEDDING_PROVIDER` sigue a `LLM_PROVIDER` si no se define. `OLLAMA_EMBEDDING_MODEL=bge-m3` (multilingüe). |
| 3 | Media | Linux: el contenedor no resuelve `host.docker.internal`. | `extra_hosts: host-gateway` en Compose y nota sobre `OLLAMA_HOST`. |
| 4 | Media | Errores 500: el código decía no registrar el texto de excepciones, pero Starlette re-lanza y uvicorn imprimía el traceback con el mensaje (puede contener texto del documento o parámetros SQL). Además esas respuestas salían sin cabeceras CORS. | Middleware `UnhandledErrors` dentro de CORS: registra tipo y trazas de código, no el mensaje. `hide_parameters=True` en el engine. |
| 5 | Media | PDF con solo contraseña de propietario (restricciones de copia/impresión, habituales en documentos oficiales) se rechazaban como «protegidos», aunque cualquier visor los abre. Además pypdf no puede descifrar AES sin `cryptography`. | Se intenta `decrypt("")`; se añade `pypdf[crypto]`. Los PDF que exigen contraseña siguen rechazándose. |
| 6 | Media | Una carga cancelada (apagado, timeout) dejaba el documento en `processing` para siempre: `CancelledError` no hereda de `Exception`. | Se captura también `CancelledError`, se marca `failed` y se re-lanza. |
| 7 | Media | La verificación de citas era literal: una cita con mayúscula inicial, comillas «» o punto final añadido se descartaba y la respuesta correcta se convertía en «No encuentro...». | Comparación normalizada (NFKC, mayúsculas, espacios, comillas y guiones tipográficos, puntuación en los extremos). Sigue exigiendo que todas las citas existan en su fragmento. |
| 8 | Baja | Ollama recibía `format: "json"` sin esquema (los modelos pequeños se desvían) y un `message: null` producía 500 en vez de 502. | JSON schema en `format` y captura de `TypeError`. |

## Bugs y riesgos pendientes

| Severidad | Problema | Recomendación |
| --- | --- | --- |
| Media | Límite de subida desincronizado: `MAX_UPLOAD_MB` admite hasta 25, pero el frontend fija 10 MB y Nginx `client_max_body_size 11m`. | Plantilla de Nginx con variable (`/etc/nginx/templates`) y `VITE_MAX_UPLOAD_MB`, o exponer el límite en un endpoint `/config`. |
| Media | Nginx resuelve `backend` una sola vez al arrancar: si el contenedor backend se recrea con otra IP, devuelve 502 hasta reiniciar Nginx. | `resolver 127.0.0.11 valid=10s;` y `proxy_pass` con variable. |
| Media | Documentos huérfanos en `processing` si el proceso muere con `SIGKILL`. | Al arrancar o periódicamente, marcar `failed` los `processing` con más de N minutos. |
| Media | `GET /history` devuelve todo el historial sin paginar, y cada respuesta guarda el texto completo de hasta 4 fragmentos en `sources`. | Paginación por `sequence` y guardar solo índice + cita (el texto está en `document_chunks`). |
| Media | Sin autenticación ni límite de peticiones: quien acceda al puerto puede consumir tokens sin control. Aceptable solo en localhost, como indica el README. | Identidad + propiedad de sesiones y `limit_req` en Nginx o límites por usuario. |
| Baja | El chat mezcla preguntas de distintos documentos de la sesión; solo las fuentes indican el archivo. | Mostrar el documento en cada mensaje o filtrar por documento activo. |
| Baja | La sugerencia «Resume los puntos más importantes» no encaja con RAG top-4 con umbral: puede dar un resumen parcial o la frase de ausencia. | Cambiar las sugerencias por preguntas puntuales o añadir un modo resumen. |
| Baja | TXT solo UTF-8: los archivos ANSI/cp1252 de Windows se rechazan. | Intentar cp1252 como alternativa, manteniendo el control de caracteres binarios. |
| Baja | Una cita de 1–2 caracteres («de») valida cualquier respuesta. | Longitud mínima de cita (p. ej. 3 palabras o 10 caracteres), calibrada con un corpus. |
| Baja | El modelo Ollama por defecto, `qwen2.5-coder:7b`, está orientado a código. | Para preguntas en español, `qwen2.5:7b` o `llama3.1:8b`. |
| Baja | CI: `playwright install --with-deps` tardó 11 minutos. | Cachear `~/.cache/ms-playwright` o usar la imagen oficial de Playwright. |

## Escalamiento

### Estado actual

- **Carga síncrona dentro de la petición HTTP.** Un PDF grande mantiene la conexión
  hasta 180 s (timeout de Nginx y del frontend). Los lotes de embeddings se envían
  en serie y pypdf es Python puro: `asyncio.to_thread` evita bloquear el event loop,
  pero compite por el GIL y aumenta la latencia del resto de peticiones del proceso.
- **Memoria por carga.** `RequestSizeLimit` guarda el cuerpo completo, el parser
  multipart lo copia a un archivo temporal y la ruta lo vuelve a leer: unas tres
  copias de hasta 10 MB por carga concurrente.
- **Un solo proceso uvicorn**, y `alembic upgrade head` en cada arranque: con varias
  réplicas las migraciones compiten entre sí.
- **Base de datos: bien resuelto.** Cada pregunta usa tres transacciones cortas y
  solo bloquea la fila de sesión al asignar la secuencia. Pool por defecto de 5+10.
- **Búsqueda vectorial: adecuada para el patrón actual.** Siempre se filtra por un
  documento (índice B-tree) y se ordenan sus pocos cientos de fragmentos. Un índice
  HNSW no ayudaría aquí; solo haría falta para buscar en muchos documentos a la vez,
  y exige una dimensión fija en la columna (hoy `Vector()` no la tiene).
- **Crecimiento sin límite**: sesiones, mensajes y fragmentos no se borran nunca.
- **OpenAI con `max_retries=1`**: bajo carga, los 429 se convierten en 502.

### Hoja de ruta sugerida

**Etapa 1: pocos usuarios internos**

1. Procesar documentos en segundo plano (arq/RQ, o una tabla de trabajos en
   PostgreSQL con `FOR UPDATE SKIP LOCKED`), con `GET /documents/{id}` para que el
   frontend consulte el estado. El modelo ya tiene los estados necesarios.
2. Limpieza de `processing` huérfanos y política de retención/borrado
   (`DELETE /sessions/{id}`).
3. Migraciones como paso de despliegue separado; `uvicorn --workers N` o varias
   réplicas detrás de Nginx.
4. Reintentos con backoff exponencial para 429/5xx del proveedor.
5. Observabilidad: request-id en logs, métricas de latencia, tokens, tasa de
   abstención y de citas rechazadas (Prometheus/OpenTelemetry).

**Etapa 2: producto multiusuario**

1. Autenticación (OIDC), propiedad de sesiones y documentos, cuotas por usuario.
2. Workers de procesamiento separados de la API, escalables de forma independiente.
3. PgBouncer; HNSW con dimensión fija si se busca en varios documentos.
4. Streaming de respuestas (SSE), validando las citas antes de confirmar el turno.

## Calidad de las respuestas (RAG)

- **Evaluación antes de ajustar**: un conjunto de preguntas respondibles y no
  respondibles para medir recall@K, fidelidad de citas y exactitud de abstención.
  Sin eso, `RETRIEVAL_MIN_SCORE=0.25` es una suposición, y depende del modelo de
  embeddings (con `bge-m3` la escala de similitud es distinta).
- **Chunking**: la extracción colapsa todos los saltos de línea, así que se pierden
  párrafos y el solapamiento empieza a mitad de palabra. Dividir por párrafos y
  oraciones mejoraría la recuperación.
- **Búsqueda híbrida**: combinar `tsvector` en español de PostgreSQL con la búsqueda
  vectorial (fusión RRF) ayuda con nombres propios, cifras y siglas.
- **Preguntas de seguimiento**: hoy cada pregunta es independiente; se podría
  reformular la pregunta con el historial, manteniendo el documento como única
  fuente de hechos.
- **OCR** (`ocrmypdf`) para PDF escaneados.

## Frontend y accesibilidad

- 27 reglas CSS usan tamaños de 6–9 px y varios textos tienen contraste de
  2,5:1 a 3,2:1 (por ejemplo `.dropzone small` `#9ba598`: 2,48:1; `.private-note`
  `#929c92`: 2,84:1), por debajo del 4,5:1 que pide WCAG AA para texto normal.
- Las fuentes se cargan desde Google Fonts con `@import`: bloquea el renderizado,
  depende de un tercero y le envía la IP del usuario. Conviene servirlas localmente.
- Nginx no define `Content-Security-Policy` ni caché larga para `/assets/` (con hash),
  no comprime con gzip y corre como root (`nginxinc/nginx-unprivileged` lo evita).
- La hora de los mensajes no incluye la fecha: al recuperar una sesión antigua no
  se sabe de qué día es cada mensaje.

## Seguridad

Correcto: validación de extensión, MIME, firma PDF y tamaño; nombres saneados; ORM
sin SQL manual; React escapa el contenido; CORS sin credenciales; `SecretStr`;
`.env` fuera de Git; puertos solo en `127.0.0.1`; prompt que trata el documento
como datos no confiables y citas verificadas.

A tener en cuenta antes de exponerlo: el UUID de sesión funciona como credencial
(no hay autorización), no hay límites de peticiones y las credenciales de
PostgreSQL de ejemplo son `postgres/postgres`.

## Cambios de esta rama

- `backend/app/infrastructure/llm/ollama_provider.py`: embeddings Ollama y JSON schema.
- `backend/app/core/config.py`, `backend/app/main.py`: `EMBEDDING_PROVIDER`,
  `OLLAMA_EMBEDDING_MODEL`, aviso de clave ausente, `hide_parameters=True`.
- `backend/app/api/middleware.py`, `exception_handlers.py`: errores 500 sin detalles
  y con CORS.
- `backend/app/infrastructure/document_processing/parsers.py`, `pyproject.toml`,
  `requirements.lock`: PDF con contraseña de propietario (`pypdf[crypto]`).
- `backend/app/application/use_cases.py`: cargas canceladas quedan en `failed`.
- `backend/app/application/grounding.py`: comparación normalizada de citas.
- `docker-compose.yml`, `.env.example`, `README.md`: modo local con Ollama.
- `backend/app/application/use_cases.py`, `schemas.py`: `document_id` opcional en
  `POST /ask`; la respuesta indica el documento usado.
- `pyproject.toml`, `requirements.lock`, `ci.yml`, `Makefile`: mypy con 7 errores
  de tipos corregidos.
- Tests nuevos en `tests/unit` y `tests/integration` para cada corrección.
