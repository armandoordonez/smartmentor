# Glosario de roles y etiquetas

Aplica la sección 13 del [plan de implementación](../../PLAN_IMPLEMENTACION_V3.md). El objetivo es que SmartMentor no quede atado al mundo universitario: el código y la base de datos usan términos neutros en inglés, y el texto que ve el usuario sale de un glosario configurable. Una instalación sirve a **un** contexto; esto no es soporte para varias organizaciones a la vez.

Los documentos de diseño usan las etiquetas del perfil `generic` (Aprendiz, Instructor, Administrador). El [brief](../../proyecto/brief.md) conserva «estudiante», «docente» y «cohorte» hasta que el brief v2 (Fase 10) adopte este vocabulario.

## Equivalencias

| Concepto | Antes | Código (inglés) | Etiqueta por defecto | Nota |
| --- | --- | --- | --- | --- |
| Quien aprende | `student` | `learner` | Aprendiz | El dominio `student` de la API pasa a `learner` |
| Quien orienta y revisa el contenido | `teacher` | `instructor` | Instructor | — |
| Quien administra la plataforma | `admin` | `admin` | Administrador (en el menú: «Admin», como en Figma) | — |
| Evaluador externo | rol `evaluator` (DEF-15) | asignación en `course_evaluators` | Evaluador | **No es un rol.** Es un `instructor` asignado a un curso sin ser su dueño; puede anotar ítems (D5b) y calificar a mano (D5c) |
| Curso, tema, ruta, inscripción | ya neutros | sin cambio | Curso, Tema, Ruta de aprendizaje, Inscripción | — |
| `syllabus` | `syllabus_*` | **se conserva** en el código (DEF-26) | «Contenido del curso» o «Programa», según el perfil | Lo usan el brief, el notebook v2 y los prompts |
| Nivel de formación del perfil | `education_level`, `degree_title` | `education_level` con valores `secondary`, `technical`, `undergraduate`, `postgraduate`, `other`, `none`, y `qualification_title` | Nivel de formación, Título | La hoja de vida ya mezcla lo académico y lo laboral (`job_title`, `experience_band`, `tools`) |
| Grupo | «cohorte» | `group_label` | Grupo | «Cohorte» queda como término del proyecto de investigación, no del producto |
| Emisor del badge y textos legales | «universidad» | `BADGE_ISSUER_NAME` y `ORGANIZATION_NAME` en `.env` | La organización responsable | Los textos de A3, A3b y A3c se revisan con jurídica |

Los campos de los esquemas de IA pasan de `student_*` a `learner_*` (por ejemplo `simulated_student` → `simulated_learner`). El notebook del Mago de Oz no se edita.

## Etiquetas por perfil de contexto

Se elige con `APP_CONTEXT_PROFILE` en `.env`. Solo `generic` es P0; `academic` y `corporate` son una mejora P2.

| Código | `generic` (por defecto) | `academic` (P2) | `corporate` (P2) |
| --- | --- | --- | --- |
| `learner` | Aprendiz | Estudiante | Colaborador |
| `instructor` | Instructor | Docente | Capacitador |
| `admin` | Administrador | Administrador | Administrador |
| Evaluador (asignación) | Evaluador | Evaluador | Evaluador |
| Grupo (`group_label`) | Grupo | Cohorte | Equipo |
| `syllabus` | Contenido del curso | Syllabus | Programa de formación |

Las etiquetas de `academic` y `corporate` de grupo y de `syllabus` son una propuesta de este documento; el plan solo fija las de los tres roles. Se validan con el dueño (DEF-23 y DEF-24) antes de implementarlas.

## Qué cambia con el perfil y qué no

| Cambia (solo texto visible) | No cambia nunca |
| --- | --- |
| Etiquetas de rol en el menú, los títulos y los avisos | Los códigos de rol `learner`, `instructor` y `admin` |
| Etiqueta de grupo y de `syllabus` | Nombres de tablas y columnas (`syllabus_documents`, `group_label`) |
| `role_labels` de `GET /me` | Rutas de la API, enumeraciones (`Role.LEARNER`, `Role.INSTRUCTOR`, `Role.ADMIN`) y esquemas JSON |
| Textos de la interfaz que citan al rol (p. ej., «Tu rol: Instructor · Solo corriges contenido de TUS cursos») | Identificadores de código, claves de sesión y `key` de widgets |
| Archivo de tema `themes/<perfil>.css`, que solo redefine variables (P2) | La matriz de permisos y la lógica de autorización |

## Dónde viven las etiquetas

- **Archivo, no tabla:** `app/src/core/labels.py` con un diccionario por perfil, más `config/labels.yaml` si se necesita compartirlo con la API. No se agrega una tabla de traducciones.
- `GET /me` devuelve `roles`, `role_labels` y `default_role` (CU-35).
- Los textos de A3, A3b y A3c usan `ORGANIZATION_NAME`, no la palabra «universidad».

## Términos del producto

| Término | Significado |
| --- | --- |
| Ruta de aprendizaje | Secuencia de pasos (temas) de un curso, personalizada para un aprendiz |
| Paso de ruta | Un tema dentro de la ruta de un aprendiz, con su estado (`path_steps.status`) |
| Tema crítico | Tema con intentos agotados; genera una alerta para el instructor |
| Intentos extra | Intentos adicionales que habilita el instructor; se registran en `attempt_grants` y se reportan aparte |
| Ruta fija | Variante del piloto para el grupo de comparación: mismo contenido y umbrales, sin omitir temas |
| Autorización | Consentimiento del aprendiz: tratamiento de datos (obligatoria) y piloto (opcional) |
| Anotación ciega | Evaluación de ítems por dos evaluadores sin ver la del otro |
| Fidelidad | Medida de qué tanto un recurso generado se apoya en sus fuentes citadas |
| Ítems equivalentes | Preguntas de diagnóstico y de la final comparables entre sí, necesarias para la ganancia de Hake |
