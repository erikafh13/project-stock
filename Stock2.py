import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
# import math # Dihapus (hanya untuk Analisa Stock)
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from googleapiclient.http import MediaIoBaseUpload
import io
import os
# import re # Dihapus (hanya untuk Analisa Stock)
from datetime import datetime, timedelta
import matplotlib.pyplot as plt

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Analisis ABC")

# --- SIDEBAR ---
st.sidebar.image("https://i.imgur.com/n0KzG1p.png", use_container_width=True)
st.sidebar.title("Analisis ABC")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa ABC"), # Opsi "Hasil Analisa Stock" dihapus
    help="Pilih halaman untuk ditampilkan."
)
st.sidebar.markdown("---")

# --- Inisialisasi Session State ---
# BLOK INI PENTING UNTUK MEMPERBAIKI ERROR
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()
# Bagian state 'df_stock', 'stock_filename', 'stock_analysis_result' dihapus
if 'abc_analysis_result' not in st.session_state:
    st.session_state.abc_analysis_result = None
# [BARU] Menambahkan state untuk metrik dan ketersediaan revenue
if 'abc_metric' not in st.session_state:
    st.session_state.abc_metric = 'Kuantitas'
if 'revenue_available' not in st.session_state:
    st.session_state.revenue_available = False


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
        # folder_stock dan folder_hasil_analisis dihapus
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

# Fungsi read_stock_file() dihapus

# --- FUNGSI MAPPING DATA ---
def map_nama_dept(row):
    # --- PERBAIKAN: Membersihkan input 'Dept.' agar lebih tangguh ---
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

# --- FUNGSI KONVERSI EXCEL (DIDEFINISIKAN SECARA GLOBAL) ---
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data


# =====================================================================================
#                               ROUTING HALAMAN
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
    
    # Baris 182 yang error sebelumnya
    # [DIUBAH] Menambahkan pengecekan 'produk_ref' in st.session_state untuk keamanan
    if 'produk_ref' in st.session_state and not st.session_state.produk_ref.empty:
        st.dataframe(st.session_state.produk_ref.head())

    # Bagian "3. Data Stock" telah dihapus seluruhnya


# SELURUH BLOK 'elif page == "Hasil Analisa Stock":' TELAH DIHAPUS
elif page == "Hasil Analisa ABC":
    st.title("📊 Analisis ABC Berdasarkan Revenue 3 Bulan Terakhir (Metode Kuartal)")
    tab1_abc, tab2_abc = st.tabs(["Hasil Tabel", "Dashboard"])

    # --- [FUNGSI BARU] ---
    # Fungsi ini menggantikan classify_abc_dynamic
    def classify_abc_new_method(df_agg):
        """
        Melakukan klasifikasi ABCDE berdasarkan grup Kota & Kategori Barang.
        Menggunakan metode kuartal relatif terhadap Total_Revenue tertinggi di grupnya.
        """
        # 1. Cari Max_Revenue untuk setiap grup (City, Kategori Barang)
        #    transform() akan mem-broadcast nilai max ke setiap baris dalam grupnya
        df_agg['Max_Revenue_in_Group'] = df_agg.groupby(['City', 'Kategori Barang'])['Total_Revenue'].transform('max')
        
        # 2. Definisikan fungsi klasifikasi untuk diterapkan per baris
        def get_category(row):
            total_revenue = row['Total_Revenue']
            max_revenue = row['Max_Revenue_in_Group']
            
            if total_revenue == 0:
                return 'E'
            
            # Hindari pembagian dengan nol jika max_revenue di grup itu 0
            if max_revenue == 0:
                return 'E' 
                
            ratio = total_revenue / max_revenue
            
            if ratio > 0.75:
                return 'A' # Kuartal 1 (Fast)
            elif ratio > 0.50:
                return 'B' # Kuartal 2 (Middle Fast)
            elif ratio > 0.25:
                return 'C' # Kuartal 3 (Middle Slow)
            else:
                return 'D' # Kuartal 4 (Slow)

        # 3. Terapkan fungsi ke setiap baris
        df_agg['Kategori ABC'] = df_agg.apply(get_category, axis=1)
        return df_agg

    # --- [FUNGSI UPDATE] ---
    # Menambahkan Kategori 'E'
    def highlight_kategori_abc(val):
        warna = {
            'A': 'background-color: #cce5ff', 
            'B': 'background-color: #d4edda', 
            'C': 'background-color: #fff3cd', 
            'D': 'background-color: #f8d7da',
            'E': 'background-color: #e2e3e5'  # Warna baru untuk Kategori E
        }
        return warna.get(val, '')

    with tab1_abc:
        # --- Pengecekan Data Awal (Sama) ---
        if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
            st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'** terlebih dahulu.")
            st.stop()
            
        all_so_df = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        
        for df in [all_so_df, produk_ref]:
            if 'No. Barang' in df.columns:
                df['No. Barang'] = df['No. Barang'].astype(str).str.strip()
                
        so_df = all_so_df.copy()
        so_df.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')

        # --- Perhitungan Revenue (Sama, tapi sekarang Wajib) ---
        if 'Harga Sat' in so_df.columns:
            so_df['Kuantitas'] = pd.to_numeric(so_df['Kuantitas'], errors='coerce')
            so_df['Harga Sat'] = pd.to_numeric(so_df['Harga Sat'], errors='coerce')
            so_df.fillna({'Kuantitas': 0, 'Harga Sat': 0}, inplace=True)
            so_df['Revenue'] = so_df['Kuantitas'] * so_df['Harga Sat']
            st.session_state.revenue_available = True
        else:
            st.error("❌ ANALISIS GAGAL: Kolom 'Harga Sat' tidak ditemukan.")
            st.warning("Analisis metode baru ini **wajib** menggunakan data 'Harga Sat' untuk menghitung Revenue. Silakan periksa kembali file penjualan Anda.")
            st.session_state.revenue_available = False
            st.stop() # Hentikan eksekusi jika tidak ada revenue

        # --- Preprocessing Data (Sama) ---
        so_df['Nama Dept'] = so_df.apply(map_nama_dept, axis=1)
        so_df['City'] = so_df['Nama Dept'].apply(map_city)
        so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
        so_df.dropna(subset=['Tgl Faktur'], inplace=True)
        
        with st.expander("Lihat Data Penjualan Siap Analisis (Setelah Preprocessing)"):
            st.dataframe(so_df)
            excel_preview = convert_df_to_excel(so_df)
            st.download_button(
                label="📥 Unduh Data Penjualan (Hasil Preprocessing)",
                data=excel_preview,
                file_name="data_penjualan_preprocessed.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # --- [LOGIKA BARU] Penentuan Rentang Waktu 3 Bulan ---
        st.header("Analisis Revenue 3 Bulan Terakhir")
        st.info("Analisis ini secara otomatis mengambil data dari 3 bulan kalender penuh terakhir (tidak termasuk bulan berjalan).")

        # Tentukan 3 bulan terakhir
        today = datetime.now().date()
        # Bulan 3 (Terkini): Bulan lalu
        end_date_bln3 = today.replace(day=1) - timedelta(days=1)
        start_date_bln3 = end_date_bln3.replace(day=1)
        # Bulan 2: Dua bulan lalu
        end_date_bln2 = start_date_bln3 - timedelta(days=1)
        start_date_bln2 = end_date_bln2.replace(day=1)
        # Bulan 1 (Terlama): Tiga bulan lalu
        end_date_bln1 = start_date_bln2 - timedelta(days=1)
        start_date_bln1 = end_date_bln1.replace(day=1)

        st.markdown(f"**Bulan 3 (Terkini):** `{start_date_bln3.strftime('%Y-%m-%d')}` s/d `{end_date_bln3.strftime('%Y-%m-%d')}`")
        st.markdown(f"**Bulan 2:** `{start_date_bln2.strftime('%Y-%m-%d')}` s/d `{end_date_bln2.strftime('%Y-%m-%d')}`")
        st.markdown(f"**Bulan 1 (Terlama):** `{start_date_bln1.strftime('%Y-%m-%d')}` s/d `{end_date_bln1.strftime('%Y-%m-%d')}`")
        
        # --- [LOGIKA BARU] Tombol Analisis ---
        # Filter tanggal dan metrik dihapus
            
        if st.button("Jalankan Analisa ABC (Metode Baru)"):
            with st.spinner("Melakukan perhitungan analisis ABC..."):
                
                # 1. Buat 3 DataFrame terfilter untuk setiap bulan
                mask1 = (so_df['Tgl Faktur'].dt.date >= start_date_bln1) & (so_df['Tgl Faktur'].dt.date <= end_date_bln1)
                so_df_bln1 = so_df.loc[mask1]
                
                mask2 = (so_df['Tgl Faktur'].dt.date >= start_date_bln2) & (so_df['Tgl Faktur'].dt.date <= end_date_bln2)
                so_df_bln2 = so_df.loc[mask2]
                
                mask3 = (so_df['Tgl Faktur'].dt.date >= start_date_bln3) & (so_df['Tgl Faktur'].dt.date <= end_date_bln3)
                so_df_bln3 = so_df.loc[mask3]

                # 2. Agregasi revenue per bulan
                agg_bln1 = so_df_bln1.groupby(['City', 'No. Barang'])['Revenue'].sum().reset_index(name='Revenue_Bulan_1')
                agg_bln2 = so_df_bln2.groupby(['City', 'No. Barang'])['Revenue'].sum().reset_index(name='Revenue_Bulan_2')
                agg_bln3 = so_df_bln3.groupby(['City', 'No. Barang'])['Revenue'].sum().reset_index(name='Revenue_Bulan_3')

                # 3. Siapkan daftar produk master (kombinasi)
                produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
                barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
                city_list = so_df['City'].dropna().unique() # Ambil semua kota dari data asli
                
                if len(city_list) == 0:
                     st.warning("Data penjualan ada, namun tidak memiliki informasi 'City' yang valid.")
                     st.session_state.abc_analysis_result = pd.DataFrame()
                else:
                    kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                    kombinasi = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                    
                    # 4. Gabungkan (merge) data bulanan ke daftar master
                    grouped = pd.merge(kombinasi, agg_bln1, on=['City', 'No. Barang'], how='left')
                    grouped = pd.merge(grouped, agg_bln2, on=['City', 'No. Barang'], how='left')
                    grouped = pd.merge(grouped, agg_bln3, on=['City', 'No. Barang'], how='left')
                    
                    # 5. Isi NaN (tidak terjual di bulan tsb) dengan 0
                    grouped.fillna({
                        'Revenue_Bulan_1': 0, 
                        'Revenue_Bulan_2': 0, 
                        'Revenue_Bulan_3': 0
                    }, inplace=True)
                    
                    # 6. Hitung Total dan Rata-rata
                    grouped['Total_Revenue'] = grouped['Revenue_Bulan_1'] + grouped['Revenue_Bulan_2'] + grouped['Revenue_Bulan_3']
                    grouped['Rata_Rata_Revenue'] = grouped['Total_Revenue'] / 3
                    
                    # 7. Jalankan fungsi klasifikasi ABCDE baru
                    result = classify_abc_new_method(grouped)
                    
                    st.session_state.abc_analysis_result = result.copy()
                    st.success("Analisis ABC (metode kuartal) berhasil dijalankan!")

        # --- [LOGIKA TAMPILAN BARU] ---
        if st.session_state.abc_analysis_result is not None and not st.session_state.abc_analysis_result.empty:
            result_display = st.session_state.abc_analysis_result.copy()
            result_display = result_display[result_display['City'] != 'Others']
            
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
                
            st.header("Hasil Analisis ABC per Kota dan Kategori")
            
            # Format Angka
            revenue_format = '{:,.0f}'
            
            for city in sorted(result_display['City'].unique()):
                with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
                    city_df = result_display[result_display['City'] == city]
                    
                    # Loop lagi per Kategori Barang
                    for kategori in sorted(city_df['Kategori Barang'].dropna().unique()):
                        st.subheader(f"Kategori: {kategori}")
                        
                        kategori_df = city_df[
                            (city_df['Kategori Barang'] == kategori)
                        ].sort_values(by='Total_Revenue', ascending=False)
                        
                        # Tentukan kolom yang akan ditampilkan
                        display_cols_order = [
                            'No. Barang', 'Nama Barang', 'BRAND Barang', 
                            'Revenue_Bulan_1', 'Revenue_Bulan_2', 'Revenue_Bulan_3',
                            'Total_Revenue', 'Rata_Rata_Revenue', 'Kategori ABC',
                            'Max_Revenue_in_Group' # Untuk referensi
                        ]
                        
                        display_cols_order = [col for col in display_cols_order if col in kategori_df.columns]
                        df_display = kategori_df[display_cols_order]
                        
                        st.dataframe(df_display.style.format({
                            'Revenue_Bulan_1': revenue_format,
                            'Revenue_Bulan_2': revenue_format,
                            'Revenue_Bulan_3': revenue_format,
                            'Total_Revenue': revenue_format,
                            'Rata_Rata_Revenue': revenue_format,
                            'Max_Revenue_in_Group': revenue_format
                        }).apply(lambda x: x.map(highlight_kategori_abc), subset=['Kategori ABC']), 
                        use_container_width=True)

            # --- [LOGIKA UNDUH BARU] ---
            # Menghapus logika pivot, menggantinya dengan unduhan file flat
            st.header("💾 Unduh Hasil Analisis ABC")
            st.warning("Pivot gabungan ditiadakan. File Excel berisi data lengkap hasil analisis (flat file) yang dapat Anda olah lebih lanjut di Excel.")
            
            # Menggunakan dataframe hasil filter (jika ada)
            df_to_download = result_display if (selected_kategori_abc or selected_brand_abc) else st.session_state.abc_analysis_result
            
            excel_data_final = convert_df_to_excel(df_to_download)
            
            st.download_button(
                "📥 Unduh Hasil Analisis ABC Lengkap (Excel)",
                data=excel_data_final,
                file_name=f"Hasil_Analisis_ABC_3Bulan_{today.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        elif st.session_state.abc_analysis_result is not None:
             st.info("Tidak ada data untuk ditampilkan. Harap periksa filter tanggal atau data input Anda.")


    with tab2_abc:
        # --- [LOGIKA DASHBOARD UPDATE] ---
        # Dashboard disesuaikan untuk menggunakan data baru (Total_Revenue dan 5 Kategori)
        metric_used = "Total_Revenue" # Hardcode karena analisis ini hanya pakai Revenue
        st.header(f"📈 Dashboard Analisis ABC (Berdasarkan {metric_used} 3 Bulan)")
        
        if 'abc_analysis_result' in st.session_state and st.session_state.abc_analysis_result is not None and not st.session_state.abc_analysis_result.empty:
            result_display_dash = st.session_state.abc_analysis_result.copy()
            if not result_display_dash.empty:
                
                # Agregasi berdasarkan 5 kategori baru (A,B,C,D,E) dan Total_Revenue
                abc_summary = result_display_dash.groupby('Kategori ABC')['Total_Revenue'].agg(['count', 'sum'])
                total_sales_sum = abc_summary['sum'].sum()
                
                if total_sales_sum > 0:
                    abc_summary['sum_perc'] = (abc_summary['sum'] / total_sales_sum) * 100
                else:
                    abc_summary['sum_perc'] = 0
                    
                abc_summary = abc_summary.reindex(['A', 'B', 'C', 'D', 'E']).fillna(0) # Pastikan semua kategori ada
                    
                st.markdown("---")
                # Menambah 1 kolom untuk kategori E
                col1, col2, col3, col4, col5 = st.columns(5)
                
                col1.metric("Produk Kelas A", f"{abc_summary.loc['A', 'count']:.0f} SKU", f"{abc_summary.loc['A', 'sum_perc']:.1f}% {metric_used}")
                col2.metric("Produk Kelas B", f"{abc_summary.loc['B', 'count']:.0f} SKU", f"{abc_summary.loc['B', 'sum_perc']:.1f}% {metric_used}")
                col3.metric("Produk Kelas C", f"{abc_summary.loc['C', 'count']:.0f} SKU", f"{abc_summary.loc['C', 'sum_perc']:.1f}% {metric_used}")
                col4.metric("Produk Kelas D", f"{abc_summary.loc['D', 'count']:.0f} SKU", f"{abc_summary.loc['D', 'sum_perc']:.1f}% {metric_used}")
                col5.metric("Produk Kelas E", f"{abc_summary.loc['E', 'count']:.0f} SKU", "Revenue 0")

                st.markdown("---")
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Komposisi Produk per Kelas ABCDE")
                    fig1, ax1 = plt.subplots()
                    # Menambah warna untuk E
                    colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e2e3e5']
                    ax1.pie(abc_summary['count'], labels=abc_summary.index, autopct='%1.1f%%', startangle=90, colors=colors)
                    ax1.axis('equal')
                    st.pyplot(fig1)
                with col_chart2:
                    st.subheader(f"Kontribusi {metric_used} per Kelas ABCDE")
                    st.bar_chart(abc_summary[['sum_perc']].rename(columns={'sum_perc': f'Kontribusi {metric_used} (%)'}))
                
                st.markdown("---")
                col_top1, col_top2 = st.columns(2)
                with col_top1:
                    st.subheader(f"Top 10 Produk Terlaris (by {metric_used})")
                    # Update ke Total_Revenue
                    top_products = result_display_dash.groupby('Nama Barang')['Total_Revenue'].sum().nlargest(10)
                    st.bar_chart(top_products)
                with col_top2:
                    st.subheader(f"Performa {metric_used} per Kota")
                    # Update ke Total_Revenue
                    city_sales = result_display_dash.groupby('City')['Total_Revenue'].sum().sort_values(ascending=False)
                    st.bar_chart(city_sales)
            else:
                st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")
        else:
            st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")

