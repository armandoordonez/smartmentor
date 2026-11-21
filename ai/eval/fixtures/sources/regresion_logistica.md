La regresión logística es un modelo de clasificación binaria. Calcula una combinación lineal de las variables y la transforma con la función sigmoide, que devuelve un valor entre cero y uno interpretable como la probabilidad de la clase positiva.

Para decidir la clase se compara esa probabilidad con un umbral, por defecto cero coma cinco. El umbral puede ajustarse según el costo de cada tipo de error: si omitir un caso positivo es muy costoso, conviene bajarlo, a cambio de más falsas alarmas.

Los parámetros se estiman minimizando la log-loss, que castiga con fuerza las predicciones muy seguras que resultan equivocadas. Cada coeficiente es el cambio en el logaritmo de las odds por unidad de la variable, y la exponencial del coeficiente es la razón de odds.

La regularización L2 penaliza los coeficientes grandes para reducir el sobreajuste. En scikit-learn su fuerza se controla con el parámetro C: un valor menor de C implica más regularización y coeficientes más pequeños.
