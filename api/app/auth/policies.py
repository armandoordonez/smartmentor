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
# Los estudiantes solo consultan el catálogo y su propio perfil (/me). Lo que hace un estudiante
# sobre sus datos (inscribirse, responder un quiz) pasará por endpoints propios con verificación de
# pertenencia, en la fase de la interfaz; por eso el CRUD genérico no se abre a su rol.
