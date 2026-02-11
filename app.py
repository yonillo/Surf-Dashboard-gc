import streamlit as st
import requests
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import pydeck as pdk
import sqlite3

# --- CONFIGURACIÓN ---
st.set_page_config(page_title="Surf Decision GC", layout="wide")

# --- ESTILOS SURFEROS ---
st.markdown("""
    <style>
    .stApp { background: #001219; color: white; }
    .verdict-box {
        padding: 40px;
        border-radius: 25px;
        text-align: center;
        margin-bottom: 20px;
        font-family: 'Arial Black', Gadget, sans-serif;
    }
    .reason-text {
        font-size: 20px;
        font-style: italic;
        margin-top: 10px;
        opacity: 0.9;
    }
    .hour-chip {
        padding: 10px;
        border-radius: 10px;
        text-align: center;
        font-weight: bold;
        margin: 2px;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SPOTS ---
SPOTS = {
    "La Cícer": {"lat": 28.1311, "lon": -15.4467, "webcam": "https://www.skylinewebcams.com/es/webcam/espana/canarias/las-palmas-gran-canaria/la-cicer-las-canteras.html"},
    "El Confital": {"lat": 28.1441, "lon": -15.4340, "webcam": "https://www.skylinewebcams.com/es/webcam/espana/canarias/las-palmas-gran-canaria/playa-confital.html"},
    "La Laja": {"lat": 28.0747, "lon": -15.4123, "webcam": "https://www.skylinewebcams.com/es/webcam/espana/canarias/las-palmas-gran-canaria/playa-de-la-laja.html"},
    "San Andrés": {"lat": 28.1338, "lon": -15.4660, "webcam": "https://www.skylinewebcams.com/es/webcam/espana/canarias/las-palmas-gran-canaria/puerto-de-las-palmas.html"},
}

# --- LÓGICA DE DECISIÓN (EL "HUMAN VERDICT") ---
def get_human_verdict(h, p, w):
    reasons = []
    score = 0
    
    # Evaluar Altura
    if h < 0.5: 
        reasons.append("está muy plato")
    elif 0.8 <= h <= 2.0: 
        score += 2
        reasons.append("el tamaño es ideal")
    else:
        score += 1
        reasons.append("hay olas, pero quizás grandes")

    # Evaluar Periodo (Calidad)
    if p > 9: 
        score += 2
        reasons.append("vienen con mucha fuerza y ordenadas")
    elif p > 7:
        score += 1
        reasons.append("tienen un periodo aceptable")
    else:
        reasons.append("están muy seguidas y desordenadas")

    # Evaluar Viento
    if w < 12:
        score += 1
        reasons.append("el viento está muy flojo (mar limpio)")
    elif w > 22:
        score -= 2
        reasons.append("el viento está rompiendo la ola")

    # Veredicto Final
    if score >= 4:
        return "✅ ¡AL AGUA YA!", "#2d6a4f", f"Es un gran momento porque {' y '.join(reasons)}."
    elif score >= 2:
        return "⚖️ ESTÁ PASABLE", "#b08d57", f"Puedes probar, aunque {' y '.join(reasons)}."
    else:
        return "❌ MEJOR QUÉDATE EN CASA", "#343a40", f"No merece la pena porque {' y '.join(reasons)}."

# --- CARGA DE DATOS ---
@st.cache_data(ttl=1800)
def fetch_surf_api(lat, lon):
    try:
        m_url = f"https://marine-api.open-meteo.com/v1/marine?latitude={lat}&longitude={lon}&hourly=wave_height,wave_period&timezone=auto"
        w_url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=wind_speed_10m&timezone=auto"
        dm = pd.DataFrame(requests.get(m_url).json()["hourly"])
        dw = pd.DataFrame(requests.get(w_url).json()["hourly"])
        df = pd.merge(dm, dw, on="time")
        df["time"] = pd.to_datetime(df["time"])
        return df
    except: return pd.DataFrame()

# --- INTERFAZ ---
st.title("🏄 ¿Se puede entrar hoy?")

selected_name = st.sidebar.selectbox("📍 ¿Dónde quieres ir?", list(SPOTS.keys()))
spot = SPOTS[selected_name]

df = fetch_surf_api(spot["lat"], spot["lon"])

if not df.empty:
    now_utc = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)
    df_next = df.loc[df['time'].dt.tz_localize('UTC') >= now_utc].head(24).copy()
    current = df_next.iloc[0]
    
    # 1. EL VEREDICTO (GIGANTE)
    verdict, color, explanation = get_human_verdict(current['wave_height'], current['wave_period'], current['wind_speed_10m'])
    
    st.markdown(f"""
        <div class="verdict-box" style="background-color: {color}; border: 3px solid rgba(255,255,255,0.2);">
            <div style="font-size: 60px;">{verdict}</div>
            <div class="reason-text">{explanation}</div>
        </div>
    """, unsafe_allow_html=True)

    # 2. CUÁNDO IR (EL SEMÁFORO DE HORAS)
    st.subheader("⏰ Previsión para las próximas horas")
    cols = st.columns(8) # Próximas 8 franjas de 3 horas
    for i, franja in enumerate(df_next.iloc[::3].head(8).itertuples()):
        v, c, _ = get_human_verdict(franja.wave_height, franja.wave_period, franja.wind_speed_10m)
        with cols[i]:
            st.markdown(f"""
                <div class="hour-chip" style="background-color: {c};">
                    {franja.time.strftime('%H:00')}<br>
                    {franja.wave_height:.1f}m
                </div>
            """, unsafe_allow_html=True)

    st.write("")
    
    # 3. ACCIÓN Y VERIFICACIÓN
    c1, c2 = st.columns(2)
    with c1:
        st.info("💡 **CONSEJO TÉCNICO:** El mar tiene energía. Si entras, respeta las prioridades y disfruta.")
        st.link_button(f"👁️ VER WEBCAM DE {selected_name.upper()}", spot['webcam'])
    with c2:
        # Mini mapa para asegurar que saben donde es
        view = pdk.ViewState(latitude=spot["lat"], longitude=spot["lon"], zoom=14, pitch=0)
        st.pydeck_chart(pdk.Deck(
            map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
            initial_view_state=view,
            layers=[pdk.Layer("ScatterplotLayer", data=pd.DataFrame([spot]), get_position='[lon, lat]', get_color=[0, 212, 255, 200], get_radius=100)]
        ))

    # 4. DATOS PARA EL QUE QUIERA MIRAR MÁS (Plegado)
    with st.expander("🤓 Soy un friki de los datos, enséñame los números"):
        st.line_chart(df_next.set_index('time')[['wave_height', 'wave_period']])
        st.write("Datos en bruto de la API:")
        st.dataframe(df_next)

else:
    st.error("No hay conexión con la boya. Mira por la ventana.")

st.caption("Yone Suarez | ULPGC Engineering | v11.0 Human Decisions")
