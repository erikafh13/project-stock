import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import os
import re

# Impor library untuk integrasi Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# =============================================================================
# --- KONFIGURASI & FUNGSI-FUNGSI UTAMA ---
# =============================================================================

st.set_page_config(layout="wide", page_title="Analisis ABC")

# --- FUNGSI-FUNGSI GOOGLE DRIVE & PEMBACAAN FILE ---

@st.cache_resource
def get_drive_service():
    """Membuat koneksi ke Google Drive API."""
    SCOPES = ['https://www.googleapis.com/auth/drive']
    credentials = None
    try:
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=SCOPES)
            st.sidebar.success("Terhubung ke Google Drive (Cloud).", icon="☁️")
        elif os.path.exists("credentials.json"):
            credentials = service_account.Credentials.from_service_account_file('credentials.json', scopes=SCOPES)
            st.sidebar.success("Terhubung ke Google Drive (Lokal).", icon="💻")
        if credentials: return build('drive', 'v3', credentials=credentials)
        st.sidebar.error("Kredensial Google Drive tidak ditemukan.")
        return None
    except Exception as e:
        st.sidebar.error(f"Gagal terhubung ke GDrive: {e}")
        return None

@st.cache_data
def list_files_in_folder(_service, folder_id):
    """Mengambil daftar file dalam folder tertentu."""
    if not _service: return []
    try:
        query = f"'{folder_id}' in parents and mimeType!='application/vnd.google-apps.folder'"
        results = _service.files().list(q=query, fields="files(id, name)").execute()
        return results.get('files', [])
    except Exception as e:
        st.error(f"Gagal mengambil daftar file: {e}")
        return []

def download_and_read_file(service, file_id, file_name, is_produk_ref=False):
    """Fungsi serbaguna untuk mengunduh dan membaca file dari Google Drive."""
    try:
        request = service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done: status, done = downloader.next_chunk()
        fh.seek(0)
        file_ext = file_name.lower().split('.')[-1]
        engine = 'xlrd' if file_ext == 'xls' else 'openpyxl'
        if is_produk_ref:
            df = pd.read_excel(fh, sheet_name="Sheet1 (2)", skiprows=6, usecols=[0, 1, 2, 3], engine=engine)
            df.columns = ['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']
        elif file_ext in ['xlsx', 'xls']:
            df = pd.read_excel(fh, engine=engine)
        else:
            st.warning(f"Format file '{file_name}' tidak didukung.")
            return pd.DataFrame()
        return df
    except Exception as e:
        st.error(f"Gagal membaca file '{file_name}'. Detail: {e}")
        return pd.DataFrame()

# --- FUNGSI PREPROCESSING & ANALISIS (KUNCI UTAMA) ---

def preprocess_penjualan_data(df_raw):
    """
    Membersihkan dan mempersiapkan data penjualan untuk analisis,
    menggunakan logika mapping yang persis sama dengan Stock (3).py.
    """
    df = df_raw.copy()

    # Fungsi internal untuk mapping nama department (diambil dari kode asli)
    def map_nama_dept(row):
        dept = row.get('Dept.', '')  # Ambil 'Dept.' dengan aman
        pelanggan = str(row.get('Nama Pelanggan', ''))
        
        dept_map = {
            'A': 'A - ITC' if not re.search('TOKOPEDIA|AIRPAY', pelanggan, re.IGNORECASE) else 'A - MP',
            'B': 'B - JKT', 'C': 'C - PUSAT', 'D': 'D - SBY',
            'E': 'E - MDN', 'F': 'F - BLI', 'H': 'H - JKT',
            'I': 'I - MDN', 'J': 'J - BLI', 'Y': 'Y - SBY'
        }
        return dept_map.get(dept, dept)

    # Fungsi internal untuk mapping ke city (diambil dari kode asli)
    def map_city(nama_dept):
        city_map = {
            'Surabaya': ['A - ITC', 'A - MP', 'C - PUSAT', 'D - SBY', 'Y - SBY'],
            'Jakarta': ['B - JKT', 'H - JKT'],
            'Medan': ['E - MDN', 'I - MDN'],
            'Bali': ['F - BLI', 'J - BLI']
        }
        for city, depts in city_map.items():
            if nama_dept in depts:
                return city
        return None

    # 1. Terapkan mapping bertingkat persis seperti kode asli
    df['nama_dept'] = df.apply(map_nama_dept, axis=1)
    df['City'] = df['nama_dept'].apply(map_city)

    # 2. Ganti nama kolom agar konsisten
    rename_map = {
        'No. Faktur': 'No_Invoice',
        'Tgl Faktur': 'Tgl_Invoice',
        'Dept.': 'Kode_Dept',
        'Qty': 'Kuantitas'
    }
    df.rename(columns=rename_map, inplace=True)

    # 3. Bersihkan data & konversi tipe data
    df.dropna(subset=['City'], inplace=True)
    df['Tgl_Invoice'] = pd.to_datetime(df['Tgl_Invoice'])
    return df

def classify_abc_dynamic(df, metric_col):
    """Mengklasifikasikan produk ke dalam kategori A, B, C, atau D."""
    df_sales = df[df[metric_col] > 0].copy()
    df_no_sales = df[df[metric_col] <= 0].copy()
    df_no_sales['Kategori_ABC'] = 'D'
    df_no_sales['Kontribusi'] = 0
    df_no_sales['Kontribusi_Kumulatif'] = 1
    if not df_sales.empty:
        df_sales = df_sales.sort_values(by=metric_col, ascending=False)
        total_metric = df_sales[metric_col].sum()
        df_sales['Kontribusi'] = (df_sales[metric_col] / total_metric)
        df_sales['Kontribusi_Kumulatif'] = df_sales['Kontribusi'].cumsum()
        conditions = [
            df_sales['Kontribusi_Kumulatif'] <= 0.70,
            (df_sales['Kontribusi_Kumulatif'] > 0.70) & (df_sales['Kontribusi_Kumulatif'] <= 0.90)
        ]
        choices = ['A', 'B']
        df_sales['Kategori_ABC'] = np.select(conditions, choices, default='C')
        result_df = pd.concat([df_sales, df_no_sales], ignore_index=True)
    else:
        result_df = df_no_sales
    return result_df.sort_values(by=['Kategori_ABC', metric_col], ascending=[True, False])

@st.cache_data
def convert_df_to_excel(df):
    """Mengonversi DataFrame ke format Excel untuk diunduh."""
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    return output.getvalue()

# =============================================================================
# --- UI & LOGIKA APLIKASI ---
# =============================================================================

st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis ABC")
page = st.sidebar.radio("Menu Navigasi:",("Input Data", "Hasil Analisa ABC"))
st.sidebar.markdown("---")

if 'df_penjualan' not in st.session_state: st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state: st.session_state.produk_ref = pd.DataFrame()

drive_service = get_drive_service()
DRIVE_AVAILABLE = drive_service is not None
folder_penjualan = "1Okgw8qHVM8HyBwnTUFHbmYkNKqCcswNZ"
folder_produk = "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv"

if page == "Input Data":
    st.title("📥 Input Data")
    st.markdown("Muat data yang diperlukan dari Google Drive.")
    if not DRIVE_AVAILABLE:
        st.warning("Koneksi ke Google Drive gagal.")
        st.stop()
    st.header("1. Data Penjualan")
    with st.spinner("Mencari file penjualan..."):
        penjualan_files_list = list_files_in_folder(drive_service, folder_penjualan)
        st.info(f"Ditemukan {len(penjualan_files_list)} file di folder penjualan.")
    if st.button("Muat / Muat Ulang Data Penjualan", type="primary"):
        if penjualan_files_list:
            with st.spinner("Mengunduh dan menggabungkan file..."):
                list_of_dfs = [download_and_read_file(drive_service, f['id'], f['name']) for f in penjualan_files_list]
                valid_dfs = [df for df in list_of_dfs if not df.empty]
                if valid_dfs:
                    st.session_state.df_penjualan = pd.concat(valid_dfs, ignore_index=True)
                    st.success("Semua data penjualan berhasil digabungkan.")
                else: st.error("Gagal memuat data dari semua file penjualan.")
        else: st.warning("⚠️ Tidak ada file penjualan ditemukan.")
    if not st.session_state.df_penjualan.empty:
        st.success(f"✅ Data penjualan dimuat: {len(st.session_state.df_penjualan)} baris.")
        st.dataframe(st.session_state.df_penjualan.head())
    st.markdown("---")
    st.header("2. Produk Referensi")
    with st.spinner("Mencari file produk..."):
        produk_files_list = list_files_in_folder(drive_service, folder_produk)
    selected_produk_file = st.selectbox("Pilih file Produk dari Google Drive:", options=[None] + produk_files_list, format_func=lambda x: x['name'] if x else "Pilih file")
    if selected_produk_file:
        with st.spinner(f"Memuat file {selected_produk_file['name']}..."):
            df_produk = download_and_read_file(drive_service, selected_produk_file['id'], selected_produk_file['name'], is_produk_ref=True)
            if not df_produk.empty:
                 st.session_state.produk_ref = df_produk
                 st.success(f"File produk referensi '{selected_produk_file['name']}' berhasil dimuat.")
    if not st.session_state.produk_ref.empty:
         st.dataframe(st.session_state.produk_ref.head())

elif page == "Hasil Analisa ABC":
    st.title("📊 Hasil Analisa ABC")
    st.markdown("Klasifikasi produk berdasarkan kontribusi penjualannya.")
    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
        st.warning("Data belum lengkap. Silakan muat file Penjualan dan Produk di halaman 'Input Data'.")
    else:
        st.sidebar.header("Filter Analisis ABC")
        try:
            # --- MENGGUNAKAN FUNGSI PREPROCESSING BARU ---
            df_penjualan = preprocess_penjualan_data(st.session_state.df_penjualan)
            produk_ref = st.session_state.produk_ref.copy()
            
            period_option = st.sidebar.selectbox("Pilih Periode Waktu:", ("7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir", "Kustom"))
            today = datetime.now().date()
            if period_option == "7 Hari Terakhir": start_date, end_date = today - timedelta(days=7), today
            elif period_option == "30 Hari Terakhir": start_date, end_date = today - timedelta(days=30), today
            elif period_option == "90 Hari Terakhir": start_date, end_date = today - timedelta(days=90), today
            else: 
                start_date = st.sidebar.date_input("Tanggal Mulai", today - timedelta(days=30))
                end_date = st.sidebar.date_input("Tanggal Selesai", today)

            if st.sidebar.button("Jalankan Analisis", type="primary"):
                mask = (df_penjualan['Tgl_Invoice'].dt.date >= start_date) & (df_penjualan['Tgl_Invoice'].dt.date <= end_date)
                filtered_sales = df_penjualan.loc[mask]
                if filtered_sales.empty:
                    st.error("Tidak ada data penjualan pada rentang tanggal yang dipilih.")
                    if 'final_abc_result' in st.session_state: del st.session_state.final_abc_result
                else:
                    with st.spinner("Melakukan kalkulasi ABC..."):
                        sales_metric = filtered_sales.groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index()
                        sales_metric.rename(columns={'Kuantitas': 'Metrik_Penjualan'}, inplace=True)
                        
                        cities = sales_metric['City'].unique()
                        produk_cols_to_merge = ['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']
                        
                        # Filter produk_ref agar hanya berisi kolom yang dibutuhkan
                        produk_ref_filtered = produk_ref[produk_cols_to_merge]
                        
                        all_products_all_cities = [produk_ref_filtered.assign(City=city) for city in cities]
                        full_product_list = pd.concat(all_products_all_cities, ignore_index=True)
                        
                        analysis_df = pd.merge(full_product_list, sales_metric, on=['City', 'No. Barang'], how='left').fillna(0)
                        
                        result_list = [classify_abc_dynamic(analysis_df[analysis_df['City'] == city], 'Metrik_Penjualan') for city in analysis_df['City'].unique()]
                        st.session_state.final_abc_result = pd.concat(result_list, ignore_index=True)
            
            if 'final_abc_result' in st.session_state and not st.session_state.final_abc_result.empty:
                result_display = st.session_state.final_abc_result.copy()
                result_display['Kontribusi'] = (result_display['Kontribusi'] * 100).map('{:.2f}%'.format)
                result_display['Kontribusi_Kumulatif'] = (result_display['Kontribusi_Kumulatif'] * 100).map('{:.2f}%'.format)

                tab1, tab2 = st.tabs(["📑 Hasil Tabel", "📈 Dashboard"])

                with tab1:
                    st.header("Tabel Hasil Analisis ABC")
                    excel_data = convert_df_to_excel(result_display)
                    st.download_button(label="📥 Unduh Hasil (Excel)", data=excel_data, file_name=f'Analisis_ABC_{start_date}_to_{end_date}.xlsx')
                    for city in sorted(result_display['City'].unique()):
                        with st.expander(f"Hasil untuk Kota: {city}"):
                            city_data = result_display[result_display['City'] == city]
                            st.dataframe(city_data.style.apply(lambda row: ['background-color: #cce5ff']*len(row) if row.Kategori_ABC == 'A' else ['background-color: #d4edda']*len(row) if row.Kategori_ABC == 'B' else ['background-color: #fff3cd']*len(row) if row.Kategori_ABC == 'C' else ['background-color: #f8d7da']*len(row), axis=1))
                
                with tab2:
                    st.header("Dashboard Visual")
                    dash_df = st.session_state.final_abc_result.copy()
                    abc_summary = dash_df.groupby('Kategori_ABC').agg(count=('No. Barang', 'size'), sum_metric=('Metrik_Penjualan', 'sum')).reset_index()
                    total_sales = abc_summary['sum_metric'].sum()
                    if total_sales > 0: abc_summary['sum_perc'] = (abc_summary['sum_metric'] / total_sales) * 100
                    else: abc_summary['sum_perc'] = 0
                    col1, col2, col3, col4 = st.columns(4)
                    metrics = {'A': col1, 'B': col2, 'C': col3, 'D': col4}
                    for category, col in metrics.items():
                        data = abc_summary[abc_summary['Kategori_ABC'] == category]
                        if not data.empty:
                            col.metric(label=f"SKU Kelas {category}", value=f"{data['count'].iloc[0]}", help=f"Kontribusi: {data['sum_perc'].iloc[0]:.2f}% dari total penjualan")
                        else: col.metric(label=f"SKU Kelas {category}", value="0")
                    st.markdown("---")
                    col_chart1, col_chart2 = st.columns(2)
                    with col_chart1:
                        st.subheader("Komposisi Produk per Kelas")
                        fig1, ax1 = plt.subplots()
                        ax1.pie(abc_summary['count'], labels=abc_summary['Kategori_ABC'], autopct='%1.1f%%', startangle=90, colors=['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da'])
                        ax1.axis('equal')
                        st.pyplot(fig1)
                    with col_chart2:
                        st.subheader("Kontribusi Penjualan per Kelas")
                        st.bar_chart(abc_summary.set_index('Kategori_ABC')[['sum_perc']].rename(columns={'sum_perc': 'Kontribusi Penjualan (%)'}))
                    st.markdown("---")
                    col_top1, col_top2 = st.columns(2)
                    with col_top1:
                        st.subheader("Top 10 Produk Terlaris (Global)")
                        top_products = dash_df.groupby('Nama Barang')['Metrik_Penjualan'].sum().nlargest(10)
                        st.bar_chart(top_products)
                    with col_top2:
                        st.subheader("Total Penjualan per Kota")
                        city_sales = dash_df.groupby('City')['Metrik_Penjualan'].sum().sort_values(ascending=False)
                        st.bar_chart(city_sales)
            else:
                st.info("Klik tombol 'Jalankan Analisis' di sidebar untuk melihat hasilnya.")
        
        except KeyError as e:
            st.error(f"Error: Kolom yang dibutuhkan untuk mapping tidak ditemukan: {e}")
            st.warning("Pastikan file Excel penjualan Anda memiliki kolom 'Dept.' dan 'Nama Pelanggan'. Cek kembali nama kolom di file asli.")
            st.info(f"Nama kolom yang ada di data Anda: {st.session_state.df_penjualan.columns.to_list()}")
        except Exception as e:
            st.error(f"Terjadi error yang tidak terduga saat analisis: {e}")
