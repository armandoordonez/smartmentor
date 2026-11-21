Qué es una prueba "Mago de Oz"

El nombre viene de la película. El "mago" impresiona a todos, pero detrás de la cortina es un hombre moviendo palancas. En diseño de producto, una prueba Mago de Oz consiste en simular que el sistema ya funciona cuando en realidad una persona produce las respuestas a mano.

En SmartMentor, la plataforma todavía no existe. Lo que pide el brief es que el equipo se siente con un notebook y le pida al LLM, a mano, tres cosas:

El syllabus estructurado: temas, resultados de aprendizaje, nivel de Bloom y prerrequisitos.
El diagnóstico: preguntas por tema y el nivel estimado del estudiante.
Un tema completo: explicación, recurso de video y quiz.

Luego esas salidas reales se copian en las pantallas del prototipo. El objetivo es doble:

Validar que el LLM sí produce algo útil antes de construir el pipeline automático. Si el syllabus sale mal estructurado o las preguntas son malas, lo descubres en la semana 1 y no en la 5.
Fijar los contratos de datos. Al ver qué devuelve el LLM y qué necesita mostrar cada pantalla, defines el esquema JSON de cada salida. Ese esquema es el acuerdo entre la IA y la interfaz: el backend le exige al LLM devolver exactamente ese formato, y la pantalla sabe qué campos va a recibir.
Por qué quedó en ⚠️ (cumple parcialmente)

Lo que sí está bien (contenido realista y trazable). Las pantallas no tienen relleno tipo "Lorem ipsum". Tienen contenido creíble y con los campos correctos:

D2 muestra el syllabus con Bloom y prerrequisitos.
E3 y E4 muestran el diagnóstico con niveles por tema.
E6 muestra la explicación con citas [1][2].
Las pantallas incluso indican la versión del prompt que generó cada contenido (explicacion_tema v1.3). A eso me refiero con "trazable": se puede rastrear qué prompt produjo cada salida.

Lo que falta (1): los esquemas JSON. Es el entregable principal de esta actividad y del criterio de salida, y no aparece en ninguna parte. Por ejemplo, para el quiz de E6 debería existir en el repositorio algo como schemas/quiz.v1.json:

json
{
  "tema_id": "regresion_logistica",
  "prompt_version": "quiz_tema v1.2",
  "preguntas": [
    {
      "id": "q1",
      "enunciado": "¿Qué valores devuelve la función sigmoide?",
      "tipo": "opcion_multiple",
      "bloom": "Recordar",
      "opciones": ["Valores entre 0 y 1", "Valores entre −1 y 1", "Cualquier número real"],
      "respuesta_correcta": 0,
      "fuentes": [1, 2]
    }
  ],
  "umbral_aprobacion": 0.7
}

Faltan los equivalentes para el syllabus, el diagnóstico, el objetivo, la explicación del tema, la calificación, la evaluación final y el badge.

Además, desde Figma no puedo comprobar que el texto salió realmente del LLM y no fue redactado a mano. Para eso conviene guardar en el repositorio el notebook con las salidas originales.

Lo que falta (2): coherencia de los datos entre pantallas. Si los datos hubieran salido de un mismo JSON, serían consistentes. No lo son:

El catálogo dice que la ruta tiene 6 temas, pero la vista de ruta y el syllabus muestran 5 (más la evaluación final).
El puntaje de Laura en regresión logística es 60 % en E5, 80 % en D4 y 72 % en D3.
E12 muestra que Laura ya obtuvo el badge, mientras E5 dice que va en el tema 3 de 5.

Esto es una señal de que cada pantalla se llenó por separado y no desde una fuente única de datos. Es justo lo que los esquemas JSON resuelven. Además, en la prueba de usabilidad confundiría a los participantes.

En resumen: el "mago" sí trabajó y el contenido luce bien, pero falta dejar escrito el contrato (los esquemas) y usar un solo conjunto de datos de ejemplo para todas las pantallas.
