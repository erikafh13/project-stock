import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Impor library untuk integrasi Google Drive
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import io

# --- FUNGSI UTAMA & KONFIGURASI ---

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis ABC")

# --- FUNGSI-FUNGSI GOOGLE DRIVE ---

# Cache resource untuk koneksi ke Google API
@st.cache_resource
def get_service():
    """Membuat dan mengembalikan service object untuk Google Drive API."""
    creds_dict = st.secrets["gcp_service_account"]
    creds = service_account.Credentials.from_service_account_info(creds_dict)
    service = build('drive', 'v3', credentials=creds)
    return service

@st.cache_data
def list_folders(_service, folder_id='root'):
    """Mengambil daftar folder dari Google Drive."""
    query = "mimeType='application/vnd.google-apps.folder'"
    results = _service.files().list(q=query, pageSize=100, fields="nextPageToken, files(id, name)").execute()
    items = results.get('files', [])
    return {item['name']: item['id'] for item in items}

@st.cache_data
def list_files_in_folder(_service, folder_id):
    """Mengambil daftar file dalam folder tertentu, diurutkan dari yang terbaru."""
    query = f"'{folder_id}' in parents"
    results = _service.files().list(q=query, orderBy='createdTime desc', pageSize=10, fields="files(id, name)").execute()
    return {item['name']: item['id'] for item in results.get('files', [])}

def load_data_from_drive(service, file_id):
    """Mengunduh dan memuat file Excel dari Google Drive ke DataFrame."""
    request = service.files().get_media(fileId=file_id)
    fh = io.BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done:
        status, done = downloader.next_chunk()
    fh.seek(0)
    return pd.read_excel(fh, engine='openpyxl')

# --- FUNGSI ANALISIS ABC ---

def classify_abc_dynamic(df, metric_col):
    """
    Mengklasifikasikan produk ke dalam kategori A, B, C, atau D berdasarkan metrik penjualan.
    - A: Top 70% kontribusi kumulatif
    - B: 70% - 90% kontribusi kumulatif
    - C: > 90% kontribusi kumulatif
    - D: Metrik penjualan <= 0
    """
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

# Fungsi untuk mengonversi DataFrame ke Excel untuk diunduh
@st.cache_data
def to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data

# --- UI & LOGIKA APLIKASI ---

# --- SIDEBAR & NAVIGASI ---
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis ABC")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa ABC"),
    help="Pilih halaman untuk ditampilkan."
)
st.sidebar.markdown("---")

# Inisialisasi Session State
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()

# --- HALAMAN INPUT DATA ---
if page == "Input Data":
    st.title("📥 Input Data dari Google Drive")
    st.markdown("Pilih folder di Google Drive yang berisi file data yang diperlukan. Sistem akan otomatis mengambil file **terbaru** dari folder yang dipilih.")

    try:
        service = get_service()
        all_folders = list_folders(service)

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("1. Folder Penjualan")
            folder_penjualan = st.selectbox("Pilih folder untuk data penjualan:", options=list(all_folders.keys()), key="folder_jual")
        
        with col2:
            st.subheader("2. Folder Referensi Produk")
            folder_produk = st.selectbox("Pilih folder untuk data referensi produk:", options=list(all_folders.keys()), key="folder_prod")

        if st.button("Load Data dari Drive", type="primary"):
            with st.spinner("Mengambil data dari Google Drive..."):
                # Load data penjualan
                if folder_penjualan:
                    folder_id_penjualan = all_folders[folder_penjualan]
                    files_penjualan = list_files_in_folder(service, folder_id_penjualan)
                    if files_penjualan:
                        latest_file_name = next(iter(files_penjualan))
                        latest_file_id = files_penjualan[latest_file_name]
                        st.session_state.df_penjualan = load_data_from_drive(service, latest_file_id)
                        st.success(f"File penjualan '{latest_file_name}' berhasil dimuat.")
                    else:
                        st.error(f"Tidak ada file ditemukan di folder '{folder_penjualan}'.")

                # Load data referensi produk
                if folder_produk:
                    folder_id_produk = all_folders[folder_produk]
                    files_produk = list_files_in_folder(service, folder_id_produk)
                    if files_produk:
                        latest_file_name = next(iter(files_produk))
                        latest_file_id = files_produk[latest_file_name]
                        st.session_state.produk_ref = load_data_from_drive(service, latest_file_id)
                        st.success(f"File referensi produk '{latest_file_name}' berhasil dimuat.")
                    else:
                        st.error(f"Tidak ada file ditemukan di folder '{folder_produk}'.")
    except Exception as e:
        st.error(f"Terjadi kesalahan saat terhubung ke Google Drive: {e}")
        st.info("Pastikan Anda telah mengatur kredensial 'gcp_service_account' di Streamlit Secrets.")

    st.markdown("---")
    st.header("Pratinjau Data yang Dimuat")
    
    if not st.session_state.df_penjualan.empty:
        st.write("Data Penjualan:")
        st.dataframe(st.session_state.df_penjualan.head())
    else:
        st.info("Data Penjualan belum dimuat.")

    if not st.session_state.produk_ref.empty:
        st.write("Data Referensi Produk:")
        st.dataframe(st.session_state.produk_ref.head())
    else:
        st.info("Data Referensi Produk belum dimuat.")

# --- HALAMAN HASIL ANALISA ABC ---
elif page == "Hasil Analisa ABC":
    # (Kode untuk halaman 'Hasil Analisa ABC' sama persis seperti kode sebelumnya, tidak perlu diubah)
    st.title("📊 Hasil Analisa ABC")
    st.markdown("Analisis ini mengklasifikasikan produk berdasarkan kontribusi penjualannya.")

    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
        st.warning("Data belum lengkap. Silakan muat file Penjualan dan Referensi Produk di halaman 'Input Data'.")
    else:
        st.sidebar.header("Filter Analisis ABC")
        map_nama_dept = {'BL': 'Bali', 'JK': 'Jakarta', 'MD': 'Medan', 'SB': 'Surabaya'}
        
        df_penjualan_raw = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        
        df_penjualan = df_penjualan_raw.rename(columns={'No. Invoice': 'No_Invoice', 'Tgl. Invoice': 'Tgl_Invoice', 'Dept': 'Kode_Dept'})
        df_penjualan['City'] = df_penjualan['Kode_Dept'].map(map_nama_dept)
        df_penjualan = df_penjualan.dropna(subset=['City'])
        df_penjualan['Tgl_Invoice'] = pd.to_datetime(df_penjualan['Tgl_Invoice'])
        
        period_option = st.sidebar.selectbox("Pilih Periode Waktu:", ("7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir", "Kustom"))

        today = datetime.now().date()
        if period_option == "7 Hari Terakhir":
            start_date, end_date = today - timedelta(days=7), today
        elif period_option == "30 Hari Terakhir":
            start_date, end_date = today - timedelta(days=30), today
        elif period_option == "90 Hari Terakhir":
            start_date, end_date = today - timedelta(days=90), today
        else: # Kustom
            start_date = st.sidebar.date_input("Tanggal Mulai", today - timedelta(days=30))
            end_date = st.sidebar.date_input("Tanggal Selesai", today)

        if st.sidebar.button("Jalankan Analisis"):
            mask = (df_penjualan['Tgl_Invoice'].dt.date >= start_date) & (df_penjualan['Tgl_Invoice'].dt.date <= end_date)
            filtered_sales = df_penjualan.loc[mask]

            if filtered_sales.empty:
                st.error("Tidak ada data penjualan pada rentang tanggal yang dipilih.")
                if 'final_abc_result' in st.session_state:
                    del st.session_state.final_abc_result # Hapus hasil lama jika ada
            else:
                sales_metric = filtered_sales.groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index()
                sales_metric.rename(columns={'Kuantitas': 'Metrik_Penjualan'}, inplace=True)
                
                cities = sales_metric['City'].unique()
                all_products_all_cities = [produk_ref[['No. Barang', 'Nama Barang']].assign(City=city) for city in cities]
                full_product_list = pd.concat(all_products_all_cities, ignore_index=True)
                
                analysis_df = pd.merge(full_product_list, sales_metric, on=['City', 'No. Barang'], how='left').fillna(0)
                
                result_list = [classify_abc_dynamic(analysis_df[analysis_df['City'] == city], 'Metrik_Penjualan') for city in analysis_df['City'].unique()]
                final_result = pd.concat(result_list, ignore_index=True)
                st.session_state.final_abc_result = final_result
        
        if 'final_abc_result' in st.session_state and not st.session_state.final_abc_result.empty:
            result_display = st.session_state.final_abc_result.copy()
            
            result_display['Kontribusi'] = (result_display['Kontribusi'] * 100).map('{:.2f}%'.format)
            result_display['Kontribusi_Kumulatif'] = (result_display['Kontribusi_Kumulatif'] * 100).map('{:.2f}%'.format)

            tab1, tab2 = st.tabs(["📑 Hasil Tabel", "📈 Dashboard"])

            with tab1:
                st.header("Tabel Hasil Analisis ABC")
                excel_data = to_excel(result_display)
                st.download_button(label="📥 Unduh Hasil sebagai Excel", data=excel_data, file_name=f'Analisis_ABC_{start_date}_to_{end_date}.xlsx')
                
                for city in sorted(result_display['City'].unique()):
                    with st.expander(f"Lihat Hasil untuk Kota: {city}"):
                        city_data = result_display[result_display['City'] == city]
                        st.dataframe(city_data.style.apply(lambda row: ['background-color: #cce5ff']*len(row) if row.Kategori_ABC == 'A' else ['background-color: #d4edda']*len(row) if row.Kategori_ABC == 'B' else ['background-color: #fff3cd']*len(row) if row.Kategori_ABC == 'C' else ['background-color: #f8d7da']*len(row), axis=1))
            
            with tab2:
                st.header("Dashboard Visual")
                result_display_dash = st.session_state.final_abc_result.copy()
                
                abc_summary = result_display_dash.groupby('Kategori_ABC').agg(count=('No. Barang', 'size'), sum_metric=('Metrik_Penjualan', 'sum')).reset_index()
                total_sales = abc_summary['sum_metric'].sum()
                if total_sales > 0:
                    abc_summary['sum_perc'] = (abc_summary['sum_metric'] / total_sales) * 100
                else:
                    abc_summary['sum_perc'] = 0

                col1, col2, col3, col4 = st.columns(4)
                metrics = {'A': col1, 'B': col2, 'C': col3, 'D': col4}
                for category, col in metrics.items():
                    data = abc_summary[abc_summary['Kategori_ABC'] == category]
                    if not data.empty:
                        col.metric(label=f"Jumlah SKU Kelas {category}", value=f"{data['count'].iloc[0]} SKU", help=f"Kontribusi: {data['sum_perc'].iloc[0]:.2f}% dari total penjualan")
                    else:
                        col.metric(label=f"Jumlah SKU Kelas {category}", value="0 SKU")
                
                st.markdown("---")
                
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Komposisi Produk per Kelas ABC")
                    fig1, ax1 = plt.subplots()
                    ax1.pie(abc_summary['count'], labels=abc_summary['Kategori_ABC'], autopct='%1.1f%%', startangle=90, colors=['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da'])
                    ax1.axis('equal')
                    st.pyplot(fig1)

                with col_chart2:
                    st.subheader("Kontribusi Penjualan per Kelas ABC")
                    st.bar_chart(abc_summary.set_index('Kategori_ABC')[['sum_perc']].rename(columns={'sum_perc': 'Kontribusi Penjualan (%)'}))
                
                st.markdown("---")
                
                col_top1, col_top2 = st.columns(2)
                with col_top1:
                    st.subheader("Top 10 Produk Terlaris")
                    top_products = result_display_dash.groupby('Nama Barang')['Metrik_Penjualan'].sum().nlargest(10)
                    st.bar_chart(top_products)
                
                with col_top2:
                    st.subheader("Performa Penjualan per Kota")
                    city_sales = result_display_dash.groupby('City')['Metrik_Penjualan'].sum().sort_values(ascending=False)
                    st.bar_chart(city_sales)
        else:
            st.info("Klik tombol 'Jalankan Analisis' di sidebar untuk melihat hasilnya.")
