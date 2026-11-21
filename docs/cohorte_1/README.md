# Documentación de la cohorte 1

Soporte técnico y evidencia del [brief de la cohorte 1](../../proyecto/cohorte_1/brief.md). Las decisiones de arquitectura ([`../adr/`](../adr/README.md)) y los contratos de la API y de la IA ([`../contracts/`](../contracts/api-v2.md)) viven aparte, en `docs/`, porque el código y la CI los citan.

| Ruta | Para qué sirve |
| --- | --- |
| [`anexos/`](anexos/) | Soporte del brief: arquitectura y despliegue (A), modelo de datos (B), agentes, prompts y modelos (C) y experimentos (D) |
| [`evaluation/`](evaluation/metrics.md) | Definición de las métricas, protocolos de E2 y E6, plan de los experimentos y [resultados](evaluation/results/resumen-r005-2026-11-16.md) |
| [`trazabilidad/`](trazabilidad/TRAZABILIDAD.md) | Lo realizado, lo abierto y lo migrado a la siguiente fase, con hoja de ruta, bugs y huecos de Figma |
| [`bitacora/`](bitacora/README.md) | Bitácoras por fase (F00 a F09), escritas por los agentes de desarrollo |
| [`runbook-despliegue.md`](runbook-despliegue.md) | Pasos operativos: arranque, base remota, respaldo y restauración, diagnóstico |
| [`flujo-por-usuario.md`](flujo-por-usuario.md) | Flujo del prototipo por rol y cruce con los objetivos del brief |
| [`decisiones.md`](decisiones.md) | Decisiones técnicas que se abrieron y cómo se cerraron |
| [`definicion-de-terminado.md`](definicion-de-terminado.md) | Lista de verificación para dar un cambio por terminado |
| [`guia-pruebas-navegador.md`](guia-pruebas-navegador.md) | Cómo probar la aplicación con un navegador controlado por un agente |
| [`release.md`](release.md) | Notas de la versión `v1.0-cohorte1` y pasos para publicarla |

Estado técnico y deuda para quien continúe: [`HANDOFF.md`](../../HANDOFF.md).
