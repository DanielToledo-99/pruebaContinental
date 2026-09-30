# Guía para la entrevista

## Presentación en un minuto

«Construí un asistente para preguntar sobre PDF y TXT. FastAPI expone una API y
React una interfaz que conserva sesiones. La aplicación extrae texto, crea fragmentos,
genera embeddings y los almacena en PostgreSQL con pgvector. Cada pregunta busca
fragmentos del documento seleccionado y el LLM recibe exclusivamente ese contexto.
Las respuestas incluyen citas comprobadas y se guardan junto con la pregunta en una
transacción. Separé proveedores y persistencia mediante puertos para poder probar
las reglas sin OpenAI ni base de datos, y añadí pruebas reales de PostgreSQL para
concurrencia y aislamiento.»

## Demo de cinco minutos

1. Abre UI y Swagger. Explica los tres servicios de Compose.
2. Sube `samples/proyecto_agua.txt`. Pregunta objetivo y presupuesto.
3. Expande una fuente y compárala con el archivo.
4. Pregunta un dato ajeno: ganador del Mundial 2018. Muestra la abstención.
5. Recarga: mensajes y fuentes reaparecen. Copia la sesión, crea otra y recupera la anterior.
6. Muestra `make test-postgres` y explica el test de ocho escrituras simultáneas.

Antes de la entrevista configura una API key válida y ensaya el flujo real. Si solo
ejecutaste tests con fakes, dilo explícitamente: no acreditan calidad del modelo.

## Preguntas probables y respuestas

**¿Por qué arquitectura limpia para una app pequeña?**

Separar reglas de frameworks hace posible probar los casos de uso con objetos simples
y cambiar infraestructura. Mantengo cuatro capas claras, pero no agrego microservicios,
CQRS ni una abstracción para cada detalle. El puerto de Unit of Work responde a una
necesidad concreta: confirmar estado y vectores, o los dos mensajes, de forma atómica.

**¿Qué diferencia hay entre LLM y embeddings?**

El proveedor de embeddings transforma texto en un vector para comparar similitud.
El LLM genera una respuesta usando los fragmentos recuperados. Son responsabilidades
separadas y pueden cambiar de proveedor de forma independiente.

**¿Cómo cambiarías OpenAI por Ollama?**

Implementaría `LLMProvider.answer` para devolver `GroundedAnswer` con citas, y un
`EmbeddingProvider` compatible con el modelo de embeddings local. Cambiaría la
composición en `main.py`. Los casos de uso permanecerían igual; habría que volver a
indexar documentos si cambia el espacio vectorial y evaluar la calidad del modelo.

**¿Por qué pgvector en vez de FAISS o Chroma?**

Ya necesito PostgreSQL. pgvector permite guardar metadata, chunks y estado en la
misma transacción, sin sincronizar otro almacenamiento. Para pocos cientos de chunks
por documento, la búsqueda exacta es suficiente. Mediría antes de agregar HNSW.

**¿Por qué 800/100/4?**

800 caracteres suele conservar varias oraciones, 100 de solapamiento protege los
límites y cuatro fragmentos mantiene el contexto pequeño. Son hipótesis razonadas,
configurables y pendientes de evaluación de corpus, no cifras universales.

**¿Qué significa el umbral de 0.25?**

Similitud coseno mínima para que un fragmento entre al contexto. No significa 25%
de certeza. Un umbral alto pierde información; uno bajo recupera ruido. Calibraría
con preguntas representativas, midiendo recuperación y abstenciones correctas.

**¿Cómo evitas alucinaciones? ¿Puedes garantizarlas al 100%?**

Limito contexto al documento, instruyo abstención, pido salida estructurada, verifico
las citas y no llamo al LLM sin contexto. No puedo garantizar cero alucinaciones:
una cita literal puede no respaldar una conclusión. Haría evaluaciones de fidelidad,
red teaming y, si el dominio lo requiere, restringiría la respuesta a extractos.

**¿Qué ocurre si el documento contiene “ignora tus instrucciones”?**

El prompt clasifica contexto y pregunta como datos no confiables y prohíbe seguir
instrucciones que cambien las reglas. No se ejecuta código ni se dan herramientas
al modelo. Eso reduce el riesgo, pero no constituye una defensa perfecta contra
prompt injection. La validación de fuentes añade una comprobación independiente.

**¿Qué pasa si falla OpenAI?**

El adaptador traduce el error a `AIProviderError`, el API devuelve 502 sin detalles
sensibles y el frontend permite reintentar. En una pregunta no se guarda medio turno.
En una carga queda metadata `failed`, pero no un índice parcial.

**¿Qué pasa si dos preguntas llegan juntas?**

Las llamadas de IA ocurren sin bloqueo. Al guardar, cada transacción bloquea brevemente
la fila de sesión y reserva dos números consecutivos. Los pares no se intercalan.
El orden corresponde a la confirmación, no necesariamente al inicio de cada request.

**¿Por qué no confiar en las fechas para ordenar?**

Los timestamps pueden coincidir y las solicitudes concurren. Una secuencia única
por sesión define un orden total explícito y mantiene cada turno contiguo.

**¿Cómo sabes que el frontend recupera una conversación?**

Guarda solo identificadores en localStorage. Al iniciar consulta el historial en la
base, incluidas metadata y fuentes. Playwright comprueba recarga y reintento tras
fallo de red. PostgreSQL comprueba que los datos sobreviven al recrear la aplicación.

**¿Es seguro un UUID de sesión sin autenticación?**

No es autorización. El desafío excluye login, por lo que los UUID permiten recuperar
historial y la app se expone solo a localhost. Para un producto agregaría identidad,
ownership verificado, cuotas y retención/borrado de datos.

**¿El historial se manda al modelo?**

No. Se guarda y muestra, pero cada pregunta se responde con el documento. Esto
evita considerar respuestas previas como evidencia, aunque limita preguntas elípticas.
Para soportarlas haría una reformulación controlada y conservaría el documento como
única fuente de hechos.

**¿Cómo probarías la calidad real del RAG?**

Construiría un conjunto de documentos con preguntas respondibles y no respondibles,
fragmentos esperados y respuestas de referencia. Mediría recall@K, fidelidad de citas,
exactitud de abstención, coste y latencia. Separaría estas evaluaciones de tests
deterministas de software.

**¿Qué cambiarías para escalar?**

Medir primero. Para documentos grandes: trabajo en segundo plano, OCR y recuperación
de estados pendientes. Para corpus mayor: índice aproximado y búsqueda híbrida.
Antes de exponerlo: autenticación, cuotas, idempotencia, límites por usuario y métricas.
La migración se ejecutaría una vez por release, no por cada réplica.

## Recorrido del código

1. `backend/app/main.py`: composición y ciclo de vida de clientes/conexiones.
2. `backend/app/api/routes.py`: contrato HTTP sin reglas de negocio.
3. `backend/app/application/use_cases.py`: flujo de carga y pregunta.
4. `backend/app/application/ports.py`: contratos sustituibles.
5. `backend/app/application/grounding.py`: comprobación de citas y abstención.
6. `backend/app/infrastructure/repositories/sqlalchemy_repository.py`: transacción del turno.
7. `backend/tests/integration/test_postgres.py`: evidencia de concurrencia y persistencia.
8. `frontend/src/App.tsx`: estados de UI y restauración de sesión.
