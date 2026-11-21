#!/bin/sh
# Arranque del contenedor `app`: genera el secrets.toml de st.login desde variables de entorno
# (sin secretos en la imagen) y lanza Streamlit.
set -eu

PYTHONPATH=/app/src python -m core.bootstrap_secrets

exec streamlit run src/main.py --server.port 8501 --server.address 0.0.0.0
