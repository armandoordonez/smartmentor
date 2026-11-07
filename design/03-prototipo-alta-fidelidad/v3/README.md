# Especificación del prototipo de Figma v3

Datos del prototipo «SmartMentor · Prototipo Fase 0 v3 (4)» extraídos de su exportación, para construir la interfaz **sin volver a conectarse a Figma**. Complementa a [`../README.md`](../README.md) y es la base de la Fase 7 del [plan de implementación](../../../PLAN_IMPLEMENTACION_V3.md).

| Dato | Valor |
| --- | --- |
| Archivo de Figma | `atp2fZdSolEoaww3n9jRLg`, página `0:1` |
| Exportación usada | `../archivo_completo.json` (22 MB, modificada en Figma el 2026-10-20) |
| Extracción | 2026-11-07 |
| Pantallas | 96 (más la biblioteca de componentes) |
| Nodos | 6.731 |
| Enlaces de navegación | 879 |

## Veredicto: ¿hace falta conectarse otra vez a Figma?

**No.** La exportación en JSON trae la estructura, los textos, el diseño automático y los enlaces entre pantallas; las 97 capturas PNG dan la referencia visual; y `variables.json` resuelve los 24 nombres de las variables de color, que el JSON solo trae como identificadores. Solo haría falta reconectar para:

1. Confirmar `error/acento` (variable `118:923`), que ninguna pantalla usa.
2. Comprobar que el archivo en vivo no cambió después del 2026-10-20.

La conexión sí funcionó (plan Starter, con cupo limitado de llamadas). `get_variable_defs` exige un frame concreto, y la exportación por la API REST de variables falla con 403 porque falta el permiso `file_variables:read`.

## Contenido

| Archivo | Para qué sirve |
| --- | --- |
| [`pantallas.md`](pantallas.md) | Inventario por rol: nodo, nombre, tamaño, captura, cantidad de textos, componentes y pantallas a las que navega |
| [`estructura-pantallas.json`](estructura-pantallas.json) | Árbol simplificado de cada pantalla: tipo, nombre, tamaño, diseño automático (`lm`, `g`, `p`), relleno (`f`), borde (`s`), radio (`r`), componente (`cmp`), texto (`c`), tipografía (`ty`) y enlaces (`go`). Los colores usan el nombre del token (por ejemplo `$aprendiz/acento`), no el hexadecimal |
| [`tokens.json`](tokens.json) | Colores, tipografías (con su número de usos), radios, espaciados y sombras tal como aparecen en el diseño |
| [`variables.json`](variables.json) | Las 24 variables de color: identificador, nombre, hexadecimal y estado, con su procedencia |
| [`extraer_especificacion.py`](extraer_especificacion.py) | Script que genera todo lo anterior (solo biblioteca estándar de Python) |

## Variables de color

| Grupo | Variables (hex) |
| --- | --- |
| Texto | `texto/principal` #15181E · `texto/secundario` #4A5160 · `texto/terciario` #5F6776 · `texto/sobre-acento` #FFFFFF |
| Fondo | `fondo/pagina` #F5F6F8 · `fondo/superficie` #FFFFFF · `fondo/sutil` #FAFBFC · `fondo/neutro` #EEF0F3 |
| Borde | `borde/default` #E3E6EB · `borde/fuerte` #C9CDD5 |
| Aprendiz | `acento` #1D5FD1 · `suave` #E8F0FC · `texto` #174EA6 |
| Instructor | `acento` #11774A · `suave` #E5F4EC · `texto` #0D6640 |
| Admin | `acento` #5B3CC4 · `suave` #EEEAFB · `texto` #4B2FB0 |
| Aviso | `acento` #D98A00 · `suave` #FFF4DE · `texto` #8A5300 |
| Error | `suave` #FDECEA · `texto` #9B1C14 · `acento` (sin uso e **inferido**) |

Dos aclaraciones sobre la procedencia: `118:904` y `118:906` valen ambos `#FFFFFF` y se asignaron por orden de creación, y `118:923` se infirió por la secuencia. Los nombres del rol siguen diciendo «aprendiz», «instructor» y «admin» porque así están en Figma; el código usa `learner`, `instructor` y `admin` (sección 13 del plan).

## Cómo regenerar

Si Figma cambia, se exporta de nuevo el archivo y se corre, desde la raíz del repositorio:

```bash
python3 -I design/03-prototipo-alta-fidelidad/v3/extraer_especificacion.py \
  --figma design/03-prototipo-alta-fidelidad/archivo_completo.json \
  --variables design/03-prototipo-alta-fidelidad/v3/variables.json \
  --pantallas design/03-prototipo-alta-fidelidad/smartmentor_figma/pantallas \
  --salida design/03-prototipo-alta-fidelidad/v3
```

Resultado esperado: «96 pantallas, 6731 nodos, 879 enlaces de navegación» y «56 estilos tipográficos, 14 radios, 20 valores de espaciado». `pantallas.md`, `estructura-pantallas.json` y `tokens.json` no se editan a mano.

## Qué no se versiona (DEF-17)

Por peso y porque se regeneran, no se versionan: `../archivo_completo.json` (22 MB), `../smartmentor_prototipo_v3.json` (versión intermedia del 2026-10-15) y `../smartmentor_figma/` (97 capturas PNG, 16 MB). Si el dueño decide versionar las capturas, DEF-17 se cierra con esa decisión.

## Límites conocidos

- Los comentarios, estilos, componentes e imágenes de la exportación vienen vacíos.
- Los componentes que sí trae el JSON son: `Badge` (Verde, Azul, Ámbar, Gris, Violeta), `Botón` (Primario azul, verde y violeta, y Secundario), `Menú superior` (Rol=Aprendiz, Instructor, Admin), `Campo` y `Estado de carga` (`94:407`).
- La página de Figma sigue llamándose «SmartMentor v2».
- Los botones «(Demo del prototipo)» y los avances automáticos de 2 segundos son del prototipo y no se construyen (sección 2.5 del plan).
