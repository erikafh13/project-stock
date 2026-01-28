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
import xgboost as xgb  # Library tambahan untuk XGBoost

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis Stock & ABC - Hybrid XGBoost")

# --- SIDEBAR ---
st.sidebar.image("https://eq-cdn.equiti-me.com/website/images/What_does_a_stock_split_mean.2e16d0ba.fill-1600x900.jpg", use_container_width=True)
st.sidebar.title("Analisis Stock dan ABC (Hybrid)")

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
# 			 			 	 	 MODUL HYBRID XGBOOST (FIXED)
# =====================================================================================

# 1. PREPROCESSING DATA
def preprocess_data_xgb(df_penjualan):
    d_clean = df_penjualan.copy()
    # [FIX] Pastikan konversi tipe data yang ketat (errors='coerce' akan mengubah error jadi NaN)
    d_clean['Tgl Faktur'] = pd.to_datetime(d_clean['Tgl Faktur'], errors='coerce')
    d_clean['Kuantitas'] = pd.to_numeric(d_clean['Kuantitas'], errors='coerce')
    
    d_clean = d_clean.dropna(subset=['Tgl Faktur', 'Kuantitas'])
    d_clean = d_clean.sort_values(by='Tgl Faktur', ascending=True)
    return d_clean

# 2. PERHITUNGAN WMA (BASELINE) - Digunakan di dalam Build Features
def compute_wma_value(series, weights):
    # series adalah array numpy dari penjualan harian
    if len(series) < len(weights):
        # Jika data kurang dari 90 hari, ambil rata-rata saja sebagai fallback
        return series.mean() * 30 if len(series) > 0 else 0 
        # *30 karena compute_wma_value ekspektasinya skala bulanan (weights sum=30)
    
    return np.dot(series[-len(weights):], weights)

# 3. FEATURE ENGINEERING UNTUK XGBOOST
def build_features_xgb(df_daily_all, city, sku, weights, min_date, max_date):
    # Filter data spesifik SKU dan City
    sku_data = df_daily_all[(df_daily_all['City'] == city) & (df_daily_all['No. Barang'] == sku)].copy()
    
    # [FIX CRITICAL BUG] Reindexing Date agar continuous (mengisi hari kosong dengan 0)
    if sku_data.empty:
        return pd.DataFrame(), None
        
    sku_data.set_index('Tgl Faktur', inplace=True)
    full_idx = pd.date_range(start=min_date, end=max_date, freq='D')
    sku_data = sku_data.reindex(full_idx, fill_value=0)
    sku_data['City'] = city
    sku_data['No. Barang'] = sku
    sku_data.index.name = 'Tgl Faktur'
    sku_data = sku_data.reset_index()
    
    # Total minimal = 30 (Lags) + 30 (Target) = 60 hari aman untuk training
    if len(sku_data) < 60:
        return pd.DataFrame(), None

    # [TARGET LOG-TRANSFORM] Menggunakan Log-Space untuk mengurangi dampak outlier
    # Target = Rolling Sum 30 Hari ke depan
    rolling_future = sku_data['Kuantitas'].rolling(window=30, min_periods=1).sum().shift(-30)
    sku_data['target'] = np.log1p(rolling_future) # Log Transformation
    
    # Lag Features (Harian)
    sku_data['Demand_t1'] = sku_data['Kuantitas'].shift(1)
    sku_data['Demand_t7'] = sku_data['Kuantitas'].shift(7)
    sku_data['Demand_t30'] = sku_data['Kuantitas'].shift(30)
    
    # Rolling Statistics
    sku_data['RollingMean_7'] = sku_data['Kuantitas'].rolling(window=7).mean()
    sku_data['RollingMean_30'] = sku_data['Kuantitas'].rolling(window=30).mean()
    sku_data['RollingStd_30'] = sku_data['Kuantitas'].rolling(window=30).std()
    
    # Temporal Features
    sku_data['DayOfWeek'] = sku_data['Tgl Faktur'].dt.dayofweek
    sku_data['Month'] = sku_data['Tgl Faktur'].dt.month
    
    # SO_WMA Feature (Rolling WMA) - Pastikan scale-nya match
    # Kita apply rolling window 90 hari, lalu dot product
    sku_data['SO_WMA_t'] = sku_data['Kuantitas'].rolling(window=90).apply(lambda x: compute_wma_value(x, weights), raw=True)
    
    # Data untuk training (hapus baris dengan NaN)
    # Target NaN di 30 hari terakhir (karena shift -30), Features NaN di awal
    train_data = sku_data.dropna(subset=['target', 'SO_WMA_t', 'RollingStd_30'])
    
    # Data terakhir untuk prediksi (hari ini)
    latest_feature = sku_data.iloc[[-1]].copy() # Ambil baris terakhir
    
    return train_data, latest_feature

# 4 & 5. TRAINING & PREDIKSI HYBRID
def predict_hybrid_so(df_penjualan, list_sku_city):
    # Agregasi penjualan harian
    df_daily = df_penjualan.groupby(['City', 'No. Barang', 'Tgl Faktur'])['Kuantitas'].sum().reset_index()
    
    # Tentukan range tanggal global untuk reindexing
    min_date = df_daily['Tgl Faktur'].min()
    max_date = df_daily['Tgl Faktur'].max()
    
    # Penyiapan bobot WMA (Sum = 30, Skala Bulanan)
    w = [0.2]*30 + [0.3]*30 + [0.5]*30 
    
    results = []
    
    # Progress bar
    progress_text = "Menjalankan Algorithm Hybrid_WMA_XGBoost_Forecasting..."
    my_bar = st.progress(0, text=progress_text)
    total = len(list_sku_city)
    
    # Training Global Model
    all_train_data = []
    latest_features_map = {}

    for i, (city, sku) in enumerate(list_sku_city):
        if i % 50 == 0:
            my_bar.progress(i/total, text=f"{progress_text} (Building Features {i}/{total})")
            
        train_df, latest_f = build_features_xgb(df_daily, city, sku, w, min_date, max_date)
        if not train_df.empty:
            all_train_data.append(train_df)
        if latest_f is not None:
            latest_features_map[(city, sku)] = latest_f

    if not all_train_data:
        my_bar.empty()
        return pd.DataFrame() # Return empty if no training data

    full_train_df = pd.concat(all_train_data)
    
    # [FIX] Reset Index sangat penting agar tidak ada index duplikat yang membingungkan XGBoost
    full_train_df.reset_index(drop=True, inplace=True)
    
    # Define Features
    features = ['SO_WMA_t', 'Demand_t1', 'Demand_t7', 'Demand_t30', 
                'RollingMean_7', 'RollingMean_30', 'RollingStd_30', 'DayOfWeek', 'Month']
    
    X = full_train_df[features]
    y = full_train_df['target'] 
    
    # [FIX] Konversi ke Numpy Array (.values) dan float untuk menghindari error metadata Pandas dan tipe object
    X_np = X.astype(float).values
    y_np = y.astype(float).values

    # 4. Train XGBoost
    model = xgb.XGBRegressor(
        n_estimators=100,
        learning_rate=0.05,
        max_depth=4, 
        objective='reg:squarederror',
        n_jobs=-1
    )
    
    # Gunakan numpy array untuk fit
    model.fit(X_np, y_np)
    
    # 5. Predict Hybrid
    my_bar.progress(0.9, text="Generating Hybrid Forecast...")
    
    for (city, sku), feat in latest_features_map.items():
        # Cek kelengkapan fitur pada data terakhir
        if feat[features].isnull().values.any():
            # Fallback ke WMA jika fitur incomplete (misal data baru < 90 hari)
            so_hybrid = feat['SO_WMA_t'].values[0] if 'SO_WMA_t' in feat else 0
        else:
            # Prediksi (Log Space)
            # Pastikan input prediksi juga float numpy array
            feat_X = feat[features].astype(float).values
            pred_log = model.predict(feat_X)[0]
            # Inverse Transform (Exp)
            so_hybrid = np.expm1(pred_log)
            
        # Pastikan tidak negatif dan handling NaN
        so_hybrid = max(0, float(so_hybrid))
        if pd.isna(so_hybrid): so_hybrid = 0
        
        results.append({'City': city, 'No. Barang': sku, 'SO Hybrid': so_hybrid})
    
    my_bar.empty()
    return pd.DataFrame(results)

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
    st.title("📈 Hasil Analisa Stock (Hybrid XGBoost)")

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
        kategori_log = row['Kategori ABC (Log-Benchmark - Hybrid)'] 
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
            # Kebutuhan 30 hari kini menggunakan SO Hybrid
            kebutuhan_30_hari = (so_cabang) 
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
        with st.spinner("Melakukan perhitungan analisis stok dengan Hybrid Model..."):
            
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

                # BASELINE: WMA
                wma_grouped = penjualan_for_wma.groupby(['City', 'No. Barang']).apply(calculate_daily_wma, end_date=end_date).reset_index(name='AVG WMA')
                
                # --- HYBRID XGBOOST FLOW ---
                # 1. Preprocess
                d_clean_xgb = preprocess_data_xgb(penjualan)
                # List SKU City untuk diproses
                sku_city_list = wma_grouped[['City', 'No. Barang']].values.tolist()
                # 3, 4, 5. Build Features, Train, Predict
                df_hybrid_forecast = predict_hybrid_so(d_clean_xgb, sku_city_list)
                
                # Merge hasil Hybrid ke data utama
                barang_list = produk_ref[['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']].drop_duplicates()
                city_list = penjualan['City'].unique()
                kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                full_data = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                
                full_data = pd.merge(full_data, wma_grouped, on=['City', 'No. Barang'], how='left')
                full_data = pd.merge(full_data, df_hybrid_forecast, on=['City', 'No. Barang'], how='left')
                
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
                
                full_data.rename(columns={'AVG WMA': 'SO WMA', 'AVG Mean': 'SO Mean', 'SO Hybrid': 'SO Hybrid'}, inplace=True)
                
                # MODIFIKASI PENELITIAN: SO Total kini berbasis SO Hybrid
                full_data['SO Total'] = full_data['SO Hybrid'] 
                
                final_result = full_data.copy() 
                
                # 6. INVENTORY ANALYSIS (ABC Class menggunakan SO Hybrid)
                log_df = classify_abc_log_benchmark(final_result.copy(), metric_col='SO Hybrid')
                
                final_result = pd.merge(
                    final_result, 
                    log_df[['City', 'No. Barang', 'Kategori ABC (Log-Benchmark - Hybrid)', 'Ratio Log Hybrid', 'Log (10) Hybrid', 'Avg Log Hybrid']], 
                    on=['City', 'No. Barang'], 
                    how='left'
                )

                # INVENTORY ANALYSIS: Min Stock & Max Stock (Berbasis SO Hybrid)
                def get_days_multiplier(kategori):                    
                    days_map = {'A': 1, 'B': 1, 'C': 0.5, 'D': 0.3, 'E': 0.25, 'F': 0.0}
                    return days_map.get(kategori, 1.0)

                def calculate_min_stock_hybrid(row):
                    so_val = row['SO Hybrid']
                    cat = row.get('Kategori ABC (Log-Benchmark - Hybrid)', 'E')
                    if so_val <= 0: return 0
                    day_mult = get_days_multiplier(cat)
                    return math.ceil(so_val * day_mult)

                final_result['Min Stock'] = final_result.apply(calculate_min_stock_hybrid, axis=1)

                def calculate_dynamic_max_stock_hybrid(row):
                    so_val = row['SO Hybrid']
                    kategori = row.get('Kategori ABC (Log-Benchmark - Hybrid)', 'E')
                    if kategori in ['A', 'B']: multiplier = 2.0
                    elif kategori == 'C': multiplier = 1.5
                    elif kategori in ['D', 'E']: multiplier = 1.0
                    else: multiplier = 0.0
                    return math.ceil(so_val * multiplier)
                
                final_result['Max Stock'] = final_result.apply(calculate_dynamic_max_stock_hybrid, axis=1)

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
                final_result = final_result.merge(total_req_df, on='No. Barang', how='left') 
                
                final_result.fillna(0, inplace=True)
                
                # PO Berbasis SO Hybrid
                final_result['Suggested PO'] = final_result.apply(lambda row: hitung_po_cabang_baru(stock_surabaya=row['Stock Surabaya'], stock_cabang=row['Stock Cabang'], stock_total=row['Stock Total'], total_add_stock_all=row['Total Add Stock All'], so_cabang=row['SO Hybrid'], add_stock_cabang=row['Add Stock']), axis=1)
                
                # --- PEMBULATAN ---
                numeric_cols = ['Stock Cabang', 'Min Stock', 'Max Stock', 'Add Stock', 'Total Add Stock All', 'Suggested PO', 'Stock Surabaya', 'Stock Total', 'SO WMA', 'SO Hybrid', 'SO Mean', 'Penjualan Bln 1', 'Penjualan Bln 2', 'Penjualan Bln 3']
                numeric_cols.extend(bulan_columns_renamed)

                for col in numeric_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(0).astype(int)
                
                float_cols = ['Log (10) Hybrid', 'Avg Log Hybrid', 'Ratio Log Hybrid']
                for col in float_cols:
                    if col in final_result.columns:
                        final_result[col] = final_result[col].round(2)
                
                st.session_state.stock_analysis_result = final_result.copy()
                st.session_state.bulan_columns_stock = bulan_columns_renamed 
                st.success("Analisis Stok Hybrid (WMA-XGBoost) berhasil dijalankan!")

    if st.session_state.stock_analysis_result is not None:
        final_result_to_filter = st.session_state.stock_analysis_result.copy()
        final_result_to_filter = final_result_to_filter[final_result_to_filter['City'] != 'OTHERS'] 
        bulan_cols = st.session_state.get('bulan_columns_stock', [])
        
        st.markdown("---")
        st.header("Filter Produk")
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
        
        st.header("Filter Hasil")
        col_h1, col_h2 = st.columns(2)
        abc_log_options = sorted(final_result_display['Kategori ABC (Log-Benchmark - Hybrid)'].dropna().unique().astype(str))
        selected_abc_log = col_h1.multiselect("Kategori ABC (Log-Benchmark):", abc_log_options)
        status_options = sorted(final_result_display['Status Stock'].dropna().unique().astype(str))
        selected_status = col_h2.multiselect("Status Stock:", status_options) 
        
        st.markdown("---")
        tab1, tab2 = st.tabs(["Hasil Tabel", "Dashboard"])

        with tab1:
            header_style = {'selector': 'th', 'props': [('background-color', '#0068c9'), ('color', 'white'), ('text-align', 'center')]}
            st.header("Hasil Analisis Stok per Kota")

            for city in sorted(final_result_display['City'].unique()):
                with st.expander(f"📍 Kota: {city}"):
                    city_df = final_result_display[final_result_display['City'] == city].copy()
                    if selected_abc_log: city_df = city_df[city_df['Kategori ABC (Log-Benchmark - Hybrid)'].isin(selected_abc_log)]
                    if selected_status: city_df = city_df[city_df['Status Stock'].isin(selected_status)]
                    
                    metric_order_kota = (
                        bulan_cols + 
                        ['SO WMA', 'SO Hybrid', 'SO Mean'] + 
                        ['Ratio Log Hybrid', 'Kategori ABC (Log-Benchmark - Hybrid)'] +
                        ['Min Stock', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock', 'Suggested PO']
                    )
                    display_cols_kota = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang'] + [col for col in metric_order_kota if col in city_df.columns]
                    
                    st.dataframe(
                        city_df[display_cols_kota].style.apply(lambda x: x.map(highlight_kategori_abc_log), subset=['Kategori ABC (Log-Benchmark - Hybrid)'])
                                        .apply(lambda x: x.map(highlight_status_stock), subset=['Status Stock'])
                                        .set_table_styles([header_style]), 
                        use_container_width=True
                    )
            
            st.header("📊 Tabel Gabungan")
            st.dataframe(final_result_display, use_container_width=True)
            
            # --- FITUR DOWNLOAD ---
            st.markdown("---")
            st.header("💾 Unduh Hasil Analisis")
            
            # Persiapan data Excel
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Sheet 1: Data Gabungan yang difilter
                final_result_display.to_excel(writer, sheet_name='Analisis_Hybrid_Summary', index=False)
                
                # Sheet per Kota (hanya jika ada data)
                for city in sorted(final_result_display['City'].unique()):
                    city_data = final_result_display[final_result_display['City'] == city]
                    sheet_name = city[:31] # Limit excel sheet name length
                    city_data.to_excel(writer, sheet_name=sheet_name, index=False)
            
            st.download_button(
                label="📥 Unduh Hasil Analisis (Excel)",
                data=output.getvalue(),
                file_name=f"Hasil_Analisis_Hybrid_{datetime.now().strftime('%Y%m%d_%H%M')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                help="Klik untuk mengunduh seluruh hasil analisis dalam format Excel."
            )

elif page == "Hasil Analisa ABC":
    st.title("📊 Analisis ABC Hybrid (XGBoost)")
    st.info("Fitur Analisis ABC kini terintegrasi dengan SO Hybrid pada menu Analisis Stock.")

elif page == "Hasil Analisis Margin":
    st.title("💰 Hasil Analisis Margin (Placeholder)")
    st.info("Halaman ini adalah placeholder.")
