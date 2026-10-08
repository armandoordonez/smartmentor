# 3. Prototipo navegable de alta fidelidad

Actividad 3 de la Fase 0. Resultado esperado: **enlace clicable para pruebas**.

## Enlaces

- **Figma (diseño):** [SmartMentor · Prototipo Fase 0 v2 (Estudiante, Docente, Admin)](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-37)
- **Streamlit con datos de ejemplo:** [`app/`](../../app/README.md), mismas pantallas que Figma, sin login (entra por el selector de rol A1).

Para incrustarlo en una página web o en Notion (GitHub no muestra iframes dentro de los `.md`):

```html
<iframe style="border: 1px solid rgba(0, 0, 0, 0.1);" width="800" height="450"
  src="https://embed.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-37&embed-host=share"
  allowfullscreen></iframe>
```

## Puntos de inicio del modo presentación

| Flujo | Primera pantalla | Uso en la prueba de usabilidad |
| --- | --- | --- |
| Selector de rol | A1 | Demo general |
| Login estudiante | A2 | Tareas T1 a T6 del estudiante |
| Login docente | A4 | Tareas del docente |
| Catálogo | E1 | Retomar una tarea sin pasar por el login |
| Mis cursos | D1 | Retomar una tarea del docente |
| Sesión expirada | A7 | Solo demo |

## Inventario de pantallas

| Código | Pantalla | Rol | Nodo de Figma | Streamlit (`app/src/pages/`) |
| --- | --- | --- | --- | --- |
| A1 | Selector de rol | Todos | [`2:169`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-169) | `common/role_selector.py` |
| A2 | Login estudiante | Estudiante | [`2:201`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-201) | — (pantallas de Keycloak; su estilo va al tema del realm) |
| A3 | Registro | Estudiante | [`2:225`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-225) | — (pantallas de Keycloak; su estilo va al tema del realm) |
| A4 | Login docente | Docente | [`2:251`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-251) | — (pantallas de Keycloak; su estilo va al tema del realm) |
| A5 | Recuperar contraseña | Todos | [`2:275`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-275) | — (pantallas de Keycloak; su estilo va al tema del realm) |
| A6 | 403 Sin permiso | Todos | [`2:290`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=2-290) | `main.py` + `core/errors.py`: se muestra al abrir una página de otro rol |
| A7 | Sesión expirada | Todos | [`8:2`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=8-2) | `main.py` + `core/errors.py` |
| E1 | Catálogo de rutas | Estudiante | [`5:2`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-2) | `student/catalog.py` |
| E2 | Perfil | Estudiante | [`5:37`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-37) | `student/diagnostic.py` (paso 1) |
| E3 | Diagnóstico | Estudiante | [`5:61`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-61) | `student/diagnostic.py` (paso 2) |
| E4 | Resultado del diagnóstico y objetivo | Estudiante | [`5:97`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-97) | `student/diagnostic.py` (paso 3) |
| E5 | Vista de ruta | Estudiante | [`5:148`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-148) | `student/my_path.py` |
| E6 | Tema | Estudiante | [`5:209`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-209) | `student/topic.py` |
| E7 | Resultado del quiz | Estudiante | [`5:245`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-245) | `student/topic.py` |
| E8 | Evaluación final | Estudiante | [`3:348`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=3-348) | `student/final_assessment.py` |
| E9 | Repaso dirigido | Estudiante | [`5:280`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-280) | `student/review.py` |
| E10 | Badge | Estudiante | [`5:311`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-311) | `student/badge.py` |
| E11 | Mi progreso | Estudiante | [`5:348`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-348) | `student/progress.py` |
| E12 | Logros | Estudiante | [`5:382`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=5-382) | `student/achievements.py` |
| D1 | Mis cursos | Docente | [`3:2`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=3-2) | `teacher/courses.py` |
| D2 | Curso y syllabus | Docente | [`6:2`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=6-2) | `teacher/syllabus_review.py` |
| D3 | Ruta y avance | Docente | [`6:107`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=6-107) | `teacher/dashboard.py` |
| D4 | Detalle de estudiante | Docente | [`3:71`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=3-71) | `teacher/student_detail.py` |
| D5 | Revisión de recursos y preguntas | Docente | [`8:13`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=8-13) | `teacher/content_review.py` |
| AD1 | Usuarios y roles | Admin | [`3:174`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=3-174) | `admin/users.py` |
| AD2 | Log LLM y costos | Admin | [`3:262`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=3-262) | `admin/llm_logs.py` |
| AD3 | Métricas globales | Admin | [`8:133`](https://www.figma.com/design/wIzBv0tOtRaoVmldEXPyff/SmartMentor-%C2%B7-Prototipo-Fase-0-v2--Estudiante--Docente--Admin-?node-id=8-133) | `admin/metrics.py` |

Además: frame «Matriz de permisos» y «Biblioteca de componentes» (13 componentes, 3 conjuntos).

> Los nodos vienen de [`app/CLAUDE.md`](../../app/CLAUDE.md#4-pantallas-de-figma--páginas). El enlace compartido para esta fase (`node-id=5-37`) abre E2 · Perfil, el inicio del recorrido del estudiante tras inscribirse.

## Ajustes pendientes antes de la prueba de usabilidad

Tomados del [análisis del prototipo](../README.md#análisis-detallado-del-prototipo-de-figma), en orden de prioridad:

- [ ] Unificar los datos de ejemplo: 5 temas más la final (E1 y E6 dicen 6), intentos y puntaje de Laura en Regresión logística (E5, D3 y D4 no coinciden), badge de E12 coherente con el avance de E5.
- [ ] Agregar login de admin (A8) o decidir que el admin no gestiona cursos (ver [casos de uso](../01-flujo-y-casos-de-uso/casos-de-uso.md#decisiones-que-el-director-debe-tomar)).
- [ ] Conectar A6 (403) desde algún punto del flujo para que se vea en modo presentación.
- [ ] Agregar estados: quiz no aprobado (E7), catálogo vacío, docente sin cursos, error al generar contenido con IA, verificación en dos pasos.
- [ ] Agregar la pantalla D0 · Crear curso y cargar syllabus.
- [ ] Mostrar preguntas de respuesta corta en E6 y E8 (D5 ya las incluye).
- [ ] Ocultar o explicar al participante el botón «(Demo del prototipo) Ver resultado menor a 80 %» de E8.
- [ ] Publicar estilos de color y texto, y trabajar sobre la versión maestra del archivo (la analizada es una copia).
