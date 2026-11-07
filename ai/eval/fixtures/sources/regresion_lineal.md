La regresión lineal modela una variable numérica como una combinación lineal de las variables de entrada más un término independiente. Cada coeficiente indica cuánto cambia la predicción cuando su variable aumenta una unidad y las demás se mantienen constantes.

Los coeficientes se estiman con mínimos cuadrados: se eligen los valores que minimizan la suma de los errores al cuadrado entre lo observado y lo predicho. Elevar al cuadrado castiga con más fuerza los errores grandes que los pequeños.

Para evaluar el modelo se usa el error cuadrático medio, que es el promedio de los errores al cuadrado sobre datos de prueba. Un error menor sobre los mismos datos indica mejores predicciones. Su raíz cuadrada vuelve a las unidades de la variable original y se interpreta más fácilmente.

El coeficiente de determinación R² mide la proporción de la variación de la variable objetivo que explica el modelo. Un R² cercano a uno indica un buen ajuste, pero un R² alto en entrenamiento no garantiza buen desempeño en prueba, y puede crecer solo por agregar variables.
