# Arquitectura de Desarrollo Frontend para Streamlit

Esta guía define una arquitectura robusta, modular y escalable para aplicaciones web desarrolladas con **Streamlit**, aplicando separación de responsabilidades y el patrón de Single Page Application (SPA) nativo.

---

## 1. Arquitectura por Capas (Patrón MVT / Decoupled UI)

Streamlit ejecuta el código en cada interacción del usuario. Para garantizar el rendimiento y la mantenibilidad, desacoplamos la UI de la lógica de negocio y las conexiones a datos:

```text
┌─────────────────────────────────────────────────────────┐
│        Capa de Presentación (Pages & Components)        │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│    Capa de Estado y Control (st.session_state & Core)   │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│    Capa de Servicios / Lógica de Negocio (Services)    │
└────────────────────────────┬────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────┐
│      Capa de Datos / Conexiones (API Clients & DB)      │
└─────────────────────────────────────────────────────────┘
```

1. **Presentación (UI):** Exclusivamente componentes visuales de Streamlit (`st.write`, `st.dataframe`, layouts). No contiene procesamiento pesado ni llamadas directas a BD.
2. **Estado y Control:** Administra el estado global (`st.session_state`), eventos y configuraciones compartidas.
3. **Servicios (Lógica):** Funciones puras de Python que aplican reglas de negocio, transforman datos o preparan DataFrames.
4. **Datos / API:** Clientes HTTP y conectores de base de datos protegidos con cachés de Streamlit (`@st.cache_data` / `@st.cache_resource`).

---

## 2. Estructura de Directorios

```text
mi_proyecto_streamlit/
│
├── .streamlit/                     # Configuración de entorno Streamlit
│   ├── config.toml                 # Tema visual (colores, fuentes, layout)
│   └── secrets.toml                # Credenciales y llaves de API (local)
│
├── src/                            # Código fuente de la aplicación
│   ├── __init__.py
│   ├── main.py                     # Router principal (st.navigation)
│   │
│   ├── core/                       # Configuración global y estado
│   │   ├── config.py               # Variables de entorno
│   │   ├── constants.py            # Constantes y textos fijos
│   │   └── state.py                # Helper para inicialización de st.session_state
│   │
│   ├── components/                 # Componentes de UI reutilizables
│   │   ├── sidebar.py              # Filtros y paneles laterales
│   │   ├── navbar.py               # Header / Footer común
│   │   ├── metrics.py              # Cards y métricas
│   │   └── charts.py               # Gráficos configurados (Plotly, Altair)
│   │
│   ├── pages/                      # Vistas / Páginas de la app
│   │   ├── home.py                 # Vista principal
│   │   ├── analytics.py            # Módulo de analítica
│   │   ├── settings.py             # Configuración de usuario
│   │   └── admin.py                # Panel de administración
│   │
│   ├── services/                   # Lógica de negocio
│   │   ├── data_processing.py      # Transformación y limpieza de datos
│   │   └── auth_service.py         # Lógica de autenticación y roles
│   │
│   └── api/                        # Conexiones externas
│       ├── client.py               # Cliente REST / FastAPI
│       └── db.py                   # Conexión a bases de datos
│
├── tests/                          # Pruebas unitarias y de integración
│   ├── test_services.py
│   └── test_components.py
│
├── assets/                         # Recursos estáticos
│   ├── css/
│   │   └── style.css               # Estilos personalizados (CSS inyectado)
│   └── images/                     # Logos, favicon e imágenes
│
├── .gitignore
├── README.md
├── requirements.txt                # Dependencias
└── Dockerfile                      # Contenedor para despliegue
```

---

## 3. Implementación Básica de Código

### A. Punto de Entrada Principal (`src/main.py`)

```python
import streamlit as st
from core.state import init_session_state
from components.sidebar import render_sidebar

# 1. Configuración global de la página
st.set_page_config(
    page_title="App Empresarial",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Inicializar el estado de la sesión
init_session_state()

# 3. Definición de páginas usando la API nativa de navegación
home_page = st.Page("pages/home.py", title="Inicio", icon="🏠", default=True)
analytics_page = st.Page("pages/analytics.py", title="Analítica", icon="📊")
settings_page = st.Page("pages/settings.py", title="Configuración", icon="⚙️")

# 4. Enrutamiento y agrupamiento
pg = st.navigation(
    {
        "Principal": [home_page, analytics_page],
        "Sistema": [settings_page],
    }
)

# 5. Renderizar layout común y ejecutar página actual
render_sidebar()
pg.run()
```

### B. Inicialización del Estado (`src/core/state.py`)

```python
import streamlit as st

def init_session_state():
    """Inicializa todas las variables globales del estado si no existen."""
    default_state = {
        "user_authenticated": False,
        "user_role": "guest",
        "selected_filters": {},
        "theme_mode": "light"
    }
    
    for key, value in default_state.items():
        if key not in st.session_state:
            st.session_state[key] = value
```

### C. Cliente de API con Caché (`src/api/client.py`)

```python
import streamlit as st
import requests

@st.cache_data(ttl=600)  # Reutiliza el resultado durante 10 minutos
def fetch_sales_data(endpoint: str, params: dict):
    """Realiza peticiones HTTP GET y almacena en caché el resultado."""
    url = f"https://api.miempresa.com/v1/{endpoint}"
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    return response.json()
```

---

## 4. Buenas Prácticas de Desarrollo

1. **Manejo Correcto de Caché:**
   * Usa `@st.cache_data` para resultados de consultas HTTP, DataFrames y transformaciones de datos.
   * Usa `@st.cache_resource` para objetos pesados o conexiones persistentes (modelos ML, clientes de base de datos).
2. **Desacoplamiento de Componentes:**
   * Pasa parámetros a las funciones de `components/` de forma explícita en lugar de hacer que dependan internamente de `st.session_state`.
3. **Control de Estilos Visuales:**
   * Mantén un archivo `.streamlit/config.toml` para definir la paleta de colores.
   * Carga estilos adicionales mediante un archivo `assets/css/style.css` inyectado a través de `st.markdown`.