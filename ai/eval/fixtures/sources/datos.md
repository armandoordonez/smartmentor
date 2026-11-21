En el aprendizaje supervisado cada ejemplo trae una etiqueta que el modelo debe aprender a predecir a partir de las variables de entrada. En el aprendizaje no supervisado no hay etiqueta y el objetivo es descubrir estructura, por ejemplo grupos de casos parecidos.

Antes de entrenar se separan los datos en un conjunto de entrenamiento y otro de prueba. El conjunto de prueba se guarda sin tocar hasta el final para estimar cómo se comportará el modelo con datos nuevos. Una partición típica reserva entre el veinte y el treinta por ciento para la prueba.

La fuga de datos ocurre cuando el modelo recibe información que no tendría en producción, por ejemplo cuando se calcula la media de una variable usando también las filas de prueba. La fuga hace que las métricas parezcan mejores de lo que son. Para evitarla, todo ajuste de preparación debe aprenderse solo con el conjunto de entrenamiento y luego aplicarse a la prueba.

El escalado de variables pone las columnas en rangos comparables, por ejemplo restando la media y dividiendo por la desviación estándar. Es importante en modelos sensibles a la magnitud, como la regresión con regularización. Las variables categóricas se codifican como números; la codificación con una columna por categoría evita sugerir un orden que no existe.
