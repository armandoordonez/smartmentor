# E6 · Videos por tema: procedimiento

Pregunta del experimento (segundo corte, tabla 9): ¿el ranking por tema pone videos pertinentes entre los tres primeros, y lo hace mejor que alternativas simples? Mide la condición previa de H3.

Se comparan cuatro ordenaciones sobre los **mismos** candidatos juzgados:

| Ordenación | Qué es |
| --- | --- |
| (a) Al azar | Valor esperado de un orden aleatorio (media de 2000 permutaciones con semilla) |
| (b) Orden de YouTube | La posición del video en los resultados de la búsqueda (`video_candidates.search_position`). Si hubo segunda consulta (B-064), sus videos van después de los de la primera |
| (c) Solo similitud | La similitud de embeddings entre el video y el tema |
| (d) Puntaje vigente | El `rank` del recomendador: similitud más 0,05 por idioma y 0,05 por duración |

Métricas: κ de Cohen entre los dos jueces (meta ≥ 0,6), Precision@3 (meta ≥ 0,7 para el puntaje vigente) y nDCG@3 con relevancia graduada (la proporción de jueces que marcó el video como pertinente). Para P@3, un video es pertinente si al menos la mitad de los jueces lo marcó así. Solo entran los temas con al menos 3 candidatos juzgados.

## Antes de empezar

1. **B-064 en `dev`.** Con la búsqueda de 15 resultados y el tope de 30 minutos ningún tema tenía más de 2 candidatos.
2. **Buscar los videos de nuevo** en cada tema de las rutas de prueba (D5e, «Buscar videos de nuevo»). Así cada candidato tiene su `search_position`: los anteriores a E6 no la tienen y sin ella no hay ordenación (b). Son unas 20 búsquedas, o hasta 40 si muchos temas necesitan la segunda consulta, dentro de las ~100 diarias de YouTube.
3. Elegir a los **dos jueces**. Se identifican solo por su ranura (1 y 2), nunca por nombre.

## 1. Exportar los candidatos (solo lectura)

Desde Ubuntu, en `~/smartmentor`, contra la base compartida:

```bash
mkdir -p ~/e6
cat > /tmp/e6.sql <<'SQL'
\copy (SELECT vc.topic_id, t.name AS topic_name, vc.id AS video_candidate_id, vc.youtube_video_id, vc.title, vc.language, vc.duration_seconds, vc.similarity, vc.rank, vc.search_position, vc.origin, vc.status FROM video_candidates vc JOIN topics t ON t.id = vc.topic_id JOIN courses c ON c.id = t.course_id WHERE vc.active AND t.active AND c.active AND c.status <> 'archived' ORDER BY vc.topic_id, vc.rank) TO STDOUT WITH CSV HEADER
SQL
( set -a; . ./.env; set +a; docker run --rm -i -e ADMIN_DATABASE_URL pgvector/pgvector:0.8.7-pg17-bookworm sh -c 'psql "$ADMIN_DATABASE_URL" -q -f -' < /tmp/e6.sql ) > ~/e6/candidatos.csv
head -3 ~/e6/candidatos.csv
```

## 2. Preparar las hojas de los jueces

```bash
cd ~/smartmentor/ai
python3 -m eval.video_experiment export --candidates ~/e6/candidatos.csv --out ~/e6
```

Deja `juez_1.csv`, `juez_2.csv` y `clave.csv` en `~/e6`. Cada hoja trae los videos de cada tema **en un orden aleatorio distinto por juez** (semilla 42) y **sin** su puesto, su puntaje ni su posición en YouTube. La clave no se comparte con los jueces.

## 3. Juzgar (cada juez por separado)

- Abrir cada enlace y ver lo suficiente para decidir.
- En `is_relevant` escribir `true` si el video **explica el tema de esa fila** a un nivel útil para el curso, o `false` si no. También se aceptan `sí` y `no`.
- No mirar la pantalla D5e ni la hoja del otro juez mientras se juzga: el κ solo vale si los juicios son independientes.
- Guardar el archivo como CSV (UTF-8), sin cambiar las columnas.

## 4. Calcular el resultado

```bash
cd ~/smartmentor/ai
python3 -m eval.video_experiment report --key ~/e6/clave.csv --judges ~/e6/juez_1.csv ~/e6/juez_2.csv --out ~/e6/resultado.md
```

El informe trae el κ, P@3 y nDCG@3 de las cuatro ordenaciones con el número de temas, P@3 del puntaje vigente por idioma del video y la regla de decisión del segundo corte:

- Si (d) no supera a (a), el recomendador no aporta y el instructor elige de la lista.
- Si (c) iguala a (d), se simplifica el puntaje.
- La personalización por aprendiz (H3) solo se construye si el ranking por tema llega a 0,7.

Publicar el resultado en `docs/cohorte_1/evaluation/results/e6-<fecha>.md`. Las hojas de los jueces solo tienen ids de YouTube y ranuras, sin datos personales; si se versionan, van en `data/eval/gold/video_relevance/`.

## Lo que el experimento no dice

- Mide el ranking **por tema**, compartido entre aprendices. No dice nada de la personalización por aprendiz (H3), que no existe todavía.
- Con 2 jueces y pocos temas, cada cifra se reporta con su n y es indicativa.
- La variante con subtítulos (caracterizar el video desde su transcripción) queda condicionada a confirmar que los términos de YouTube lo permiten.
