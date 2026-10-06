# Estrategia de Versionamiento y Ramas

## 1. Objetivo

Definir una estrategia de versionamiento para el proyecto que permita:

- Mantener la rama `main` siempre estable y desplegable.
- Desarrollar nuevas funcionalidades de forma aislada.
- Garantizar revisión mediante Pull Request.
- Aplicar **Conventional Commits**.
- Ejecutar validaciones automáticas mediante GitHub Actions.
- Mantener los secretos exclusivamente mediante variables de entorno.
- Identificar claramente las versiones entregadas por cada cohorte.
- Asociar cada versión cerrada con un `tag` y un `release` que contenga el informe de métricas.

---

# 2. Estructura de ramas

Se propone utilizar **tres niveles principales de ramas**:

```text
main
│
├── feature/*
│
└── fix/*
```

No se recomienda crear ramas permanentes adicionales como `develop`, `release` o `staging`, a menos que el proyecto crezca y posteriormente exista una necesidad explícita de ellas.

## 2.1. Rama `main`

La rama `main` representa siempre la versión **estable y desplegable** del proyecto.

### Reglas

- Debe estar protegida.
- No se permite hacer `push` directo.
- Todo cambio debe ingresar mediante Pull Request.
- El Pull Request debe ser revisado y aprobado por otro integrante.
- Las pruebas y validaciones de GitHub Actions deben finalizar correctamente.
- No debe contener código experimental o incompleto.
- Cada cierre de cohorte debe generar un `tag` y un GitHub Release.

Ejemplo:

```text
main
```

---

# 3. Ramas de desarrollo

## 3.1. `feature/*`

Se utilizarán para desarrollar nuevas funcionalidades, componentes, experimentos integrables o cambios funcionales.

### Convención

```text
feature/<descripcion-corta>
```

Ejemplos:

```text
feature/prompt-supervisor
feature/validacion-esquemas
feature/pipeline-inferencia
feature/metricas-evaluacion
feature/integracion-modelo
```

La descripción debe ser:

- corta;
- clara;
- en minúsculas;
- utilizando guiones (`-`);
- relacionada directamente con el objetivo de la rama.

### Flujo

```text
main
  │
  └── feature/nueva-funcionalidad
          │
          ├── commits
          ├── pruebas
          └── Pull Request
                  │
                  ▼
                main
```

Una vez aprobado y fusionado el Pull Request, la rama `feature/*` debe eliminarse.

---

# 4. Ramas para correcciones

## 4.1. `fix/*`

Se utilizarán cuando sea necesario corregir errores encontrados en la versión actual.

Convención:

```text
fix/<descripcion-corta>
```

Ejemplos:

```text
fix/validacion-prompt
fix/error-calculo-metricas
fix/parser-respuesta-modelo
fix/error-esquema
```

Flujo:

```text
main
  │
  └── fix/correccion
          │
          ├── cambios
          ├── pruebas
          └── Pull Request
                  │
                  ▼
                main
```

Al igual que las ramas `feature/*`, deben eliminarse después de ser fusionadas.

---

# 5. Niveles de ramas

La estrategia propuesta queda estructurada de la siguiente manera:

| Nivel | Rama | Propósito | Permanente |
|---|---|---|---|
| 1 | `main` | Código estable y desplegable | Sí |
| 2 | `feature/*` | Nuevas funcionalidades | No |
| 2 | `fix/*` | Correcciones de errores | No |

La estructura deliberadamente evita ramas como:

```text
develop
release/*
hotfix/*
staging
qa
```

Estas ramas pueden introducir complejidad innecesaria para el tamaño inicial del proyecto.

Si posteriormente el proyecto requiere múltiples ambientes o varias versiones mantenidas simultáneamente, la estrategia podrá evolucionar.

---

# 6. Convención de commits

Todos los commits deberán seguir **Conventional Commits**.

Formato:

```text
<tipo>(<alcance>): <descripcion>
```

Tipos principales:

```text
feat      Nueva funcionalidad
fix       Corrección de error
docs      Documentación
test      Pruebas
refactor  Refactorización sin cambio funcional
perf      Mejora de rendimiento
ci        Cambios en integración continua
build     Cambios de construcción/dependencias
chore     Tareas de mantenimiento
```

## Ejemplos

```text
feat(prompt): add supervisor prompt schema
```

```text
fix(metrics): correct accuracy calculation
```

```text
test(prompt): add schema validation tests
```

```text
ci(actions): validate prompt schemas
```

```text
docs(readme): update installation instructions
```

---

# 7. Pull Requests

Ningún cambio debe incorporarse directamente a `main`.

El flujo obligatorio será:

```text
feature/* o fix/*
        │
        ▼
    Pull Request
        │
        ├── Revisión por otro integrante
        ├── Pruebas automáticas
        ├── Validación de esquemas
        └── Aprobación
                │
                ▼
              main
```

## Reglas mínimas del Pull Request

Cada Pull Request debe:

1. Tener un título descriptivo.
2. Explicar qué problema resuelve.
3. Indicar los cambios realizados.
4. Indicar las pruebas ejecutadas.
5. Tener al menos una revisión/aprobación de otro integrante.
6. Tener exitosos los checks de GitHub Actions.
7. No introducir secretos o credenciales.
8. Mantener `main` en un estado desplegable.

---

# 8. Protección de `main`

Se recomienda configurar las siguientes reglas en GitHub:

```text
main
├── Require a pull request before merging
├── Require at least 1 approval
├── Require status checks to pass
├── Require branches to be up to date
├── Restrict direct pushes
└── Automatically delete head branches
```

Como mínimo, debe quedar garantizado:

```text
NO push directo
        +
Pull Request
        +
Revisión
        +
GitHub Actions OK
        =
Merge a main
```

---

# 9. Integración continua

GitHub Actions deberá ejecutarse automáticamente sobre Pull Requests y cambios relevantes en `main`.

Flujo recomendado:

```text
Pull Request
     │
     ▼
GitHub Actions
     │
     ├── Instalación de dependencias
     ├── Lint
     ├── Tests
     ├── Cobertura
     ├── Validación de esquemas de prompts
     └── Otras validaciones
             │
             ▼
       Checks OK / FAIL
```

Un Pull Request no deberá fusionarse si las validaciones obligatorias fallan.

---

# 10. Secretos y configuración

Los secretos **no deben almacenarse en Git**.

No se deben incluir:

```text
.env
credentials.json
*.key
*.pem
tokens
API keys
passwords
```

Los valores sensibles deberán proporcionarse mediante:

```text
Variables de entorno
```

Ejemplo:

```bash
OPENAI_API_KEY=...
DATABASE_URL=...
PINECONE_API_KEY=...
```

Los archivos `.env` utilizados localmente deberán estar incluidos en `.gitignore`.

Se recomienda mantener un archivo de referencia:

```text
.env.example
```

sin valores sensibles:

```env
OPENAI_API_KEY=
DATABASE_URL=
PINECONE_API_KEY=
```

---

# 11. Versionamiento de cohortes

Cada cohorte representa una versión formal del proyecto.

La nomenclatura establecida será:

```text
v<version>-cohorte<n>
```

Ejemplos:

```text
v1.0-cohorte1
v2.0-cohorte2
v3.0-cohorte3
```

La versión se crea únicamente cuando la cohorte haya finalizado y el conjunto de cambios correspondiente esté integrado en `main`.

---

# 12. Tags

El tag debe crearse sobre el commit exacto de `main` correspondiente al cierre de la cohorte.

Ejemplo:

```bash
git checkout main
git pull origin main

git tag -a v1.0-cohorte1 -m "Cierre cohorte 1"
git push origin v1.0-cohorte1
```

Visualmente:

```text
                  v1.0-cohorte1
                         │
                         ▼
main ────●────●────●────●────●────●────
                         │
                    cierre cohorte 1
```

Para la siguiente cohorte:

```text
                  v1.0-cohorte1
                         │
                         ▼
main ────●────●────●────●────●────●────●────●────
                                                   ▲
                                                   │
                                            v2.0-cohorte2
```

---

# 13. GitHub Releases

Cada `tag` de cierre de cohorte deberá tener asociado un **GitHub Release**.

Ejemplo:

```text
Tag:
v1.0-cohorte1

Release:
Cohorte 1 - Versión 1.0
```

El Release debe contener como mínimo:

```text
# Cohorte 1

## Versión
v1.0-cohorte1

## Descripción
Resumen de los principales cambios realizados.

## Funcionalidades
- ...
- ...
- ...

## Métricas
- Accuracy: ...
- Precision: ...
- Recall: ...
- F1: ...
- IoU: ...
- Dice: ...

## Validaciones
- Tests: PASS
- Prompt schemas: PASS
- CI: PASS

## Informe
Referencia o archivo correspondiente al informe de métricas.
```

---

# 14. Flujo completo de trabajo

El flujo recomendado para cualquier nueva funcionalidad será:

```text
                    ┌───────────────┐
                    │     main      │
                    │   protegida   │
                    └───────┬───────┘
                            │
                            ▼
                  Crear feature/fix
                            │
                            ▼
                 ┌──────────────────┐
                 │ feature/* / fix/*│
                 └────────┬─────────┘
                          │
                          ▼
                       Commits
                  Conventional Commits
                          │
                          ▼
                    Pull Request
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
       Revisión integrante       GitHub Actions
              │                       │
              └───────────┬───────────┘
                          ▼
                       Aprobado
                          │
                          ▼
                     Merge a main
                          │
                          ▼
                    Rama eliminada
```

Al finalizar la cohorte:

```text
main estable
     │
     ▼
Validación final
     │
     ▼
Tag v1.0-cohorte1
     │
     ▼
GitHub Release
     │
     ├── Resumen
     ├── Cambios
     ├── Métricas
     └── Informe
```

---

# 15. Ejemplo de estructura real

Durante el desarrollo de la primera cohorte podrían existir:

```text
main

feature/prompt-supervisor
feature/validacion-esquemas
feature/evaluacion-modelo
feature/calculo-metricas

fix/error-parser
fix/calculo-f1
```

Después de integrar los cambios:

```text
main
  │
  ├── ●
  ├── ●
  ├── ●
  └── ●  ← v1.0-cohorte1
```

Las ramas de trabajo ya integradas se eliminan.

Para la siguiente cohorte:

```text
main
  │
  ├── v1.0-cohorte1
  │
  ├── feature/nueva-evaluacion
  ├── feature/mejora-prompts
  └── fix/error-metricas
                  │
                  ▼
              v2.0-cohorte2
```

---

# 16. Resumen de la estrategia

La estructura final propuesta es:

```text
main
│
├── feature/<funcionalidad>
│
└── fix/<correccion>
```

Con las siguientes reglas:

| Elemento | Regla |
|---|---|
| `main` | Protegida y siempre desplegable |
| `feature/*` | Nuevas funcionalidades |
| `fix/*` | Correcciones |
| Commits | Conventional Commits |
| Integración | Pull Request |
| Revisión | Mínimo 1 integrante |
| CI | GitHub Actions |
| Prompts | Validación automática de esquemas |
| Secretos | Variables de entorno |
| Cierre de cohorte | Tag + GitHub Release |
| Tag cohorte 1 | `v1.0-cohorte1` |
| Tag cohorte 2 | `v2.0-cohorte2` |
| Release | Informe de métricas incluido |

## Principio fundamental

> **Todo lo que está en `main` debe estar listo para ejecutarse o desplegarse. Todo lo que está en desarrollo debe vivir temporalmente en una rama `feature/*` o `fix/*` y entrar mediante Pull Request revisado.**