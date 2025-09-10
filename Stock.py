import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import math
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io
import os
from datetime import datetime, timedelta

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis Stock & ROP")

# --- SIDEBAR ---
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis Stock dan ROP")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa ROP"),
    help="Pilih halaman untuk ditampilkan."
)
st.sidebar.markdown("---")

# --- Inisialisasi Session State ---
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()
if 'df_stock' not in st.session_state:
    st.session_state.df_stock = pd.DataFrame()
if 'stock_filename' not in st.session_state:
    st.session_state.stock_filename = ""
if 'rop_analysis_result' not in st.session_state:
    st.session_state.rop_analysis_result = None

# --------------------------------Fungsi Umum & Google Drive--------------------------------

# --- KONEKSI GOOGLE DRIVE ---
SCOPES = ['https://www.googleapis.com/auth/drive']
DRIVE_AVAILABLE = False
try:
    if "gcp_service_account" in st.secrets:
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        st.sidebar.success("Terhubung ke Google Drive.", icon="☁️")
    elif os.path.exists("credentials.json"):
        credentials = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES
        )
        st.sidebar.success("Terhubung ke Google Drive.", icon="💻")
    else:
        st.sidebar.error("Kredensial Google Drive tidak ditemukan.")
        credentials = None

    if credentials:
        drive_service = build('drive', 'v3', credentials=credentials)
        folder_penjualan = "1wH9o4dyNfjve9ScJ_DB2TwT0EDsPe9Zf"
        folder_produk = "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv"
        folder_stock = "1PMeH_wvgRUnyiZyZ_wrmKAATX9JyWzq_"
        DRIVE_AVAILABLE = True

except Exception as e:
    st.sidebar.error(f"Gagal terhubung ke Google Drive.")
    st.error(f"Detail Error: {e}")


@st.cache_data(ttl=600)
def list_files_in_folder(_drive_service, folder_id):
    if not DRIVE_AVAILABLE: return []
    query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder'"
    response = _drive_service.files().list(q=query, fields="files(id, name)").execute()
    return response.get('files', [])

@st.cache_data(ttl=600)
def download_file_from_gdrive(file_id):
    request = drive_service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def download_and_read(file_id, file_name, **kwargs):
    fh = download_file_from_gdrive(file_id)
    return pd.read_csv(fh, **kwargs) if file_name.endswith('.csv') else pd.read_excel(fh, **kwargs)

def read_produk_file(file_id):
    fh = download_file_from_gdrive(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1 (2)", skiprows=6, usecols=[0, 1, 2, 3])
    df.columns = ['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']
    return df

# --- FUNGSI MAPPING DATA ---
def map_nama_dept(row):
    dept = str(row.get('Dept.', '')).strip().upper()
    pelanggan = str(row.get('Nama Pelanggan', '')).strip().upper()
    if dept == 'A':
        if pelanggan in ['A - CASH', 'AIRPAY INTERNATIONAL INDONESIA', 'TOKOPEDIA']: return 'A - ITC'
        else: return 'A - RETAIL'
    mapping = {'B': 'B - JKT', 'C': 'C - PUSAT', 'D': 'D - SMG','E': 'E - JOG', 'F': 'F - MLG', 'G': 'G - PROJECT','H': 'H - BALI', 'X': 'X'}
    return mapping.get(dept, 'X')

def map_city(nama_dept):
    if nama_dept in ['A - ITC', 'A - RETAIL', 'C - PUSAT', 'G - PROJECT']: return 'Surabaya'
    elif nama_dept == 'B - JKT': return 'Jakarta'
    elif nama_dept == 'D - SMG': return 'Semarang'
    elif nama_dept == 'E - JOG': return 'Jogja'
    elif nama_dept == 'F - MLG': return 'Malang'
    elif nama_dept == 'H - BALI': return 'Bali'
    else: return 'Others'

# =====================================================================================
#                                       HALAMAN INPUT DATA
# =====================================================================================

if page == "Input Data":
    st.title("📥 Input Data")
    st.markdown("Muat atau muat ulang data yang diperlukan dari Google Drive.")

    if not DRIVE_AVAILABLE:
        st.warning("Tidak dapat melanjutkan karena koneksi ke Google Drive gagal.")
        st.stop()

    st.header("1. Data Penjualan")
    with st.spinner("Mencari file penjualan di Google Drive..."):
        penjualan_files_list = list_files_in_folder(drive_service, folder_penjualan)
    if st.button("Muat / Muat Ulang Data Penjualan"):
        if penjualan_files_list:
            with st.spinner("Menggabungkan semua file penjualan..."):
                df_penjualan = pd.concat([download_and_read(f['id'], f['name']) for f in penjualan_files_list], ignore_index=True)
                st.session_state.df_penjualan = df_penjualan
                st.success("Data penjualan berhasil dimuat ulang.")
        else:
            st.warning("⚠️ Tidak ada file penjualan ditemukan di folder Google Drive.")

    if not st.session_state.df_penjualan.empty:
        df_penjualan = st.session_state.df_penjualan
        st.success(f"✅ Data penjualan telah dimuat ({len(df_penjualan)} baris).")
        df_penjualan['Tgl Faktur'] = pd.to_datetime(df_penjualan['Tgl Faktur'], errors='coerce')
        min_date = df_penjualan['Tgl Faktur'].min()
        max_date = df_penjualan['Tgl Faktur'].max()
        
        if pd.notna(min_date) and pd.notna(max_date):
            num_months = len(df_penjualan['Tgl Faktur'].dt.to_period('M').unique())
            st.info(f"📅 **Rentang Data:** Dari **{min_date.strftime('%d %B %Y')}** hingga **{max_date.strftime('%d %B %Y')}** ({num_months} bulan data).")
        st.dataframe(df_penjualan)

    st.header("2. Produk Referensi")
    with st.spinner("Mencari file produk di Google Drive..."):
        produk_files_list = list_files_in_folder(drive_service, folder_produk)
    selected_produk_file = st.selectbox(
        "Pilih file Produk dari Google Drive:",
        options=[None] + produk_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    if selected_produk_file:
        with st.spinner(f"Memuat file {selected_produk_file['name']}..."):
            st.session_state.produk_ref = read_produk_file(selected_produk_file['id'])
            st.success(f"File produk referensi '{selected_produk_file['name']}' berhasil dimuat.")
    if not st.session_state.produk_ref.empty:
        st.dataframe(st.session_state.produk_ref.head())

# =====================================================================================
#                                    HALAMAN HASIL ANALISA ROP
# =====================================================================================
elif page == "Hasil Analisa ROP":
    st.title("📈 Hasil Analisa Reorder Point (ROP)")

    @st.cache_data(ttl=3600)
    def calculate_rop_vectorized(penjualan_df, produk_df, start_date, end_date):
        # 1. Siapkan kerangka data lengkap
        analysis_start_date = pd.to_datetime(start_date) - pd.DateOffset(days=90)
        date_range_full = pd.date_range(start=analysis_start_date, end=end_date, freq='D')
        
        penjualan_df = penjualan_df[penjualan_df['City'] != 'Others']
        unique_cities = penjualan_df['City'].unique()
        unique_products = produk_df['No. Barang'].unique()

        multi_index = pd.MultiIndex.from_product([date_range_full, unique_cities, unique_products], names=['Date', 'City', 'No. Barang'])
        full_df = pd.DataFrame(index=multi_index).reset_index()

        # 2. Gabungkan dengan data penjualan harian
        daily_sales = penjualan_df.groupby(['Tgl Faktur', 'City', 'No. Barang'])['Kuantitas'].sum().reset_index()
        daily_sales.rename(columns={'Tgl Faktur': 'Date'}, inplace=True)
        
        full_df = pd.merge(full_df, daily_sales, on=['Date', 'City', 'No. Barang'], how='left').fillna(0)
        
        # Urutkan nilai untuk memastikan kalkulasi rolling window benar
        full_df.sort_values(['City', 'No. Barang', 'Date'], inplace=True)

        # 3. Hitung WMA & Std Dev menggunakan .transform untuk menjamin keamanan indeks
        g = full_df.groupby(['City', 'No. Barang'])
        sales_30d = g['Kuantitas'].transform(lambda x: x.rolling(window=30, min_periods=1).sum())
        sales_60d = g['Kuantitas'].transform(lambda x: x.rolling(window=60, min_periods=1).sum())
        sales_90d = g['Kuantitas'].transform(lambda x: x.rolling(window=90, min_periods=1).sum())
        std_dev_90d = g['Kuantitas'].transform(lambda x: x.rolling(window=90, min_periods=1).std())

        full_df['WMA'] = (sales_30d * 0.5) + ((sales_60d - sales_30d) * 0.3) + ((sales_90d - sales_60d) * 0.2)

        # 4. Klasifikasi ABC (hanya untuk menentukan Z-Score)
        avg_sales = full_df.groupby(['City', 'No. Barang'])['WMA'].mean().reset_index()
        
        def classify_abc(df_city):
            df_city = df_city.sort_values(by='WMA', ascending=False)
            total_sales = df_city['WMA'].sum()
            if total_sales > 0:
                df_city['Cumulative_Perc'] = 100 * df_city['WMA'].cumsum() / total_sales
                df_city['Kategori ABC'] = pd.cut(df_city['Cumulative_Perc'], bins=[-1, 70, 90, 101], labels=['A', 'B', 'C'], right=True)
            else:
                df_city['Kategori ABC'] = 'D'
            return df_city[['No. Barang', 'Kategori ABC']]

        abc_classification = avg_sales.groupby('City', group_keys=False).apply(classify_abc)
        full_df = pd.merge(full_df, abc_classification, on=['City', 'No. Barang'], how='left')

        # 5. Hitung Safety Stock, Min Stock, dan ROP
        z_scores = {'A': 1.65, 'B': 1.0, 'C': 0.0, 'D': 0.0}
        full_df['Z_Score'] = full_df['Kategori ABC'].map(z_scores).fillna(0)
        full_df['Safety Stock'] = full_df['Z_Score'] * std_dev_90d.fillna(0) * math.sqrt(0.7)
        full_df['Min Stock'] = full_df['WMA'] * (21/30)
        full_df['ROP'] = full_df['Min Stock'] + full_df['Safety Stock']

        # 6. Finalisasi
        final_df = pd.merge(full_df, produk_df, on='No. Barang', how='left')
        final_df = final_df[final_df['Date'].dt.date >= start_date]
        final_df['ROP'] = final_df['ROP'].round().astype(int)
        
        return final_df[['Date', 'City', 'No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang', 'ROP']]

    # --- UI & Logika Halaman ---
    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
        st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'**.")
        st.stop()

    with st.spinner("Menyiapkan data..."):
        penjualan = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        for df in [penjualan, produk_ref]:
            if 'No. Barang' in df.columns:
                df['No. Barang'] = df['No. Barang'].astype(str).str.strip()
        penjualan['Nama Dept'] = penjualan.apply(map_nama_dept, axis=1)
        penjualan['City'] = penjualan['Nama Dept'].apply(map_city)
        penjualan['Tgl Faktur'] = pd.to_datetime(penjualan['Tgl Faktur'], errors='coerce')
        penjualan.dropna(subset=['Tgl Faktur'], inplace=True)
    
    st.markdown("---")
    st.header("Pilih Rentang Tanggal untuk Perhitungan ROP")
    
    default_end_date = penjualan['Tgl Faktur'].max().date()
    default_start_date = default_end_date - timedelta(days=89)

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Awal", value=default_start_date, key="rop_start")
    end_date = col2.date_input("Tanggal Akhir", value=default_end_date, key="rop_end")

    if st.button("🚀 Jalankan Analisa ROP 🚀"):
        if start_date > end_date:
            st.error("Tanggal Awal tidak boleh melebihi Tanggal Akhir.")
        else:
            with st.spinner(f"Menghitung ROP dari {start_date} hingga {end_date}..."):
                try:
                    rop_result_df = calculate_rop_vectorized(penjualan, produk_ref, start_date, end_date)
                    if not rop_result_df.empty:
                        st.session_state.rop_analysis_result = rop_result_df
                        st.success(f"Analisis ROP berhasil dijalankan!")
                    else:
                        st.error("Tidak ada data yang dihasilkan.")
                except Exception as e:
                    st.error(f"Terjadi kesalahan saat perhitungan: {e}")
                    st.exception(e) # Menampilkan detail error untuk debugging

    if st.session_state.rop_analysis_result is not None:
        result_df = st.session_state.rop_analysis_result.copy()
        
        st.markdown("---"); st.header("🔍 Filter Hasil")
        # ... (UI Filter tidak berubah)
        col_f1, col_f2, col_f3 = st.columns(3)
        selected_kategori = col_f1.multiselect("Kategori:", sorted(result_df['Kategori Barang'].dropna().unique().astype(str)))
        selected_brand = col_f2.multiselect("Brand:", sorted(result_df['BRAND Barang'].dropna().unique().astype(str)))
        selected_products = col_f3.multiselect("Nama Produk:", sorted(result_df['Nama Barang'].dropna().unique().astype(str)))
        
        if selected_kategori: result_df = result_df[result_df['Kategori Barang'].astype(str).isin(selected_kategori)]
        if selected_brand: result_df = result_df[result_df['BRAND Barang'].astype(str).isin(selected_brand)]
        if selected_products: result_df = result_df[result_df['Nama Barang'].astype(str).isin(selected_products)]
        
        st.markdown("---")
        
        st.header("Tabel ROP per Kota")
        for city in sorted(result_df['City'].unique()):
            with st.expander(f"📍 Lihat Hasil ROP untuk Kota: {city}"):
                city_df = result_df[result_df['City'] == city]
                if not city_df.empty:
                    pivot_city = city_df.pivot_table(index=['No. Barang', 'Nama Barang', 'BRAND Barang', 'Kategori Barang'], columns=city_df['Date'].dt.date, values='ROP').fillna(0).astype(int)
                    st.dataframe(pivot_city, use_container_width=True)
                else:
                    st.write("Tidak ada data yang cocok dengan filter.")

        st.header("📊 Tabel Gabungan ROP Seluruh Kota")
        if not result_df.empty:
            with st.spinner("Membuat tabel pivot gabungan..."):
                pivot_all = result_df.pivot_table(index=['No. Barang', 'Nama Barang', 'BRAND Barang', 'Kategori Barang'], columns=result_df['Date'].dt.date, values='ROP', aggfunc='sum').fillna(0).astype(int)
                st.dataframe(pivot_all, use_container_width=True)
        else:
            st.warning("Tidak ada data untuk ditampilkan berdasarkan filter.")
        
        st.header("💾 Unduh Hasil Analisis ROP")

        # --- Fungsi Unduh ---
        st.header("💾 Unduh Hasil Analisis ROP")
        output_rop = BytesIO()
        with pd.ExcelWriter(output_rop, engine='openpyxl') as writer:
            if 'pivot_all' in locals() and not pivot_all.empty:
                pivot_all.to_excel(writer, sheet_name="All_Cities_ROP")
            
            # ... (kode unduh per kota tidak berubah)

        st.download_button(
            "📥 Unduh Hasil Analisis ROP (Excel)",
            data=output_rop.getvalue(),
            file_name=f"Hasil_Analisis_ROP_{start_date}_sd_{end_date}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )


