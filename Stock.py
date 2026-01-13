
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
    st.session_state.produk_ref = pd.DataFrame()
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
    if nama_dept in ['A - ITC', 'A - RETAIL', 'C - PUSAT', 'G - PROJECT']: return 'Surabaya'
    elif nama_dept == 'B - JKT': return 'Jakarta'
    elif nama_dept == 'D - SMG': return 'Semarang'
    elif nama_dept == 'E - JOG': return 'Jogja'
    elif nama_dept == 'F - MLG': return 'Malang'
    elif nama_dept == 'H - BALI': return 'Bali'
    else: return 'Others'

# --- FUNGSI KONVERSI EXCEL ---
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

# --- [CORE FUNCTION] Metode Log-Benchmark (Sinkron dengan Excel) ---
def classify_abc_log_benchmark(df_grouped, metric_col):
    df = df_grouped.copy()

    if 'Kategori Barang' not in df.columns:
        st.warning("Kolom 'Kategori Barang' tidak ada untuk metode benchmark.")
        return df

    clean_metric = metric_col.replace('SO ', '').replace('AVG ', '')
    log_col = f'Log (10) {clean_metric}'
    avg_log_col = f'Avg Log {clean_metric}'
    ratio_col = f'Ratio Log {clean_metric}'
    kategori_col_name = f'Kategori ABC (Log-Benchmark - {clean_metric})'

    # 1. BULATKAN DULU (Agar sinkron dengan Excel)
    df['Rounded_Metric'] = df[metric_col].apply(np.round)
    
    # 2. Hitung Log Individu (Paksa min 1)
    df['Log_Input'] = np.maximum(1, df['Rounded_Metric']).astype(float)
    
    df[log_col] = np.where(
        df[metric_col] > 0,
        np.log10(df['Log_Input']),
        np.nan 
    )

    # 3. Hitung Rata-rata Log (Benchmark) - Filter Rounded >= 1
    valid_data_for_avg = df[df['Rounded_Metric'] >= 1].copy()
    
    avg_reference = valid_data_for_avg.groupby(['City', 'Kategori Barang'])[log_col].mean().reset_index()
    avg_reference.rename(columns={log_col: avg_log_col}, inplace=True)
    
    if avg_log_col in df.columns:
        df.drop(columns=[avg_log_col], inplace=True)

    df = pd.merge(df, avg_reference, on=['City', 'Kategori Barang'], how='left')
    df[avg_log_col] = df[avg_log_col].fillna(0)

    # 4. Hitung Rasio & Kategori
    df[ratio_col] = df[log_col] / df[avg_log_col]
    df[ratio_col] = df[ratio_col].fillna(0)

    df.drop(columns=['Rounded_Metric', 'Log_Input'], inplace=True, errors='ignore')

    def apply_category_log(row):
        if row[metric_col] <= 0 or pd.isna(row[metric_col]): return 'F'
        ratio = row[ratio_col]
        if ratio > 2: return 'A'
        elif ratio > 1.5: return 'B'
        elif ratio > 1: return 'C'
        elif ratio > 0.5: return 'D'
        else: return 'E'

    df[kategori_col_name] = df.apply(apply_category_log, axis=1)

    return df

# =====================================================================================
# 			 			 	 	 ROUTING HALAMAN
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
    
    st.header("4. Data Portal (Margin)")
    with st.spinner("Mencari file portal di Google Drive..."):
        portal_files_list = list_files_in_folder(drive_service, folder_portal)
    
    selected_portal_file = st.selectbox(
        "Pilih file Portal dari Google Drive (pilih 1 file):",
        options=[None] + portal_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    
    if st.button("Muat Data Portal"):
        if selected_portal_file:
            with st.spinner(f"Memuat file {selected_portal_file['name']}..."):
                df_portal = download_and_read(selected_portal_file['id'], selected_portal_file['name'])
                st.session_state.df_portal = df_portal
                st.session_state.df_portal_analyzed = pd.DataFrame()
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

    def highlight_kategori_abc_log(val): 
        warna = {'A': '#cce5ff', 'B': '#d4edda', 'C': '#fff3cd', 'D': '#f8d7da', 'E': '#e9ecef', 'F': '#6c757d'}
        color = warna.get(val, "")
        text_color = "white" if val == 'F' else "black"
        return f'background-color: {color}; color: {text_color}'

    def get_status_stock(row):
        kategori_log = row['Kategori ABC (Log-Benchmark - WMA)'] 
        if kategori_log == 'F': 
            return 'Overstock F' if row['Stock Cabang'] > 2 else 'Balance'
        if row['Stock Cabang'] > row['Max Stock']: return 'Overstock'
        if row['Stock Cabang'] < row['Min Stock']: return 'Understock' 
        if row['Stock Cabang'] >= row['Min Stock']: return 'Balance' 
        return '-'

    def highlight_status_stock(val):
        colors = {'Understock': '#fff3cd', 'Balance': '#d4edda', 'Overstock': '#ffd6a5', 'Overstock F': '#f5c6cb'}
        return f'background-color: {colors.get(val, "")}'

    def hitung_po_cabang_baru(stock_surabaya, stock_cabang, stock_total, total_add_stock_all, so_cabang, add_stock_cabang):
        try:
            if stock_surabaya < add_stock_cabang: return 0
            kebutuhan_30_hari = (so_cabang / 30) * 30
            kondisi_3_terpenuhi = stock_cabang < kebutuhan_30_hari
            kondisi_2_terpenuhi = stock_total < total_add_stock_all
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

    if 'No. Faktur' in penjualan.columns and 'No. Barang' in penjualan.columns:
        penjualan['No. Faktur'] = penjualan['No. Faktur'].astype(str).str.strip()
        penjualan['Faktur + Barang'] = penjualan['No. Faktur'] + penjualan['No. Barang']
        duplicates = penjualan[penjualan.duplicated(subset=['Faktur + Barang'], keep=False)].sort_values(by=['Faktur + Barang', 'Tgl Faktur'])
        penjualan.drop_duplicates(subset=['Faktur + Barang'], keep='first', inplace=True)
        st.session_state.df_penjualan = penjualan.copy()
        
        if not duplicates.empty:
            deleted_duplicates = duplicates[~duplicates.index.isin(penjualan.index)]
            st.warning(f"⚠️ Ditemukan dan dihapus {len(deleted_duplicates)} baris duplikat berdasarkan 'Faktur + Barang'.")
            with st.expander("Lihat Detail Duplikat yang Dihapus"):
                st.dataframe(deleted_duplicates)
        else:
             st.info("✅ Tidak ada duplikat 'Faktur + Barang' yang ditemukan.")

    penjualan.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')
    penjualan['Nama Dept'] = penjualan.apply(map_nama_dept, axis=1)
    penjualan['City'] = penjualan['Nama Dept'].apply(map_city)
    
    produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang'}, inplace=True, errors='ignore')
    if 'Kategori Barang' in produk_ref.columns:
        produk_ref['Kategori Barang'] = produk_ref['Kategori Barang'].astype(str).str.strip().str.upper()
    if 'City' in penjualan.columns:
        penjualan['City'] = penjualan['City'].astype(str).str.strip().str.upper()
    
    penjualan['Tgl Faktur'] = pd.to_datetime(penjualan['Tgl Faktur'], errors='coerce')
    
    with st.expander("Lihat Data Penjualan Setelah Preprocessing"):
        preview_cols = ['No. Faktur', 'Tgl Faktur', 'Nama Pelanggan', 'No. Barang', 'Faktur + Barang', 'Kuantitas']
        preview_cols_filtered = [col for col in preview_cols if col in penjualan.columns]
        st.dataframe(penjualan[preview_cols_filtered].head(20), use_container_width=True)
        excel_cleaned_penjualan = convert_df_to_excel(penjualan)
        st.download_button("📥 Unduh Data Penjualan Bersih (Excel)", data=excel_cleaned_penjualan, file_name="data_penjualan_bersih.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
    st.markdown("---")

    default_end_date = penjualan['Tgl Faktur'].dropna().max().date()
    if st.session_state.stock_filename:
        match = re.search(r'(\d{8})', st.session_state.stock_filename)
        if match:
            try: default_end_date = datetime.strptime(match.group(1), '%d%m%Y').date()
            except ValueError: pass
    default_start_date = default_end_date - timedelta(days=89)

    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Awal (90 Hari Belakang)", value=default_start_date, key="stock_start", disabled=True)
    end_date = col2.date_input("Tanggal Akhir", value=default_end_date, key="stock_end")

    if st.button("Jalankan Analisa Stock"):
        with st.spinner("Melakukan perhitungan analisis stok..."):
            
            bulan_indonesia = {
                1: 'JANUARI', 2: 'FEBRUARI', 3: 'MARET', 4: 'APRIL', 5: 'MEI', 6: 'JUNI',
                7: 'JULI', 8: 'AGUSTUS', 9: 'SEPTEMBER', 10: 'OKTOBER', 11: 'NOVEMBER', 12: 'DESEMBER'
            }
            
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
                
                penjualan_for_wma['Bulan'] = penjualan_for_wma['Tgl Faktur'].dt.to_period('M')
                monthly_sales = penjualan_for_wma.groupby(['City', 'No. Barang', 'Bulan'])['Kuantitas'].sum().unstack(fill_value=0).reset_index()
                full_data = pd.merge(full_data, monthly_sales, on=['City', 'No. Barang'], how='left')
                
                full_data.fillna(0, inplace=True)

                bulan_columns_period = [col for col in full_data.columns if isinstance(col, pd.Period)]
                bulan_columns_period.sort()
                rename_map = {col: f"{bulan_indonesia[col.month]} {col.year}" for col in bulan_columns_period}
                full_data.rename(columns=rename_map, inplace=True)
                bulan_columns_renamed = [rename_map[col] for col in bulan_columns_period]
                
                full_data.rename(columns={'AVG WMA': 'SO WMA', 'AVG Mean': 'SO Mean', 'Total Kuantitas': 'SO Total'}, inplace=True)
                
                # SO Total dihitung dari SO WMA
                full_data['SO Total'] = full_data['SO WMA'] 
                
                final_result = full_data.copy() 
                
                # --- [CORE] Jalankan Analisa ABC Log-Benchmark ---
                log_df = classify_abc_log_benchmark(final_result.copy(), metric_col='SO WMA')
                
                final_result = pd.merge(
                    final_result, 
                    log_df[['City', 'No. Barang', 'Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10) WMA', 'Avg Log WMA']], 
                    on=['City', 'No. Barang'], 
                    how='left'
                )

                # ==============================================================================
                # [FITUR BARU] Hitung 3 Variasi Min Stock (STRATEGI ULTRA-LEAN)
                # ==============================================================================
                
                def get_days_multiplier(kategori):                    
                    # 2. Days Multiplier (Time Based - Asumsi Lead Time 30 Hari)
                    # A: 33 Hari (1.1x)
                    # B: 30 Hari (1.0x)
                    # C: 24 Hari (0.8x - Sedikit di bawah sebulan)
                    # D: 15 Hari (0.5x - Setengah bulan)
                    # E: 7 Hari (0.25x - Seminggu)
                    days_map = {
                        'A': 1, 'B': 1, 'C': 0.5, 
                        'D': 0.3, 'E': 0.25, 'F': 0.0
                    }
                    return days_map.get(kategori, 1.0)

                def calculate_min_stock_days_only(row):
                    wma = row['SO WMA']
                    cat = row.get('Kategori ABC (Log-Benchmark - WMA)', 'E')
                    if wma <= 0: 
                        return 0
                    
                    # Ambil multiplier
                    day_mult = get_days_multiplier(cat)
                    
                    # Hitung Min Stock (WMA * Multiplier Hari)
                    raw_min = wma * day_mult
                    
                    # PEMBULATAN KE ATAS (CEILING)
                    # Contoh: 2.1 jadi 3, 4.8 jadi 5
                    return math.ceil(raw_min)

                final_result['Min Stock'] = final_result.apply(calculate_min_stock_days_only, axis=1)

                # ==============================================================================
                # [KONFIGURASI] Informasi Metode Aktif (Tampilan Saja)
                # ==============================================================================
                st.markdown("### ⚙️ Konfigurasi Stok Minimal")
                st.info("""
                ✅ **Metode Terkunci: Min Stock (Days / Time Based)**
                
                Perhitungan otomatis menggunakan multiplier waktu (WMA × Hari):
                * **A & B:** 1.0x (Buffer 30 Hari)
                * **C:** 0.75x (Buffer 24 Hari)
                * **D:** 0.50x (Buffer 15 Hari)
                * **E:** 0.25x (Buffer 7 Hari)
                """)
                
                # ==============================================================================
                # [LOGIKA MAX STOCK - ULTRA LEAN]
                # ==============================================================================
                def calculate_dynamic_max_stock(row):
                    # Basis perhitungan Max Stock menggunakan SO WMA (sesuai request)
                    wma = row['SO WMA']
                    kategori = row.get('Kategori ABC (Log-Benchmark - WMA)', 'E')
                    
                    # Aturan Multiplier Max Stock:
                    # A & B : 2x SO WMA
                    # C     : 1.5x SO WMA
                    # D & E : 1x SO WMA
                    
                    if kategori in ['A', 'B']: 
                        multiplier = 2.0
                    elif kategori == 'C': 
                        multiplier = 1.5
                    elif kategori in ['D', 'E']: 
                        multiplier = 1.0
                    else: 
                        multiplier = 0.0 # F atau lainnya
                    
                    raw_max = wma * multiplier
                    
                    # Pastikan Max Stock tidak lebih kecil dari Min Stock (safety logic)
                    # min_stock = row['Min Stock']
                    # if raw_max < min_stock: raw_max = min_stock
                    
                    # PEMBULATAN KE ATAS (CEILING)
                    return math.ceil(raw_max)
                
                final_result['Max Stock'] = final_result.apply(calculate_dynamic_max_stock, axis=1)

                # --- Lanjut ke Stock Cabang ---
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
                
                final_result['Add Stock'] = final_result.apply(lambda row: max(0, row['Min Stock'] - row['Stock Cabang']), axis=1)
                
                stock_surabaya = stock_melted[stock_melted['City'] == 'SURABAYA'][['No. Barang', 'Stock']].rename(columns={'Stock': 'Stock Surabaya'})
                stock_total = stock_melted.groupby('No. Barang')['Stock'].sum().reset_index().rename(columns={'Stock': 'Stock Total'})
                total_req_df = final_result.groupby('No. Barang')['Add Stock'].sum().reset_index(name='Total Add Stock All')
                
                # Merge Data Pendukung ke Tabel Utama
                final_result = final_result.merge(stock_surabaya, on='No. Barang', how='left')
                final_result = final_result.merge(stock_total, on='No. Barang', how='left')
                final_result = final_result.merge(total_req_df, on='No. Barang', how='left') # Merge Total Permintaan
                
                final_result.fillna(0, inplace=True)
                
                final_result['Suggested PO'] = final_result.apply(lambda row: hitung_po_cabang_baru(stock_surabaya=row['Stock Surabaya'], stock_cabang=row['Stock Cabang'], stock_total=row['Stock Total'], total_add_stock_all=row['Total Add Stock All'], so_cabang=row['SO WMA'], add_stock_cabang=row['Add Stock']), axis=1)
                
                # --- PEMBULATAN (INTEGER) ---
                numeric_cols = ['Stock Cabang', 'Min Stock', 'Max Stock', 'Add Stock', 'Total Add Stock All', 'Suggest PO All', 'Suggested PO', 'Stock Surabaya', 'Stock Total', 'SO WMA', 'SO Mean', 'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3']
                numeric_cols.extend(['Min Stock (Flat)', 'Min Stock (SS)', 'Min Stock (Days)'])
                numeric_cols.extend(bulan_columns_renamed)

                for col in numeric_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(0).astype(int)
                
                # --- PEMBULATAN (FLOAT/LOG) ---
                float_cols = ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA']
                for col in float_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(2)
                
                st.session_state.stock_analysis_result = final_result.copy()
                st.session_state.bulan_columns_stock = bulan_columns_renamed 
                st.success("Analisis Stok berhasil dijalankan!")

    if st.session_state.stock_analysis_result is not None:
        final_result_to_filter = st.session_state.stock_analysis_result.copy()
        final_result_to_filter = final_result_to_filter[final_result_to_filter['City'] != 'OTHERS'] 
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
        col_h1, col_h2 = st.columns(2)
        abc_log_options = sorted(final_result_display['Kategori ABC (Log-Benchmark - WMA)'].dropna().unique().astype(str))
        selected_abc_log = col_h1.multiselect("Kategori ABC (Log-Benchmark):", abc_log_options)
        status_options = sorted(final_result_display['Status Stock'].dropna().unique().astype(str))
        selected_status = col_h2.multiselect("Status Stock:", status_options) 
        
        st.markdown("---")
        tab1, tab2 = st.tabs(["Hasil Tabel", "Dashboard"])

        with tab1:
            header_style = {'selector': 'th', 'props': [('background-color', '#0068c9'), ('color', 'white'), ('text-align', 'center')]}
            st.header("Hasil Analisis Stok per Kota")

            for city in sorted(final_result_display['City'].unique()):
                with st.expander(f"📍 Lihat Hasil Stok untuk Kota: {city}"):
                    city_df = final_result_display[final_result_display['City'] == city].copy()
                    if selected_abc_log: city_df = city_df[city_df['Kategori ABC (Log-Benchmark - WMA)'].isin(selected_abc_log)]
                    if selected_status: city_df = city_df[city_df['Status Stock'].isin(selected_status)]
                    if city_df.empty:
                        st.write("Tidak ada data yang cocok dengan filter yang dipilih.")
                        continue
                    
                    keys_base = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                    metric_order_kota = (
                        bulan_cols + 
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA', 'Kategori ABC (Log-Benchmark - WMA)'] +
                        ['Min Stock (Flat)', 'Min Stock (SS)', 'Min Stock (Days)'] +
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    display_cols_kota = keys_base + [col for col in metric_order_kota if col in city_df.columns]
                    city_df_display = city_df[display_cols_kota]
                    
                    format_dict_kota = {}
                    keys_to_skip = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                    for col_name in city_df_display.columns:
                        if pd.api.types.is_numeric_dtype(city_df_display[col_name]):
                            if col_name in keys_to_skip: continue
                            if "Ratio" in col_name or "Log" in col_name: format_dict_kota[col_name] = '{:.2f}'
                            else: format_dict_kota[col_name] = '{:.0f}'

                    st.dataframe(
                        city_df_display.style.format(format_dict_kota, na_rep='-') 
                                        .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - WMA)'])
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
                    pivot_cols = (
                        bulan_cols + 
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA', 'Kategori ABC (Log-Benchmark - WMA)'] +
                        ['Min Stock (Flat)', 'Min Stock (SS)', 'Min Stock (Days)'] +
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    pivot_cols_existing = [col for col in pivot_cols if col in final_result_display.columns]
                    pivot_result = final_result_display.pivot_table(index=keys, columns='City', values=pivot_cols_existing, aggfunc='first')
                    pivot_result.columns = [f"{level1}_{level0}" for level0, level1 in pivot_result.columns]
                    pivot_result.reset_index(inplace=True)
                    cities = sorted(final_result_display['City'].unique())
                    
                    metric_order = (
                        bulan_cols + 
                        ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3'] +
                        ['SO WMA', 'SO Mean', 'SO Total'] + 
                        ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA', 'Kategori ABC (Log-Benchmark - WMA)'] +
                        ['Min Stock (Flat)', 'Min Stock (SS)', 'Min Stock (Days)'] +
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    ordered_city_cols = [f"{city}_{metric}" for city in cities for metric in metric_order]
                    existing_ordered_cols = [col for col in ordered_city_cols if col in pivot_result.columns]
                    
                    total_agg = final_result_display.groupby(keys).agg(
                        All_Stock=('Stock Cabang', 'sum'), 
                        All_SO=('SO WMA', 'sum'),
                        All_Add_Stock=('Add Stock', 'sum'),
                        All_Suggested_PO=('Suggested PO', 'sum')
                    ).reset_index()
                    
                    all_sales_for_abc = total_agg.copy()
                    all_sales_for_abc.rename(columns={'All_SO': 'Total Kuantitas'}, inplace=True)
                    all_sales_for_abc['City'] = 'ALL' 
                    all_classified = classify_abc_log_benchmark(all_sales_for_abc, metric_col='Total Kuantitas') 
                    all_classified.rename(columns={'Kategori ABC (Log-Benchmark - Total Kuantitas)': 'All_Kategori ABC All'}, inplace=True)
                    total_agg['All_Restock 1 Bulan'] = np.where(total_agg['All_Stock'] < total_agg['All_SO'], 'PO', 'NO')
                    
                    pivot_result = pd.merge(pivot_result, total_agg, on=keys, how='left')
                    pivot_result = pd.merge(pivot_result, all_classified[keys + ['All_Kategori ABC All']], on=keys, how='left')
                    
                    final_summary_cols = ['All_Stock', 'All_SO', 'All_Add_Stock', 'All_Suggested_PO', 'All_Kategori ABC All', 'All_Restock 1 Bulan']
                    final_display_cols = keys + existing_ordered_cols + final_summary_cols
                    
                    df_to_style = pivot_result[final_display_cols].copy()
                    numeric_cols_to_format = []
                    float_cols_to_format = []
                    object_cols_to_format = []
                    for col in df_to_style.columns:
                        if col not in keys:
                            if "Ratio" in col or "Log" in col: float_cols_to_format.append(col)
                            elif pd.api.types.is_numeric_dtype(df_to_style[col]): numeric_cols_to_format.append(col)
                            else: object_cols_to_format.append(col)
                    
                    df_to_style[numeric_cols_to_format] = df_to_style[numeric_cols_to_format].fillna(0).astype(int) 
                    df_to_style[float_cols_to_format] = df_to_style[float_cols_to_format].fillna(0) 
                    df_to_style[object_cols_to_format] = df_to_style[object_cols_to_format].fillna('-')
                    
                    column_config_stock = {}
                    for col in numeric_cols_to_format: column_config_stock[col] = st.column_config.NumberColumn(format="%.0f")
                    for col in float_cols_to_format: column_config_stock[col] = st.column_config.NumberColumn(format="%.2f")

                    st.dataframe(df_to_style, column_config=column_config_stock, use_container_width=True)

            st.header("💾 Unduh Hasil Analisis Stock")
            output_stock = BytesIO()
            with pd.ExcelWriter(output_stock, engine='openpyxl') as writer:
                if 'df_to_style' in locals() and not df_to_style.empty:
                    df_to_style.to_excel(writer, sheet_name="All Cities Pivot", index=False)
                final_result_display.to_excel(writer, sheet_name="Filtered Data", index=False)
            st.download_button("📥 Unduh Hasil Analisis Stock (Excel)", data=output_stock.getvalue(), file_name=f"Hasil_Analisis_Stock_{start_date}_sd_{end_date}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

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
    st.title("📊 Analisis ABC Berdasarkan Metrik Penjualan Dinamis (Log-Benchmark)")
    tab1_abc, tab2_abc = st.tabs(["Hasil Tabel", "Dashboard"])

    with tab1_abc:
        # Validasi Data
        if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
            st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'** terlebih dahulu.")
            st.stop()
            
        # Preprocessing Data
        all_so_df = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        for df in [all_so_df, produk_ref]:
            if 'No. Barang' in df.columns:
                df['No. Barang'] = df['No. Barang'].astype(str).str.strip()
        so_df = all_so_df.copy()
        so_df.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')
        so_df['Nama Dept'] = so_df.apply(map_nama_dept, axis=1)
        so_df['City'] = so_df['Nama Dept'].apply(map_city)
        if 'Kategori Barang' in produk_ref.columns:
            produk_ref['Kategori Barang'] = produk_ref['Kategori Barang'].astype(str).str.strip().str.upper()
        if 'City' in so_df.columns:
            so_df['City'] = so_df['City'].astype(str).str.strip().str.upper()
        so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
        so_df.dropna(subset=['Tgl Faktur'], inplace=True)

        st.header("Filter Rentang Waktu Analisis ABC")
        st.info("Analisis akan didasarkan pada data penjualan 90 hari *sebelum* **Tanggal Akhir** yang dipilih.")
        today = datetime.now().date()
        min_date = so_df['Tgl Faktur'].min().date()
        max_date = so_df['Tgl Faktur'].max().date()
        end_date_input = st.date_input("Tanggal Akhir", value=max_date, min_value=min_date, max_value=max_date)

        if st.button("Jalankan Analisa ABC (2 Metode Log-Benchmark)"):
            with st.spinner("Melakukan perhitungan analisis ABC (Log-Benchmark)..."):
                end_date_dt = pd.to_datetime(end_date_input)
                range1_start = end_date_dt - pd.DateOffset(days=29); range1_end = end_date_dt
                range2_start = end_date_dt - pd.DateOffset(days=59); range2_end = end_date_dt - pd.DateOffset(days=30)
                range3_start = end_date_dt - pd.DateOffset(days=89); range3_end = end_date_dt - pd.DateOffset(days=60)
                start_date_90d = end_date_dt - pd.DateOffset(days=89)
                penjualan_90d = so_df[(so_df['Tgl Faktur'] >= start_date_90d) & (so_df['Tgl Faktur'] <= end_date_dt)]

                if penjualan_90d.empty:
                    st.error("Tidak ada data penjualan pada rentang 90 hari dari tanggal akhir yang dipilih.")
                    st.session_state.abc_analysis_result = None
                    st.stop()

                sales_m1 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range1_start, range1_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 1')
                sales_m2 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range2_start, range2_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 2')
                sales_m3 = penjualan_90d[penjualan_90d['Tgl Faktur'].between(range3_start, range3_end)].groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Penjualan Bln 3')

                produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
                barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
                city_list = so_df['City'].dropna().unique() 
                kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                grouped = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                
                grouped = pd.merge(grouped, sales_m1, on=['City', 'No. Barang'], how='left')
                grouped = pd.merge(grouped, sales_m2, on=['City', 'No. Barang'], how='left')
                grouped = pd.merge(grouped, sales_m3, on=['City', 'No. Barang'], how='left')
                
                grouped.fillna({'Penjualan Bln 1': 0, 'Penjualan Bln 2': 0, 'Penjualan Bln 3': 0}, inplace=True)
                grouped['AVG Mean'] = (grouped['Penjualan Bln 1'] + grouped['Penjualan Bln 2'] + grouped['Penjualan Bln 3']) / 3
                grouped['AVG WMA'] = (grouped['Penjualan Bln 1'] * 0.5) + (grouped['Penjualan Bln 2'] * 0.3) + (grouped['Penjualan Bln 3'] * 0.2)
                
                result_log_bench_mean = classify_abc_log_benchmark(grouped.copy(), metric_col='AVG Mean')
                result_log_bench_wma = classify_abc_log_benchmark(grouped.copy(), metric_col='AVG WMA')
                
                merge_keys = ['City', 'No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang', 'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA']
                result_final = result_log_bench_mean.copy()

                cols_to_keep_wma = merge_keys + [col for col in result_log_bench_wma.columns if 'Log-Benchmark - WMA' in col or 'Log (10) WMA' in col or 'Avg Log WMA' in col or 'Ratio Log WMA' in col]
                result_final = pd.merge(
                    result_final,
                    result_log_bench_wma[[col for col in cols_to_keep_wma if col not in result_final.columns or col in ['City', 'No. Barang']]],
                    on=['City', 'No. Barang'],
                    how='left'
                )

                metric_cols_int = ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA']
                for col in metric_cols_int:
                    if col in result_final.columns: result_final[col] = result_final[col].round(0).astype(int)

                metric_cols_float = ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA', 'Log (10) Mean', 'Avg Log Mean', 'Ratio Log Mean']
                for col in metric_cols_float:
                    if col in result_final.columns: result_final[col] = result_final[col].round(2)
                
                st.session_state.abc_analysis_result = result_final.copy()
                st.success("Analisis ABC (2 Metode Log-Benchmark) berhasil dijalankan!")
        
        if st.session_state.abc_analysis_result is not None:
            result_display = st.session_state.abc_analysis_result.copy()
            result_display = result_display[result_display['City'] != 'OTHERS']
            
            st.header("Filter Hasil Analisis")
            col_f1, col_f2 = st.columns(2)
            kategori_options_abc = sorted(produk_ref['Kategori Barang'].dropna().unique().astype(str))
            selected_kategori_abc = col_f1.multiselect("Filter berdasarkan Kategori:", kategori_options_abc, key="abc_cat_filter")
            brand_options_abc = sorted(produk_ref['BRAND Barang'].dropna().unique().astype(str))
            selected_brand_abc = col_f2.multiselect("Filter berdasarkan Brand:", brand_options_abc, key="abc_brand_filter")
            if selected_kategori_abc: result_display = result_display[result_display['Kategori Barang'].astype(str).isin(selected_kategori_abc)]
            if selected_brand_abc: result_display = result_display[result_display['BRAND Barang'].astype(str).isin(selected_brand_abc)]
            
            st.header("Hasil Analisis ABC per Kota")
            keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang'] 
            
            for city in sorted(result_display['City'].unique()):
                with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
                    city_df = result_display[result_display['City'] == city]
                    display_cols_order = [
                        'No. Barang', 'BRAND Barang', 'Nama Barang', 'Kategori Barang', 
                        'AVG Mean', 'AVG WMA',
                        'Kategori ABC (Log-Benchmark - Mean)', 'Kategori ABC (Log-Benchmark - WMA)', 
                        'Log (10) Mean', 'Avg Log Mean', 'Ratio Log Mean',
                        'Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA'
                    ]
                    display_cols = [col for col in display_cols_order if col in city_df.columns]
                    df_city_display = city_df[display_cols]
                    
                    format_dict_abc_kota = {}
                    for col_name in df_city_display.columns:
                        if pd.api.types.is_numeric_dtype(df_city_display[col_name]):
                            if col_name in keys: continue
                            if "Ratio" in col_name or "Log" in col_name: format_dict_abc_kota[col_name] = '{:.2f}'
                            else: format_dict_abc_kota[col_name] = '{:.0f}'

                    st.dataframe(
                        df_city_display.style.format(format_dict_abc_kota, na_rep='-')
                            .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - Mean)'])
                            .apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - WMA)']),
                        use_container_width=True
                    )
            
            st.header("📊 Tabel Gabungan Seluruh Kota (ABC)")
            with st.spinner("Membuat tabel pivot gabungan untuk ABC..."):
                pivot_values = [
                    'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA',
                    'Kategori ABC (Log-Benchmark - Mean)', 'Ratio Log Mean', 'Log (10) Mean', 'Avg Log Mean', 
                    'Kategori ABC (Log-Benchmark - WMA)', 'Ratio Log WMA', 'Log (10) WMA', 'Avg Log WMA' 
                ]
                pivot_values_existing = [col for col in pivot_values if col in result_display.columns]
                pivot_abc = result_display.pivot_table(index=keys, columns='City', values=pivot_values_existing, aggfunc='first')
                pivot_abc.columns = [f"{level1}_{level0}" for level0, level1 in pivot_abc.columns]
                pivot_abc.reset_index(inplace=True)
                
                total_abc = result_display.groupby(keys).agg({'Penjualan Bln 1': 'sum', 'Penjualan Bln 2': 'sum', 'Penjualan Bln 3': 'sum'}).reset_index()
                total_abc['AVG Mean'] = (total_abc['Penjualan Bln 1'] + total_abc['Penjualan Bln 2'] + total_abc['Penjualan Bln 3']) / 3
                total_abc['AVG WMA'] = (total_abc['Penjualan Bln 1'] * 0.5) + (total_abc['Penjualan Bln 2'] * 0.3) + (total_abc['Penjualan Bln 3'] * 0.2)
                
                metric_cols_total = ['Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3', 'AVG Mean', 'AVG WMA']
                for col in metric_cols_total:
                    if col in total_abc.columns: total_abc[col] = total_abc[col].round(0).astype(int)

                total_abc['City'] = 'ALL' 
                all_log_bench_mean = classify_abc_log_benchmark(total_abc.copy(), metric_col='AVG Mean')
                all_log_bench_wma = classify_abc_log_benchmark(total_abc.copy(), metric_col='AVG WMA') 

                total_final = total_abc.copy()
                total_final = total_final.drop(columns=['City'], errors='ignore')
                total_final = pd.merge(total_final, all_log_bench_mean[keys + [col for col in all_log_bench_mean.columns if 'Log-Benchmark - Mean' in col or 'Log (10) Mean' in col or 'Avg Log Mean' in col or 'Ratio Log Mean' in col]], on=keys, how='left')
                total_final = pd.merge(total_final, all_log_bench_wma[keys + [col for col in all_log_bench_wma.columns if 'Log-Benchmark - WMA' in col or 'Log (10) WMA' in col or 'Avg Log WMA' in col or 'Ratio Log WMA' in col]], on=keys, how='left')

                log_cols_total = ['Log (10) WMA', 'Avg Log WMA', 'Ratio Log WMA', 'Log (10) Mean', 'Avg Log Mean', 'Ratio Log Mean']
                for col in log_cols_total:
                    if col in total_final.columns: total_final[col] = total_final[col].round(2)

                total_final.columns = [f"All_{col}" if col not in keys else col for col in total_final.columns]
                pivot_abc_final = pd.merge(pivot_abc, total_final, on=keys, how='left')
                
                df_to_style_abc = pivot_abc_final.copy() 
                numeric_cols_abc = []
                float_cols_abc = [] 
                object_cols_abc = []
                for col in df_to_style_abc.columns:
                    if col not in keys:
                        if "Ratio" in col or "Log" in col: float_cols_abc.append(col)
                        elif pd.api.types.is_numeric_dtype(df_to_style_abc[col]): numeric_cols_abc.append(col)
                        else: object_cols_abc.append(col)
                            
                df_to_style_abc[numeric_cols_abc] = df_to_style_abc[numeric_cols_abc].fillna(0).astype(int) 
                df_to_style_abc[float_cols_abc] = df_to_style_abc[float_cols_abc].fillna(0) 
                df_to_style_abc[object_cols_abc] = df_to_style_abc[object_cols_abc].fillna('-')
                
                column_config_abc = {}
                for col in numeric_cols_abc: column_config_abc[col] = st.column_config.NumberColumn(format="%.0f")
                for col in float_cols_abc: column_config_abc[col] = st.column_config.NumberColumn(format="%.2f")

                st.dataframe(df_to_style_abc, column_config=column_config_abc, use_container_width=True)
                
            st.header("💾 Unduh Hasil Analisis ABC")
            output_abc = BytesIO()
            with pd.ExcelWriter(output_abc, engine='openpyxl') as writer:
                df_to_style_abc.to_excel(writer, sheet_name="All Cities Pivot", index=False)
                for city in sorted(result_display['City'].unique()):
                    result_display[result_display['City'] == city].to_excel(writer, sheet_name=city[:31], index=False)
            st.download_button("📥 Unduh Hasil Analisis ABC (Excel)",data=output_abc.getvalue(),file_name=f"Hasil_Analisis_ABC_{end_date_input}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # --- Dashboard ABC ---
        if 'abc_analysis_result' in st.session_state and st.session_state.abc_analysis_result is not None:
            result_display_dash = st.session_state.abc_analysis_result.copy()
            metode_dashboard = st.selectbox("Pilih Metode ABC untuk Dashboard:", ("Log-Benchmark - WMA", "Log-Benchmark - Mean"))
            if metode_dashboard == "Log-Benchmark - WMA": 
                kategori_col = 'Kategori ABC (Log-Benchmark - WMA)'
                metric_col = 'AVG WMA'
                kategori_labels = ['A', 'B', 'C', 'D', 'E', 'F']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e9ecef', '#6c757d']
                metric_labels = {'A': ("Produk Kelas A", "{:.1f} Rata-rata Penjualan"), 'B': ("Produk Kelas B", "{:.1f} Rata-rata Penjualan"), 'C': ("Produk Kelas C", "{:.1f} Rata-rata Penjualan"), 'D': ("Produk Kelas D", "{:.1f} Rata-rata Penjualan"), 'E': ("Produk Kelas E", "{:.1f} Rata-rata Penjualan"), 'F': ("Produk Kelas F", "Tidak Terjual")}
            elif metode_dashboard == "Log-Benchmark - Mean": 
                kategori_col = 'Kategori ABC (Log-Benchmark - Mean)'
                metric_col = 'AVG Mean'
                kategori_labels = ['A', 'B', 'C', 'D', 'E', 'F']
                colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e9ecef', '#6c757d']
                metric_labels = {'A': ("Produk Kelas A", "{:.1f} Rata-rata Penjualan"), 'B': ("Produk Kelas B", "{:.1f} Rata-rata Penjualan"), 'C': ("Produk Kelas C", "{:.1f} Rata-rata Penjualan"), 'D': ("Produk Kelas D", "{:.1f} Rata-rata Penjualan"), 'E': ("Produk Kelas E", "{:.1f} Rata-rata Penjualan"), 'F': ("Produk Kelas F", "Tidak Terjual")}

            if not result_display_dash.empty:
                abc_summary = result_display_dash.groupby(kategori_col)[metric_col].agg(['count', 'sum'])
                for label in kategori_labels:
                    if label not in abc_summary.index: abc_summary.loc[label] = [0, 0]
                abc_summary = abc_summary.reindex(kategori_labels).fillna(0)
                total_sales_sum = abc_summary['sum'].sum()
                if total_sales_sum > 0:
                    abc_summary['sum_perc'] = (abc_summary['sum'] / total_sales_sum) * 100
                    abc_summary['avg_unit'] = abc_summary['sum'] / abc_summary['count']
                else:
                    abc_summary['sum_perc'] = 0
                    abc_summary['avg_unit'] = 0
                    
                st.markdown("---")
                cols = st.columns(len(kategori_labels))
                for i, label in enumerate(kategori_labels):
                    title, delta_template = metric_labels[label]
                    count = abc_summary.loc[label, 'count']
                    if label == 'F': delta_text = "Tidak Terjual"
                    elif count == 0: delta_text = f"0.0 {metric_col.replace('AVG ', '')}"
                    else:
                        avg_unit = abc_summary.loc[label, 'avg_unit']
                        delta_text = delta_template.format(avg_unit)
                    cols[i].metric(title, f"{int(count)} SKU", delta_text)
                        
                st.markdown("---")
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Komposisi Produk per Kelas (SKU Count)")
                    data_pie = abc_summary[abc_summary['count'] > 0]
                    if not data_pie.empty:
                        fig1, ax1 = plt.subplots()
                        ax1.pie(data_pie['count'], labels=data_pie.index, autopct='%1.1f%%', startangle=90, colors=[colors[kategori_labels.index(i)] for i in data_pie.index])
                        ax1.axis('equal')
                        st.pyplot(fig1)
                    else: st.info("Tidak ada data untuk pie chart.")
                with col_chart2:
                    st.subheader(f"Kontribusi {metric_col} per Kelas")
                    data_bar = abc_summary[abc_summary['sum'] > 0]
                    if not data_bar.empty: st.bar_chart(data_bar[['sum']].rename(columns={'sum': metric_col}))
                    else: st.info("Tidak ada kontribusi penjualan untuk ditampilkan.")
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
            else: st.info("Tidak ada data untuk ditampilkan di dashboard. Sesuaikan filter Anda.")
        else: st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")

elif page == "Hasil Analisis Margin":
    st.title("💰 Hasil Analisis Margin (Placeholder)")
    st.info("Halaman ini adalah placeholder untuk analisis margin yang akan dikembangkan selanjutnya.")







