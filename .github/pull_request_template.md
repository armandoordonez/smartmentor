## Qué cambia

<!-- Resumen en pocas líneas. Una rama por tema; pull request hacia `dev`. -->

## Fase y decisiones relacionadas

<!-- Por ejemplo: Fase 3, DEF-12, ADR 0010. -->

## Cómo se probó

<!-- Comandos ejecutados y resultado real (lint, tipos, pruebas, `liquibase validate`). -->

## Lista de verificación

Detalle en [`docs/standards/definition-of-done.md`](../docs/standards/definition-of-done.md).

- [ ] Ruff (`check` y `format --check`), mypy y pytest en verde en los servicios tocados
- [ ] `liquibase validate` en verde si hay changesets (y ninguno aplicado fue modificado)
- [ ] Pruebas nuevas o actualizadas para el comportamiento que cambia
- [ ] Sin secretos ni valores reales en archivos versionados; variables nuevas documentadas en `.env.example`
- [ ] Documentos y comentarios en español; identificadores en inglés; roles `learner`, `instructor`, `admin`
- [ ] Decisión de arquitectura nueva registrada como ADR
- [ ] Commits en español con Conventional Commits y el pie de coautoría
- [ ] El pull request es pequeño y de un solo tema
