# Seguimiento y trazabilidad

Esta carpeta lleva el registro de lo que falta, lo que se hace, los bugs y las subidas a GitHub, con fecha y hora de cada cosa. Empezó el 2026-11-12 13:57 (-05), con `dev` en `d8de841`.

Completa al plan, no lo reemplaza. [`PLAN_IMPLEMENTACION_V3.md`](../../PLAN_IMPLEMENTACION_V3.md) sigue siendo el plan, y [`proyecto/bitacora/`](../bitacora/) guarda las bitácoras por fase para el brief v2. Aquí se lleva el trabajo del día a día.

## Archivos

| Archivo | Qué guarda | Cómo se escribe |
| --- | --- | --- |
| [`HOJA_DE_RUTA.md`](HOJA_DE_RUTA.md) | Lo que falta, por etapas, con tareas `T-NNN` y su estado | Se actualiza el estado y la fecha de cada tarea |
| [`BITACORA.md`](BITACORA.md) | Cada cambio, en orden cronológico | **Solo se agregan entradas al final**, nunca se borran ni se editan |
| [`BUGS.md`](BUGS.md) | Bugs `B-NNN`: cuándo se encontró, cuándo se corrigió y dónde | Se actualiza el estado; el historial va en la bitácora |
| [`FIGMA.md`](FIGMA.md) | Lo que Figma no tiene o contradice, y cómo se resolvió (`F-NNN`) | Igual que los bugs |
| [`SUBIDAS.md`](SUBIDAS.md) | Cada `push` a GitHub y cada pull request (`S-NNN`) | Solo se agregan entradas |
| [`MEJORAS.md`](MEJORAS.md) | Propuestas que nadie pidió pero conviene hacer (`M-NNN`) | Se marca si se aceptan o se descartan |

## Fecha y hora

- Siempre en la hora de Bogotá (`America/Bogota`, -05), la misma zona de la base de datos. Formato: `AAAA-MM-DD HH:MM`.
- Se saca así, para no depender de la zona del equipo (este equipo está en UTC):

  ```bash
  TZ=America/Bogota date '+%Y-%m-%d %H:%M'
  ```

## Estados

| Símbolo | Tareas y mejoras | Bugs y huecos de Figma |
| --- | --- | --- |
| ☐ | Pendiente | Abierto |
| ◐ | En curso | En corrección |
| ⏳ | Hecho en local, sin subir | Corregido en local, sin subir |
| ⬆ | Subido a una rama, sin PR | Corrección subida, sin PR |
| 🔼 | Subido a una rama, con PR abierto | Corrección subida, PR abierto |
| ✔ | En `dev` | Corregido y en `dev` |
| ⛔ | Bloqueado (se dice por qué) | Bloqueado |
| ✖ | Descartado (se dice por qué) | No es un bug, o no se corrige |

## Identificadores

`T-NNN` tarea, `B-NNN` bug, `F-NNN` hueco de Figma, `V-NNN` diferencia visual frente a Figma (revisión T-034, en `FIGMA.md`), `M-NNN` mejora, `S-NNN` subida. Son correlativos, nunca se reutilizan y se citan en los commits y los PR. Así, desde cualquier commit se llega a la tarea y desde la tarea al commit.

## Flujo de trabajo

1. **Local.** Los cambios se hacen en este equipo, en una rama `feature/<tema>` o `fix/<tema>` creada desde `dev` actualizada (`git fetch origin && git switch -c feature/<tema> origin/dev`).
2. **Registro al momento.** Al empezar, al terminar y al encontrar algo, se agrega una entrada en `BITACORA.md` y se cambia el estado en el archivo que corresponda.
3. **Commit.** Se usa [Conventional Commits](../../CONTRIBUTING.md#3-commits) en español, con el ID entre corchetes al final del título (`fix(app): … [B-002]`) y el pie de coautoría del equipo. El hash queda anotado en la bitácora.
4. **Pruebas.** `api/scripts/dev.sh all` y `app/scripts/dev.sh all` se corren antes de subir. El resultado real se anota en la bitácora, también si falla. *Desde el 2026-11-12 el dueño autorizó levantar el stack y correr las pruebas en este equipo. Lo que no se puede correr aquí (por ejemplo, la integración de la API, que usaría la base de Neon) queda «sin verificar» hasta que pase la CI.*
5. **Subida.** `git push -u origin <rama>` **solo con la aprobación del dueño en cada subida**. Nunca a `dev`, `stage` ni `main`, y nunca con `--force`.
6. **Pull request** hacia `dev`, con la [plantilla](../../.github/pull_request_template.md) y los IDs que cubre. Se registra en `SUBIDAS.md` con la fecha, la rama, los commits, el enlace y el estado de la CI.
7. **Fusión.** Cuando el PR entra a `dev`, los IDs pasan a ✔ con la fecha y el commit de la fusión.

### Lección aprendida: PR apilados

Si un PR va encima de otro (su base no es `dev`), **antes de fusionar el de abajo** hay que cambiar la base del de arriba a `dev`. Si no se hace, el de arriba se fusiona en una rama ya cerrada y su cambio nunca llega a `dev`. Eso pasó con el PR 4 ([B-001](BUGS.md)).
