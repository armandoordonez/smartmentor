# Guía: probar SmartMentor con un navegador controlado por el agente

Para un integrante del equipo que usa su propio agente. El agente abre la app en un navegador real, inicia sesión con los usuarios de prueba, recorre el flujo, captura cada pantalla y la compara con Figma. Sirve para validar requerimientos de punta a punta con datos reales.

## 1. Requisitos

- Repositorio clonado, rama `dev` al día y tu propio `.env` (te lo pasa el dueño por un canal privado; nunca se sube a git).
- Stack local arriba con `scripts/local-up.sh`: la app en `http://localhost:8501`, la API en `http://localhost:8020` y Keycloak en `http://localhost:8180`.
- Si cambió código reciente, reconstruye las imágenes antes de probar. Probar contenedores viejos da falsos resultados.

## 2. Qué decirle a tu agente

Copia y pega este texto:

> Vas a probar SmartMentor con un navegador automático. Reglas:
>
> 1. **Navegador:** Playwright con Chromium sin ventana (`uv run --no-project --with playwright python script.py`; si falta el navegador, `executable_path="/usr/bin/chromium"`). Viewport 1280×800.
> 2. **Streamlit es una SPA por websocket:** después de cada clic espera a que desaparezca `[data-testid="stStatusWidget"]`. Registra los mensajes de consola y las respuestas 4xx y 5xx de cada página.
> 3. **Usuarios de prueba:** los de la sección «Usuarios de prueba» de `.env.example` (`SEED_*_EMAIL`). La clave común está en `SEED_USERS_PASSWORD` de tu `.env`; pásala **solo por variable de entorno**, nunca en archivos, commits ni informes.
> 4. **Evidencia:** guarda scripts, capturas y registros en una carpeta fuera del repo (por ejemplo `/tmp/<tu-agente>/e2e/`). Una captura por pantalla.
> 5. **Comparar con Figma:** las capturas de Figma v3 están en `design/03-prototipo-alta-fidelidad/smartmentor_figma/pantallas/` (no versionadas; pídelas al dueño). Los nombres y códigos de pantalla (E1, D5b, AD4…) están en `design/03-prototipo-alta-fidelidad/v3/pantallas.md`. Reporta solo diferencias reales y no lo ya aceptado en `app/CLAUDE.md` ni en `proyecto/seguimiento/FIGMA.md`.
> 6. **Datos reales y compartidos:** la base es Neon y la usa todo el equipo. Solo flujo normal de usuario: no borres datos, no toques la base ni Keycloak directamente, no reinicies contenedores de otros, no uses el simulador de aprendices y no crees cursos sin permiso (generan bancos de preguntas y cuestan).
> 7. **Costo de IA:** fija un tope en dólares (por ejemplo, US$ 1) antes de empezar. Mide el gasto antes y después con `GET /api/v1/llm-call-logs/summary` (token como en `api/scripts/token.sh`; solo GET) y detente al 90 % del tope.
> 8. **Errores:** para cada fallo guarda la pantalla, los pasos para reproducirlo, lo esperado frente a lo obtenido, la captura y las líneas del log (`docker logs smartmentor-app`, `smartmentor-api`, `smartmentor-ai-worker`) de esa hora.
> 9. **Límite de uso:** si te detienes por límite de uso o falta de créditos, dilo de forma explícita, con la hora de reinicio y lo que quedó pendiente.
> 10. **Informe final:** tabla por pantalla (código, resultado, nota, captura), bugs nuevos con severidad, qué IDs del seguimiento se pueden cerrar y por qué, y el costo de IA.

## 3. Flujo de trabajo del equipo

- **Código:** cada cambio va en una rama `feature/*` o `fix/*` desde `dev` actualizada, con un PR hacia `dev`. El dueño fusiona. Nunca se sube a `stage` ni `main`, ni se hace `push --force`.
- **Commits:** en español, con Conventional Commits y el ID al final del título (`fix(app): … [B-040]`). Pie de coautoría: los cuatro integrantes, sin línea de Claude.
- **Antes de empezar un requerimiento:** haz pull de `dev` y comprueba en [`TRAZABILIDAD.md`](trazabilidad/TRAZABILIDAD.md) que nadie más lo haya tomado. Ponlo a tu nombre ahí, en curso.
- **`TRAZABILIDAD.md`:** es el único archivo que se actualiza **directo en `dev`**, sin rama ni PR, apenas cambie algo: asignación, estado, PR fusionado o decisión. Revisa también la tabla «General · G-001» (el % y «validado agente» de las pantallas ajustadas).
- **Idioma:** documentos en español; identificadores de código y de base de datos en inglés.
- **Agentes en paralelo:** cada uno en su propio worktree y su propia rama, con puertos de prueba distintos (del 8503 al 8513 ya se usaron). Si dos ramas tocan los mismos archivos, el integrador prueba su fusión antes de abrir los PR.

## 4. Si prefieres ver el navegador en vivo

- **Claude in Chrome (extensión):** controla tu Chrome real y ves cada clic. Hay que instalar la extensión y habilitarla en la sesión.
- **Navegador integrado de la app de escritorio de Claude:** igual, pero solo si usas esa app. Desde VS Code en Linux no está disponible.

Es más lento que Playwright, pero sirve para revisarlo juntos.
