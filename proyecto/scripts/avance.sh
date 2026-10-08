#!/usr/bin/env bash
# Calcula el avance de proyecto/checklist.md a partir de sus casillas (- [ ] pendiente, - [x] hecha).
#
# Uso:
#   proyecto/scripts/avance.sh                     # muestra el avance por sección
#   proyecto/scripts/avance.sh --actualizar        # reescribe la tabla de «Avance de la fase» en el checklist
#   proyecto/scripts/avance.sh pendientes <nombre> # tareas abiertas de una persona; «por asignar» lista las sin dueño
#
# Cuenta las casillas de cada sección «## ...» y omite las de los bloques de código.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FILE="$ROOT_DIR/proyecto/checklist.md"

resumen() {
  awk '
    /^```/ { fence = !fence; next }
    fence { next }
    /^## / { section = substr($0, 4); next }
    /^[[:space:]]*- \[[ xX]\] / {
      if (!(section in total)) order[++n] = section
      total[section]++; all++
      if ($0 ~ /^[[:space:]]*- \[[xX]\] /) { done[section]++; alldone++ }
    }
    END {
      print "| Sección | Hechas | Total | Avance |"
      print "| --- | ---: | ---: | ---: |"
      for (i = 1; i <= n; i++) {
        s = order[i]
        printf "| %s | %d | %d | %d %% |\n", s, done[s], total[s], int(done[s] * 100 / total[s] + 0.5)
      }
      printf "| **Total** | **%d** | **%d** | **%d %%** |\n", alldone, all, (all ? int(alldone * 100 / all + 0.5) : 0)
    }' "$FILE"
}

case "${1:-}" in
  "")
    resumen
    ;;
  --actualizar)
    HOY="$(TZ=America/Bogota date +%F)"
    TABLA="$(resumen)"
    awk -v tabla="$TABLA" -v hoy="$HOY" '
      /<!-- AVANCE:INICIO -->/ { print; print ""; print tabla; print ""; print "_Calculado el " hoy " con `proyecto/scripts/avance.sh --actualizar`._"; print ""; skip = 1; next }
      /<!-- AVANCE:FIN -->/ { skip = 0 }
      !skip { print }
    ' "$FILE" > "$FILE.tmp"
    mv "$FILE.tmp" "$FILE"
    sed -i -E "s/^(\*\*Última actualización:\*\* )[0-9-]+/\1$HOY/" "$FILE"
    echo "Checklist actualizado ($HOY)."
    ;;
  pendientes)
    QUIEN="${2:?Indica un nombre (por ejemplo eduar.troyano) o «por asignar»}"
    awk -v quien="$QUIEN" '
      /^```/ { fence = !fence; next }
      fence { next }
      /^## / { section = substr($0, 4); next }
      /^[[:space:]]*- \[ \] / {
        if (index($0, "**Resp.:** " quien) || (quien == "por asignar" && index($0, "_por asignar_")))
          print "[" section "] " substr($0, index($0, "]") + 2)
      }' "$FILE"
    ;;
  *)
    sed -n '2,10p' "${BASH_SOURCE[0]}"
    exit 1
    ;;
esac
