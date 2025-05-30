import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta
from PIL import Image, ImageDraw, ImageFont
import zipfile
import os

# Usar backend sin GUI para matplotlib (recomendado en Streamlit Cloud)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

import matplotlib.dates as mdates
from matplotlib.gridspec import GridSpec
import numpy as np
from io import BytesIO
import base64

# --- Configuración Inicial ---
TOKEN = "1440756de925e6f19ce08bd468d397923d94430ac3480c33386a74a4f1dd94e0"
HEADERS = {"Bmx-Token": TOKEN}
BASE_URL = "https://www.banxico.org.mx/SieAPIRest/service/v1/series/{}/datos/{}/{}"
SERIES = {
    "28 Días": "SF43936",
    "91 Días": "SF43939",
    "182 Días": "SF43942",
    "364 Días": "SF43945",
    "728 Días": "SF349785",
    "Tasa Objetivo": "SF61745",
    "Tipo de Cambio FIX": "SF43718"
}

hoy = datetime.today()
inicio = (hoy - timedelta(days=365)).strftime("%Y-%m-%d")
fin = hoy.strftime("%Y-%m-%d")

st.set_page_config(layout="wide")
st.title("📈 Resumen CETES y Tasa Objetivo - Banxico")

# --- Archivos embebidos por defecto ---
def cargar_icono_por_defecto():
    with open("hucha.png", "rb") as f:
        return Image.open(f).resize((150, 150)).convert("RGBA")

def buscar_fuente(nombre):
    for root, _, files in os.walk("fuentes"):
        for file in files:
            if file.lower() == nombre.lower():
                return os.path.join(root, file)
    return None

def cargar_fuente_por_defecto(size):
    path = buscar_fuente("Lato-Bold.ttf")
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception as e:
        print(f"⚠️ Error cargando fuente embebida: {e}")
    return ImageFont.load_default()

# --- Carga de Archivos ---
st.sidebar.header("Carga de Archivos (opcional)")
icon_file = st.sidebar.file_uploader("Icono Hucha (PNG)", type=["png"])
font_zip = st.sidebar.file_uploader("Fuente .zip (ej: lato.zip)", type=["zip"])

# --- Extraer fuentes ---
if font_zip is not None:
    with zipfile.ZipFile(font_zip, 'r') as zip_ref:
        zip_ref.extractall("fuentes")

def cargar_fuente(nombre, size):
    path = buscar_fuente(nombre)
    try:
        if path and os.path.exists(path):
            return ImageFont.truetype(path, size)
    except Exception as e:
        print(f"⚠️ Error cargando fuente subida: {e}")
    return ImageFont.load_default()

# --- Procesamiento de datos ---
@st.cache_data
def obtener_serie(clave):
    url = BASE_URL.format(clave, inicio, fin)
    r = requests.get(url, headers=HEADERS)
    datos = r.json()["bmx"]["series"][0]["datos"]
    df = pd.DataFrame(datos)
    df["fecha"] = pd.to_datetime(df["fecha"], dayfirst=True)
    df["dato"] = pd.to_numeric(df["dato"].str.replace(",", ""), errors="coerce")
    return df.dropna().sort_values("fecha")

# --- Crear Imagen Resumen ---
def generar_imagen_resumen(icon_img):
    resumen_series = {}
    for nombre, clave in SERIES.items():
        if nombre != "Tipo de Cambio FIX":
            df = obtener_serie(clave)
            if df is not None and len(df) >= 2:
                resumen_series[nombre] = {
                    "anterior": df["dato"].iloc[-2],
                    "actual": df["dato"].iloc[-1]
                }

    tasa_obj = resumen_series.get("Tasa Objetivo")

    img = Image.new("RGB", (1080, 1350), "white")
    draw = ImageDraw.Draw(img)
    for y in range(1350):
        r = int(173 + (255 - 173) * y / 1350)
        g = int(216 + (255 - 216) * y / 1350)
        b = int(230 + (255 - 230) * y / 1350)
        draw.line([(0, y), (1080, y)], fill=(r, g, b))

    if icon_img:
        icon = Image.open(icon_img).resize((150, 150)).convert("RGBA")
    else:
        icon = cargar_icono_por_defecto()
    img.paste(icon, (900, 20), icon)

    title_font = cargar_fuente("Lato-Bold.ttf", 90) if font_zip else cargar_fuente_por_defecto(90)
    label_font = cargar_fuente("Lato-Bold.ttf", 70) if font_zip else cargar_fuente_por_defecto(70)
    value_font = cargar_fuente("Lato-Bold.ttf", 65) if font_zip else cargar_fuente_por_defecto(65)
    small_font = cargar_fuente("Lato-Bold.ttf", 40) if font_zip else cargar_fuente_por_defecto(40)
    tiny_font = cargar_fuente("Lato-Bold.ttf", 35) if font_zip else cargar_fuente_por_defecto(35)

    draw.text((40, 40), "Resumen CETES", fill="#222222", font=title_font)
    y_pos = 180
    for plazo in ["28 Días", "91 Días", "182 Días", "364 Días", "728 Días"]:
        datos = resumen_series[plazo]
        draw.text((60, y_pos), plazo, fill="#D32F2F", font=label_font)
        draw.text((500, y_pos), f"Actual: {datos['actual']:.2f}%", fill="black", font=value_font)
        draw.text((500, y_pos + 70), f"Anterior: {datos['anterior']:.2f}%", fill="#555555", font=tiny_font)
        y_pos += 180

    draw.multiline_text((60, y_pos + 10), "Tasa\nObjetivo", fill="#D32F2F", font=label_font, spacing=10)
    draw.text((500, y_pos + 10), f"Actual: {tasa_obj['actual']:.2f}%", fill="black", font=value_font)
    draw.text((500, y_pos + 80), f"Anterior: {tasa_obj['anterior']:.2f}%", fill="#555555", font=tiny_font)

    fecha_texto = hoy.strftime("*datos para el %d de %B de %Y").replace("May", "Mayo")
    draw.text((40, 1270), fecha_texto, fill="#555555", font=small_font)
    draw.text((780, 1285), "Fuente: Banxico", fill="#555555", font=small_font)

    return img

# --- Crear Gráficas ---
def generar_grafica_evolucion():
    series_largas = {}
    for nombre, clave in SERIES.items():
        if nombre != "Tasa Objetivo":
            df = obtener_serie(clave)
            df = df[(df["fecha"] >= pd.to_datetime(inicio)) & (df["fecha"] <= pd.to_datetime(fin))]
            df = df.set_index("fecha").resample("D").interpolate().reset_index()
            series_largas[nombre] = df

    n_series = len(series_largas)
    n_cols = 2
    n_rows = int(np.ceil(n_series / n_cols))
    fig = plt.figure(figsize=(12, 12))
    gs = GridSpec(n_rows, n_cols, figure=fig, hspace=0.5, wspace=0.3)
    fig.suptitle("CETES y Tipo de Cambio", fontsize=20, weight='bold', y=0.99)

    for i, (nombre, df) in enumerate(series_largas.items()):
        fechas = mdates.date2num(df["fecha"])
        valores = df["dato"].astype(float).values
        row = i // n_cols
        col = i % n_cols
        ax = fig.add_subplot(gs[row, col])

        ax.plot(df["fecha"], valores, "-", linewidth=2, color='black')
        ax.fill_between(fechas, valores, color='gray', alpha=0.2)

        valor_ini = valores[0]
        valor_fin = valores[-1]
        cambio_pct = ((valor_fin - valor_ini) / valor_ini) * 100
        ypos = valor_ini * 0.65

        ax.text(df["fecha"].iloc[0], ypos, f"{valor_ini:.2f}", fontsize=10, color='red', weight='bold')
        ax.text(df["fecha"].iloc[-1], ypos, f"{valor_fin:.2f}", fontsize=10, color='green', ha='right', weight='bold')

        if "FIX" not in nombre:
            ax.text(df["fecha"].iloc[-1], ypos * 0.85, f"({cambio_pct:+.1f}%)", fontsize=9, color='green', ha='right', weight='bold')

        ax.set_title(nombre, fontsize=12, weight='bold')
        ax.xaxis.set_major_locator(mdates.MonthLocator(interval=2))
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%b-%y'))
        ax.tick_params(axis='x', rotation=45)
        ax.grid(True, linestyle='--', alpha=0.3)
        ax.set_ylabel("Valor")

    buf = BytesIO()
    plt.savefig(buf, format='png', dpi=150)
    plt.close()
    buf.seek(0)
    return buf

# --- Mostrar Resultados ---
if st.sidebar.button("Generar Visualizaciones"):
    with st.spinner("Generando resumen..."):
        img = generar_imagen_resumen(icon_file)
        st.image(img, caption="Resumen CETES", use_column_width=True)

    with st.spinner("Generando gráficas..."):
        buf = generar_grafica_evolucion()
        st.image(buf, caption="Gráficas de evolución", use_column_width=True)

