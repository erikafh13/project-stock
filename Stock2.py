import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import os, io, math, re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

# --- KONFIGURASI DASAR ---
st.set_page_config(layout="wide", page_title="Analisis Stock & ABC")
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis Stock & ABC")
page = st.sidebar.radio("Navigasi", ("Input Data", "Analisis ABC"))

# --- INISIALISASI STATE ---
for key in ["df_penjualan", "produk_ref", "df_stock", "abc_analysis_result"]:
    if key not in st.session_state: st.session_state[key] = pd.DataFrame() if 'df' in key else None

# --- KONEKSI GOOGLE DRIVE ---
SCOPES = ['https://www.googleapis.com/auth/drive']
DRIVE_AVAILABLE = False
try:
    creds = (service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
             if "gcp_service_account" in st.secrets else None)
    if creds: DRIVE_AVAILABLE, drive_service = True, build('drive', 'v3', credentials=creds)
    st.sidebar.success("✅ Terhubung ke Google Drive")
except Exception as e:
    st.sidebar.error(f"Gagal koneksi ke Google Drive: {e}")

# --- UTILITAS GOOGLE DRIVE ---
@st.cache_data(ttl=600)
def list_files(folder_id):
    if not DRIVE_AVAILABLE: return []
    query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'"
    res = drive_service.files().list(q=query, fields="files(id,name)").execute()
    return res.get("files", [])

@st.cache_data(ttl=600)
def read_drive_excel(file_id, skiprows=0, **kwargs):
    req = drive_service.files().get(fileId=file_id, fields="name").execute()
    file_name = req['name']

    req = drive_service.files().get_media(fileId=file_id)
    fh = BytesIO(); downloader = MediaIoBaseDownload(fh, req)
    done = False
    while not done:
        _, done = downloader.next_chunk()
    fh.seek(0)

    # Pilih engine berdasarkan ekstensi
    if file_name.lower().endswith('.xls'):
        engine = 'xlrd'
    else:
        engine = 'openpyxl'

    return pd.read_excel(fh, skiprows=skiprows, engine=engine, **kwargs)


# --- MAPPING & PREPROCESSING ---
def map_nama_dept(row):
    dept, pelanggan = str(row.get('Dept.', '')).strip().upper(), str(row.get('Nama Pelanggan', '')).strip().upper()
    if dept == 'A': return 'A - ITC' if pelanggan in ['A - CASH','AIRPAY INTERNATIONAL INDONESIA','TOKOPEDIA'] else 'A - RETAIL'
    return {'B':'B - JKT','C':'C - PUSAT','D':'D - SMG','E':'E - JOG','F':'F - MLG','H':'H - BALI','G':'G - PROJECT'}.get(dept,'X')

def map_city(dept):
    return {'A - ITC':'Surabaya','A - RETAIL':'Surabaya','B - JKT':'Jakarta','C - PUSAT':'Surabaya','D - SMG':'Semarang',
            'E - JOG':'Jogja','F - MLG':'Malang','H - BALI':'Bali','G - PROJECT':'Surabaya'}.get(dept,'Others')

def convert_excel(df):
    out = BytesIO()
    with pd.ExcelWriter(out, engine='openpyxl') as writer: df.to_excel(writer, index=False)
    return out.getvalue()

# =====================================================================================
#                              HALAMAN INPUT DATA
# =====================================================================================
if page == "Input Data":
    st.title("📥 Input Data dari Google Drive")
    if not DRIVE_AVAILABLE:
        st.error("Tidak dapat terhubung ke Google Drive."); st.stop()

    folder_penjualan, folder_produk, folder_stock = (
        "1Okgw8qHVM8HyBwnTUFHbmYkNKqCcswNZ",
        "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv",
        "1PMeH_wvgRUnyiZyZ_wrmKAATX9JyWzq_"
    )

    # --- PENJUALAN ---
    st.subheader("📦 Data Penjualan")
    penjualan_files = list_files(folder_penjualan)
    if st.button("Muat Semua File Penjualan"):
        if penjualan_files:
            df_penjualan = pd.concat(
                [pd.read_excel(read_drive_excel(f['id'])) for f in penjualan_files],
                ignore_index=True
            )
            # --- PREPROCESSING PENJUALAN ---
            df_penjualan['No. Barang'] = df_penjualan['No. Barang'].astype(str).str.strip()
            df_penjualan['Nama Dept'] = df_penjualan.apply(map_nama_dept, axis=1)
            df_penjualan['City'] = df_penjualan['Nama Dept'].apply(map_city)
            df_penjualan['Tgl Faktur'] = pd.to_datetime(df_penjualan['Tgl Faktur'], dayfirst=True, errors='coerce')
            df_penjualan.dropna(subset=['Tgl Faktur'], inplace=True)
            if all(x in df_penjualan.columns for x in ['Qty', 'Harga Sat']):
                df_penjualan['Revenue'] = df_penjualan['Qty'] * df_penjualan['Harga Sat']
            st.session_state.df_penjualan = df_penjualan
            st.success("✅ Data penjualan berhasil dimuat & diproses.")
        else:
            st.warning("Tidak ada file penjualan ditemukan.")
    if not st.session_state.df_penjualan.empty:
        st.dataframe(st.session_state.df_penjualan.head())
        st.download_button("📥 Unduh Penjualan Gabungan", convert_excel(st.session_state.df_penjualan),
                           "Penjualan_Gabungan.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- PRODUK REFERENSI ---
    st.subheader("🏷️ Produk Referensi")
    produk_files = list_files(folder_produk)
    selected_produk = st.selectbox("Pilih File Produk", options=[None]+produk_files, format_func=lambda x: x['name'] if x else "Pilih file")
    if selected_produk:
        df_produk = read_drive_excel(selected_produk['id'], skiprows=6, usecols=[0,1,2,3])
        df_produk.columns = ['No. Barang','BRAND Barang','Kategori Barang','Nama Barang']
        st.session_state.produk_ref = df_produk
        st.success(f"File produk '{selected_produk['name']}' dimuat.")
        st.dataframe(df_produk.head())

    # --- STOCK ---
    st.subheader("📊 Data Stock")
    stock_files = list_files(folder_stock)
    selected_stock = st.selectbox("Pilih File Stock", options=[None]+stock_files, format_func=lambda x: x['name'] if x else "Pilih file")
    if selected_stock:
        df_stock = read_drive_excel(selected_stock['id'], skiprows=9, header=None)
        st.session_state.df_stock = df_stock
        st.success(f"File stock '{selected_stock['name']}' dimuat.")
        st.dataframe(df_stock.head())

# =====================================================================================
#                              HALAMAN ANALISIS ABC
# =====================================================================================
elif page == "Analisis ABC":
    st.title("📊 Analisis ABC Berdasarkan Penjualan")
    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
        st.warning("⚠️ Harap muat data Penjualan dan Produk terlebih dahulu.")
        st.stop()

    df = st.session_state.df_penjualan.copy()
    produk = st.session_state.produk_ref.copy()

    st.subheader("Pilih Rentang Waktu")
    today = datetime.now().date()
    option = st.selectbox("Rentang:", ["7 Hari", "30 Hari", "90 Hari", "Custom"])
    if option == "7 Hari": start, end = today - timedelta(days=6), today
    elif option == "30 Hari": start, end = today - timedelta(days=29), today
    elif option == "90 Hari": start, end = today - timedelta(days=89), today
    else:
        c1, c2 = st.columns(2)
        start, end = c1.date_input("Awal", today - timedelta(days=30)), c2.date_input("Akhir", today)

    if st.button("🔍 Jalankan Analisis ABC"):
        mask = (df['Tgl Faktur'].dt.date >= start) & (df['Tgl Faktur'].dt.date <= end)
        df_filtered = df.loc[mask].copy()

        # --- Gabung dengan produk referensi ---
        merged = df_filtered.merge(produk, on='No. Barang', how='left')
        grouped = merged.groupby(['City','No. Barang','Nama Barang','BRAND Barang','Kategori Barang'], as_index=False)['Revenue'].sum()

        # --- Fungsi klasifikasi ABC ---
        def classify_abc_dynamic(df_grouped, metric_col='Revenue'):
            results = []
            for city, group in df_grouped.groupby('City'):
                g = group.sort_values(by=metric_col, ascending=False).reset_index(drop=True)
                g['% kontribusi'] = 100 * g[metric_col] / g[metric_col].sum() if g[metric_col].sum() > 0 else 0
                g['% kumulatif'] = g['% kontribusi'].cumsum()
                g['Kategori ABC'] = g['% kumulatif'].apply(lambda x: 'A' if x <= 70 else ('B' if x <= 90 else 'C'))
                results.append(g)
            return pd.concat(results, ignore_index=True)

        result = classify_abc_dynamic(grouped)
        st.session_state.abc_analysis_result = result
        st.success("✅ Analisis ABC selesai.")

    if isinstance(st.session_state.abc_analysis_result, pd.DataFrame) and not st.session_state.abc_analysis_result.empty:
        st.dataframe(st.session_state.abc_analysis_result.head())

        # --- Ringkasan Dashboard ---
        summary = st.session_state.abc_analysis_result.groupby('Kategori ABC')['Revenue'].agg(['count','sum'])
        total_rev = summary['sum'].sum()
        summary['Persentase'] = (summary['sum']/total_rev*100).round(2)
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Distribusi Produk per Kelas")
            st.bar_chart(summary['count'])
        with col2:
            st.subheader("Kontribusi Revenue per Kelas")
            st.bar_chart(summary['Persentase'])

        # --- Unduh hasil ---
        st.download_button("📥 Unduh Hasil Analisis ABC", convert_excel(st.session_state.abc_analysis_result),
                           f"Hasil_ABC_{start}_sd_{end}.xlsx",
                           "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
