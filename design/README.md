# design/

Prototipo, wireframes y enlace a Figma (Fase 0). Hay una carpeta por cada actividad de la [Fase 0 del brief](../proyecto/brief.md#fase-0-prototipado-de-la-interfaz-y-del-flujo). El punto de partida es el análisis del prototipo de Figma que se resume abajo, hecho sobre el archivo «SmartMentor · Prototipo Fase 0 v2 (Estudiante, Docente, Admin) (Copy)», modificado por última vez el 2026-10-08 a las 03:25 UTC. La fuente fue el JSON de la API de Figma (estructura, textos, interacciones y puntos de inicio del prototipo); el aspecto visual (contraste, jerarquía, legibilidad) no se evaluó.

Leyenda: ✅ cumple · ⚠️ cumple parcialmente · ❌ no cumple · ➖ no verificable desde Figma

## Resumen del análisis

| Actividad de la Fase 0 | Estado | Comentario breve |
|---|---|---|
| 1. Mapa del flujo y casos de uso | ⚠️ | Hay matriz de permisos y flujos por rol, pero no hay diagrama BPMN ni de estados |
| 2. Wireframes de baja fidelidad (7 pantallas) | ➖ | No están en el archivo; las 7 pantallas sí existen en alta fidelidad |
| 3. Prototipo navegable de alta fidelidad | ✅ | 28 pantallas, 6 puntos de inicio, casi todas conectadas |
| 4. Prueba "Mago de Oz" (salidas de IA) | ⚠️ | Contenido realista y trazable, pero sin esquemas JSON y con datos inconsistentes entre pantallas |
| 5. Prueba de usabilidad (3 a 5 usuarios) | ❌ / ➖ | No hay guion de tareas, SUS ni lista de cambios en el archivo |
| Criterio de salida | ❌ / ➖ | Falta evidencia de aprobación y de esquemas JSON versionados |

## Estado de la fase

Actualizado el 2026-10-08. La columna «Análisis de Figma» es el punto de partida (ver el [análisis detallado](#análisis-detallado-del-prototipo-de-figma)); «Estado actual» es lo que ya está en cada carpeta. Ninguna actividad está cerrada: todas dependen de una aprobación o de una prueba con usuarios.

| # | Actividad | Carpeta | Resultado esperado | Análisis de Figma | Estado actual |
| --- | --- | --- | --- | --- | --- |
| 1 | Mapa del flujo y casos de uso | [`01-flujo-y-casos-de-uso/`](01-flujo-y-casos-de-uso/README.md) | Flujo aprobado por el director | ⚠️ Matriz de permisos y flujos por rol, sin diagrama de flujo ni de estados | ⚠️ BPMN 2.0 con carriles y diagramas de estados en draw.io (con SVG), flujos por rol y 16 casos de uso en Mermaid; falta la aprobación del director |
| 2 | Wireframes de baja fidelidad (7 pantallas) | [`02-wireframes-baja-fidelidad/`](02-wireframes-baja-fidelidad/README.md) | Estructura de cada pantalla | ➖ No están en Figma; las 7 pantallas existen en alta fidelidad | ⚠️ Las 7 pantallas en Excalidraw y SVG; falta la revisión del responsable de producto |
| 3 | Prototipo navegable de alta fidelidad | [`03-prototipo-alta-fidelidad/`](03-prototipo-alta-fidelidad/README.md) | Enlace clicable para pruebas | ✅ 28 pantallas, 6 puntos de inicio, casi todas conectadas | [Figma](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-37) y Streamlit. ⚠️ Faltan los ajustes de la lista de abajo antes de la prueba de usabilidad |
| 4 | Prueba de prompts «Mago de Oz» | [`04-prueba-mago-de-oz/`](04-prueba-mago-de-oz/README.md) | Ejemplos reales de salida y esquemas JSON | ⚠️ Contenido realista y trazable, sin esquemas JSON y con datos inconsistentes | ⚠️ Protocolo y campos de las 9 salidas listos; sin ejecutar y sin esquemas en `prompts/` |
| 5 | Prueba de usabilidad (3 a 5 usuarios) | [`05-prueba-de-usabilidad/`](05-prueba-de-usabilidad/README.md) | Lista priorizada de cambios | ❌ / ➖ Sin guion, SUS ni lista de cambios | ❌ Guion de tareas, SUS y plantilla de resultados listos; sin ejecutar |

## Criterio de salida de la fase

- [ ] Flujo y pantallas aprobados por el director (registro en [`01-flujo-y-casos-de-uso/README.md`](01-flujo-y-casos-de-uso/README.md#registro-de-aprobación)).
- [ ] Esquemas JSON de cada salida de IA definidos y versionados en [`prompts/`](../prompts/README.md) (lista en [`04-prueba-mago-de-oz/README.md`](04-prueba-mago-de-oz/README.md#salidas-y-esquemas)).

## Cambios recomendados, en orden de prioridad

Salen del [análisis detallado](#análisis-detallado-del-prototipo-de-figma). Para cada uno se indica dónde se atiende.

| # | Cambio | Dónde | Estado |
| --- | --- | --- | --- |
| 1 | Definir y versionar los esquemas JSON de las 9 salidas de IA, con los campos que ya muestran las pantallas | [`04-prueba-mago-de-oz/`](04-prueba-mago-de-oz/README.md#salidas-y-esquemas) → `prompts/schemas/` | Campos identificados; esquemas sin escribir |
| 2 | Unificar los datos de ejemplo: número de temas, puntajes e intentos de Laura, fecha del badge | Reglas en [`estados.md`](01-flujo-y-casos-de-uso/estados.md); aplicar en Figma y en `app/` | Reglas propuestas; falta aplicarlas |
| 3 | Crear el diagrama de flujo o de estados y registrar la aprobación del director | [`01-flujo-y-casos-de-uso/`](01-flujo-y-casos-de-uso/README.md) | BPMN y estados en draw.io, flujos en Mermaid; falta la aprobación |
| 4 | Agregar login de admin y conectar su navegación con la gestión de cursos, o ajustar la matriz de permisos | [Decisión 1 de los casos de uso](01-flujo-y-casos-de-uso/casos-de-uso.md#decisiones-que-el-director-debe-tomar) | Pendiente de decisión |
| 5 | Conectar A6 (403) y agregar los estados faltantes: quiz no aprobado, estados vacíos, error de generación con IA | [`03-prototipo-alta-fidelidad/`](03-prototipo-alta-fidelidad/README.md#ajustes-pendientes-antes-de-la-prueba-de-usabilidad) | Pendiente en Figma |
| 6 | Agregar la pantalla de creación de curso y carga del syllabus (D0) | [Flujo del docente](01-flujo-y-casos-de-uso/flujos.md#docente) | Propuesta en el flujo; pendiente en Figma |
| 7 | Preparar el guion y el SUS, ejecutar la prueba con 3 a 5 estudiantes y un docente, y documentar los cambios | [`05-prueba-de-usabilidad/`](05-prueba-de-usabilidad/README.md) | Instrumentos listos; sin ejecutar |
| 8 | Publicar estilos de color y texto, y trabajar sobre la versión maestra de Figma (la analizada es una copia) | Figma | Pendiente |

## Inconsistencias del prototipo que hay que resolver antes de las pruebas

- **Número de temas:** E1 dice «6 temas» y E6 «Tema 3 de 6», mientras E4, E5, E10, E11 y D2 trabajan con 5. Propuesta: 5 temas y la evaluación final aparte.
- **Laura en Regresión logística:** E5 dice «Intento 2 de 3 · 60 %, en curso», D4 «Intento 2 · 80 %, aprobado» y D3 «72 %».
- **Badge:** E12 lo muestra obtenido (5 oct, 88 %) mientras E5 y E11 muestran 2 de 5 temas.
- **Cortes del diagnóstico:** E4 usa «por reforzar» y «por aprender» sin cortes definidos. Propuesta: ≥ 80 % dominado, 50 a 79 % por reforzar y < 50 % por aprender.
- **Tipos de pregunta:** D5 incluye respuesta corta, pero E6 y E8 solo muestran opción múltiple.
- **Botón de demo de E8** («Ver resultado menor a 80 %»): hay que ocultarlo o explicarlo al participante.

## Análisis detallado del prototipo de Figma

Lista de chequeo por actividad, tal como quedó en el análisis. Lo que ya se atendió en las carpetas está en «Estado de la fase» y en «Cambios recomendados».

### 1. Flujo y casos de uso (estudiante, docente, admin)

- [ ] ❌ **Diagrama BPMN o de estados del flujo.** No existe en el archivo ningún frame de diagrama. → Atendido en [`01-flujo-y-casos-de-uso/`](01-flujo-y-casos-de-uso/README.md).
- [x] ✅ **Casos de uso por rol documentados.** El frame «Matriz de permisos» define 12 acciones con permisos por Estudiante, Docente y Admin.
- [x] ✅ **Caso de uso Estudiante de extremo a extremo.** Login → Catálogo → Perfil → Diagnóstico → Resultado → Ruta → Tema → Resultado del quiz → Evaluación final → Repaso dirigido o Badge → Logros.
- [x] ✅ **Caso de uso Docente.** Mis cursos → Curso y syllabus → Revisión de recursos y preguntas → Ruta y avance → Detalle de estudiante.
- [ ] ⚠️ **Caso de uso Admin.** Existen Usuarios y roles, Log LLM y Métricas globales, pero:
  - No hay pantalla de login de admin: «Entrar como admin» (A1) lleva directo a AD1, sin autenticación.
  - La matriz dice que el admin puede crear cursos, aprobar temas y configurar umbrales, pero su navegación no conecta con ninguna pantalla D1 a D5.
- [ ] ⚠️ **Flujo de carga del syllabus.** D1 tiene el botón «Nuevo curso», pero no existe una pantalla de creación de curso ni de carga del PDF; D2 ya muestra el syllabus cargado.
- [ ] ➖ **Flujo aprobado por el director.** No hay evidencia en el archivo (comentario, nota o frame de aprobación).

### 2. Wireframes de baja fidelidad (7 pantallas)

- [ ] ➖ **Wireframes en papel o Excalidraw.** No están en el archivo de Figma. → Atendido en [`02-wireframes-baja-fidelidad/`](02-wireframes-baja-fidelidad/README.md).
- Cobertura de las 7 pantallas requeridas (en alta fidelidad):
  - [x] ✅ Login → A2 · Login estudiante (más A4 · Login docente)
  - [x] ✅ Catálogo de rutas → E1
  - [x] ✅ Perfil → E2
  - [x] ✅ Diagnóstico → E3 (más E4 · Resultado del diagnóstico)
  - [x] ✅ Vista de ruta → E5
  - [x] ✅ Tema (video + texto + quiz) → E6 (más E7 · Resultado del quiz)
  - [x] ✅ Badge → E10 (más E12 · Logros)
- **Pantallas adicionales al alcance:** A1, A3, A5, A6, A7, E8, E9, E11, D1 a D5, AD1 a AD3, Matriz de permisos y Biblioteca de componentes. El alcance se superó; conviene confirmar con el director que las pantallas extra no retrasan la Fase 1.

### 3. Prototipo navegable de alta fidelidad

- [x] ✅ **Enlace clicable con puntos de inicio.** 6 flujos definidos: Selector de rol, Login estudiante, Login docente, Catálogo, Mis cursos y Sesión expirada.
- [x] ✅ **Conexiones entre pantallas.** Todas las pantallas de estudiante, docente y admin tienen navegación de ida y vuelta.
- [ ] ⚠️ **Pantallas sin conexión de entrada:**
  - A6 · 403 Sin permiso: ninguna pantalla lleva a ella y no es punto de inicio, por lo que no se puede ver en modo presentación.
  - A7 · Sesión expirada: solo accesible como punto de inicio (aceptable para la demo).
- [ ] ⚠️ **Estados alternos.** Existen 403, sesión expirada, repaso dirigido (final < 80 %) y un botón de demo para forzar ese caso en E8. Faltan:
  - Quiz de tema no aprobado (E7 solo muestra el caso aprobado).
  - Estados vacíos (catálogo sin rutas, docente sin cursos).
  - Estado de carga o error al generar contenido con IA.
  - Recuperar contraseña y verificación en dos pasos para docente (A4 menciona la verificación, pero no hay pantalla).
- [x] ✅ **Biblioteca de componentes.** 13 componentes y 3 conjuntos (botón, estado, barras de navegación por rol).
- [ ] ⚠️ **Estilos compartidos.** El archivo tiene 0 estilos publicados (color, texto). Recomendable definirlos antes de pasar a código para fijar los tokens de diseño.
- [ ] ⚠️ **Versión del archivo.** El archivo analizado es una copia («(Copy)»). Verificar que el enlace de pruebas apunte a la versión maestra.

### 4. Prueba de prompts «Mago de Oz» (salidas de IA)

- [x] ✅ **Syllabus estructurado.** D2 muestra temas con resultado de aprendizaje, nivel de Bloom, prerrequisitos y estado del embedding.
- [x] ✅ **Diagnóstico.** E3 muestra pregunta por tema con nivel de Bloom y opción «No lo sé»; E4 muestra nivel por tema, clasificación y objetivo propuesto con IA.
- [x] ✅ **Tema generado.** E6 incluye explicación con citas [1][2], video con relevancia, quiz y versión del prompt (explicacion_tema v1.3).
- [x] ✅ **Trazabilidad de prompts.** AD2 registra prompts versionados (quiz_tema v1.2, explicacion_tema v1.3, rubrica_corta v1.0), tokens, costo, latencia y tasa de JSON inválido.
- [ ] ➖ **Contenido generado realmente con el LLM.** El texto es verosímil, pero desde Figma no se puede confirmar que proviene de salidas reales y no de redacción manual. Falta enlazar el notebook con las salidas.
- [ ] ❌ **Esquemas JSON definidos.** No hay ningún esquema en el archivo. Los campos de pantalla sugieren estos esquemas mínimos: syllabus, pregunta y resultado del diagnóstico, objetivo, explicación del tema, quiz, calificación del quiz, evaluación final y badge (Open Badges). → Campos en [`04-prueba-mago-de-oz/`](04-prueba-mago-de-oz/README.md#salidas-y-esquemas).
- [ ] ⚠️ **Consistencia de datos entre pantallas.** Ver [inconsistencias del prototipo](#inconsistencias-del-prototipo-que-hay-que-resolver-antes-de-las-pruebas).

### 5. Prueba de usabilidad (3 a 5 usuarios, pensar en voz alta)

- [ ] ❌ / ➖ **Guion de tareas.** No está en el archivo. → Preparado en [`05-prueba-de-usabilidad/`](05-prueba-de-usabilidad/README.md).
- [ ] ❌ / ➖ **Cuestionario SUS aplicado.** El valor «Usabilidad SUS 72» de AD3 es un dato de ejemplo del panel, no evidencia de una prueba.
- [ ] ❌ / ➖ **Registro de participantes (1 docente y 3 a 5 estudiantes).** Sin evidencia.
- [ ] ❌ / ➖ **Lista priorizada de cambios.** Sin evidencia.
- **Insumo aprovechable:** el botón «(Demo del prototipo) Ver resultado menor a 80 %» de E8 sirve para una tarea del guion, pero debe ocultarse o explicarse al participante.

### 6. Criterio de salida

- [ ] ⚠️ **Flujo y pantallas aprobados.** Pantallas completas y navegables; falta la evidencia de aprobación del director.
- [ ] ❌ / ➖ **Esquemas JSON de cada salida de IA definidos y versionados en el repositorio.** No verificable desde Figma y sin referencias en el archivo (no hay enlace al repositorio ni nombres de archivo de esquema).

## Herramientas

Se privilegian herramientas que producen archivos versionables en esta carpeta, porque el criterio de salida exige evidencia versionada.

| Entregable | Herramienta | Alternativa | Archivos |
| --- | --- | --- | --- |
| Mapa de flujo y casos de uso | Mermaid (GitHub lo muestra en los `.md`; se edita en [mermaid.live](https://mermaid.live)) y draw.io con la librería BPMN 2.0 para el BPMN formal | — | `01-flujo-y-casos-de-uso/*.md`, `flujo-bpmn.drawio` y sus `.svg` |
| Wireframes de baja fidelidad | Excalidraw | Papel fotografiado | `02-wireframes-baja-fidelidad/*.excalidraw` y `*.svg` |
| Prototipo de alta fidelidad | Figma | Streamlit con datos de ejemplo ([`app/`](../app/README.md)) | Enlace en `03-prototipo-alta-fidelidad/` |

Notas:

- Mermaid no tiene notación BPMN real; por eso el BPMN formal (carriles, eventos, compuertas) se hizo en draw.io.
- Excalidraw es gratuito, no requiere cuenta y su trazo a mano alzada comunica que es baja fidelidad. Desde *Browse libraries* se puede cargar una biblioteca de wireframing.
- FigJam serviría para los dos primeros entregables sin salir de Figma, pero la cuenta actual (plan Starter) alcanzó el límite de llamadas del conector de Figma, así que no se pueden generar diagramas desde el asistente hasta que se renueve la cuota o se cambie de plan.
