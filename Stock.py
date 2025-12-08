import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
import math
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaIoBaseUpload
import io
import os
import re
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
# import locale # Dihapus, tidak perlu lagi

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis Stock & ABC")

# --- SIDEBAR ---
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis Stock dan ABC")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa Stock", "Hasil Analisa ABC", "Hasil Analisis Margin"),
    help="Pilih halaman untuk ditampilkan."
)
st.sidebar.markdown("---")

# --- Inisialisasi Session State ---
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.df_produk_ref = pd.DataFrame()
if 'df_stock' not in st.session_state:
    st.session_state.df_stock = pd.DataFrame()
if 'stock_filename' not in st.session_state:
    st.session_state.stock_filename = ""
if 'stock_analysis_result' not in st.session_state:
    st.session_state.stock_analysis_result = None
if 'abc_analysis_result' not in st.session_state:
    st.session_state.abc_analysis_result = None
if 'bulan_columns_stock' not in st.session_state:
    st.session_state.bulan_columns_stock = [] 
if 'df_portal_analyzed' not in st.session_state:
    st.session_state.df_portal_analyzed = pd.DataFrame()


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
        folder_penjualan = "1Okgw8qHVM8HyBwnTUFHbmYkNKqCcswNZ"
        folder_produk = "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv"
        folder_stock = "1PMeH_wvgRUnyiZyZ_wrmKAATX9JyWzq_"
        folder_hasil_analisis = "1TE4a8IegbWDKoVeLPG_oCbuU-qnhd1jE"
        folder_portal = "1GOKVWugUMqN9aOWYCeFlKj-qTr2dA7_u"
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
    if file_name.endswith('.csv'):
        return pd.read_csv(fh, **kwargs)
    else:
        return pd.read_excel(fh, **kwargs)

def read_produk_file(file_id):
    fh = download_file_from_gdrive(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1 (2)", skiprows=6, usecols=[0, 1, 2, 3])
    df.columns = ['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']
    return df

def read_stock_file(file_id):
    fh = download_file_from_gdrive(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1", skiprows=9, header=None)
    header = ['No. Barang', 'Keterangan Barang', 'A - ITC', 'AT - TRANSIT ITC', 'B', 'BT - TRANSIT JKT', 'C', 'C6', 'CT - TRANSIT PUSAT', 'D - SMG', 'DT - TRANSIT SMG', 'E - JOG', 'ET - TRANSIT JOG', 'F - MLG', 'FT - TRANSIT MLG', 'H - BALI', 'HT - TRANSIT BALI', 'X', 'Y - SBY', 'Y3 - Display Y', 'YT - TRANSIT Y']
    df.columns = header[:len(df.columns)]
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
    if nama_dept in ['A - ITC', 'A - RETAIL', 'C - PUSAT', 'G - PROJECT']: return 'SURABAYA'
    elif nama_dept == 'B - JKT': return 'JAKARTA'
    elif nama_dept == 'D - SMG': return 'SEMARANG'
    elif nama_dept == 'E - JOG': return 'JOGJA'
    elif nama_dept == 'F - MLG': return 'MALANG'
    elif nama_dept == 'H - BALI': return 'BALI'
    else: return 'OTHERS'

# --- FUNGSI KONVERSI EXCEL ---
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data


# [DITAMBAHKAN/MODIFIKASI] Metode Log-Benchmark (A, B, C, D, E, F) - Dipindahkan ke Global
def classify_abc_log_benchmark(df_grouped, metric_col):
    df = df_grouped.copy()
    if 'Kategori Barang' not in df.columns:
        st.warning("Kolom 'Kategori Barang' tidak ada untuk metode benchmark.")
        df[f'Kategori ABC (Log-Benchmark - {metric_col.replace("AVG ", "").replace("SO ", "")})'] = 'N/A'
        return df
    
    # Buat nama kolom unik
    kategori_col_name = f'Kategori ABC (Log-Benchmark - {metric_col.replace("AVG ", "").replace("SO ", "")})'
    metric_name_suffix = metric_col.replace('AVG ', '').replace('SO ', '')
    ratio_col_name = 'Ratio Log WMA' if 'WMA' in metric_col else 'Ratio Log Mean'
    log_col_name = 'Log (10)' if 'WMA' in metric_col else 'Log (10) Mean'
    avg_log_col_name = 'Avg Log' if 'WMA' in metric_col else 'Avg Log Mean'
    
    # 1. Hitung Log10(metric) hanya untuk metric > 0, sisanya NaN
    df[log_col_name] = df[metric_col].apply(lambda x: np.log10(x) if x > 0 else np.nan)
    
    # 2. Hitung patokan (rata-rata log) per grup, abaikan NaN
    df[avg_log_col_name] = df.groupby(['City', 'Kategori Barang'])[log_col_name].transform('mean')
    
    # 3. Hitung rasio Log(WMA) / Avg_Log_WMA
    df[ratio_col_name] = df[log_col_name] / df[avg_log_col_name]
    
    # Isi NaN hasil pembagian (misal 0/0 atau log/NaN) dengan 0
    df[ratio_col_name] = df[ratio_col_name].fillna(0)
    
    def apply_category_log(row):
        # 4. Kategori 'F' untuk metric <= 0
        if row[metric_col] <= 0:
            return 'F'
        
        # 5. Kategorikan sisanya (A-E) berdasarkan rasio
        ratio = row[ratio_col_name]
        if ratio > 2:
            return 'A'
        elif ratio > 1.5:
            return 'B'
        elif ratio > 1:
            return 'C'
        elif ratio > 0.5:
            return 'D'
        else:
            return 'E' # Termasuk 0-0.5
    
    # 6. Terapkan kategori
    df[kategori_col_name] = df.apply(apply_category_log, axis=1)
    
    # Hanya kembalikan kolom yang relevan
    cols_to_return = ['City', 'No. Barang', kategori_col_name, ratio_col_name, log_col_name, avg_log_col_name]
    return df


# =====================================================================================
#                                       ROUTING HALAMAN
# =====================================================================================

if page == "Input Data":
    st.title("📥 Input Data")
    st.markdown("Muat atau muat ulang data yang diperlukan dari Google Drive.")

    if not DRIVE_AVAILABLE:
        st.warning("Tidak dapat melanjutkan karena koneksi ke Google Drive gagal. Periksa log di sidebar.")
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
        st.success(f"✅ Data penjualan telah dimuat.")
        st.dataframe(st.session_state.df_penjualan)
        
        excel_data = convert_df_to_excel(st.session_state.df_penjualan)
        st.download_button(
            label="📥 Unduh Data Penjualan Gabungan (Excel)",
            data=excel_data,
            file_name="data_penjualan_gabungan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    st.header("2. Produk Referensi")
    with st.spinner("Mencari file produk di Google Drive..."):
        produk_files_list = list_files_in_folder(drive_service, folder_produk)
    selected_produk_file = st.selectbox(
        "Pilih file Produk dari Google Drive (pilih 1 file):",
        options=[None] + produk_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    if selected_produk_file:
        with st.spinner(f"Memuat file {selected_produk_file['name']}..."):
            st.session_state.produk_ref = read_produk_file(selected_produk_file['id'])
            st.success(f"File produk referensi '{selected_produk_file['name']}' berhasil dimuat.")
    if not st.session_state.produk_ref.empty:
        st.dataframe(st.session_state.produk_ref.head())

    st.header("3. Data Stock")
    with st.spinner("Mencari file stock di Google Drive..."):
        stock_files_list = list_files_in_folder(drive_service, folder_stock)
    selected_stock_file = st.selectbox(
        "Pilih file Stock dari Google Drive (pilih 1 file):",
        options=[None] + stock_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    if selected_stock_file:
        with st.spinner(f"Memuat file {selected_stock_file['name']}..."):
            st.session_state.df_stock = read_stock_file(selected_stock_file['id'])
            st.session_state.stock_filename = selected_stock_file['name']
            st.success(f"File stock '{selected_stock_file['name']}' berhasil dimuat.")
    if not st.session_state.df_stock.empty:
        st.dataframe(st.session_state.df_stock.head())
    
    # [DITAMBAHKAN] Input Data Portal
    st.header("4. Data Portal (Margin)")
    with st.spinner("Mencari file portal di Google Drive..."):
        portal_files_list = list_files_in_folder(drive_service, folder_portal)
    
    selected_portal_file = st.selectbox(
        "Pilih file Portal dari Google Drive (pilih 1 file):",
        options=[None] + portal_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    
    # Tombol ini hanya untuk memuat, analisis akan di halaman terpisah
    if st.button("Muat Data Portal"):
        if selected_portal_file:
            with st.spinner(f"Memuat file {selected_portal_file['name']}..."):
                # Gunakan download_and_read yang fleksibel
                df_portal = download_and_read(selected_portal_file['id'], selected_portal_file['name'])
                st.session_state.df_portal = df_portal # Simpan data mentah
                st.session_state.df_portal_analyzed = pd.DataFrame() # Reset hasil analisis
                st.success(f"File portal '{selected_portal_file['name']}' berhasil dimuat.")
                st.dataframe(st.session_state.df_portal.head())
        else:
            st.warning("⚠️ Harap pilih file portal terlebih dahulu.")
            
    if 'df_portal' in st.session_state and not st.session_state.df_portal.empty:
        st.success("✅ Data portal telah dimuat.")


elif page == "Hasil Analisa Stock":
    st.title("📈 Hasil Analisa Stock")

    # --- FUNGSI-FUNGSI SPESIFIK ANALISA STOCK ---
    
    def calculate_daily_wma(group, end_date):
        end_date = pd.to_datetime(end_date)
        range1_start = end_date - pd.DateOffset(days=29)
        range2_start = end_date - pd.DateOffset(days=59); range2_end = end_date - pd.DateOffset(days=30)
        range3_start = end_date - pd.DateOffset(days=89); range3_end = end_date - pd.DateOffset(days=60)
        sales_last_30_days = group[(group['Tgl Faktur'] >= range1_start) & (group['Tgl Faktur'] <= end_date)]['Kuantitas'].sum()
        sales_31_to_60_days = group[(group['Tgl Faktur'] >= range2_start) & (group['Tgl Faktur'] <= range2_end)]['Kuantitas'].sum()
        sales_61_to_90_days = group[(group['Tgl Faktur'] >= range3_start) & (group['Tgl Faktur'] <= range3_end)]['Kuantitas'].sum()
        wma = (sales_last_30_days * 0.5) + (sales_31_to_60_days * 0.3) + (sales_61_to_90_days * 0.2)
        return wma

    # [MODIFIKASI] Metode Persentase (A, B, C, D, E)
    def classify_abc(df_group):
        # [PERBAIKAN] Mengganti 'Total Kuantitas' menjadi 'SO Total'
        group = df_group.sort_values(by='SO Total', ascending=False).reset_index(drop=True)
        terjual = group[group['SO Total'] > 0].copy() 
        tidak_terjual = group[group['SO Total'] <= 0].copy() 
        total_kuantitas = terjual['SO Total'].sum() # [PERBAIKAN]
        
        if total_kuantitas > 0:
            terjual['% kontribusi'] = 100 * terjual['SO Total'] / total_kuantitas # [PERBAIKAN]
            terjual['% Kumulatif'] = terjual['% kontribusi'].cumsum()
            # [PERUBAHAN DARI USER] A=50, B=75, C=90, D=100
            terjual['Kategori ABC'] = terjual['% Kumulatif'].apply(lambda x: 'A' if x <= 50 else ('B' if x <= 75 else ('C' if x <= 90 else 'D')))
        else:
            terjual['% kontribusi'] = 0
            terjual['% Kumulatif'] = 0
            terjual['Kategori ABC'] = 'D' # Jika total = 0, semua 'D' (bukan 'E' krn E khusus 0)
        
        tidak_terjual['% kontribusi'] = 0
        tidak_terjual['% Kumulatif'] = 100
        # [MODIFIKASI] Kuantitas 0 = E
        tidak_terjual['Kategori ABC'] = 'E' 
        
        result_df = pd.concat([terjual, tidak_terjual], ignore_index=True)
        # [MODIFIKASI] Hapus kolom %
        cols_to_drop = ['% kontribusi', '% Kumulatif']
        result_df.drop([col for col in cols_to_drop if col in result_df.columns], axis=1, inplace=True)
        return result_df

    # [DITAMBAHKAN] Highlight untuk Persen A-E
    def highlight_kategori_abc_persen(val): # A, B, C, D, E
        warna = {'A': '#cce5ff', 'B': '#d4edda', 'C': '#fff3cd', 'D': '#f8d7da', 'E': '#e9ecef'}
        return f'background-color: {warna.get(val, "")}'

    # [DITAMBAHKAN] Highlight untuk Log A-F
    def highlight_kategori_abc_log(val): # A, B, C, D, E, F
        warna = {
            'A': '#cce5ff', 'B': '#d4edda', 'C': '#fff3cd', 
            'D': '#f8d7da', 'E': '#e9ecef', 'F': '#6c757d'
        }
        color = warna.get(val, "")
        text_color = "white" if val == 'F' else "black"
        return f'background-color: {color}; color: {text_color}'


    def calculate_min_stock(avg_wma):
        # [PERUBAHAN DARI USER]
        return avg_wma * (30/30)

    # [MODIFIKASI] Logika Status Stock
    def get_status_stock(row):
        kategori_log = row['Kategori ABC (Log-Benchmark - WMA)'] 
        
        # [MODIFIKASI] Cek F (kuantitas 0)
        if kategori_log == 'F': 
            return 'Overstock E' if row['Stock Cabang'] > 2 else 'Balance'
        
        # [MODIFIKASI] Kategori A, B, C, D, E (semua yg terjual) pakai logika Min/Max
        if row['Stock Cabang'] > row['Max Stock']: return 'Overstock'
        # [MODIFIKASI] Gunakan Min Stock, bukan ROP
        if row['Stock Cabang'] < row['Min Stock']: return 'Understock' 
        if row['Stock Cabang'] >= row['Min Stock']: return 'Balance' 
        return '-'

    def highlight_status_stock(val):
        colors = {'Understock': '#fff3cd', 'Balance': '#d4edda', 'Overstock': '#ffd6a5', 'Overstock E': '#f5c6cb', 'Overstock D': '#f5c6cb'} # Overstock D dipertahankan jika E gagal
        return f'background-color: {colors.get(val, "")}'

    # [MODIFIKASI] Logika Max Stock A-E
    def calculate_max_stock(avg_wma, category):
        # [PERUBAHAN DARI USER] A=2, B=1.5, C=1, D=1, E=0
        multiplier = {'A': 2, 'B': 1.5, 'C': 1, 'D': 1, 'E': 0} 
        return avg_wma * multiplier.get(category, 0)

    # [DIHAPUS] calculate_rop
    
    def hitung_po_cabang_baru(stock_surabaya, stock_cabang, stock_total, suggest_po_all, so_cabang, add_stock_cabang):
        try:
            if stock_surabaya < stock_cabang: return 0
            # [PERUBAHAN DARI USER] kebutuhan 30 hari
            kebutuhan_30_hari = (so_cabang / 30) * 30
            kondisi_3_terpenuhi = stock_cabang < kebutuhan_30_hari
            kondisi_2_terpenuhi = stock_total < suggest_po_all
            if kondisi_2_terpenuhi and kondisi_3_terpenuhi:
                if stock_total > 0:
                    ideal_po = ((stock_cabang + add_stock_cabang) / stock_total * stock_surabaya) - stock_cabang
                    return max(0, round(ideal_po))
                else: return 0
            else: return round(add_stock_cabang)
        except (ZeroDivisionError, TypeError): return 0

    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty or st.session_state.df_stock.empty:
        st.warning("⚠️ Harap muat semua file di halaman **'Input Data'** terlebih dahulu untuk melihat hasil analisis.")
        st.stop()

    penjualan = st.session_state.df_penjualan.copy()
    produk_ref = st.session_state.produk_ref.copy()
    df_stock = st.session_state.df_stock.copy()

    for df in [penjualan, produk_ref, df_stock]:
        if 'No. Barang' in df.columns:
            df['No. Barang'] = df['No. Barang'].astype(str).str.strip()

    # [DITAMBAHKAN] PREPROCESSING: DETEKSI DAN HAPUS DUPLIKAT
    if 'No. Faktur' in penjualan.columns and 'No. Barang' in penjualan.columns:
        # Konversi No. Faktur ke string dan bersihkan
        penjualan['No. Faktur'] = penjualan['No. Faktur'].astype(str).str.strip()
        
        # Buat kolom kunci duplikat
        penjualan['Faktur + Barang'] = penjualan['No. Faktur'] + penjualan['No. Barang']
        
        # Deteksi duplikat (baris yang duplikat)
        duplicates = penjualan[penjualan.duplicated(subset=['Faktur + Barang'], keep=False)].sort_values(by=['Faktur + Barang', 'Tgl Faktur'])
        
        # Hapus duplikat (pertahankan baris pertama)
        penjualan.drop_duplicates(subset=['Faktur + Barang'], keep='first', inplace=True)
        
        # --- FIX: SIMPAN DATA BERSIH KEMBALI KE SESSION STATE ---
        st.session_state.df_penjualan = penjualan.copy()
        
        if not duplicates.empty:
            # Identifikasi baris yang dihapus (duplikat yang bukan yang pertama)
            deleted_duplicates = duplicates[~duplicates.index.isin(penjualan.index)]
            st.warning(f"⚠️ Ditemukan dan dihapus {len(deleted_duplicates)} baris duplikat berdasarkan 'Faktur + Barang'.")
            with st.expander("Lihat Detail Duplikat yang Dihapus"):
                st.dataframe(deleted_duplicates)
        else:
             st.info("✅ Tidak ada duplikat 'Faktur + Barang' yang ditemukan.")
    # [AKHIR DETEKSI DUPLIKAT]


    penjualan.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')
    penjualan['Nama Dept'] = penjualan.apply(map_nama_dept, axis=1)
    penjualan['City'] = penjualan['Nama Dept'].apply(map_city)
    produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang'}, inplace=True, errors='ignore')
    penjualan['Tgl Faktur'] = pd.to_datetime(penjualan['Tgl Faktur'], errors='coerce')
    
    with st.expander("Lihat Data Penjualan Setelah Preprocessing"):
        # [PERUBAHAN TAMPILAN] Tampilkan kolom kunci untuk verifikasi data duplikat
        preview_cols = ['No. Faktur', 'Tgl Faktur', 'Nama Pelanggan', 'No. Barang', 'Faktur + Barang', 'Kuantitas']
        preview_cols_filtered = [col for col in preview_cols if col in penjualan.columns]
        
        st.dataframe(penjualan[preview_cols_filtered].head(20), use_container_width=True) # Display top 20 rows
        
        excel_cleaned_penjualan = convert_df_to_excel(penjualan)
        st.download_button(
            label="📥 Unduh Data Penjualan Bersih (Excel)",
            data=excel_cleaned_penjualan,
            file_name="data_penjualan_bersih.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    st.markdown("---")

    default_end_date = penjualan['Tgl Faktur'].dropna().max().date()
    if st.session_state.stock_filename:
        match = re.search(r'(\d{8})', st.session_state.stock_filename)
        if match:
            try: default_end_date = datetime.strptime(match.group(1), '%d%m%Y').date()
            except ValueError: pass
    default_start_date = default_end_date - timedelta(days=89)

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Awal", value=default_start_date, key="stock_start")
    end_date = col2.date_input("Tanggal Akhir", value=default_end_date, key="stock_end")

    if st.button("Jalankan Analisa Stock"):
        with st.spinner("Melakukan perhitungan analisis stok..."):
            
            # [MODIFIKASI] Kamus bulan manual (tidak perlu locale)
            bulan_indonesia = {
                1: 'Januari', 2: 'Februari', 3: 'Maret', 4: 'April', 5: 'Mei', 6: 'Juni',
                7: 'Juli', 8: 'Agustus', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Desember'
            }
            
            # [DIHAPUS] locale.setlocale() sudah tidak diperlukan lagi
            
            end_date_dt = pd.to_datetime(end_date)
            wma_start_date = end_date_dt - pd.DateOffset(days=89)
            penjualan_for_wma = penjualan[(penjualan['Tgl Faktur'] >= wma_start_date) & (penjualan['Tgl Faktur'] <= end_date_dt)]
            
            if penjualan_for_wma.empty:
                st.error("Tidak ada data penjualan dalam rentang 90 hari terakhir dari tanggal akhir yang dipilih.")
                st.session_state.stock_analysis_result = None
            else:
                range1_start = end_date_dt - pd.DateOffset(days=29); range1_end = end_date_dt
                range2_start = end_date_dt - pd.DateOffset(days=59); range2_end = end_date_dt - pd.DateOffset(days=30)
                range3_start = end_date_dt - pd.DateOffset(days=89); range3_end = end_date_dt - pd.DateOffset(days=60)

                sales_m1 = penjualan_for_wma[penjualan_for_wma['Tgl Faktur'].between(range1_start, range1_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 1')
                sales_m2 = penjualan_for_wma[penjualan_for_wma['Tgl Faktur'].between(range2_start, range2_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 2')
                sales_m3 = penjualan_for_wma[penjualan_for_wma['Tgl Faktur'].between(range3_start, range3_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 3')
                
                total_sales_90d = penjualan_for_wma.groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index()
                total_sales_90d['AVG Mean'] = total_sales_90d['Kuantitas'] / 3
                total_sales_90d.drop('Kuantitas', axis=1, inplace=True)

                wma_grouped = penjualan_for_wma.groupby(['City', 'No. Barang']).apply(calculate_daily_wma, end_date=end_date).reset_index(name='AVG WMA')
                barang_list = produk_ref[['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']].drop_duplicates()
                city_list = penjualan['City'].unique()
                kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                full_data = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                
                full_data = pd.merge(full_data, wma_grouped, on=['City', 'No. Barang'], how='left')
                full_data = pd.merge(full_data, sales_m1, on=['City', 'No. Barang'], how='left')
                full_data = pd.merge(full_data, sales_m2, on=['City', 'No. Barang'], how='left')
                full_data = pd.merge(full_data, sales_m3, on=['City', 'No. Barang'], how='left')
                full_data = pd.merge(full_data, total_sales_90d, on=['City', 'No. Barang'], how='left')
                
                # [MODIFIKASI] Hitung data bulanan
                penjualan_for_wma['Bulan'] = penjualan_for_wma['Tgl Faktur'].dt.to_period('M')
                monthly_sales = penjualan_for_wma.groupby(['City', 'No. Barang', 'Bulan'])['Kuantitas'].sum().unstack(fill_value=0).reset_index()
                full_data = pd.merge(full_data, monthly_sales, on=['City', 'No. Barang'], how='left')
                
                full_data.fillna(0, inplace=True)

                # [MODIFIKASI] Rename kolom bulan menggunakan kamus
                bulan_columns_period = [col for col in full_data.columns if isinstance(col, pd.Period)]
                bulan_columns_period.sort() # Urutkan
                # Menggunakan kamus 'bulan_indonesia'
                rename_map = {col: f"{bulan_indonesia[col.month]} {col.year}" for col in bulan_columns_period}
                full_data.rename(columns=rename_map, inplace=True)
                bulan_columns_renamed = [rename_map[col] for col in bulan_columns_period] # Simpan nama baru
                
                # [REVISI NAMA] Renaming utama
                full_data.rename(columns={'AVG WMA': 'SO WMA', 'AVG Mean': 'SO Mean', 'Total Kuantitas': 'SO Total'}, inplace=True)
                
                full_data['SO Total'] = full_data['SO WMA']
                
                # [MODIFIKASI] Jalankan ABC Persen (A-E)
                final_result = full_data.groupby('City', group_keys=False).apply(classify_abc).reset_index(drop=True)
                # [MODIFIKASI] Rename kolom ABC Persen
                final_result.rename(columns={'Kategori ABC': 'Kategori ABC (Persen - WMA)'}, inplace=True)
                
                # [DITAMBAHKAN] Jalankan ABC Log-Benchmark (A-F)
                # Ambil kolom yang sudah ada untuk merge, agar final_result tetap di update.
                log_df = classify_abc_log_benchmark(final_result.copy(), metric_col='SO WMA')
                final_result = pd.merge(
                    final_result, 
                    log_df[['City', 'No. Barang', 'Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10)', 'Avg Log']], 
                    on=['City', 'No. Barang'], 
                    how='left'
                )

                # [DIHAPUS] Perhitungan Safety Stock
                
                # [REVISI] Menggunakan SO WMA
                final_result['Min Stock'] = final_result['SO WMA'].apply(calculate_min_stock)
                
                # [DIHAPUS] Perhitungan ROP
                
                # [MODIFIKASI] Perhitungan Max Stock (pakai Log-Benchmark)
                final_result['Max Stock'] = final_result.apply(
                    lambda row: calculate_max_stock(row['SO WMA'], row['Kategori ABC (Log-Benchmark - WMA)']), 
                    axis=1
                )
                
                stock_df_raw = df_stock.rename(columns=lambda x: x.strip())
                stok_columns = [col for col in stock_df_raw.columns if col not in ['No. Barang', 'Keterangan Barang']]
                stock_melted_list = []
                city_prefix_map = {'SURABAYA': ['A - ITC', 'AT - TRANSIT ITC', 'C', 'C6', 'CT - TRANSIT PUSAT', 'Y - SBY', 'Y3 - Display Y', 'YT - TRANSIT Y'],'JAKARTA': ['B', 'BT - TRANSIT JKT'],'SEMARANG': ['D - SMG', 'DT - TRANSIT SMG'],'JOGJA': ['E - JOG', 'ET - TRANSIT JOG'],'MALANG': ['F - MLG', 'FT - TRANSIT MLG'],'BALI': ['H - BALI', 'HT - TRANSIT BALI']}
                for city_name, prefixes in city_prefix_map.items():
                    city_cols = [col for col in stok_columns if any(col.startswith(p) for p in prefixes)]
                    if not city_cols: continue
                    city_stock = stock_df_raw[['No. Barang'] + city_cols].copy()
                    city_stock['Stock'] = city_stock[city_cols].sum(axis=1)
                    city_stock['City'] = city_name
                    stock_melted_list.append(city_stock[['No. Barang', 'City', 'Stock']])
                stock_melted = pd.concat(stock_melted_list, ignore_index=True)
                
                final_result = pd.merge(final_result, stock_melted, on=['City', 'No. Barang'], how='left').rename(columns={'Stock': 'Stock Cabang'})
                final_result['Stock Cabang'].fillna(0, inplace=True)
                final_result['Status Stock'] = final_result.apply(get_status_stock, axis=1)
                
                # [MODIFIKASI] Perhitungan Add Stock (pakai Min Stock)
                final_result['Add Stock'] = final_result.apply(lambda row: max(0, row['Min Stock'] - row['Stock Cabang']), axis=1)
                
                stock_surabaya = stock_melted[stock_melted['City'] == 'SURABAYA'][['No. Barang', 'Stock']].rename(columns={'Stock': 'Stock Surabaya'})
                stock_total = stock_melted.groupby('No. Barang')['Stock'].sum().reset_index().rename(columns={'Stock': 'Stock Total'})
                suggest_po_all_df = final_result.groupby('No. Barang')['Add Stock'].sum().reset_index(name='Suggest PO All')
                
                final_result = final_result.merge(stock_surabaya, on='No. Barang', how='left')
                final_result = final_result.merge(stock_total, on='No. Barang', how='left')
                final_result = final_result.merge(suggest_po_all_df, on='No. Barang', how='left')
                final_result.fillna(0, inplace=True)
                
                # [REVISI] Menggunakan SO WMA
                final_result['Suggested PO'] = final_result.apply(lambda row: hitung_po_cabang_baru(stock_surabaya=row['Stock Surabaya'], stock_cabang=row['Stock Cabang'], stock_total=row['Stock Total'], suggest_po_all=row['Suggest PO All'], so_cabang=row['SO WMA'], add_stock_cabang=row['Add Stock']), axis=1)
                
                # [REVISI] numeric_cols untuk int
                numeric_cols = ['Stock Cabang', 'Min Stock', 'Max Stock', 'Add Stock', 'Suggest PO All', 'Suggested PO', 'Stock Surabaya', 'Stock Total', 'SO WMA', 'SO Mean', 'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3']
                numeric_cols.extend(bulan_columns_renamed)

                for col in numeric_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(0).astype(int)
                
                # [DITAMBAHKAN] Bulatkan kolom float
                float_cols = [
                    'Log (10)', 'Avg Log', 'Ratio Log WMA'
                ]
                for col in float_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(2)
                
                st.session_state.stock_analysis_result = final_result.copy()
                # [DITAMBAHKAN] Simpan nama kolom bulan
                st.session_state.bulan_columns_stock = bulan_columns_renamed 
                st.success("Analisis Stok berhasil dijalankan!")

    if st.session_state.stock_analysis_result is not None:
        final_result_to_filter = st.session_state.stock_analysis_result.copy()
        final_result_to_filter = final_result_to_filter[final_result_to_filter['City'] != 'OTHERS']
        # [DITAMBAHKAN] Ambil nama kolom bulan dari session state
        bulan_cols = st.session_state.get('bulan_columns_stock', [])
        
        st.markdown("---")
        st.header("Filter Produk (Berlaku untuk Semua Tabel)")
        col_f1, col_f2, col_f3 = st.columns(3)
        kategori_options = sorted(final_result_to_filter['Kategori Barang'].dropna().unique().astype(str))
        selected_kategori = col_f1.multiselect("Kategori:", kategori_options)
        brand_options = sorted(final_result_to_filter['BRAND Barang'].dropna().unique().astype(str))
        selected_brand = col_f2.multiselect("Brand:", brand_options)
        product_options = sorted(final_result_to_filter['Nama Barang'].dropna().unique().astype(str))
        selected_products = col_f3.multiselect("Nama Produk:", product_options)
        if selected_kategori: final_result_to_filter = final_result_to_filter[final_result_to_filter['Kategori Barang'].astype(str).isin(selected_kategori)]
        if selected_brand: final_result_to_filter = final_result_to_filter[final_result_to_filter['BRAND Barang'].astype(str).isin(selected_brand)]
        if selected_products: final_result_to_filter = final_result_to_filter[final_result_to_filter['Nama Barang'].astype(str).isin(selected_products)]
        final_result_display = final_result_to_filter.copy()
        
        st.header("Filter Hasil (Hanya untuk Tabel per Kota)")
        # [PERUBAHAN] Kembali ke 3 kolom filter
        col_h1, col_h2, col_h3 = st.columns(3)
        
        # [DIHAPUS FILTER ABC PERSEN]
        # abc_persen_options = sorted(final_result_display['Kategori ABC (Persen - WMA)'].dropna().unique().astype(str))
        # selected_abc_persen = col_h1.multiselect("Kategori ABC (Persen):", abc_persen_options)
        
        # [REVISI] Pindahkan ABC Log ke col_h1
        abc_log_options = sorted(final_result_display['Kategori ABC (Log-Benchmark - WMA)'].dropna().unique().astype(str))
        selected_abc_log = col_h1.multiselect("Kategori ABC (Log):", abc_log_options) # Pindah ke col h1
        
        # [PERUBAHAN] Pindahkan Status Stock ke col_h2
        status_options = sorted(final_result_display['Status Stock'].dropna().unique().astype(str))
        selected_status = col_h2.multiselect("Status Stock:", status_options) # Pindah ke col h2
        
        # [PENTING] Filter data sebelum display
        city_df = final_result_display.copy()
        
        # Filter Log
        if selected_abc_log: city_df = city_df[city_df['Kategori ABC (Log-Benchmark - WMA)'].isin(selected_abc_log)]
        # Filter Status
        if selected_status: city_df = city_df[city_df['Status Stock'].isin(selected_status)]
        
        # [PENTING] Hapus kolom ABC Persen sebelum display (jika ada)
        if 'Kategori ABC (Persen - WMA)' in final_result_display.columns:
            final_result_display.drop(columns=['Kategori ABC (Persen - WMA)'], inplace=True, errors='ignore')
            
        st.markdown("---")
        tab1, tab2 = st.tabs(["Hasil Tabel", "Dashboard"])

        with tab1:
            header_style = {'selector': 'th', 'props': [('background-color', '#0068c9'), ('color', 'white'), ('text-align', 'center')]}
            st.header("Hasil Analisis Stok per Kota")

            for city in sorted(final_result_display['City'].unique()):
                with st.expander(f"📍 Lihat Hasil Stok untuk Kota: {city}"):
                    current_city_df = city_df[city_df['City'] == city].copy()
                    
                    if current_city_df.empty:
                        st.write("Tidak ada data yang cocok dengan filter yang dipilih.")
                        continue
                    
                    # [REVISI] Tentukan urutan kolom sesuai permintaan (Hapus Persen, Ubah Nama)
                    keys_base = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                    metric_order_kota = (
                        bulan_cols + # [URUTAN BARU] Kolom bulan dulu
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10)', 'Avg Log'] + # [REVISI NAMA & URUTAN]
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    
                    # Gabungkan dan pastikan hanya kolom yang ada di city_df
                    display_cols_kota = keys_base + [col for col in metric_order_kota if col in current_city_df.columns]
                    
                    # Terapkan urutan kolom
                    city_df_display = current_city_df[display_cols_kota]
                    
                    # [REVISI] Buat format dict untuk tabel kota secara dinamis
                    format_dict_kota = {}
                    keys_to_skip = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                    for col_name in city_df_display.columns: # Gunakan city_df_display
                        if pd.api.types.is_numeric_dtype(city_df_display[col_name]):
                            if col_name in keys_to_skip:
                                continue
                            
                            # [DITAMBAHKAN] Format untuk log/ratio
                            if "Ratio" in col_name or "Log" in col_name:
                                format_dict_kota[col_name] = '{:.2f}'
                            else:
                                format_dict_kota[col_name] = '{:.0f}'

                    # [MODIFIKASI] Terapkan 2 highlight (Log dan Status)
                    st.dataframe(
                        city_df_display.style.format(format_dict_kota, na_rep='-') # Gunakan city_df_display
                                     # [DIHAPUS] ABC Persen Highlight
                                     .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - WMA)']) # [DITAMBAHKAN]
                                     .apply(lambda x: x.map(highlight_status_stock), subset=['Status Stock'])
                                     .set_table_styles([header_style]), 
                        use_container_width=True
                    )
            
            st.header("📊 Tabel Gabungan Seluruh Kota (Stock)")
            with st.spinner("Membuat tabel pivot gabungan untuk stok..."):
                if final_result_display.empty:
                    st.warning("Tidak ada data untuk ditampilkan pada tabel gabungan berdasarkan filter produk yang dipilih.")
                else:
                    keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                    
                    # [REVISI] Daftar kolom pivot sesuai urutan (Hapus Persen ABC)
                    pivot_cols = (
                        bulan_cols + 
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10)', 'Avg Log'] + # [REVISI NAMA & URUTAN]
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    
                    # Pastikan hanya kolom yang ada di df yang dipivot
                    pivot_cols_existing = [col for col in pivot_cols if col in final_result_display.columns]
                    
                    pivot_result = final_result_display.pivot_table(index=keys, columns='City', values=pivot_cols_existing, aggfunc='first')
                    pivot_result.columns = [f"{level1}_{level0}" for level0, level1 in pivot_result.columns]
                    pivot_result.reset_index(inplace=True)
                    cities = sorted(final_result_display['City'].unique())
                    
                    # [REVISI] Urutan metrik sesuai urutan (Hapus Persen ABC)
                    metric_order = (
                        bulan_cols + 
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10)', 'Avg Log'] + # [REVISI NAMA & URUTAN]
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    
                    ordered_city_cols = [f"{city}_{metric}" for city in cities for metric in metric_order]
                    existing_ordered_cols = [col for col in ordered_city_cols if col in pivot_result.columns]
                    
                    total_agg = final_result_display.groupby(keys).agg(
                        All_Stock=('Stock Cabang', 'sum'), 
                        All_SO=('SO WMA', 'sum'), # [REVISI NAMA]
                        All_Suggested_PO=('Suggested PO', 'sum')
                    ).reset_index()
                    
                    # [MODIFIKASI] Gunakan Log-Benchmark Total
                    all_sales_for_abc = total_agg.copy()
                    all_sales_for_abc.rename(columns={'All_SO': 'Total Kuantitas'}, inplace=True)
                    # Ganti ABC Persen Total dengan Log-Benchmark Total
                    all_classified = classify_abc_log_benchmark(all_sales_for_abc, metric_col='Total Kuantitas') 
                    all_classified.rename(columns={'Kategori ABC (Log-Benchmark - Total Kuantitas)': 'All_Kategori ABC All'}, inplace=True)
                    
                    total_agg['All_Restock 1 Bulan'] = np.where(total_agg['All_Stock'] < total_agg['All_SO'], 'PO', 'NO')
                    
                    pivot_result = pd.merge(pivot_result, total_agg, on=keys, how='left')
                    pivot_result = pd.merge(pivot_result, all_classified[keys + ['All_Kategori ABC All']], on=keys, how='left')
                    
                    final_summary_cols = ['All_Stock', 'All_SO', 'All_Suggested_PO', 'All_Kategori ABC All', 'All_Restock 1 Bulan']
                    final_display_cols = keys + existing_ordered_cols + final_summary_cols
                    
                    
                    # =================================================================
                    # [PERBAIKAN] Mengganti Styler dengan column_config
                    # =================================================================
                    
                    # [REVISI] Buat DataFrame yang akan ditampilkan terlebih dahulu
                    df_to_style = pivot_result[final_display_cols].copy() # Gunakan .copy()
                    
                    # 1. Tentukan kolom numerik vs. object/string
                    numeric_cols_to_format = []
                    float_cols_to_format = [] # [DITAMBAHKAN]
                    object_cols_to_format = []
                    
                    for col in df_to_style.columns:
                        if col not in keys: # 'keys' adalah index
                            # [DITAMBAHKAN] Kondisi untuk log/ratio
                            if "Ratio" in col or "Log" in col:
                                float_cols_to_format.append(col)
                            elif pd.api.types.is_numeric_dtype(df_to_style[col]):
                                numeric_cols_to_format.append(col)
                            else:
                                object_cols_to_format.append(col)
                                
                    # 2. Isi NaN di DataFrame SEBELUM styling
                    # Isi NaN numerik dengan 0
                    df_to_style[numeric_cols_to_format] = df_to_style[numeric_cols_to_format].fillna(0)
                    df_to_style[float_cols_to_format] = df_to_style[float_cols_to_format].fillna(0) # [DITAMBAHKAN]
                    # Isi NaN string/object with '-'
                    df_to_style[object_cols_to_format] = df_to_style[object_cols_to_format].fillna('-')
                    
                    # 3. [REVISI] Buat column_config untuk st.dataframe
                    column_config_stock = {}
                    for col in numeric_cols_to_format:
                        column_config_stock[col] = st.column_config.NumberColumn(format="%.0f")
                    for col in float_cols_to_format: # [DITAMBAHKAN]
                        column_config_stock[col] = st.column_config.NumberColumn(format="%.2f")

                    # Tampilkan DataFrame (bukan Styler) dengan format baru
                    st.dataframe(
                        df_to_style,  # <-- Gunakan DataFrame-nya, bukan Styler
                        column_config=column_config_stock, # <-- Gunakan column_config
                        use_container_width=True
                    )
                    # =================================================================
                    # [AKHIR PERBAIKAN]
                    # =================================================================


            st.header("💾 Unduh Hasil Analisis Stock")
            output_stock = BytesIO()
            with pd.ExcelWriter(output_stock, engine='openpyxl') as writer:
                if 'df_to_style' in locals() and not df_to_style.empty:
                    # [REVISI] Gunakan df_to_style yang sudah bersih untuk di-download
                    df_to_style.to_excel(writer, sheet_name="All Cities Pivot", index=False)
                final_result_display.to_excel(writer, sheet_name="Filtered Data", index=False)

            st.download_button(
                "📥 Unduh Hasil Analisis Stock (Excel)",
                data=output_stock.getvalue(),
                file_name=f"Hasil_Analisis_Stock_{start_date}_sd_{end_date}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        with tab2:
            st.header("📈 Dashboard Analisis Stock")
            if not final_result_display.empty:
                total_understock = final_result_display[final_result_display['Status Stock'] == 'Understock'].shape[0]
                total_overstock = final_result_display[final_result_display['Status Stock'].str.contains('Overstock', na=False)].shape[0]
                col1, col2 = st.columns(2)
                col1.metric("Total Produk Understock", f"{total_understock} SKU")
                col2.metric("Total Produk Overstock", f"{total_overstock} SKU")
                st.markdown("---")
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    # [REVISI] Dashboard sekarang menunjukkan Log-Benchmark
                    st.subheader("Distribusi Kategori ABC (Log-Benchmark)")
                    abc_counts = final_result_display['Kategori ABC (Log-Benchmark - WMA)'].value_counts()
                    st.bar_chart(abc_counts)
                with col_chart2:
                    st.subheader("Distribusi Status Stok")
                    status_counts = final_result_display['Status Stock'].value_counts()
                    st.bar_chart(status_counts)
                st.markdown("---")
                col_top1, col_top2 = st.columns(2)
                with col_top1:
                    st.subheader("Top 5 Produk Paling Understock")
                    top_understock = final_result_display[final_result_display['Status Stock'] == 'Understock'].sort_values(by='Add Stock', ascending=False).head(5)
                    # [MODIFIKASI] Ganti ROP dengan Min Stock
                    st.dataframe(top_understock[['Nama Barang', 'City', 'Add Stock', 'Stock Cabang', 'Min Stock']], use_container_width=True)
                with col_top2:
                    st.subheader("Top 5 Produk Paling Overstock")
                    overstock_df = final_result_display[final_result_display['Status Stock'].str.contains('Overstock', na=False)].copy()
                    overstock_df['Kelebihan Stok'] = overstock_df['Stock Cabang'] - overstock_df['Max Stock']
                    top_overstock = overstock_df.sort_values(by='Kelebihan Stok', ascending=False).head(5)
                    st.dataframe(top_overstock[['Nama Barang', 'City', 'Kelebihan Stok', 'Stock Cabang', 'Max Stock']], use_container_width=True)
            else:
                st.info("Tidak ada data untuk ditampilkan di dashboard. Sesuaikan filter Anda.")

elif page == "Hasil Analisa ABC":
    st.title("📊 Analisis ABC Berdasarkan Metrik Penjualan Dinamis")
    tab1_abc, tab2_abc = st.tabs(["Hasil Tabel", "Dashboard"])

    with tab1_abc:
        # --- [MODIFIKASI] Fungsi Analisis ABC ---

        # Metode 1: Persentase (A, B, C, D)
        def classify_abc_dynamic(df_grouped, metric_col):
            abc_results = []
            if 'City' not in df_grouped.columns:
                if not df_grouped.empty:
                    st.warning("Kolom 'City' tidak ditemukan dalam data untuk klasifikasi ABC.")
                return pd.DataFrame()
            
            # Buat nama kolom unik berdasarkan metrik yang digunakan
            kategori_col_name = f'Kategori ABC (Persen - {metric_col.replace("AVG ", "")})'
            kontribusi_col_name = f'% Kontribusi (Persen - {metric_col.replace("AVG ", "")})'
            kumulatif_col_name = f'% Kumulatif (Persen - {metric_col.replace("AVG ", "")})'

            for city, city_group in df_grouped.groupby('City'):
                group = city_group.sort_values(by=metric_col, ascending=False).reset_index(drop=True)
                terjual = group[group[metric_col] > 0].copy()
                tidak_terjual = group[group[metric_col] <= 0].copy()
                total_metric = terjual[metric_col].sum()
                
                if total_metric == 0:
                    terjual[kontribusi_col_name] = 0
                    terjual[kumulatif_col_name] = 0
                    terjual[kategori_col_name] = 'D'
                else:
                    terjual[kontribusi_col_name] = 100 * terjual[metric_col] / total_metric
                    terjual[kumulatif_col_name] = terjual[kontribusi_col_name].cumsum()
                    terjual[kategori_col_name] = terjual[kumulatif_col_name].apply(lambda x: 'A' if x <= 70 else ('B' if x <= 90 else 'C'))
                
                tidak_terjual[kontribusi_col_name] = 0
                tidak_terjual[kumulatif_col_name] = 100
                tidak_terjual[kategori_col_name] = 'D'
                
                result = pd.concat([terjual, tidak_terjual], ignore_index=True)
                abc_results.append(result)
                
            return pd.concat(abc_results, ignore_index=True) if abc_results else pd.DataFrame()

        # [DITAMBAHKAN] Metode 3: Log-Benchmark (A, B, C, D, E, F)
        def classify_abc_log_benchmark(df_grouped, metric_col):
            df = df_grouped.copy()
            if 'Kategori Barang' not in df.columns:
                st.warning("Kolom 'Kategori Barang' tidak ada untuk metode benchmark.")
                df[f'Kategori ABC (Log-Benchmark - {metric_col.replace("AVG ", "")})'] = 'N/A'
                return df
            
            # Buat nama kolom unik
            kategori_col_name = f'Kategori ABC (Log-Benchmark - {metric_col.replace("AVG ", "")})'
            ratio_col_name = f'Ratio (Log-Benchmark - {metric_col.replace("AVG ", "")})'
            log_col_name = f'Log ({metric_col.replace("AVG ", "")})'
            avg_log_col_name = f'Avg_Log ({metric_col.replace("AVG ", "")})'
            
            # 1. Hitung Log(metric) hanya untuk metric > 0, sisanya NaN
            df[log_col_name] = df[metric_col].apply(lambda x: np.log(x) if x > 0 else np.nan)
            
            # 2. Hitung patokan (rata-rata log) per grup, abaikan NaN
            df[avg_log_col_name] = df.groupby(['City', 'Kategori Barang'])[log_col_name].transform('mean')
            
            # 3. Hitung rasio Log(metric) / Avg_Log_metric
            df[ratio_col_name] = df[log_col_name] / df[avg_log_col_name]
            
            # Isi NaN hasil pembagian (misal 0/0 atau log/NaN) dengan 0
            df[ratio_col_name] = df[ratio_col_name].fillna(0)
            
            def apply_category_log(row):
                # 4. Kategori 'F' untuk metric <= 0
                if row[metric_col] <= 0:
                    return 'F'
                
                # 5. Kategorikan sisanya (A-E) berdasarkan rasio
                ratio = row[ratio_col_name]
                if ratio > 2:
                    return 'A'
                elif ratio > 1.5:
                    return 'B'
                elif ratio > 1:
                    return 'C'
                elif ratio > 0.5:
                    return 'D'
                else:
                    return 'E' # Termasuk 0-0.5
            
            # 6. Terapkan kategori
            df[kategori_col_name] = df.apply(apply_category_log, axis=1)
            return df


        # --- Fungsi Highlighting ---
        def highlight_kategori_abc_persen(val): # A, B, C, D
            warna = {'A': '#cce5ff', 'B': '#d4edda', 'C': '#fff3cd', 'D': '#f8d7da'}
            return f'background-color: {warna.get(val, "")}'
        
        # [DITAMBAHKAN] Highlight untuk A-F
        def highlight_kategori_abc_log(val): # A, B, C, D, E, F
            warna = {
                'A': '#cce5ff', 'B': '#d4edda', 'C': '#fff3cd', 
                'D': '#f8d7da', 'E': '#e9ecef', 'F': '#6c757d'
            }
            color = warna.get(val, "")
            text_color = "white" if val == 'F' else "black"
            return f'background-color: {color}; color: {text_color}'


        # --- Validasi Data ---
        if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
            st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'** terlebih dahulu.")
            st.stop()
            
        # --- Preprocessing Data ---
        all_so_df = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        for df in [all_so_df, produk_ref]:
            if 'No. Barang' in df.columns:
                df['No. Barang'] = df['No. Barang'].astype(str).str.strip()
        so_df = all_so_df.copy()
        so_df.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')
        so_df['Nama Dept'] = so_df.apply(map_nama_dept, axis=1)
        so_df['City'] = so_df['Nama Dept'].apply(map_city)
        so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
        so_df.dropna(subset=['Tgl Faktur'], inplace=True)

        # --- Filter Tanggal (Hanya Tanggal Mulai dan Akhir) ---
        st.header("Filter Rentang Waktu Analisis ABC")
        st.info("Analisis akan didasarkan pada data penjualan 90 hari *sebelum* **Tanggal Akhir** yang dipilih untuk menghitung AVG Mean dan WMA.")
        
        # --- [BARU] Menambahkan Notes Penjelasan Rentang Waktu ---
        notes_text = """
        Perhitungan `Penjualan Bln 1`, `Bln 2`, dan `Bln 3` semuanya didasarkan pada **"Tanggal Akhir"** yang Anda pilih. 
        Logikanya menghitung mundur 3 blok waktu (masing-masing 30 hari) dari tanggal tersebut.

        **Contoh jika Anda memilih 30 November 2025 sebagai `Tanggal Akhir`:**

        * **Penjualan Bln 1 (30 Hari Terakhir):**
            * *Penjualan paling baru.*
            * Rentang: **1 November 2025 s/d 30 November 2025**
            * *(Logika: dari `Tanggal Akhir - 29 hari` s/d `Tanggal Akhir`)*

        * **Penjualan Bln 2 (30 Hari di Tengah):**
            * *30 hari sebelum Bln 1.*
            * Rentang: **2 Oktober 2025 s/d 31 Oktober 2025**
            * *(Logika: dari `Tanggal Akhir - 59 hari` s/d `Tanggal Akhir - 30 hari`)*

        * **Penjualan Bln 3 (30 Hari Paling Lama):**
            * *30 hari paling awal dari periode 90 hari.*
            * Rentang: **2 September 2025 s/d 1 Oktober 2025**
            * *(Logika: dari `Tanggal Akhir - 89 hari` s/d `Tanggal Akhir - 60 hari`)*
        """
        with st.expander("ℹ️ Klik untuk melihat detail perhitungan rentang 90 hari"):
            st.markdown(notes_text)
        # --- Akhir Notes ---
        
        today = datetime.now().date()
        min_date = so_df['Tgl Faktur'].min().date()
        max_date = so_df['Tgl Faktur'].max().date()

        # Tanggal akhir default adalah tanggal maks di data penjualan
        end_date_input = st.date_input(
            "Tanggal Akhir (untuk basis perhitungan 90 hari)", 
            value=max_date, 
            min_value=min_date, 
            max_value=max_date
        )

        # --- Tombol Eksekusi ---
        # [PERUBAHAN] Mengubah nama tombol
        if st.button("Jalankan Analisa ABC (4 Metode)"):
            # [PERUBAHAN] Mengubah spinner
            with st.spinner("Melakukan perhitungan analisis ABC (4 Metode)..."):
                
                # --- [BARU] Logika Perhitungan Metrik ---
                end_date_dt = pd.to_datetime(end_date_input)
                # Tentukan 3 rentang 30 hari
                range1_start = end_date_dt - pd.DateOffset(days=29); range1_end = end_date_dt
                range2_start = end_date_dt - pd.DateOffset(days=59); range2_end = end_date_dt - pd.DateOffset(days=30)
                range3_start = end_date_dt - pd.DateOffset(days=89); range3_end = end_date_dt - pd.DateOffset(days=60)
                
                # Filter data penjualan hanya untuk 90 hari
                start_date_90d = end_date_dt - pd.DateOffset(days=89)
                penjualan_90d = so_df[(so_df['Tgl Faktur'] >= start_date_90d) & (so_df['Tgl Faktur'] <= end_date_dt)]

                if penjualan_90d.empty:
                    st.error("Tidak ada data penjualan pada rentang 90 hari dari tanggal akhir yang dipilih.")
                    st.session_state.abc_analysis_result = None
                    st.stop()

                # Hitung penjualan per 30 hari
                sales_m1 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range1_start, range1_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 1')
                sales_m2 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range2_start, range2_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 2')
                sales_m3 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range3_start, range3_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 3')

                # Siapkan master list produk
                produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
                barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
                
                # Buat kombinasi lengkap (Penting untuk produk yg tidak terjual)
                city_list = so_df['City'].dropna().unique() 
                kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                grouped = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                
                # Gabungkan master list dengan data penjualan bulanan
                grouped = pd.merge(grouped, sales_m1, on=['City', 'No. Barang'], how='left')
                grouped = pd.merge(grouped, sales_m2, on=['City', 'No. Barang'], how='left')
                grouped = pd.merge(grouped, sales_m3, on=['City', 'No. Barang'], how='left')
                
                # Isi 0 untuk produk yg tidak terjual di bulan tsb
                grouped.fillna({'Penjualan Bln 1': 0, 'Penjualan Bln 2': 0, 'Penjualan Bln 3': 0}, inplace=True)
                
                # [BARU] Hitung 2 metrik (AVG Mean & WMA)
                grouped['AVG Mean'] = (grouped['Penjualan Bln 1'] + grouped['Penjualan Bln 2'] + grouped['Penjualan Bln 3']) / 3
                grouped['AVG WMA'] = (grouped['Penjualan Bln 1'] * 0.5) + (grouped['Penjualan Bln 2'] * 0.3) + (grouped['Penjualan Bln 3'] * 0.2)
                
                # --- [MODIFIKASI] Jalankan 4 Metode Analisis ---
                
                # 1. Persen - Mean
                result_persen_mean = classify_abc_dynamic(grouped.copy(), metric_col='AVG Mean')
                
                # 2. Persen - WMA
                result_persen_wma = classify_abc_dynamic(grouped.copy(), metric_col='AVG WMA')
                
                # 3. [DITAMBAHKAN] Log-Benchmark - Mean
                result_log_bench_mean = classify_abc_log_benchmark(grouped.copy(), metric_col='AVG Mean')
                
                # 4. [DITAMBAHKAN] Log-Benchmark - WMA
                result_log_bench_wma = classify_abc_log_benchmark(grouped.copy(), metric_col='AVG WMA')
                
                
                # --- [PERBAIKAN] Gabungkan Semua Hasil ---
                
                # Tentukan kunci merge utama
                merge_keys = ['City', 'No. Barang']
                
                # Tentukan kolom data yang akan diduplikasi jika tidak dihapus
                data_cols_to_drop = [
                    'BRAND Barang', 'Kategori Barang', 'Nama Barang', 
                    'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA'
                ]

                # Mulai dengan hasil Log-Benchmark Mean (Log-Benchmark - Mean)
                # [REVISI] Mulai dengan Log-Benchmark Mean
                result_final = result_log_bench_mean.copy()

                # Gabungkan hasil Log-Benchmark - WMA
                cols_to_keep_4 = merge_keys + [col for col in result_log_bench_wma.columns if 'Log-Benchmark - WMA' in col or 'Log (WMA)' in col or 'Avg_Log (WMA)' in col or 'Ratio (Log-Benchmark - WMA' in col]
                result_final = pd.merge(
                    result_final,
                    result_log_bench_wma[cols_to_keep_4],
                    on=merge_keys,
                    how='left'
                )
                
                # Gabungkan hasil Persen - Mean
                cols_to_keep_1 = merge_keys + [col for col in result_persen_mean.columns if 'Persen - Mean' in col]
                result_final = pd.merge(
                    result_final,
                    result_persen_mean[cols_to_keep_1],
                    on=merge_keys,
                    how='left'
                )

                # Gabungkan hasil Persen - WMA
                cols_to_keep_2 = merge_keys + [col for col in result_persen_wma.columns if 'Persen - WMA' in col]
                result_final = pd.merge(
                    result_final,
                    result_persen_wma[cols_to_keep_2],
                    on=merge_keys,
                    how='left'
                )
                
                
                # [REVISI] Bulatkan semua metrik numerik (INT)
                metric_cols_int = ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA']
                
                for col in metric_cols_int:
                    if col in result_final.columns:
                         result_final[col] = result_final[col].round(0).astype(int)

                # [DITAMBAHKAN] Bulatkan kolom log/ratio ke 2 desimal (FLOAT)
                metric_cols_float = [
                    'Log (WMA)', 'Avg_Log (WMA)', 'Ratio (Log-Benchmark - WMA)',
                    'Log (Mean)', 'Avg_Log (Mean)', 'Ratio (Log-Benchmark - Mean)'
                ]
                for col in metric_cols_float:
                    if col in result_final.columns:
                        result_final[col] = result_final[col].round(2)
                
                st.session_state.abc_analysis_result = result_final.copy()
                st.success("Analisis ABC (4 Metode) berhasil dijalankan!")
        
        # --- [MODIFIKASI] Tampilan Hasil ---
        if st.session_state.abc_analysis_result is not None:
            result_display = st.session_state.abc_analysis_result.copy()
            result_display = result_display[result_display['City'] != 'OTHERS']
            
            # Filter (tidak berubah)
            st.header("Filter Hasil Analisis")
            col_f1, col_f2 = st.columns(2)
            kategori_options_abc = sorted(produk_ref['Kategori Barang'].dropna().unique().astype(str))
            selected_kategori_abc = col_f1.multiselect("Filter berdasarkan Kategori:", kategori_options_abc, key="abc_cat_filter")
            brand_options_abc = sorted(produk_ref['BRAND Barang'].dropna().unique().astype(str))
            selected_brand_abc = col_f2.multiselect("Filter berdasarkan Brand:", brand_options_abc, key="abc_brand_filter")
            if selected_kategori_abc:
                result_display = result_display[result_display['Kategori Barang'].astype(str).isin(selected_kategori_abc)]
            if selected_brand_abc:
                result_display = result_display[result_display['BRAND Barang'].astype(str).isin(selected_brand_abc)]
            
            # [MODIFIKASI] Tabel per Kota
            st.header("Hasil Analisis ABC per Kota")
            keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang'] # Definisikan keys di sini
            
            for city in sorted(result_display['City'].unique()):
                with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
                    city_df = result_display[result_display['City'] == city]
                    
                    # [BARU] Urutan kolom baru
                    display_cols_order = [
                        'No. Barang', 'BRAND Barang', 'Nama Barang', 'Kategori Barang', 
                        'AVG Mean', 'AVG WMA',
                        # Kolom Analisa (paling kanan)
                        'Kategori ABC (Persen - Mean)', 'Kategori ABC (Persen - WMA)',
                        'Kategori ABC (Log-Benchmark - Mean)', # [DITAMBAHKAN]
                        'Kategori ABC (Log-Benchmark - WMA)', # [DITAMBAHKAN]
                        # Kolom pendukung
                        '% Kontribusi (Persen - Mean)', '% Kontribusi (Persen - WMA)',
                        'Ratio (Log-Benchmark - Mean)', # [DITAMBAHKAN]
                        'Log (Mean)', # [DITAMBAHKAN]
                        'Avg_Log (Mean)', # [DITAMBAHKAN]
                        'Ratio (Log-Benchmark - WMA)', # [DITAMBAHKAN]
                        'Log (WMA)', # [DITAMBAHKAN]
                        'Avg_Log (WMA)' # [DITAMBAHKAN]
                    ]
                    display_cols = [col for col in display_cols_order if col in city_df.columns]
                    df_city_display = city_df[display_cols]
                    
                    # [REVISI] Buat format dict dinamis untuk tabel kota ABC
                    format_dict_abc_kota = {}
                    for col_name in df_city_display.columns:
                         if pd.api.types.is_numeric_dtype(df_city_display[col_name]):
                            if col_name in keys:
                                continue
                            
                            if "% Kontribusi" in col_name:
                                format_dict_abc_kota[col_name] = '{:.2f}%'
                            # [DITAMBAHKAN] Format untuk log/ratio
                            elif "Ratio" in col_name or "Log" in col_name:
                                format_dict_abc_kota[col_name] = '{:.2f}'
                            else:
                                format_dict_abc_kota[col_name] = '{:.0f}'

                    # [MODIFIKASI] Terapkan 4 highlight + format dinamis
                    st.dataframe(
                        df_city_display.style
                            .format(format_dict_abc_kota, na_rep='-')
                            .apply(lambda x: x.map(highlight_kategori_abc_persen), subset=['Kategori ABC (Persen - Mean)'])
                            .apply(lambda x: x.map(highlight_kategori_abc_persen), subset=['Kategori ABC (Persen - WMA)'])
                            .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - Mean)']) # [DITAMBAHKAN]
                            .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - WMA)']), # [DITAMBAHKAN]
                        use_container_width=True
                    )
            
            # [MODIFIKASI] Tabel Gabungan
            st.header("📊 Tabel Gabungan Seluruh Kota (ABC)")
            with st.spinner("Membuat tabel pivot gabungan untuk ABC..."):
                # keys sudah didefinisikan di atas
                
                # [REVISI] Daftar kolom pivot
                pivot_values = [
                    'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA',
                    'Kategori ABC (Persen - Mean)', 'Kategori ABC (Persen - WMA)',
                    'Kategori ABC (Log-Benchmark - Mean)', # [DITAMBAHKAN]
                    'Ratio (Log-Benchmark - Mean)', # [DITAMBAHKAN]
                    'Log (Mean)', # [DITAMBAHKAN]
                    'Avg_Log (Mean)', # [DITAMBAHKAN]
                    'Kategori ABC (Log-Benchmark - WMA)', # [DITAMBAHKAN]
                    'Ratio (Log-Benchmark - WMA)', # [DITAMBAHKAN]
                    'Log (WMA)', # [DITAMBAHKAN]
                    'Avg_Log (WMA)' # [DITAMBAHKAN]
                ]
                
                # Pastikan hanya kolom yang ada di df yang dipivot
                pivot_values_existing = [col for col in pivot_values if col in result_display.columns]

                pivot_abc = result_display.pivot_table(
                    index=keys, 
                    columns='City', 
                    values=pivot_values_existing, 
                    aggfunc='first' # 'first' cocok di sini krn data sudah per City
                )
                pivot_abc.columns = [f"{level1}_{level0}" for level0, level1 in pivot_abc.columns]
                pivot_abc.reset_index(inplace=True)
                
                # --- [MODIFIKASI] Perhitungan Total Gabungan ("All") ---
                total_abc = result_display.groupby(keys).agg(
                    {'Penjualan Bln 1': 'sum', 'Penjualan Bln 2': 'sum', 'Penjualan Bln 3': 'sum'}
                ).reset_index()
                
                # Hitung AVG Mean dan WMA untuk total
                total_abc['AVG Mean'] = (total_abc['Penjualan Bln 1'] + total_abc['Penjualan Bln 2'] + total_abc['Penjualan Bln 3']) / 3
                total_abc['AVG WMA'] = (total_abc['Penjualan Bln 1'] * 0.5) + (total_abc['Penjualan Bln 2'] * 0.3) + (total_abc['Penjualan Bln 3'] * 0.2)
                
                # [REVISI] Bulatkan metrik total_abc
                metric_cols_total = ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA']
                for col in metric_cols_total:
                    if col in total_abc.columns:
                        total_abc[col] = total_abc[col].round(0).astype(int)

                total_abc['City'] = 'All' # Dummy city
                
                # [PERBAIKAN] Hapus dua baris yang error
                # kategori_mapping = result_display[keys].drop_duplicates()
                # total_abc = pd.merge(total_abc.drop(columns=['Kategori Barang'], errors='ignore'), kategori_mapping, on=keys, how='left')

                # Jalankan 4 Analisa untuk 'All'
                all_persen_mean = classify_abc_dynamic(total_abc.copy(), metric_col='AVG Mean')
                all_persen_wma = classify_abc_dynamic(total_abc.copy(), metric_col='AVG WMA')
                all_log_bench_mean = classify_abc_log_benchmark(total_abc.copy(), metric_col='AVG Mean') # [DITAMBAHKAN]
                all_log_bench_wma = classify_abc_log_benchmark(total_abc.copy(), metric_col='AVG WMA') # [DITAMBAHKAN]

                # [PERBAIKAN] Pastikan kolom kunci (keys) ada untuk setiap merge
                total_final = pd.merge(
                    all_persen_mean[keys + [col for col in all_persen_mean.columns if 'Persen - Mean' in col or 'Penjualan' in col or 'AVG' in col]], 
                    all_persen_wma[keys + [col for col in all_persen_wma.columns if 'Persen - WMA' in col]], 
                    on=keys, how='left'
                )
                
                # [DITAMBAHKAN] Merge Log-Benchmark 'All' (Mean)
                total_final = pd.merge(
                    total_final, 
                    all_log_bench_mean[keys + [col for col in all_log_bench_mean.columns if 'Log-Benchmark - Mean' in col or 'Log (Mean)' in col or 'Avg_Log (Mean)' in col or 'Ratio (Log-Benchmark - Mean' in col]], 
                    on=keys, how='left'
                )
                
                # [DITAMBAHKAN] Merge Log-Benchmark 'All' (WMA)
                total_final = pd.merge(
                    total_final, 
                    all_log_bench_wma[keys + [col for col in all_log_bench_wma.columns if 'Log-Benchmark - WMA' in col or 'Log (WMA)' in col or 'Avg_Log (WMA)' in col or 'Ratio (Log-Benchmark - WMA' in col]], 
                    on=keys, how='left'
                )

                # [DITAMBAHKAN] Bulatkan log/ratio di total_final
                log_cols_total = [
                    'Log (WMA)', 'Avg_Log (WMA)', 'Ratio (Log-Benchmark - WMA)',
                    'Log (Mean)', 'Avg_Log (Mean)', 'Ratio (Log-Benchmark - Mean)'
                ]
                for col in log_cols_total:
                    if col in total_final.columns:
                        total_final[col] = total_final[col].round(2)

                # Rename kolom 'All'
                total_final.columns = [f"All_{col}" if col not in keys else col for col in total_final.columns]

                # Gabungkan pivot utama dengan data 'All'
                pivot_abc_final = pd.merge(pivot_abc, total_final, on=keys, how='left')
                
                
                # =================================================================
                # [PERBAIKAN] Mengganti Styler dengan column_config
                # =================================================================
                
                # [REVISI] Buat DataFrame yang akan ditampilkan terlebih dahulu
                df_to_style_abc = pivot_abc_final.copy() # .copy() untuk keamanan
                
                # 1. Pisahkan kolom
                numeric_cols_abc = []
                perc_cols_abc = []
                float_cols_abc = [] # [DITAMBAHKAN] Untuk log/ratio
                object_cols_abc = []
                
                for col in df_to_style_abc.columns:
                    if col not in keys:
                        if "% Kontribusi" in col:
                            perc_cols_abc.append(col)
                        # [DITAMBAHKAN] Kondisi untuk log/ratio
                        elif "Ratio" in col or "Log" in col:
                            float_cols_abc.append(col)
                        elif pd.api.types.is_numeric_dtype(df_to_style_abc[col]):
                            numeric_cols_abc.append(col)
                        else:
                            object_cols_abc.append(col)
                            
                # 2. Isi NaN di DataFrame SEBELUM styling
                df_to_style_abc[numeric_cols_abc] = df_to_style_abc[numeric_cols_abc].fillna(0)
                df_to_style_abc[perc_cols_abc] = df_to_style_abc[perc_cols_abc].fillna(0) # Persen NaN jadi 0
                df_to_style_abc[float_cols_abc] = df_to_style_abc[float_cols_abc].fillna(0) # Log/Ratio NaN jadi 0
                df_to_style_abc[object_cols_abc] = df_to_style_abc[object_cols_abc].fillna('-')
                
                # 3. [REVISI] Buat column_config untuk st.dataframe
                column_config_abc = {}
                for col in numeric_cols_abc:
                    column_config_abc[col] = st.column_config.NumberColumn(format="%.0f")
                for col in perc_cols_abc:
                    column_config_abc[col] = st.column_config.NumberColumn(format="%.2f%%")
                # [DITAMBAHKAN] Format untuk log/ratio
                for col in float_cols_abc:
                    column_config_abc[col] = st.column_config.NumberColumn(format="%.2f")

                # Tampilkan DataFrame (bukan Styler) dengan format baru
                st.dataframe(
                    df_to_style_abc,  # <-- Gunakan DataFrame-nya, bukan Styler
                    column_config=column_config_abc, # <-- Gunakan column_config
                    use_container_width=True
                )
                # =================================================================
                # [AKHIR PERBAIKAN]
                # =================================================================
                
            # Download
            st.header("💾 Unduh Hasil Analisis ABC")
            output_abc = BytesIO()
            with pd.ExcelWriter(output_abc, engine='openpyxl') as writer:
                # [REVISI] Gunakan df_to_style_abc yang sudah bersih untuk di-download
                df_to_style_abc.to_excel(writer, sheet_name="All Cities Pivot", index=False)
                for city in sorted(result_display['City'].unique()):
                    sheet_name = city[:31]
                    result_display[result_display['City'] == city].to_excel(writer, sheet_name=sheet_name, index=False)
            st.download_button("📥 Unduh Hasil Analisis ABC (Excel)",data=output_abc.getvalue(),file_name=f"Hasil_Analisis_ABC_{end_date_input}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- [MODIFIKASI TOTAL] Dashboard ---
    with tab2_abc:
        st.header("📈 Dashboard Analisis ABC")
        if 'abc_analysis_result' in st.session_state and st.session_state.abc_analysis_result is not None:
            result_display_dash = st.session_state.abc_analysis_result.copy()
            
            # [PERUBAHAN] Mengubah pilihan selectbox
            metode_dashboard = st.selectbox(
                "Pilih Metode ABC untuk Dashboard:",
                ("Persen - WMA", "Persen - Mean", "Log-Benchmark - WMA", "Log-Benchmark - Mean") # [DITAMBAHKAN]
            )
            
            # Tentukan kolom dan metrik berdasarkan pilihan
            if metode_dashboard == "Persen - WMA":
                kategori_col = 'Kategori ABC (Persen - WMA)'
                metric_col = 'AVG WMA'
                kategori_labels = ['A', 'B', 'C', 'D']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da']
                metric_labels = {
                    'A': ("Produk Kelas A", "{:.1f}% Penjualan"),
                    'B': ("Produk Kelas B", "{:.1f}% Penjualan"),
                    'C': ("Produk Kelas C", "{:.1f}% Penjualan"),
                    'D': ("Produk Kelas D", "Tidak Terjual")
                }
            elif metode_dashboard == "Persen - Mean": 
                kategori_col = 'Kategori ABC (Persen - Mean)'
                metric_col = 'AVG Mean'
                kategori_labels = ['A', 'B', 'C', 'D']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da']
                metric_labels = {
                    'A': ("Produk Kelas A", "{:.1f}% Penjualan"),
                    'B': ("Produk Kelas B", "{:.1f}% Penjualan"),
                    'C': ("Produk Kelas C", "{:.1f}% Penjualan"),
                    'D': ("Produk Kelas D", "Tidak Terjual")
                }
            # [DITAMBAHKAN] Logika dashboard untuk metode baru
            elif metode_dashboard == "Log-Benchmark - WMA": 
                kategori_col = 'Kategori ABC (Log-Benchmark - WMA)'
                metric_col = 'AVG WMA'
                kategori_labels = ['A', 'B', 'C', 'D', 'E', 'F']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e9ecef', '#6c757d']
                metric_labels = {
                    'A': ("Produk Kelas A", "{:.1f}% Penjualan"),
                    'B': ("Produk Kelas B", "{:.1f}% Penjualan"),
                    'C': ("Produk Kelas C", "{:.1f}% Penjualan"),
                    'D': ("Produk Kelas D", "{:.1f}% Penjualan"),
                    'E': ("Produk Kelas E", "{:.1f}% Penjualan"),
                    'F': ("Produk Kelas F", "Tidak Terjual")
                }
            # [DITAMBAHKAN] Logika dashboard untuk metode baru
            elif metode_dashboard == "Log-Benchmark - Mean": 
                kategori_col = 'Kategori ABC (Log-Benchmark - Mean)'
                metric_col = 'AVG Mean'
                kategori_labels = ['A', 'B', 'C', 'D', 'E', 'F']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e9ecef', '#6c757d']
                metric_labels = {
                    'A': ("Produk Kelas A", "{:.1f}% Penjualan"),
                    'B': ("Produk Kelas B", "{:.1f}% Penjualan"),
                    'C': ("Produk Kelas C", "{:.1f}% Penjualan"),
                    'D': ("Produk Kelas D", "{:.1f}% Penjualan"),
                    'E': ("Produk Kelas E", "{:.1f}% Penjualan"),
                    'F': ("Produk Kelas F", "Tidak Terjual")
                }


            if not result_display_dash.empty:
                # Grup berdasarkan kolom yang dipilih dan gunakan metrik yang sesuai
                abc_summary = result_display_dash.groupby(kategori_col)[metric_col].agg(['count', 'sum'])
                
                for label in kategori_labels:
                    if label not in abc_summary.index:
                        abc_summary.loc[label] = [0, 0]
                abc_summary = abc_summary.reindex(kategori_labels).fillna(0)
                
                total_sales_sum = abc_summary['sum'].sum()
                if total_sales_sum > 0:
                    abc_summary['sum_perc'] = (abc_summary['sum'] / total_sales_sum) * 100
                else:
                    abc_summary['sum_perc'] = 0
                    
                st.markdown("---")
                
                cols = st.columns(len(kategori_labels))
                for i, label in enumerate(kategori_labels):
                    title, delta_template = metric_labels[label]
                    count = abc_summary.loc[label, 'count']
                    
                    # [PERBAIKAN] Logika delta text untuk A-F
                    if label == 'D' and 'Persen' in metode_dashboard:
                        delta_text = "Tidak Terjual"
                    elif label == 'F' and 'Log-Benchmark' in metode_dashboard:
                        delta_text = "Tidak Terjual"
                    elif abc_summary.loc[label, 'sum_perc'] == 0:
                         delta_text = "0.0% Penjualan"
                    else:
                        delta_text = delta_template.format(abc_summary.loc[label, 'sum_perc'])
                    
                    cols[i].metric(title, f"{int(count)} SKU", delta_text)
                        
                st.markdown("---")
                
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Komposisi Produk per Kelas")
                    data_pie = abc_summary[abc_summary['count'] > 0]
                    if not data_pie.empty:
                        fig1, ax1 = plt.subplots()
                        ax1.pie(data_pie['count'], labels=data_pie.index, autopct='%1.1f%%', startangle=90, colors=[colors[kategori_labels.index(i)] for i in data_pie.index])
                        ax1.axis('equal')
                        st.pyplot(fig1)
                    else:
                        st.info("Tidak ada data untuk pie chart.")
                        
                with col_chart2:
                    st.subheader("Kontribusi Penjualan per Kelas")
                    data_bar = abc_summary[abc_summary['sum_perc'] > 0]
                    if not data_bar.empty:
                        st.bar_chart(data_bar[['sum_perc']].rename(columns={'sum_perc': 'Kontribusi Penjualan (%)'}))
                    else:
                        st.info("Tidak ada kontribusi penjualan untuk ditampilkan.")
                        
                st.markdown("---")
                
                col_top1, col_top2 = st.columns(2)
                with col_top1:
                    st.subheader(f"Top 10 Produk Terlaris (berdasarkan {metric_col})")
                    top_products = result_display_dash.groupby('Nama Barang')[metric_col].sum().nlargest(10)
                    st.bar_chart(top_products)
                with col_top2:
                    st.subheader(f"Performa Penjualan per Kota (berdasarkan {metric_col})")
                    city_sales = result_display_dash.groupby('City')[metric_col].sum().sort_values(ascending=False)
                    st.bar_chart(city_sales)
            else:
                st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")
        else:
            st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")
