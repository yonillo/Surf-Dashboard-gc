import streamlit as st
import requests
import pandas as pd
import plotly.express as px
from datetime import datetime, timedelta, timezone
import pydeck as pdk
from PIL import Image
import base64
import io

# Coordenadas de los spots de surf
SPOTS = {
    "La Cícer": (28.13110735259434, -15.446698859594266),
    "El Confital": (28.1441, -15.4340),
    "La Laja": (28.0747, -15.4123),
    "San Andrés": (28.14670670936141, -15.555085904921604),
}


# Antes de crear df_spots, obtenemos la puntuación para cada spot y el color

def score_to_color(score):
    if score >= 4:
        return [0, 255, 0, 160]   # Verde
    elif score >= 2:
        return [255, 255, 0, 160] # Amarillo
    else:
        return [255, 0, 0, 160]   # Rojo

comparativa_colores = []
for spot, (lat, lon) in SPOTS.items():
    wave = get_wave_data(lat, lon, inicio, fin)
    weather = get_weather_data(lat, lon, inicio, fin)
    if wave.empty or weather.empty:
        color = [128,128,128,160]  # Gris si no hay datos
    else:
        comb = pd.merge(wave, weather, on="time", how="inner")
        comb['score'] = comb.apply(evaluar_condiciones, axis=1)
        score = comb['score'].iloc[-1]
        color = score_to_color(score)
    comparativa_colores.append({"Spot": spot, "lat": lat, "lon": lon, "color": color})

df_spots = pd.DataFrame(comparativa_colores)

# Y luego, en la capa pydeck, en lugar de get_color fijo:
layers=[
    pdk.Layer(
        'ScatterplotLayer',
        data=df_spots,
        get_position='[lon, lat]',
        get_color='color',
        get_radius=300,
        pickable=True,
        auto_highlight=True,
    )
]

# Crear DataFrame con spots
df_spots = pd.DataFrame([
    {"Spot": name, "lat": coord[0], "lon": coord[1]} 
    for name, coord in SPOTS.items()
])

# Configuración del mapa centrado en Gran Canaria
midpoint = (df_spots["lat"].mean(), df_spots["lon"].mean())

st.set_page_config(page_title="Surf Dashboard - Canarias", layout="wide")
st.title("\U0001F3C4 Surf Dashboard - Spots de Gran Canaria")

st.subheader("\U0001F4CD Mapa de Spots de Surf en Gran Canaria")

# Mostrar mapa con marcadores
st.pydeck_chart(pdk.Deck(
    map_style='https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
    initial_view_state=pdk.ViewState(
        latitude=midpoint[0],
        longitude=midpoint[1],
        zoom=11,
        pitch=0,
    ),
    layers=[
        pdk.Layer(
            'ScatterplotLayer',
            data=df_spots,
            get_position='[lon, lat]',
            get_color='[0, 128, 255, 160]',
            get_radius=300,
            pickable=True,
            auto_highlight=True,
        )
    ],
    tooltip={"text": "{Spot}"}
))

# Función para obtener datos marinos
def get_wave_data(lat, lon, start_date, end_date):
    url = "https://marine-api.open-meteo.com/v1/marine"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "wave_height,wind_wave_height,swell_wave_height,wind_wave_direction,swell_wave_period",
        "start_date": start_date,
        "end_date": end_date,
        "timezone": "auto"
    }
    response = requests.get(url, params=params)
    data = response.json()
    st.write("Datos crudos API marina:", data)
    if "hourly" not in data:
        st.error("No se encontraron datos horarios marinos en la respuesta de la API.")
        return pd.DataFrame()
    df = pd.DataFrame(data["hourly"])
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])
    return df

# Función para obtener datos meteorológicos (viento)
def get_weather_data(lat, lon, start_date, end_date):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "hourly": "windspeed_10m",
        "start": start_date,
        "end": end_date,
        "timezone": "auto"
    }
    response = requests.get(url, params=params)
    data = response.json()
    st.write("Datos crudos API meteorológica:", data)
    if "hourly" not in data:
        st.error("No se encontraron datos horarios meteorológicos en la respuesta de la API.")
        return pd.DataFrame()
    df = pd.DataFrame(data["hourly"])
    if not df.empty:
        df["time"] = pd.to_datetime(df["time"])
    return df

# Función para obtener datos de mareas desde Puertos del Estado (simulado para Las Palmas)
def get_tides_puertos(start_date, end_date):
    example_data = {
        "datetime": pd.date_range(start=start_date, periods=48, freq="H"),
        "tide": [0.5 + 0.3 * ((i % 12) / 6 - 1)**2 for i in range(48)]
    }
    return pd.DataFrame(example_data)

# Función para evaluar condiciones de surf y asignar una puntuación de 1 a 5
def evaluar_condiciones(row):
    score = 0
    if 0.8 <= row['wave_height'] <= 2.0:
        score += 2
    elif 0.5 <= row['wave_height'] < 0.8:
        score += 1
    if row['swell_wave_period'] >= 10:
        score += 2
    elif row['swell_wave_period'] >= 7:
        score += 1
    if row['windspeed_10m'] < 15:
        score += 1
    return min(score, 5)

spot_name = st.selectbox("Selecciona un spot de surf:", list(SPOTS.keys()))
lat, lon = SPOTS[spot_name]

# Fechas: hoy y mañana
hoy = datetime.now(timezone.utc).date()
inicio = hoy.strftime("%Y-%m-%d")
fin = (hoy + timedelta(days=1)).strftime("%Y-%m-%d")

# Obtener datos
wave_data = get_wave_data(lat, lon, inicio, fin)
weather_data = get_weather_data(lat, lon, inicio, fin)
tide_data = get_tides_puertos(inicio, fin)

if wave_data.empty or weather_data.empty:
    st.warning("No se han encontrado datos suficientes para las fechas seleccionadas y el spot.")
else:
    combined = pd.merge(wave_data, weather_data, on="time", how="inner")
    combined['score'] = combined.apply(evaluar_condiciones, axis=1)

    actual = combined.iloc[-1]
    col1, col2, col3 = st.columns(3)
    col1.metric("Altura de ola", f"{actual['wave_height']:.2f} m")
    col2.metric("Viento (10m)", f"{actual['windspeed_10m']:.1f} km/h")
    col3.metric("Altura ola swell", f"{actual['swell_wave_height']:.2f} m")

    st.markdown("### ⭐ Condiciones actuales de surf")
    ola_url = "https://cdn-icons-png.flaticon.com/512/861/861060.png"
    st.image([ola_url]*actual['score'], width=40)

    if actual['score'] >= 4:
        st.success("\U0001F7E2 ¡Condiciones óptimas para surfear!")
    elif actual['score'] >= 2:
        st.info("\U0001F7E1 Condiciones moderadas, consulta la evolución.")
    else:
        st.warning("\U0001F534 Condiciones desfavorables para surf.")

    st.subheader("\U0001F4C8 Evolución de las condiciones marinas y meteorológicas (48h)")
    fig1 = px.line(combined, x="time", y="wave_height", title="Altura de las olas (m)")
    fig2 = px.line(combined, x="time", y="swell_wave_period", title="Periodo de las olas swell (s)")
    fig3 = px.line(combined, x="time", y="windspeed_10m", title="Velocidad del viento a 10m (km/h)")

    st.plotly_chart(fig1, use_container_width=True)
    st.plotly_chart(fig2, use_container_width=True)
    st.plotly_chart(fig3, use_container_width=True)

    st.subheader("\U0001F30A Nivel de mareas (Puertos del Estado)")
    fig4 = px.line(tide_data, x="datetime", y="tide", title="Nivel de marea (estimado)",
                   labels={"tide": "Nivel (m)", "datetime": "Hora"})
    st.plotly_chart(fig4, use_container_width=True)

    # Comparativa de spots
    st.subheader("\U0001F4CA Comparativa entre spots hoy")
    comparativa = []
    for spot, (lat, lon) in SPOTS.items():
        wave = get_wave_data(lat, lon, inicio, fin)
        weather = get_weather_data(lat, lon, inicio, fin)
        if wave.empty or weather.empty:
            continue
        comb = pd.merge(wave, weather, on="time", how="inner")
        comb['score'] = comb.apply(evaluar_condiciones, axis=1)
        comparativa.append({"Spot": spot, "Puntuación máx": comb['score'].max(), "Score icons": [ola_url]*comb['score'].max()})
    df_comp = pd.DataFrame(comparativa).sort_values("Puntuación máx", ascending=False)

    for _, row in df_comp.iterrows():
        st.markdown(f"**{row['Spot']}**")
        st.image(row["Score icons"], width=30)

st.caption("Datos obtenidos desde Open-Meteo y Puertos del Estado (simulación de mareas)")
