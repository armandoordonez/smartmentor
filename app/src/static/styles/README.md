# Estilos de la interfaz

Todo el CSS de `app/` vive en este directorio y lo carga un único módulo, [`../../core/styles.py`](../../core/styles.py). Está registrado en el [ADR 0017](../../../../docs/adr/0017-frontend-rebuilt-from-figma-v3.md) y en la sección 5.5.1 del plan.

## Orden de carga

1. `tokens.css`: **único** archivo con hexadecimales. Las 24 variables de Figma v3 con nombre en inglés (`--text-primary`, `--learner-accent`…), más radios, espaciados, tipografía y `--border-field` (propuesta, ver abajo).
2. `base.css`: tipografía, enlaces y foco visible.
3. `layout.css`: barra superior, tarjetas y paneles.
4. `roles.css`: acento por rol (`--accent`, `--accent-soft`, `--accent-text`) y botón principal del color del rol.
5. `components/*.css`: un archivo por componente, en orden alfabético.

`main.py` llama a `inject_styles()` una vez por ejecución (antes de la barra superior, para que también queden estilizadas las pantallas de acceso). Con `APP_ENV=local` se relee de disco en cada ejecución; en los demás entornos se guarda en caché.

## Cómo cambiar un color

1. Edita el valor en `tokens.css` (es el único lugar). Si Streamlit lo usa (`primaryColor`, fondos, texto, bordes, paleta de badges), cámbialo también en `app/.streamlit/config.toml`.
2. Corre `app/scripts/dev.sh test tests/unit/test_styles.py`: verifica que `config.toml` coincide con `tokens.css`, que no hay hexadecimales fuera de `tokens.css` y que los pares de colores cumplen el contraste.
3. Si el cambio viene de Figma, actualiza también la tabla de la sección 2 de `app/CLAUDE.md`.

## Reglas

| Regla | Detalle |
| --- | --- |
| Colores solo como variables | Fuera de `tokens.css` no hay hexadecimales, `rgb()`, `hsl()` ni colores con nombre. Se usa `var(--learner-accent)` y similares |
| Selectores estables | Solo clases propias (`.sm-*`) y `.st-key-<nombre>` (el contenedor de Streamlit que lleva `key`). Nunca clases internas de Streamlit. La excepción única es el `data-testid` del botón principal en `roles.css` (P1) |
| Texto del usuario | El CSS es propio. El texto del usuario o de la IA nunca se inyecta con `unsafe_allow_html` |
| `--warning-accent` | Solo decorativo (bordes, barras): su contraste con blanco es 2,77:1. Nunca como `color` de texto; una prueba lo verifica |
| Un archivo por componente | Un componente con estilo propio tiene su `components/<nombre>.css`, y su `key` de contenedor es el selector (`st-key-<prefijo>-…`) |
| Perfiles de contexto (P2) | `APP_CONTEXT_PROFILE` podrá cargar `themes/<perfil>.css`, que solo redefine variables |

## Contraste (WCAG 2.2)

La prueba `tests/unit/test_styles.py` calcula el contraste de los pares de `tokens.css`: 4,5:1 para texto y 3:1 para bordes de campos (1.4.11).

| Par | Contraste |
| --- | --- |
| `--border-default` sobre blanco | 1,25:1 (no llega; solo decorativo en tarjetas) |
| `--border-strong` sobre blanco | 1,59:1 (no llega) |
| `--border-field` sobre blanco y sobre `--bg-page` | 3,5:1 y 3,2:1 (**propuesta de este directorio**, no está en Figma) |

Ni `borde/default` ni `borde/fuerte` de Figma alcanzan 3:1, así que los bordes de campos y de controles usan `--border-field`, que Streamlit toma como `borderColor`. Hay que validarlo con el dueño y con diseño: cambia levemente el aspecto de los campos frente a Figma.
