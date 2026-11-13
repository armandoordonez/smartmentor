# Mejoras propuestas

Cosas que nadie pidió pero conviene hacer. El dueño decide: ✔ aceptada, ✖ descartada (con el motivo).

| ID | Propuesta | Por qué | Registrada | Estado |
| --- | --- | --- | --- | --- |
| M-001 | Agregar a la [plantilla de PR](../../.github/pull_request_template.md) una sección «IDs de seguimiento» y la casilla «la base es `dev`, o se cambió antes de fusionar el PR de abajo» | Así cada PR enlaza con su tarea y se evita que se repita B-001 | 2026-11-12 13:57 | ☐ |
| M-002 | Mover `pr-3-descripcion-actualizada.md` (sin versionar, solo en el equipo del dueño) de la raíz a `proyecto/seguimiento/pr/` o borrarlo, porque ya está publicado como descripción del PR 3 | Hoy está suelto en la raíz y sin versionar | 2026-11-12 13:57 | ☐ |
| M-003 | Que `proyecto/scripts/avance.sh` lea también `HOJA_DE_RUTA.md` para calcular el avance | Así el porcentaje del checklist no se queda viejo (B-002) | 2026-11-12 13:57 | ☐ |
| M-004 | Etiquetar los PR en GitHub con su ID (`T-012`, `B-001`) | Para buscarlos rápido desde la interfaz de GitHub | 2026-11-12 13:57 | ☐ |
| M-005 | Hacer la revisión visual en el navegador de cada pantalla frente a su captura de Figma, con un registro aquí | Las bitácoras F07b y F07c dicen que nunca se hizo; las pruebas comparan textos, no cómo se ve | 2026-11-12 13:57 | ☐ Requiere levantar la app (hoy no autorizado) |
| M-006 | Que D5 («Revisar recursos y preguntas») avise, mientras el curso está en borrador, que los recursos y las preguntas se generan al pulsar «Aprobar y publicar» | El dueño vio la pantalla vacía y no sabía por qué. Figma no dibuja ese estado, así que el texto se decide con el dueño | 2026-11-12 17:39 | ☐ |
| M-007 | Revisar si el p95 de unos 120 s en `items.generate_quiz_bank`, `items.generate_final_bank` y `diagnostic.generate_items` es un límite de tiempo del cliente de Gemini o del trabajador, y si corta generaciones | En la evidencia de F6, las 3 tareas tienen el mismo p95 (120,1 a 120,9 s) | 2026-11-13 10:19 | ✔ Confirmado: es el timeout de `ai/` → [B-013](BUGS.md) |
| M-008 | Una prueba de la app que compare `services/staff_prompts.py` con `prompts/catalog.yaml` (ids, versiones y nombres) | Hoy coinciden, pero la prueba que existe solo revisa que no se repitan los ids: un prompt v2 no se notaría en C4 | 2026-11-13 10:22 | ◐ Hecho, sin commit: `app/tests/unit/test_prompt_catalog_sync.py` |
