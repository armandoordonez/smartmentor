"""Quién puede qué: grupos de roles para proteger las rutas (matriz del plan, sección 5.3.2).

Los roles salen de `user_roles` en la base de datos, no del token. Un usuario puede tener varios
roles y la autorización usa la unión: el «rol activo» de la app es solo de presentación (CU-35).
"""

from app.common.constants import RoleCode

ADMIN = (RoleCode.ADMIN,)
INSTRUCTOR = (RoleCode.INSTRUCTOR,)
LEARNER = (RoleCode.LEARNER,)
STAFF = (RoleCode.ADMIN, RoleCode.INSTRUCTOR)
ANY_ROLE = (RoleCode.ADMIN, RoleCode.INSTRUCTOR, RoleCode.LEARNER)

# Resumen de la matriz de esta parte (lectura / escritura):
#   /me, /me/profile, /me/consents, /me/data-subject-requests   cualquier rol, solo lo propio
#   roles                          cualquier rol / admin
#   users, user-roles, users/{id}/roles   admin / admin
#   courses, topics, syllabus      instructor (los suyos) y admin (todos)
#   courses/{id}/owner             admin
#   jobs/{id}                      dueño del trabajo (instructor, aprendiz) y admin
# Pedir un objeto ajeno responde 404, nunca 403 (sección 18.2 del plan).
