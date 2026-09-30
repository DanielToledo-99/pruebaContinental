# Decisiones técnicas

## ADR-001 Arquitectura limpia

**Decisión:** Domain / Application / Infrastructure / API. Entidades como
dataclasses; puertos como `Protocol`; composición mediante inyección en `main.py`.

**Motivo:** probar las reglas sin iniciar servicios ni importar frameworks en los
casos de uso. Separación visible y explicable en una entrevista.

**Alternativa:** estructura FastAPI plana con lógica en las rutas. Se descartó
porque mezcla HTTP, transacciones y prompts. No se crearon microservicios ni una
clase por cada función: el tamaño del desafío no lo justifica.

## ADR-002 PostgreSQL

**Decisión:** PostgreSQL 16, SQLAlchemy 2 async y Alembic.

**Motivo:** integridad referencial, transacciones y bloqueo de filas para turnos
concurrentes. Alembic aporta un historial explícito de esquema y `alembic check`
detecta diferencias entre modelos y migraciones.

**Alternativas:** SQLite simplifica desarrollo pero no cumple el stack pedido ni
reproduce las garantías de concurrencia/pgvector. MongoDB añade variabilidad sin
beneficio para relaciones tan claras. Las pruebas de persistencia usan PostgreSQL.

## ADR-003 Vector store

**Decisión:** pgvector en la misma base, implementando `VectorStore`.

**Motivo:** metadata, chunks y cambio a `processed` se confirman juntos. No hay
dos sistemas cuyo estado deba reconciliarse. La búsqueda exacta usa distancia coseno
y filtro por `document_id`, con índice B-tree del identificador.

**Alternativas:** FAISS requiere persistir/sincronizar índices de archivos; Chroma
añade otro almacenamiento y problemas de atomicidad. HNSW no se añade todavía:
cada documento genera pocos cientos de fragmentos, por lo que se favorece exactitud
y simplicidad sobre índices aproximados.

La columna usa `Vector()` sin dimensión fija para permitir proveedores con otras
dimensiones sin cambiar el esquema. Cada documento registra proveedor:modelo:dimensión;
la consulta rechaza espacios distintos. El adaptador valida dimensiones, valores
finitos y vectores no nulos. No se comparan documentos entre sí.

## ADR-004 RAG

**Decisión:** embedding de pregunta → recuperación del top K → generación con contexto.

**Motivo:** enviar el documento completo escala peor en tokens/latencia, distrae al
modelo y dificulta las referencias. RAG acota el contexto y hace visibles las fuentes.

**Coste:** si retrieval no recupera el fragmento correcto, generación no puede
resolverlo. Se devuelve ausencia de información, incluso si esto produce falsos
negativos. No se promete precisión perfecta sin evaluar un corpus representativo.

## ADR-005 Proveedor LLM desacoplado

**Decisión:** interfaces separadas `LLMProvider`, `EmbeddingProvider`, `VectorStore`
y `DocumentParser`. Adaptadores OpenAI con cliente asíncrono, timeout y un reintento.

**Motivo:** embeddings y generación pueden usar distintos proveedores. Para añadir
Ollama/Gemini/Anthropic basta implementar los puertos y cambiar la composición.
Los casos de uso conservan sus reglas. `LLMProvider.answer` devuelve una entidad
`GroundedAnswer` con citas, en lugar de solo un string, para validar respaldo.

**Alternativas:** importar el SDK desde el caso de uso o introducir LangChain.
Se descartan para evitar acoplamiento o abstracciones adicionales innecesarias.

Se usa `gpt-4o-mini` como base económica configurable y `text-embedding-3-small`
para embeddings. No se codifican precios en la app. Su disponibilidad depende de la
cuenta. Las respuestas estructuradas siguen el contrato de la Responses API;
los tests del adaptador verifican la petición mediante un transporte simulado.

## ADR-006 Chunking y recuperación

**Decisión:** 800 caracteres, solapamiento de 100, top K=4, similitud mínima=0.25.

**Motivo:** 800 caracteres suelen contener varias oraciones; 100 preservan contexto
en límites con un coste duplicado cercano al 14% para texto largo. Se busca un espacio
en la segunda mitad del fragmento para evitar cortar palabras cuando sea posible.
Cuatro fragmentos acotan el contexto a aproximadamente 3200 caracteres más el prompt.

El umbral 0.25 es un punto de partida conservador para descartar vecinos claramente
lejanos, no una métrica calibrada ni probabilidad de verdad. El LLM debe abstenerse
también ante vecinos temáticos que no respondan a la pregunta. Todos los parámetros
se configuran por entorno y deben evaluarse con preguntas positivas y negativas.

**Alternativas:** división por tokens o semántica. Mejoran control de contexto, pero
agregan dependencias y complejidad; se documentan como evolución. No se afirma que
800 caracteres equivalgan a un número fijo de tokens.

## ADR-007 Testing

**Decisión:** fakes en aplicación, TestClient en API, MockTransport para el SDK,
PostgreSQL real para persistencia y Playwright en escritorio/móvil.

**Motivo:** pruebas deterministas, sin coste ni claves. La suite de PostgreSQL
comprueba aquello que los fakes no demuestran: pgvector, transacciones, locks,
orden de turnos concurrentes y persistencia al recrear la aplicación.

**Alternativa:** tests dependientes de una API real. Se descartan como comprobación
obligatoria por coste, variación y fallos de red. Las evaluaciones semánticas reales
son una verificación manual separada. No se confunden mocks con calidad del modelo.

## ADR-008 No streaming

**Decisión:** petición/respuesta convencional, con indicador de espera.

**Motivo:** solo se muestran y persisten respuestas completas tras validar citas.
Streaming exigiría gestionar fragmentos parciales, cancelación y validación tardía.
Se prioriza funcionalidad demostrable sin SSE, WebSockets ni colas.

## ADR-009 Transacciones y estados

**Decisión:** guardar metadata `processing`, extraer/generar fuera de transacción,
y después guardar chunks + estado `processed` de forma atómica. Ante excepción se
registra `failed`. Las preguntas/respuestas se guardan como un turno atómico.

**Motivo:** no mantener conexiones/locks abiertos durante llamadas lentas a IA.
Bloquear la sesión únicamente al asignar la secuencia evita intercalar mensajes.
El orden es el de confirmación, que puede diferir del de inicio de peticiones simultáneas.

**Alternativas:** una transacción durante todo el request o dos inserts independientes.
La primera retiene recursos; la segunda deja preguntas huérfanas. Una interrupción
del proceso puede dejar metadata pendiente; se documenta sin introducir workers.

## ADR-010 Respaldo de respuestas y prompt injection

**Decisión:** prompt centralizado, contexto considerado no confiable, salida
estructurada con `supported` y citas; validar que cada cita pertenece al fragmento.
Sin contexto o con evidencia inválida, usar exactamente la frase de ausencia.

**Motivo:** un prompt solo no permite auditar fuentes. Las citas comprobadas impiden
referencias a fragmentos inexistentes, pero **no garantizan que toda afirmación sea
una consecuencia lógica de la cita**. No se ofrece garantía absoluta anti-alucinación.

**Alternativas:** respuestas puramente extractivas sacrifican síntesis; un segundo LLM
verificador añade coste y tampoco ofrece garantía formal. Se priorizan abstención,
evidencia visible y honestidad sobre los límites. No se incluye historial como fuente
de hechos, para evitar que respuestas anteriores contaminen el contexto.

## ADR-011 Sesiones, UX y alcance

**Decisión:** creación explícita de sesiones en backend, `session_id` y documento
seleccionado en localStorage, recuperación de metadata junto con historial.

**Motivo:** recargar restaura tanto mensajes como el documento necesario para seguir
preguntando. El usuario puede copiar/introducir el identificador. Un fallo transitorio
de red no borra su sesión. Las preguntas fallidas permanecen en el editor.

No se agrega router: una pantalla cubre el flujo. Sin login, roles, Redis, OAuth,
administración, streaming ni DOCX. PDF y TXT cubren los requisitos obligatorios.
No hay autorización real: un UUID conocido permite acceder al historial. Esta versión
se sirve solo en localhost y no debe publicarse como producto multiusuario sin cambios.

## ADR-012 Ejecución y reproducibilidad

**Decisión:** Compose con healthchecks, migración al iniciar y Nginx como proxy
de `/api`. Puerto 3000 para UI y 8000 para Swagger. Versiones de Python fijadas en
`requirements.lock` como constraints y `package-lock.json` para Node.

**Motivo:** el navegador usa una URL resoluble; el nombre Docker `backend` no sale
al cliente. CI ejecuta las mismas pruebas con Python 3.12 y PostgreSQL/pgvector.
Se mantiene un solo proceso de migración en este despliegue local; al escalar habría
que separarlo como paso de release para evitar migraciones concurrentes.

## Nota sobre el flujo de generación local

Se intentó generar el borrador con Ollama local y modelo `mistral`, como requerían
las preferencias del proyecto. Ollama respondió `model 'mistral' not found`.
Se aplicó la alternativa autorizada: implementación directa revisada por Codex.
No se atribuyen correcciones a un borrador que no llegó a generarse.
