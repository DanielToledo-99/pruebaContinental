# Verificación de entrega

Ejecutada el 30 de septiembre de 2026 en Docker Desktop, con Python 3.12 dentro
del contenedor y PostgreSQL 16/pgvector real. El frontend se compiló también en
su imagen Node.js 22/Nginx.

| Verificación | Resultado |
| --- | --- |
| `docker compose config --quiet` | Correcto |
| `docker compose up --build -d --wait` | db, backend y frontend saludables |
| Frontend `http://localhost:3000/` | HTTP 200 |
| Proxy `http://localhost:3000/api/health` | `{"status":"ok"}` |
| Swagger `http://localhost:8000/docs` | HTTP 200 |
| Migración inicial con `alembic upgrade head` | Aplicada a desarrollo y base de pruebas |
| `alembic check` | Sin diferencias con los modelos |
| pytest con `TEST_DATABASE_URL` | **43 passed** |
| Ruff | Sin errores |
| Black | 41 archivos sin cambios pendientes |
| isort | Sin errores |
| `npm run build` | TypeScript y Vite correctos |
| `npm run lint` | Sin errores |
| Playwright contra frontend Docker | **6 passed**, escritorio y móvil |
| Inspección de capturas | Sin desbordamiento horizontal; chat y controles visibles |

## Alcance de las pruebas

- Carga y extracción de PDF/TXT, UTF-8, archivos vacíos, MIME/extensión, tamaño,
  ausencia de texto, límite de texto y chunking con solapamiento.
- Validaciones del caso de uso, propiedad de documento por sesión, cambio de espacio
  de embeddings, abstención sin contexto, citas inventadas y fallo del proveedor.
- Formato HTTP consistente, documentación, healthcheck, CORS y cuerpo grande sin
  Content-Length.
- Contrato HTTP del SDK OpenAI con MockTransport, salida estructurada, `store=False`,
  orden de embeddings y errores sin detalles sensibles.
- PostgreSQL real: ocho turnos concurrentes (16 mensajes), rollback, aislamiento y
  umbral de búsqueda vectorial; carga/pregunta/historial por HTTP al recrear la app.
- Navegador: archivo → pregunta → fuentes → recarga → pregunta sin respuesta;
  recuperación tras fallo de red y reintento de una carga fallida, en dos tamaños.

La suite emite un aviso de deprecación de Starlette sobre TestClient/httpx, sin
errores de ejecución. Se conserva `httpx` por ser el cliente pedido y usado por el SDK.

## Pendiente que requiere configuración del usuario

**No se ejecutaron llamadas reales a OpenAI:** no se proporcionó una API key.
Los tests de IA y navegador emplean fakes/transporte simulado; no prueban la calidad
semántica de un modelo real. Tras configurar `OPENAI_API_KEY`, ejecutar la prueba
manual del README con `samples/proyecto_agua.txt` y un PDF con texto seleccionable.

Los controles de grounding reducen alucinaciones, pero una cita válida no demuestra
que todas las afirmaciones sean correctas. El umbral no fue calibrado con un corpus real.

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
