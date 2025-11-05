import streamlit as st
import os
import pandas as pd # <-- Tambahkan import pandas
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Impor halaman-halaman Anda
import page_input_data
import page_analisa_abc
import utils  # Impor file utilitas Anda

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis ABC")

# --- Inisialisasi Session State ---
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()
# [DIHAPUS] if 'df_portal' not in st.session_state:
#    st.session_state.df_portal = pd.DataFrame() 
if 'abc_analysis_result' not in st.session_state:
    st.session_state.abc_analysis_result = None
if 'abc_metric' not in st.session_state:
    st.session_state.abc_metric = 'Kuantitas'
if 'revenue_available' not in st.session_state:
    st.session_state.revenue_available = False

# --- SIDEBAR ---
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis ABC")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa ABC"),
    help="Pilih halaman untuk ditampilkan."
)
st.sidebar.markdown("---")

# --- KONEKSI GOOGLE DRIVE (Dilakukan sekali di app utama) ---
drive_service, DRIVE_AVAILABLE = utils.connect_gdrive()


# =====================================================================================
#                            ROUTING HALAMAN
# =====================================================================================

if page == "Input Data":
    # Kirim 'drive_service' dan 'DRIVE_AVAILABLE' ke halaman input data
    page_input_data.render_page(drive_service, DRIVE_AVAILABLE)

elif page == "Hasil Analisa ABC":
    # Halaman analisa tidak perlu 'drive_service' karena datanya sudah ada di session_state
    page_analisa_abc.render_page()
