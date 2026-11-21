# Guion de tareas

Actualizado al prototipo de Figma **v3** ([inventario](../03-prototipo-alta-fidelidad/README.md), [especificación](../03-prototipo-alta-fidelidad/v3/pantallas.md)). Los casos de uso a los que apunta cada tarea están en [`casos-de-uso.md`](../01-flujo-y-casos-de-uso/casos-de-uso.md). Los roles se llaman Aprendiz, Instructor y Administrador.

## Introducción (leer al participante)

> Gracias por participar. Vamos a probar un prototipo de una plataforma que arma rutas de aprendizaje con inteligencia artificial. Estamos evaluando el prototipo, no a ti: si algo no se entiende, es un problema del diseño. Mientras trabajas, di en voz alta lo que piensas, lo que buscas y lo que esperas que pase. No puedo ayudarte durante las tareas, pero al final respondo todas tus preguntas. Algunas partes no funcionan del todo porque es un prototipo. Antes de empezar, te voy a pedir que leas un consentimiento sobre el uso de tus datos. ¿Tienes alguna pregunta?

Si el participante se queda en silencio: «¿Qué estás pensando?». Si pide ayuda: «¿Qué harías si yo no estuviera aquí?». Si lleva más de 3 minutos atascado en una tarea, se marca como fallida y se pasa a la siguiente.

Los botones «(Demo del prototipo)» y los avances automáticos de 2 segundos no se explican al participante; el observador los usa solo para llegar a la pantalla que toca (sección 2.5 del plan).

## Tareas del aprendiz

Punto de inicio en Figma: **Registro aprendiz (A3)**. Escenario: «Eres una persona que trabaja en análisis de crédito y quieres reforzar tus bases de machine learning».

| # | Tarea (leer tal cual) | Éxito si… | Pantallas | Qué observar |
| --- | --- | --- | --- | --- |
| T1 | Crea tu cuenta. Lee con calma lo que te piden aceptar y decide qué aceptas. | Marca la casilla de datos y decide sobre la del piloto sabiendo la diferencia | A3, A3b, A3c | ¿Lee el consentimiento? ¿Entiende que el piloto es voluntario y que puede retirarse? ¿Abre «Tus datos y tus derechos»? |
| T2 | Encuentra una ruta sobre machine learning. | Abre la ruta Fundamentos de ML | E1 | ¿Entiende los dos grupos del catálogo y las etiquetas «Recomendada para ti» y «Nueva»? |
| T3 | Inscríbete y cuéntale a la plataforma qué sabes del tema y cuál es tu experiencia. | Completa el perfil y la hoja de vida, o elige «Completar más tarde» sabiendo qué implica | E2, E2b | ¿Qué escribe? ¿Entiende para qué sirve la hoja de vida y el aviso de los pesos? |
| T4 | Responde el diagnóstico. Si no sabes una respuesta, haz lo que harías normalmente. | Llega al resultado | E3, U1a, E4 | ¿Usa «No lo sé»? ¿Le preocupa la nota? ¿Entiende la pantalla de carga de «menos de 20 segundos»? |
| T5 | Mira tu resultado. ¿Qué significa? Cambia tu objetivo para que sea algo que puedas medir. | Explica el nivel por tema; edita el objetivo con verbo, contenido y criterio | E4, E4b | ¿Entiende «Por reforzar», «Por aprender» y «Obligatorio»? ¿Entiende por qué «Guardar» se desactiva? ¿Confía en el objetivo propuesto por la IA? |
| T6 | ¿Por qué algunos temas aparecen como omitidos? Continúa con el tema que te toca. | Explica la omisión y abre el tema 3 | E5, E6 | ¿Entiende el motivo de cada paso y el ahorro de tiempo? |
| T7 | Estudia el tema, dile a la plataforma si el video te sirvió y presenta el quiz. | Califica el video y envía el quiz incluida la respuesta corta | E6, E6b, E6c, U1c | ¿Usa el video, el texto o ambos? ¿Nota las citas y el aviso de IA? ¿Entiende la rúbrica de 3 criterios? |
| T8 | **Estado de error de la IA.** Tu respuesta corta no se pudo calificar. ¿Qué haces? | Encuentra «Reintentar» o «Volver a mi ruta» y confirma que su respuesta no se perdió | U1c (estado de error) | ¿Entiende que su avance está guardado? ¿Se asusta o intenta empezar de nuevo? ¿Qué espera que pase al reintentar? |
| T9 | Tu respuesta se calificó, pero crees que merece más puntos. ¿Qué puedes hacer? | Encuentra «Pedir revisión del instructor» | E7 | ¿Entiende el detalle por criterio? ¿Confía en la nota? |
| T10 | Imagina que no aprobaste el quiz en tres intentos. ¿Qué puedes hacer ahora? | Explica que el tema queda como crítico, que el instructor recibió una alerta y que puede seguir con temas que no dependen de este | E7b, E7c | ¿Entiende «En espera» y «Puedes seguir»? ¿Se siente bloqueado? |
| T11 | Imagina que ya terminaste todos los temas: presenta la evaluación final y consulta tu badge. | Llega al badge y encuentra cómo descargarlo | E8, U1d, E10 | ¿Entiende qué pasa si saca menos de 80 %? |
| T12 | Cambia de idea sobre el piloto: sal de él sin perder tu ruta. | Llega a «Gestionar mis autorizaciones» desde Mi progreso y distingue «salir del piloto» de «revocar y borrar» | E11, E11b | ¿Encuentra dónde? ¿Entiende la diferencia? |

Nota sobre T8: Figma v3 solo dibuja el camino feliz de las pantallas de carga U1x. Para esta tarea hace falta un frame de error de U1c, o que el observador lo simule (Mago de Oz) con el texto «No pudimos calificar tu respuesta corta. Reintentar · Volver a mi ruta». **Pendiente: dibujar el frame** (ver [`flujos.md`](../01-flujo-y-casos-de-uso/flujos.md#casos-de-error-de-las-pantallas-de-carga-u1x)).

Preguntas de cierre: ¿qué fue lo más confuso? ¿Confiarías en el contenido generado por IA? ¿Te sentiste con el control de tus datos? ¿Usarías la plataforma para un curso real?

## Tareas del instructor

Punto de inicio en Figma: **Login instructor (A4)**. Escenario: «Vas a dictar Fundamentos de ML con esta plataforma».

| # | Tarea (leer tal cual) | Éxito si… | Pantallas | Qué observar |
| --- | --- | --- | --- | --- |
| T1 | Entra y crea un curso nuevo con tu syllabus. | Encuentra «Nuevo curso», indica grupo y sube el archivo | A4, D1, D1b | ¿Entiende el límite de 10 MB y el campo de grupo o periodo? |
| T2 | **Estado de error.** El archivo que subiste no se pudo leer. ¿Cómo sigues? | Elige «Pegar el texto» o «Subir otro archivo» y entiende que sus datos están guardados | D1c, D1d | ¿Entiende por qué falló (PDF escaneado, 0 caracteres)? ¿Le da confianza el mensaje «No se perdió nada»? |
| T3 | Revisa los temas que extrajo la IA y corrige lo que no te convenza. | Edita un tema, sus resultados de aprendizaje y un prerrequisito, y aprueba | D2, D2b, D2d | ¿Entiende la columna «Revisión», Bloom y el grafo «Sin ciclos · validado»? ¿Qué hace ante un error de ciclo? |
| T4 | La extracción salió muy mal. Quieres empezar de nuevo. | Usa «Volver a extraer» sabiendo que pierde sus correcciones | D2c | ¿Lee el aviso antes de confirmar? |
| T5 | Revisa los recursos y las preguntas de un tema, y corrige una explicación. | Aprueba o edita un recurso y ve la nueva versión | D5, D5d | ¿Qué información le falta para confiar en una pregunta? ¿Entiende la fidelidad? |
| T6 | Elige el video para el tema y deja uno de respaldo. | Marca Pertinente o No pertinente, deja un video «En uso» y agrega un respaldo | D5e | ¿Entiende por qué el video «relevancia 94 %» solo lo ve él? |
| T7 | Configura la ruta para que un tema se apruebe con 75 %. | Encuentra los umbrales y lee el aviso del piloto | D3b | ¿Entiende que cambiar umbrales durante el piloto rompe la comparación? |
| T8 | Averigua cómo va Julián Pérez y dale dos intentos más. | Llega a su detalle, ve los intentos agotados y habilita intentos extra | D3, D4, D4b, D4c | ¿Entiende «En espera»? ¿Los datos coinciden con lo que vio en D3? |
| T9 | Tu colega te pidió ayuda: califica a mano algunas respuestas cortas. | Califica una respuesta con la rúbrica y ve la nota del LLM al guardar | D5c | ¿Entiende por qué no ve antes la nota del LLM? ¿Y la diferencia con las solicitudes «Pedir revisión»? |

Preguntas de cierre: ¿qué revisarías antes de publicar un curso? ¿Cuánto tiempo estarías dispuesto a dedicar a validar lo que genera la IA?

## Tareas del administrador

Punto de inicio en Figma: **Usuarios y roles (AD1)**. Escenario: «Eres responsable de la plataforma durante un piloto con 24 aprendices».

| # | Tarea (leer tal cual) | Éxito si… | Pantallas | Qué observar |
| --- | --- | --- | --- | --- |
| T1 | Una persona nueva va a dictar un curso. Dale el acceso que necesita. | Crea el usuario y le asigna el rol Instructor | AD1 | ¿Entiende la diferencia entre roles? ¿Qué espera si la misma persona también aprende? |
| T2 | El curso «Estadística para ciencia de datos» no tiene instructor. Asígnaselo. | Asigna instructor en la fila del curso | AD5 | ¿Encuentra la acción en «Cursos y rutas»? |
| T3 | Inscribe a una persona al curso y asegúrate de que entra al piloto. | Inscribe y revisa el consentimiento y el grupo del piloto | AD5 | ¿Entiende «Consentimiento» y «Grupo del piloto»? |
| T4 | Configura e inicia el piloto de Fundamentos de ML. | Define fechas, sortea los grupos y entiende los avisos antes de iniciar | AD4, AD4b | ¿Entiende la semilla del sorteo, los ítems equivalentes y qué pasa con 2 consentimientos pendientes? |
| T5 | Averigua cuánto está costando la IA y qué prompt generó una pregunta dudosa. | Llega al log y al catálogo de prompts | AD2, C4 | ¿Relaciona la versión del prompt con el log? |

Preguntas de cierre: ¿qué información te falta para decidir si el piloto va bien?

## Después de las tareas

1. Aplicar el [cuestionario SUS](cuestionario-sus.md).
2. Responder las preguntas del participante.
3. El observador pasa sus notas a [`resultados.md`](resultados.md) el mismo día.
