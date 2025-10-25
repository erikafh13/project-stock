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
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()
if 'abc_analysis_result' not in st.session_state:
    st.session_state.abc_analysis_result = None

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
    if not st.session_state.produk_ref.empty:
        st.dataframe(st.session_state.produk_ref.head())

    # Bagian "3. Data Stock" telah dihapus seluruhnya


# SELURUH BLOK 'elif page == "Hasil Analisa Stock":' TELAH DIHAPUS


elif page == "Hasil Analisa ABC":
    st.title("📊 Analisis ABC Berdasarkan Metrik Penjualan Dinamis")
    # ... (kode untuk halaman Analisa ABC tidak diubah) ...
    tab1_abc, tab2_abc = st.tabs(["Hasil Tabel", "Dashboard"])
    with tab1_abc:
        def classify_abc_dynamic(df_grouped, metric_col='Metrik_Penjualan'):
            abc_results = []
            if 'City' not in df_grouped.columns:
                if not df_grouped.empty:
                    st.warning("Kolom 'City' tidak ditemukan dalam data untuk klasifikasi ABC.")
                return pd.DataFrame()
            for city, city_group in df_grouped.groupby('City'):
                group = city_group.sort_values(by=metric_col, ascending=False).reset_index(drop=True)
                terjual = group[group[metric_col] > 0].copy()
                tidak_terjual = group[group[metric_col] <= 0].copy()
                total_metric = terjual[metric_col].sum()
                if total_metric == 0:
                    terjual['% kontribusi'] = 0; terjual['% Kumulatif'] = 0; terjual['Kategori ABC'] = 'D'
                else:
                    terjual['% kontribusi'] = 100 * terjual[metric_col] / total_metric
                    terjual['% Kumulatif'] = terjual['% kontribusi'].cumsum()
                    terjual['Kategori ABC'] = terjual['% Kumulatif'].apply(lambda x: 'A' if x <= 70 else ('B' if x <= 90 else 'C'))
                tidak_terjual['% kontribusi'] = 0; tidak_terjual['% Kumulatif'] = 100; tidak_terjual['Kategori ABC'] = 'D'
                result = pd.concat([terjual, tidak_terjual], ignore_index=True)
                abc_results.append(result)
            return pd.concat(abc_results, ignore_index=True) if abc_results else pd.DataFrame()

        def highlight_kategori_abc(val):
            warna = {'A': 'background-color: #cce5ff', 'B': 'background-color: #d4edda', 'C': 'background-color: #fff3cd', 'D': 'background-color: #f8d7da'}
            return warna.get(val, '')

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
        so_df['Nama Dept'] = so_df.apply(map_nama_dept, axis=1)
        so_df['City'] = so_df['Nama Dept'].apply(map_city)
        so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
        so_df.dropna(subset=['Tgl Faktur'], inplace=True)
        st.header("Filter Rentang Waktu Analisis ABC")
        today = datetime.now().date()
        date_option = st.selectbox("Pilih Rentang Waktu:",("7 Hari Terakhir", "30 Hari Terakhir", "90 Hari Terakhir", "Custom"))
        if date_option == "7 Hari Terakhir":
            start_date, end_date = today - timedelta(days=6), today
        elif date_option == "30 Hari Terakhir":
            start_date, end_date = today - timedelta(days=29), today
        elif date_option == "90 Hari Terakhir":
            start_date, end_date = today - timedelta(days=89), today
        else: # Custom
            col1, col2 = st.columns(2)
            start_date = col1.date_input("Tanggal Awal", value=today - timedelta(days=29))
            end_date = col2.date_input("Tanggal Akhir", value=today)
        if st.button("Jalankan Analisa ABC"):
            with st.spinner("Melakukan perhitungan analisis ABC..."):
                mask = (so_df['Tgl Faktur'].dt.date >= start_date) & (so_df['Tgl Faktur'].dt.date <= end_date)
                so_df_filtered = so_df.loc[mask].copy()
                produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
                barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
                city_list = so_df_filtered['City'].dropna().unique()
                kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
                kombinasi = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
                agg_so = so_df_filtered.groupby(['City', 'No. Barang'])['Kuantitas'].sum().reset_index(name='Metrik_Penjualan')
                grouped = pd.merge(kombinasi, agg_so, on=['City', 'No. Barang'], how='left')
                grouped['Metrik_Penjualan'] = grouped['Metrik_Penjualan'].fillna(0)
                result = classify_abc_dynamic(grouped, metric_col='Metrik_Penjualan')
                st.session_state.abc_analysis_result = result.copy()
                st.success("Analisis ABC berhasil dijalankan!")
        if st.session_state.abc_analysis_result is not None:
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
            st.header("Hasil Analisis ABC per Kota")
            for city in sorted(result_display['City'].unique()):
                with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
                    city_df = result_display[result_display['City'] == city]
                    display_cols_order = ['No. Barang', 'BRAND Barang', 'Nama Barang', 'Kategori Barang', 'Metrik_Penjualan', 'Kategori ABC', '% kontribusi', '% Kumulatif']
                    df_city_display = city_df[display_cols_order]
                    st.dataframe(df_city_display.style.format({'Metrik_Penjualan': '{:.2f}', '% kontribusi': '{:.2f}%', '% Kumulatif': '{:.2f}%'}).apply(lambda x: x.map(highlight_kategori_abc), subset=['Kategori ABC']), use_container_width=True)
            st.header("📊 Tabel Gabungan Seluruh Kota (ABC)")
            with st.spinner("Membuat tabel pivot gabungan untuk ABC..."):
                keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
                pivot_abc = result_display.pivot_table(index=keys, columns='City', values=['Metrik_Penjualan', 'Kategori ABC'], aggfunc={'Metrik_Penjualan': 'sum', 'Kategori ABC': 'first'})
                pivot_abc.columns = [f"{level1}_{level0}" for level0, level1 in pivot_abc.columns]
                pivot_abc.reset_index(inplace=True)
                total_abc = result_display.groupby(keys).agg(Total_Metrik=('Metrik_Penjualan', 'sum')).reset_index()
                total_abc['City'] = 'All'
                total_abc_classified = classify_abc_dynamic(total_abc.rename(columns={'Total_Metrik': 'Metrik_Penjualan'}), metric_col='Metrik_Penjualan')
                total_abc_classified.rename(columns={'Kategori ABC': 'All_Kategori_ABC', '% kontribusi': 'All_%_Kontribusi'}, inplace=True)
                pivot_abc_final = pd.merge(pivot_abc, total_abc_classified[keys + ['All_Kategori_ABC', 'All_%_Kontribusi']], on=keys, how='left')
                st.dataframe(pivot_abc_final, use_container_width=True)
            st.header("💾 Unduh Hasil Analisis ABC")
            output_abc = BytesIO()
            with pd.ExcelWriter(output_abc, engine='openpyxl') as writer:
                pivot_abc_final.to_excel(writer, sheet_name="All Cities Pivot", index=False)
                for city in sorted(result_display['City'].unique()):
                    sheet_name = city[:31]
                    result_display[result_display['City'] == city].to_excel(writer, sheet_name=sheet_name, index=False)
            st.download_button("📥 Unduh Hasil Analisis ABC (Excel)",data=output_abc.getvalue(),file_name=f"Hasil_Analisis_ABC_{start_date}_sd_{end_date}.xlsx",mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    with tab2_abc:
        st.header("📈 Dashboard Analisis ABC")
        if 'abc_analysis_result' in st.session_state and st.session_state.abc_analysis_result is not None:
            result_display_dash = st.session_state.abc_analysis_result.copy()
            if not result_display_dash.empty:
                abc_summary = result_display_dash.groupby('Kategori ABC')['Metrik_Penjualan'].agg(['count', 'sum'])
                total_sales_sum = abc_summary['sum'].sum()
                if total_sales_sum > 0:
                    abc_summary['sum_perc'] = (abc_summary['sum'] / total_sales_sum) * 100
                else:
                    abc_summary['sum_perc'] = 0
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                if 'A' in abc_summary.index:
                    col1.metric("Produk Kelas A", f"{abc_summary.loc['A', 'count']} SKU", f"{abc_summary.loc['A', 'sum_perc']:.1f}% Penjualan")
                if 'B' in abc_summary.index:
                    col2.metric("Produk Kelas B", f"{abc_summary.loc['B', 'count']} SKU", f"{abc_summary.loc['B', 'sum_perc']:.1f}% Penjualan")
                if 'C' in abc_summary.index:
                    col3.metric("Produk Kelas C", f"{abc_summary.loc['C', 'count']} SKU", f"{abc_summary.loc['C', 'sum_perc']:.1f}% Penjualan")
                if 'D' in abc_summary.index:
                    col4.metric("Produk Kelas D", f"{abc_summary.loc['D', 'count']} SKU", "Tidak Terjual")
                st.markdown("---")
                col_chart1, col_chart2 = st.columns(2)
                with col_chart1:
                    st.subheader("Komposisi Produk per Kelas ABC")
                    fig1, ax1 = plt.subplots()
                    ax1.pie(abc_summary['count'], labels=abc_summary.index, autopct='%1.1f%%', startangle=90, colors=['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da'])
                    ax1.axis('equal')
                    st.pyplot(fig1)
                with col_chart2:
                    st.subheader("Kontribusi Penjualan per Kelas ABC")
                    st.bar_chart(abc_summary[['sum_perc']].rename(columns={'sum_perc': 'Kontribusi Penjualan (%)'}))
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
                st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")
        else:
            st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis atau sesuaikan filter Anda.")
