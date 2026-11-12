# Figma: huecos y contradicciones

El [archivo de Figma v3](https://www.figma.com/design/atp2fZdSolEoaww3n9jRLg/SmartMentor-%C2%B7-Prototipo-Fase-0-v3-4) es el **prototipo para ver cómo luce** cada pantalla. Las reglas y los datos salen de la API y de los casos de uso ([`design/01-flujo-y-casos-de-uso/`](../../design/01-flujo-y-casos-de-uso/)). Cuando Figma no dibuja algo que el código necesita, o se contradice, se anota aquí y **se avisa al dueño antes de inventar el diseño**.

## Estado del archivo en vivo (revisado el 2026-11-12 13:55)

- Una página, «SmartMentor v2», con 96 pantallas, la matriz de permisos y la biblioteca de componentes.
- Los nombres de todas las pantallas coinciden con la copia del repo en [`design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json`](../../design/03-prototipo-alta-fidelidad/v3/estructura-pantallas.json). No apareció ninguna pantalla nueva ni faltó ninguna. Solo se compararon los nombres, no el contenido de cada una (eso deja abierta en parte la P-14 del plan).
- Todas las pantallas que le tocan a la app tienen página en `app/src/pages/` ([`navigation.py`](../../app/src/core/navigation.py)). A2, A4 y A5 son de Keycloak y no se construyen.

## Huecos (Figma no lo dibuja)

| ID | Registrado | Qué falta | Dónde se necesita | Mientras tanto | Estado |
| --- | --- | --- | --- | --- | --- |
| F-001 | 2026-11-12 13:55 | Estado de **error de un trabajo de IA** en las pantallas de carga (U1a–U1d, D1c) | Diagnóstico, quiz, final y extracción del syllabus | El código lo resuelve con `ai_jobs.status` ([`flujos.md`](../../design/01-flujo-y-casos-de-uso/flujos.md#casos-de-error-de-las-pantallas-de-carga-u1x)) | ☐ Dibujar o aprobar lo que hay |
| F-002 | 2026-11-12 13:55 | **Catálogo vacío** (E1 sin rutas) | CU-02 | Por definir | ☐ |
| F-003 | 2026-11-12 13:55 | **Instructor sin cursos** (D1 vacío) | Primer ingreso del instructor | Por definir | ☐ |
| F-004 | 2026-11-12 13:55 | **Menú de perfil con cambio de rol** (CU-35). Figma solo tiene el selector previo al login (A1) | Usuarios con varios roles | Por definir | ☐ |
| F-012 | 2026-11-12 14:18 | **D5f pide datos que el sistema no recoge.** Figma muestra una calificación promedio («4,5»), el efecto en el quiz («+11 pts»), los reportes y un índice con 6 pesos (calificación 30 %, quiz 30 %, vista completa 15 %, reportes 10 %, fuente 10 %, subtítulos 5 %). El aprendiz (E6) solo elige una etiqueta (`useful`, `audio_issue`, `outdated`, `too_long`), si vio el video completo y un comentario. La API calcula un índice bayesiano con la proporción de «útil». Tampoco calcula el estado (recomendado, en observación, en revisión) ni agrupa los comentarios con IA | Calidad de los videos (T-014) | Decisión del dueño (2026-11-12 14:22): **la pantalla se ajusta a lo que mide la API**. Índice, «% útil», vista completa y etiquetas; «Efecto en el quiz» en «—»; la API calcula el estado con los umbrales 75 y 60 de Figma | ✔ Decidido (código ⏳ sin commit) |
| F-013 | 2026-11-12 14:33 | **No hay estado «sin piloto»** en AD4: Figma siempre muestra un piloto ya creado. Con la API real puede no existir ninguno (se crea con `POST /pilots`) | Piloto (T-015d) | La página muestra un aviso y no ofrece crear uno. Falta decidir si se agrega un formulario de creación (ruta y fechas) | ☐ Decide el dueño |
| F-014 | 2026-11-12 14:3x (aprox.) | **AD4 dice «ítems equivalentes entre el diagnóstico y la evaluación final»**, pero el modelo de datos agrupa como equivalentes las versiones paralelas de la final y de la prueba de retención (`assessment_items.equivalence_group`, `docs/evaluation/metrics.md`). El diagnóstico no tiene grupo | Piloto (T-015d) | Decisión del dueño (2026-11-12 14:38): se cuenta lo que define `metrics.md` (temas con un grupo de dos o más versiones) y se cambia el texto de la pantalla | ✔ Decidido (código ⏳ sin commit) |
| F-005 | 2026-11-12 13:55 | **Login del administrador**: no tiene pantalla propia | Acceso admin | Se usa la de A4 (Keycloak) | ✖ Resuelto por Keycloak |

## Contradicciones conocidas (de [`design/03…/README.md`](../../design/03-prototipo-alta-fidelidad/README.md#ajustes-pendientes-antes-de-la-prueba-de-usabilidad))

| ID | Registrado | Contradicción | Estado |
| --- | --- | --- | --- |
| F-006 | 2026-11-12 13:55 | Los datos de Laura (Regresión logística) no coinciden entre E5, D3 y D4. Julián Pérez aparece como «Abandonada» en D3 y «En espera por intentos agotados» en D4b (C-14, C-15) | ☐ |
| F-007 | 2026-11-12 13:55 | A3b muestra la fecha del piloto como del 2 al 15 de noviembre de 2026, que ya no es posible (C-03, P-09) | ☐ Decide el dueño |
| F-008 | 2026-11-12 13:55 | La calidad del video («81 de 100») se muestra antes de que el aprendiz califique (C-08) | ☐ |
| F-009 | 2026-11-12 13:55 | Marcas de terceros en los cursos de IA aplicada («Nuevo · Anthropic», «Nuevo · Google», «Claude Ventas») (C-01, DEF-04) | ☐ Decide el dueño |
| F-010 | 2026-11-12 13:55 | D2b dice «Embedding» donde debe decir «Revisión» (C-16) | ☐ |
| F-011 | 2026-11-12 13:55 | Falta confirmar el valor de la variable `error/acento` (`118:923`) (P-13) | ☐ |
