# Bitácora F01 · ADR de la arquitectura v3

Agente `adrs` (Ola 0, Fase 1). Rama `feature/adr-architecture-v3`, creada desde `feature/baseline-dev` (`eb84c97`). Fecha: 2026-11-07.

## Hecho

| Bloque | Contenido | Commit |
| --- | --- | --- |
| 0 | Rama creada; lectura de las reglas, del plan (0.1, 1.3, 2.2–2.6, 3, 4, 5.2–5.6, 9, 13, 15, 16, 17, 18, 19), de los ADR 0001–0006 y de `proyecto/decisiones-pendientes.md` | — |
| 1 | `docs/adr/_template.md`; ADR 0007 (re-base `v2.0.0`, Aceptado), 0008 (arquitectura de `ai/`), 0009 (propiedad de los datos) y 0010 (trabajos en PostgreSQL e ingesta por consulta), Propuestos | `d46880a` |
| 2 | ADR 0011 (proveedor de LLM, Aceptado, DEF-01), 0012 (embeddings 768 provisional, Aceptado, DEF-02), 0013 (fragmentos RAG), 0015 (banco de ítems) y 0016 (videos con curaduría), Propuestos | `b85fb45` |
| 3 | ADR 0014 (client credentials y endurecimiento de Keycloak), 0018 (datos personales), 0019 (usuarios de base), 0020 (despliegue), Propuestos; 0017 (interfaz desde Figma v3 con directorio de estilos) y 0021 (roles neutros), Aceptados. Índice `docs/adr/README.md` con los 21 ADR; nota «complementado por» en 0004 (→ 0014) y 0006 (→ 0017) | ver `git log` (commit del bloque 3) |

Estados finales: **Aceptado** 0007, 0011, 0012, 0017, 0021 (más 0001–0006). **Propuesto** 0008, 0009, 0010, 0013, 0014, 0015, 0016, 0018, 0019, 0020; cada uno dice en su cabecera qué DEF o fase lo cierra.

ADR 0005: **no se tocó**. Ya decía «la sección 3 fue reemplazada el 2026-11-07» en su estado y en el título de la sección 3, así que la nota pedida ya existía. En el índice figura como «Aceptado; sección 3 modificada el 2026-11-07».

### Pendientes D que cierra cada ADR (para que la sesión principal actualice `proyecto/decisiones-pendientes.md`)

| Pendiente | ADR | Estado del ADR | Cómo marcarlo |
| --- | --- | --- | --- |
| D-01 Modelo de embeddings y dimensión | [0012](../../docs/adr/0012-embedding-model-and-dimension.md) | Aceptado (768 provisional) | **Cerrada (ADR 0012)**; valor `vector(768)`; confirmar modelo en P-05 antes de la Fase 5. Ojo: la tabla «Respuestas» aún dice que la propuesta `text-embedding-3-large` está «pendiente de confirmar»; el ADR lo deja como alternativa descartada y advierte que se reemplaza si el dueño elige otro modelo antes de indexar |
| D-02 Proveedor de LLM | [0011](../../docs/adr/0011-llm-provider.md) | Aceptado | **Cerrada (ADR 0011)**: Gemini por defecto, Claude por el mismo puerto; faltan modelos y tarifas (P-05) |
| D-04 Almacenamiento de fragmentos RAG | [0013](../../docs/adr/0013-rag-chunks-in-liquibase-tables.md) | Propuesto | «Propuesta en ADR 0013»; se cierra al aceptarlo (Fases 2 y 5, DEF-08) |
| D-05 Usuario de base con mínimo privilegio | [0019](../../docs/adr/0019-least-privilege-db-users.md) | Propuesto | «Propuesta en ADR 0019»; se cierra en la Fase 2 |
| D-06 Destino de despliegue | [0020](../../docs/adr/0020-deployment-target.md) | Propuesto | «Propuesta en ADR 0020»; se cierra con DEF-16 antes de la Fase 9 |

## Desviaciones frente al plan o al brief

- **Fase 1 del plan** pedía 0007 a 0010, 0015, 0017, 0018 y 0021 «en estado Propuesto». Siguiendo el encargo, 0007, 0017 y 0021 quedan **Aceptados** (decisiones del dueño del 2026-11-07) y se adelantan además 0011–0014, 0016, 0019 y 0020.
- **Título del ADR 0014** ampliado a «… con *client credentials* y endurecimiento de Keycloak», porque el encargo pide que cubra también el autorregistro, la fuerza bruta y el reflejo de roles (G-01 a G-03, DEF-13, DEF-27).
- **Vocabulario:** el ADR 0021 menciona una vez los códigos heredados (`student`, `teacher`) porque describe qué se reemplaza; ningún otro ADR nuevo los usa. «Docente validador» (DEF-06, DEF-08) se escribió como «validador del curso».

## Decisiones

- **Formato:** se copió el de los ADR 0001–0006 (título `# ADR NNNN:`, cabecera en viñetas con Estado, Fecha, Autor, Fuente, Relacionados; secciones numeradas). Plantilla con cuatro secciones obligatorias: Contexto, Decisión, Alternativas descartadas, Consecuencias.
- **Nombres de archivo en inglés** (`0007-schema-rebase-v2.md`…), igual que los existentes.
- **ADR heredados sin «Alternativas descartadas»** (0001, 0002, 0003): no se reescriben (son históricos y aceptados). El validador los informa como aviso, no como error, y exige la plantilla completa desde el 0007.
- **Estado «Propuesto» con su cierre en la cabecera**, en lugar de una sección aparte, para no salirse de la plantilla.
- **Precisiones de diseño agregadas por el agente** (no están literales en el plan; revisar al aceptar):
  - 0018: la purga de `_audit` la hace un procedimiento con permiso explícito y probado por integración; la supresión también se aplica en Keycloak; los logs guardan `input_sha256` y no el texto.
  - 0019: ningún usuario de servicio escribe `_audit` fuera del trigger; usuario de solo lectura para el notebook (el plan lo menciona en 5.6 sin nombre).
  - 0014: el segundo factor exigido en las rutas protege el intervalo entre asignar un rol en la base y reflejarlo en Keycloak; la API necesitará una credencial de administración de Keycloak con permisos mínimos.
  - 0020: se descarta Hugging Face Spaces por ser de un solo contenedor.
- **Validador fuera del repositorio** (en el scratchpad de la sesión), porque el encargo prohíbe tocar código. Se sugiere llevarlo a la CI (ver abajo).

## Problemas y lecciones

- El worktree partía de `main` (`3dae23d`, solo el brief) y no de `feature/baseline-dev`: la rama se creó explícitamente desde `feature/baseline-dev`.
- Los enlaces entre ADR se escribieron antes de que existieran todos los archivos; el validador los marcó como rotos en el bloque 1 y quedaron resueltos al terminar el bloque 3.
- El aislamiento del worktree rechaza comandos con rutas en variables; las pruebas negativas se hicieron con rutas literales.

## Métricas

- 15 ADR nuevos (685 líneas), 1 plantilla, índice reescrito, 2 notas en ADR existentes.
- Validación (`python3 -I validate_adrs.py <repo>`): **OK**. 21 ADR encontrados, 21 en el índice, 0 enlaces rotos, 0 secciones faltantes en 0007–0021; 3 avisos (0001–0003 sin «Alternativas descartadas», anteriores a la plantilla).
- Prueba negativa del validador sobre una copia: detectó la sección faltante, el enlace roto, el ADR fuera del índice y la cabecera incompleta (8 errores esperados).
- Búsqueda de vocabulario prohibido (`student`, `teacher`, `estudiante`, `docente`, `Fable`) en los ADR nuevos: 1 coincidencia justificada (0021). Búsqueda de secretos: ninguno.

## Impacto en el brief

| Sección del brief | Cambio sugerido | ADR |
| --- | --- | --- |
| Arquitectura técnica y stack («capa de IA» en el backend; LlamaIndex) | `ai/` como servicio aparte con trabajos asíncronos; recuperación con SQL sobre pgvector | 0008, 0010, 0013 (B-03, B-04) |
| Modelo de datos principal (14 tablas, esquema evolutivo) | Re-base `v2.0.0` con unas 20 tablas más; un escritor por tabla; usuarios de base de mínimo privilegio | 0007, 0009, 0019 (B-05, B-06) |
| Evaluación («preguntas regeneradas en cada intento») | Banco pre-generado y revisado; ítems no vistos por intento | 0015 (B-02) |
| Componente de IA (re-ranking de videos) | Ranking por tema con curaduría del instructor y respaldos | 0016 (B-08) |
| Proveedor de LLM y embeddings | Gemini por defecto, Claude por puerto; embeddings a 768 | 0011, 0012 (B-09) |
| Roles (estudiante, docente, administrador) | Aprendiz, Instructor, Administrador con glosario | 0021 (B-01) |
| Ética y datos personales | Consentimiento versionado, supresión con purga de `_audit`, envío seudonimizado | 0018 |

## Cambios pedidos a archivos compartidos

- `proyecto/decisiones-pendientes.md` (lo edita la sesión principal): marcar D-01 y D-02 como cerradas con los ADR 0012 y 0011, y D-04, D-05, D-06 como «propuestas» en los ADR 0013, 0019 y 0020 (tabla de arriba).
- `docs/adr/0001-postgres-pgvector.md`, sección 7: dice «provisional: 1024». Sugerencia: agregar una nota «superada por el ADR 0012 (768)». No se editó porque el encargo solo pedía notas en 0004, 0005 y 0006.
- `docs/adr/0003-api-domain-first-layout.md`: el dominio `student` pasa a `learner` (ADR 0021) y `ai/` es una excepción por capas (ADR 0008). Sugerencia: nota «complementado por 0008 y 0021».
- `docs/adr/0005-keycloak-postgres-realm-versioned.md`, sección 4: la alternativa «exportar el realm sin usuarios ni secretos» figura como descartada, pero es lo que la sección 3 modificada adoptó. Sugerencia: aclararlo.
- CI (`feature/repo-standards` o Fase 8): incorporar el validador de ADR (`validate_adrs.py`, hoy en el scratchpad de la sesión) como paso de documentación.
