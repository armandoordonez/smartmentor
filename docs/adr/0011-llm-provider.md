# ADR 0011: Proveedor de LLM (cierra D-02)

* **Estado:** Aceptado (DEF-01, decidido por el dueño el 2026-11-07). Quedan por fijar los nombres exactos de los modelos y sus tarifas (P-05) y el monto real del presupuesto (P-20)
* **Fecha:** 2026-11-07
* **Autor:** eduar.troyano
* **Fuente:** [plan de implementación v3](../../PLAN_IMPLEMENTACION_V3.md), secciones 3.2, 5.4.6, 5.4.11, 16.2, 18.5 y DEF-01; [`proyecto/decisiones-pendientes.md`](../../proyecto/decisiones-pendientes.md), D-02
* **Relacionados:** [ADR 0008](0008-ai-service-architecture.md), [ADR 0012](0012-embedding-model-and-dimension.md), [ADR 0018](0018-personal-data-protection.md)

---

## 1. Contexto

El brief admite Claude, GPT u open source, y pide salida estructurada (JSON), modelos pequeños para tareas simples y una métrica de costo por aprendiz y ruta. El pendiente D-02 seguía abierto y las fuentes se contradecían:

- el notebook v2 del Mago de Oz usa Gemini (`google-genai` con `response_json_schema`, modelo de generación en `SM_LLM_MODEL`);
- la pantalla AD2 de Figma v3 muestra modelos de Claude.

Ninguno de los dos notebooks se ejecutó con el LLM real: no hay datos de calidad, costo ni latencia (plan 3.1). Las tarifas vigentes y la existencia del modelo que cita el notebook no se verificaron (P-05).

## 2. Decisión

1. **Gemini es el proveedor por defecto**, el mismo del notebook v2, y **Claude es la alternativa** por el mismo puerto.
2. **Puerto `LlmProvider.generate_structured(prompt, schema, model, temperature) -> (json_text, usage)`** con los adaptadores `GeminiProvider` y `AnthropicProvider`, y `FakeLlmProvider` para pruebas y CI. El SDK de cada proveedor vive solo en su adaptador ([ADR 0008](0008-ai-service-architecture.md)).
3. **Dos niveles de modelo:** `AI_LLM_MODEL_DEFAULT` (generación) y `AI_LLM_MODEL_SMALL` (revisión de ítems, calificación y texto del badge).
4. **Todo en `.env`:** `AI_LLM_PROVIDER`, `AI_LLM_MODEL_DEFAULT`, `AI_LLM_MODEL_SMALL` y `GEMINI_API_KEY` o `ANTHROPIC_API_KEY`. **El código no trae nombres de modelos por defecto**: si falta uno, `/ready` falla con un mensaje claro. `.env.example` los deja vacíos.
5. **Precios en `ai/config/prices.yaml`** (USD por millón de tokens por modelo). El servicio no arranca con un modelo sin precio; el costo de cada llamada queda en `llm_call_logs.cost_usd`.
6. **Presupuesto con topes** (`AI_DAILY_BUDGET_USD`, `AI_COURSE_BUDGET_USD`, `AI_ENROLLMENT_BUDGET_USD`, y la variable nueva `AI_MONTHLY_BUDGET_USD`), vacíos en el ejemplo. Topes simulados del plan (18.5), a reemplazar con el costo real tras la primera corrida: 0,50 USD por inscripción, 2 por curso, 5 al día y 30 al mes.
7. **Temperaturas iniciales del notebook:** 0,1 syllabus; 0,0 revisión de ítems, fidelidad y calificación; 0,5 diagnóstico; 0,6 quiz y final.

## 3. Alternativas descartadas

- **Claude como proveedor por defecto:** coincide con AD2, pero obliga a reescribir lo que el notebook ya resuelve con Gemini (esquemas, reintentos, embeddings del mismo proveedor). Queda disponible por el puerto.
- **Un modelo open source local:** costo por token cero, pero exige operar infraestructura de inferencia que el piloto no necesita.
- **Fijar los nombres de modelos en el código:** contradice la decisión R-3 (modelos y configuración en `.env`).

## 4. Consecuencias

- **Positivas:** se reutiliza el código y los esquemas del notebook; un solo proveedor para el LLM y los embeddings ([ADR 0012](0012-embedding-model-and-dimension.md)); cambiar de proveedor es configuración y una corrida del arnés de evaluación.
- **Negativas y pendientes:**
  - Gemini respeta peor las uniones y los diccionarios libres (lección L-07): los esquemas `…LLM` son planos y los rangos se validan en código.
  - Antes de la primera corrida con LLM real (Fase 4) hay que verificar los modelos vigentes y sus tarifas (P-05) y llenar `prices.yaml`.
  - Los datos que se envían al proveedor dependen de la política de datos personales ([ADR 0018](0018-personal-data-protection.md), DEF-05).
  - AD2 debe mostrar lo que diga el log, no los modelos fijos del prototipo (C-06).
