"""Quién puede qué: grupos de roles para proteger los recursos (decisión D-03).

Los roles salen de `user_roles` en la base de datos, no del token.
"""

from app.common.constants import RoleCode

ADMIN = (RoleCode.ADMIN,)
STAFF = (RoleCode.ADMIN, RoleCode.TEACHER)
ANY_ROLE = (RoleCode.ADMIN, RoleCode.TEACHER, RoleCode.STUDENT)

# Resumen de la matriz (lectura / escritura):
#   roles                        cualquier rol / admin
#   users                        admin, teacher / admin
#   user-roles                   admin / admin
#   courses, topics, topic-prerequisites, learning-paths, resources
#                                cualquier rol / admin, teacher
#   enrollments, path-steps, diagnostics, assessment-attempts, badges
#                                admin, teacher / admin, teacher
#   llm-call-logs                admin / admin
#   /me/**                       cualquier rol, solo sobre lo propio (dominio student)
# Los estudiantes consultan el catálogo y gestionan lo suyo con /me/enrollments y lo que cuelga de
# ellas (inscribirse, ver su ruta, entregar respuestas, ver su badge); cada operación verifica que
# la inscripción sea del usuario autenticado. El CRUD genérico de enrollments, path-steps,
# diagnostics, assessment-attempts y badges sigue reservado al personal (admin y teacher).
