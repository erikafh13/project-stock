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

# Konfigurasi awal halaman Streamlit
st.set_page_config(layout="wide", page_title="Sparrow Stock Analysis")

# --- SIDEBAR ---
st.sidebar.image("https://storage.googleapis.com/gemini-prod/images/19efd01d-1377-4208-bab7-349d4d104044", use_column_width=True)
st.sidebar.title("Sparrow")

page = st.sidebar.radio(
    "Menu Navigasi:",
    ("Input Data", "Hasil Analisa Stock", "Hasil Analisa ABC", "Dashboard"),
    help="Pilih halaman untuk ditampilkan."
)

st.sidebar.markdown("---")
st.sidebar.info("User: John Doe\n\nVersion: 1.0.0")
if st.sidebar.button("Logout"):
    st.sidebar.success("Anda berhasil logout!")

# --- Inisialisasi Session State ---
if 'df_penjualan' not in st.session_state:
    st.session_state.df_penjualan = pd.DataFrame()
if 'produk_ref' not in st.session_state:
    st.session_state.produk_ref = pd.DataFrame()
if 'df_stock' not in st.session_state:
    st.session_state.df_stock = pd.DataFrame()

# --------------------------------Fungsi Umum & Google Drive--------------------------------

# --- KONEKSI GOOGLE DRIVE ---
SCOPES = ['https://www.googleapis.com/auth/drive']
DRIVE_AVAILABLE = False
try:
    # FIXED: Coba muat dari Streamlit Secrets terlebih dahulu (untuk deployment)
    if st.secrets.has_key("gcp_service_account"):
        credentials = service_account.Credentials.from_service_account_info(
            st.secrets["gcp_service_account"], scopes=SCOPES
        )
        st.sidebar.success("Berhasil terhubung ke Google Drive via Secrets.", icon="☁️")
    # Jika gagal (misalnya saat dijalankan lokal), gunakan file credentials.json
    elif os.path.exists("credentials.json"):
        credentials = service_account.Credentials.from_service_account_file(
            'credentials.json', scopes=SCOPES
        )
        st.sidebar.success("Berhasil terhubung ke Google Drive via file lokal.", icon="💻")
    else:
        st.sidebar.error("Kredensial Google Drive tidak ditemukan.")
        credentials = None

    if credentials:
        drive_service = build('drive', 'v3', credentials=credentials)
        folder_penjualan = "1Okgw8qHVM8HyBwnTUFHbmYkNKqCcswNZ"
        folder_produk = "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv"
        folder_stock = "1PMeH_wvgRUnyiZyZ_wrmKAATX9JyWzq_"
        folder_hasil_analisis = "1TE4a8IegbWDKoVeLPG_oCbuU-qnhd1jE"
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
    df.columns = ['No. Barang', 'BRAND Barang', 'Nama Kategori Barang', 'Keterangan Barang']
    return df

def read_stock_file(file_id):
    fh = download_file_from_gdrive(file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1", skiprows=9, header=None)
    header = ['No. Barang', 'Keterangan Barang', 'A - ITC', 'AT - TRANSIT ITC', 'B', 'BT - TRANSIT JKT', 'C', 'C6', 'CT - TRANSIT PUSAT', 'D - SMG', 'DT - TRANSIT SMG', 'E - JOG', 'ET - TRANSIT JOG', 'F - MLG', 'FT - TRANSIT MLG', 'H - BALI', 'HT - TRANSIT BALI', 'X', 'Y - SBY', 'Y3 - Display Y', 'YT - TRANSIT Y']
    df.columns = header[:len(df.columns)]
    return df

# --- FUNGSI MAPPING DATA ---
def map_nama_dept(row):
    dept = row.get('Dept.', '')
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
#                                    ROUTING HALAMAN
# =====================================================================================

if page == "Input Data":
    st.title("📥 Input Data")
    st.markdown("Muat data yang diperlukan dari Google Drive. Data hanya akan dimuat sekali per sesi.")

    if not DRIVE_AVAILABLE:
        st.warning("Tidak dapat melanjutkan karena koneksi ke Google Drive gagal. Periksa log di sidebar.")
        st.stop()

    # --- Penjualan (Otomatis) ---
    st.header("1. Data Penjualan")
    if not st.session_state.df_penjualan.empty:
        st.success(f"✅ Data penjualan telah digabungkan dan dimuat secara otomatis.")
        st.dataframe(st.session_state.df_penjualan)
    else:
        with st.spinner("Mencari dan menggabungkan semua file penjualan..."):
            penjualan_files_list = list_files_in_folder(drive_service, folder_penjualan)
            if penjualan_files_list:
                df_penjualan = pd.concat([download_and_read(f['id'], f['name']) for f in penjualan_files_list], ignore_index=True)
                st.session_state.df_penjualan = df_penjualan
                st.rerun()
            else:
                st.warning("⚠️ Tidak ada file penjualan ditemukan di folder Google Drive.")

    # --- Produk Ref (Dengan Slicer) ---
    st.header("2. Produk Referensi")
    if not st.session_state.produk_ref.empty:
        st.success("✅ File Produk Referensi sudah dimuat.")
        st.dataframe(st.session_state.produk_ref.head())
    else:
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
                st.rerun()

    # --- Stock (Dengan Slicer) ---
    st.header("3. Data Stock")
    if not st.session_state.df_stock.empty:
        st.success("✅ File Stock sudah dimuat.")
        st.dataframe(st.session_state.df_stock.head())
    else:
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
                st.rerun()


elif page == "Hasil Analisa Stock":
    st.title("🔬 Hasil Analisa Stock")
    
    # --- FUNGSI-FUNGSI SPESIFIK ANALISA STOCK ---
    def classify_abc_stock(city_df):
        city_df = city_df.sort_values(by='Total Kuantitas', ascending=False).reset_index(drop=True)
        total = city_df['Total Kuantitas'].sum()
        if total == 0:
            city_df['% kontribusi'] = 0; city_df['% Kumulatif'] = 0; city_df['Kategori ABC'] = 'D'
        else:
            city_df['% kontribusi'] = 100 * city_df['Total Kuantitas'] / total
            city_df['% Kumulatif'] = city_df['% kontribusi'].cumsum()
            city_df['Kategori ABC'] = city_df['% Kumulatif'].apply(lambda x: 'A' if x <= 70 else ('B' if x <= 90 else 'C'))
        return city_df

    def highlight_kategori(val):
        warna = {'A': 'background-color: #b6e4b6', 'B': 'background-color: #fff3b0', 'C': 'background-color: #ffd6a5', 'D': 'background-color: #f4bbbb'}
        return warna.get(val, '')

    def calculate_min_stock(avg_wma): return avg_wma * 0.7

    def get_status_stock(row):
        if row['Kategori ABC'] == 'D': return 'Overstock D' if row['Stock Cabang'] > 2 else 'Balance'
        if row['Stock Cabang'] > row['Max Stock']: return 'Overstock no D'
        if row['Stock Cabang'] >= row['ROP']: return 'Balance'
        if row['Stock Cabang'] < row['ROP']: return 'Understock'
        return '-'

    def highlight_status_stock(val):
        colors = {'Understock': 'background-color: #fff3b0', 'Balance': 'background-color: #b6e4b6', 'Overstock no D': 'background-color: #ffd6a5', 'Overstock D': 'background-color: #f4bbbb'}
        return colors.get(val, '')

    def calculate_max_stock(avg_wma, category):
        multiplier = {'A': 2, 'B': 1, 'C': 0.5, 'D': 0}
        return avg_wma * multiplier.get(category, 0)
    
    def calculate_rop(min_stock, safety_stock): return min_stock + safety_stock

    def hitung_po_cabang(stock_surabaya, add_stock_cabang, stock_cabang, so_cabang, stock_total, so_total):
        try:
            add_stock_cabang_val = 0 if add_stock_cabang == '-' else add_stock_cabang
            if stock_surabaya < add_stock_cabang_val or stock_total <= 0: return 0
            kebutuhan_20hari = so_cabang / 30 * 20
            if stock_total < so_total and stock_cabang < kebutuhan_20hari:
                ideal_po = ((stock_cabang + add_stock_cabang_val) / stock_total * stock_surabaya) - stock_cabang
                return max(0, round(ideal_po))
            else: return round(add_stock_cabang_val)
        except (ZeroDivisionError, TypeError): return 0

    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty or st.session_state.df_stock.empty:
        st.warning("⚠️ Harap muat semua file di halaman **'Input Data'** terlebih dahulu untuk melihat hasil analisis.")
        st.stop()
    
    penjualan = st.session_state.df_penjualan.copy()
    produk_ref = st.session_state.produk_ref.copy()
    stock_df_raw = st.session_state.df_stock.copy()

    penjualan['Nama Dept'] = penjualan.apply(map_nama_dept, axis=1)
    penjualan['City'] = penjualan['Nama Dept'].apply(map_city)
    produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
    penjualan['Tgl Faktur'] = pd.to_datetime(penjualan['Tgl Faktur'], errors='coerce')

    st.header("Filter Tanggal Analisis Stock")
    min_date, max_date = penjualan['Tgl Faktur'].dropna().min().date(), penjualan['Tgl Faktur'].dropna().max().date()
    col1, col2 = st.columns(2)
    start_date = col1.date_input("Tanggal Awal", value=min_date, min_value=min_date, max_value=max_date, key="stock_start")
    end_date = col2.date_input("Tanggal Akhir", value=max_date, min_value=start_date, max_value=max_date, key="stock_end")

    penjualan = penjualan[(penjualan['Tgl Faktur'] >= pd.to_datetime(start_date)) & (penjualan['Tgl Faktur'] <= pd.to_datetime(end_date))]
    if penjualan.empty:
        st.error("Tidak ada data penjualan dalam rentang tanggal yang dipilih.")
        st.stop()
    
    with st.spinner("Melakukan perhitungan analisis stok..."):
        penjualan['Bulan'] = penjualan['Tgl Faktur'].dt.to_period('M')
        bulan_unik = sorted(penjualan['Bulan'].unique(), reverse=True)[:3]
        bobot_dict = {bulan: [0.5, 0.3, 0.2][i] for i, bulan in enumerate(bulan_unik)}
        penjualan_wma = penjualan[penjualan['Bulan'].isin(bobot_dict.keys())].copy()
        penjualan_wma['Bobot'] = penjualan_wma['Bulan'].map(bobot_dict)
        penjualan_wma['WMA_Kuantitas'] = penjualan_wma.get('Qty', 0) * penjualan_wma['Bobot']
        
        wma_grouped = penjualan_wma.groupby(['City', 'No. Barang'])['WMA_Kuantitas'].sum().reset_index().rename(columns={'WMA_Kuantitas': 'AVG WMA'})

        barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
        kombinasi = pd.MultiIndex.from_product([penjualan['City'].unique(), barang_list['No. Barang'].unique()], names=['City', 'No. Barang']).to_frame(index=False)
        full_data = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
        full_data = pd.merge(full_data, wma_grouped, on=['City', 'No. Barang'], how='left').fillna(0)

        final_result = full_data.copy()
        final_result['Total Kuantitas'] = final_result['AVG WMA']
        
        final_result = final_result.groupby('City', group_keys=False).apply(classify_abc_stock).reset_index(drop=True)
        
        final_result['Min Stock'] = final_result['AVG WMA'].apply(calculate_min_stock)
        final_result['Safety Stock'] = 0 
        final_result['ROP'] = final_result.apply(lambda row: calculate_rop(row['Min Stock'], row['Safety Stock']), axis=1)
        final_result['Max Stock'] = final_result.apply(lambda row: calculate_max_stock(row['AVG WMA'], row['Kategori ABC']), axis=1)

        prefix_to_city_map = {'A - ITC': 'Surabaya','AT - TRANSIT ITC': 'Surabaya','B': 'Jakarta','BT - TRANSIT JKT': 'Jakarta','C': 'Surabaya','C6': 'Surabaya','CT - TRANSIT PUSAT': 'Surabaya','D - SMG': 'Semarang','DT - TRANSIT SMG': 'Semarang','E - JOG': 'Jogja','ET - TRANSIT JOG': 'Jogja','F - MLG': 'Malang','FT - TRANSIT MLG': 'Malang','H - BALI': 'Bali','HT - TRANSIT BALI': 'Bali','Y - SBY': 'Surabaya','Y3 - Display Y': 'Surabaya','YT - TRANSIT Y': 'Surabaya'}
        id_vars = ['No. Barang', 'Keterangan Barang']
        value_vars = [col for col in stock_df_raw.columns if col not in id_vars]
        stock_long = stock_df_raw.melt(id_vars=id_vars, value_vars=value_vars, var_name='Gudang', value_name='Stock')
        stock_long['City'] = stock_long['Gudang'].str.strip().map(prefix_to_city_map)
        stock_melted = stock_long.dropna(subset=['City']).groupby(['City', 'No. Barang'])['Stock'].sum().reset_index()

        final_result = pd.merge(final_result, stock_melted, on=['City', 'No. Barang'], how='left').rename(columns={'Stock': 'Stock Cabang'})
        final_result['Stock Cabang'].fillna(0, inplace=True)
        final_result['Status Stock'] = final_result.apply(get_status_stock, axis=1)
        final_result['Add Stock'] = final_result.apply(lambda row: max(0, row['ROP'] - row['Stock Cabang']), axis=1)

        stock_surabaya = stock_melted[stock_melted['City'] == 'Surabaya'][['No. Barang', 'Stock']].rename(columns={'Stock': 'Stock Surabaya'})
        stock_total = stock_melted.groupby('No. Barang')['Stock'].sum().reset_index().rename(columns={'Stock': 'Stock Total'})
        so_total = final_result.groupby('No. Barang')['AVG WMA'].sum().reset_index().rename(columns={'AVG WMA': 'SO Total'})
        final_result = final_result.merge(stock_surabaya, on='No. Barang', how='left').merge(stock_total, on='No. Barang', how='left').merge(so_total, on='No. Barang', how='left').fillna(0)
        
        final_result['Suggested PO'] = final_result.apply(lambda row: hitung_po_cabang(row['Stock Surabaya'], row['Add Stock'], row['Stock Cabang'], row['AVG WMA'], row['Stock Total'], row['SO Total']), axis=1)
        
        for col in ['Stock Cabang', 'Min Stock', 'Max Stock', 'Safety Stock', 'ROP', 'Add Stock', 'Suggested PO', 'Stock Surabaya', 'Stock Total', 'SO Total']:
            final_result[col] = final_result[col].round(0).astype(int)

    st.success("✅ Analisis Stok selesai!")
    st.header("Hasil Analisis Stok per Kota")
    
    for city in sorted(final_result['City'].unique()):
        with st.expander(f"📍 Lihat Hasil Stok untuk Kota: {city}"):
            city_df = final_result[final_result['City'] == city]
            display_cols_city = ['No. Barang', 'Nama Barang', 'Kategori Barang', 'BRAND Barang', 'Kategori ABC', 'Status Stock', 'AVG WMA', 'Stock Cabang', 'Min Stock', 'Max Stock', 'Safety Stock', 'ROP', 'Add Stock', 'Suggested PO']
            styled_df = city_df[display_cols_city].style.apply(lambda x: x.map(highlight_kategori), subset=['Kategori ABC']).apply(lambda x: x.map(highlight_status_stock), subset=['Status Stock'])
            st.dataframe(styled_df, use_container_width=True)
            
    st.header("📊 Tabel Gabungan Seluruh Kota (Stock)")
    with st.spinner("Membuat tabel pivot gabungan untuk stok..."):
        keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
        pivot_cols = ['AVG WMA', 'Kategori ABC', 'Min Stock', 'Safety Stock', 'ROP', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock']
        
        agg_functions = {col: 'first' for col in pivot_cols}
        
        pivot_result = final_result.pivot_table(index=keys, columns='City', values=pivot_cols, aggfunc=agg_functions)
        
        pivot_result.columns = [f"{level1}_{level0}" for level0, level1 in pivot_result.columns]
        pivot_result.reset_index(inplace=True)

        cities = sorted(final_result['City'].unique())
        metric_order = ['AVG WMA', 'Kategori ABC', 'Min Stock', 'Safety Stock', 'ROP', 'Max Stock', 'Stock Cabang', 'Status Stock', 'Add Stock']
        ordered_city_cols = [f"{city}_{metric}" for city in cities for metric in metric_order]
        
        existing_ordered_cols = [col for col in ordered_city_cols if col in pivot_result.columns]
        
        total_agg = final_result.groupby(keys).agg(
            All_Stock=('Stock Cabang', 'sum'), 
            All_SO=('AVG WMA', 'sum'), 
            All_Suggested_PO=('Suggested PO', 'sum')
        ).reset_index()
        
        all_sales_for_abc = total_agg.copy()
        all_sales_for_abc.rename(columns={'All_SO': 'Total Kuantitas'}, inplace=True)
        all_sales_for_abc['City'] = 'All'
        
        all_classified = all_sales_for_abc.groupby('City', group_keys=False).apply(classify_abc_stock).reset_index(drop=True)
        all_classified.rename(columns={'Kategori ABC': 'All_Kategori ABC All'}, inplace=True)
        
        total_agg['All_Restock 1 Bulan'] = np.where(total_agg['All_Stock'] < total_agg['All_SO'], 'PO', 'NO')

        pivot_result = pd.merge(pivot_result, total_agg, on=keys, how='left')
        pivot_result = pd.merge(pivot_result, all_classified[keys + ['All_Kategori ABC All']], on=keys, how='left')

        final_summary_cols = ['All_Stock', 'All_SO', 'All_Suggested_PO', 'All_Kategori ABC All', 'All_Restock 1 Bulan']
        final_display_cols = keys + existing_ordered_cols + final_summary_cols
        
        st.dataframe(pivot_result[final_display_cols], use_container_width=True)

    # ADDED: Tombol Download untuk Hasil Analisa Stock
    st.header("💾 Unduh Hasil Analisis Stock")
    output_stock = BytesIO()
    with pd.ExcelWriter(output_stock, engine='openpyxl') as writer:
        pivot_result[final_display_cols].to_excel(writer, sheet_name="All Cities Pivot", index=False)
        for city in sorted(final_result['City'].unique()):
            sheet_name = city[:31]
            final_result[final_result['City'] == city].to_excel(writer, sheet_name=sheet_name, index=False)
    
    st.download_button(
        "📥 Unduh Hasil Analisis Stock (Excel)",
        data=output_stock.getvalue(),
        file_name=f"Hasil_Analisis_Stock_{start_date}_sd_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

elif page == "Hasil Analisa ABC":
    st.title("📊 Analisis ABC Berdasarkan Metrik Penjualan Dinamis")
    
    def classify_abc_dynamic(df_grouped, metric_col='Metrik_Penjualan'):
        abc_results = []
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
            tidak_terjual['% kontribusi'] = 0; tidak_terjual['% Kumulatif'] = 0; tidak_terjual['Kategori ABC'] = 'D'
            result = pd.concat([terjual, tidak_terjual], ignore_index=True)
            abc_results.append(result)
        return pd.concat(abc_results, ignore_index=True) if abc_results else pd.DataFrame()

    def calculate_wma(group):
        if group.empty: return 0
        monthly_sales = group.resample('M', on='Tgl Faktur')['Qty'].sum().sort_index(ascending=True)
        recent_sales = monthly_sales.tail(3)
        if len(recent_sales) == 0: return 0
        weights_map = {1: [1.0], 2: [0.4, 0.6], 3: [0.2, 0.3, 0.5]}
        weights = weights_map.get(len(recent_sales), [1.0])
        return np.average(recent_sales, weights=weights)

    def highlight_kategori_abc(val):
        warna = {'A': 'background-color: #b6e4b6', 'B': 'background-color: #fff3b0', 'C': 'background-color: #ffd6a5', 'D': 'background-color: #f4bbbb'}
        return warna.get(val, '')

    if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
        st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'** terlebih dahulu.")
        st.stop()

    all_so_df = st.session_state.df_penjualan.copy()
    produk_ref = st.session_state.produk_ref.copy()
    
    so_df = all_so_df.copy()
    so_df['Nama Dept'] = so_df.apply(map_nama_dept, axis=1)
    so_df['City'] = so_df['Nama Dept'].apply(map_city)
    so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
    so_df.dropna(subset=['Tgl Faktur'], inplace=True)
    
    st.header("Filter Rentang Waktu Analisis ABC")
    col1, col2 = st.columns(2)
    default_start = so_df['Tgl Faktur'].max() - pd.DateOffset(months=3)
    start_date = col1.date_input("Pilih Tanggal Awal", value=default_start, key="abc_start")
    end_date = col2.date_input("Pilih Tanggal Akhir", value=so_df['Tgl Faktur'].max(), key="abc_end")

    mask = (so_df['Tgl Faktur'] >= pd.to_datetime(start_date)) & (so_df['Tgl Faktur'] <= pd.to_datetime(end_date))
    so_df_filtered = so_df.loc[mask].copy()

    produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
    barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
    
    city_list = so_df_filtered['City'].dropna().unique()
    kombinasi = pd.MultiIndex.from_product([city_list, barang_list['No. Barang']], names=['City', 'No. Barang']).to_frame(index=False)
    kombinasi = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')

    duration = (pd.to_datetime(end_date) - pd.to_datetime(start_date)).days
    
    if duration <= 30:
        st.info(f"Rentang waktu {duration} hari (<= 30 hari). Metode: **Rata-rata (Mean)**.")
        agg_so = so_df_filtered.groupby(['City', 'No. Barang'])['Qty'].agg(Metrik_Penjualan='mean').reset_index()
    else:
        st.info(f"Rentang waktu {duration} hari (> 30 hari). Metode: **Weighted Moving Average (WMA)**.")
        with st.spinner("Menghitung WMA untuk setiap produk..."):
            agg_so = so_df_filtered.groupby(['City', 'No. Barang']).apply(calculate_wma).reset_index(name='Metrik_Penjualan')

    agg_so['Metrik_Penjualan'] = agg_so['Metrik_Penjualan'].apply(lambda x: max(x, 0))

    grouped = pd.merge(kombinasi, agg_so, on=['City', 'No. Barang'], how='left')
    grouped['Metrik_Penjualan'] = grouped['Metrik_Penjualan'].fillna(0)

    with st.spinner("Mengklasifikasikan produk dengan metode ABC..."):
        result = classify_abc_dynamic(grouped, metric_col='Metrik_Penjualan')
    
    st.header("📊 Hasil Analisis ABC")
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        result.to_excel(writer, sheet_name="Data Gabungan ABC", index=False)
        for city in sorted(result['City'].unique()):
            sheet_name = city[:31]
            result[result['City'] == city].to_excel(writer, sheet_name=sheet_name, index=False)
    
    st.download_button(
        "📥 Unduh Hasil Analisis Lengkap (Excel)",
        data=output.getvalue(),
        file_name=f"Hasil_Analisis_ABC_{start_date}_sd_{end_date}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    for city in sorted(result['City'].unique()):
        with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
            df_city = result[result['City'] == city]
            display_cols_order = ['No. Barang', 'BRAND Barang', 'Nama Barang', 'Kategori Barang', 'Metrik_Penjualan', 'Kategori ABC', '% kontribusi', '% Kumulatif']
            df_city_display = df_city[display_cols_order]
            st.dataframe(df_city_display.style.format({'Metrik_Penjualan': '{:.2f}', '% kontribusi': '{:.2f}%', '% Kumulatif': '{:.2f}%'}).apply(lambda x: x.map(highlight_kategori_abc), subset=['Kategori ABC']), use_container_width=True)

    st.header("📊 Tabel Gabungan Seluruh Kota (ABC)")
    with st.spinner("Membuat tabel pivot gabungan untuk ABC..."):
        keys = ['No. Barang', 'Kategori Barang', 'BRAND Barang', 'Nama Barang']
        
        pivot_abc = result.pivot_table(index=keys, columns='City', values=['Metrik_Penjualan', 'Kategori ABC'], aggfunc={'Metrik_Penjualan': 'sum', 'Kategori ABC': 'first'})
        pivot_abc.columns = [f"{level1}_{level0}" for level0, level1 in pivot_abc.columns]
        pivot_abc.reset_index(inplace=True)
        
        total_abc = result.groupby(keys).agg(Total_Metrik=('Metrik_Penjualan', 'sum')).reset_index()
        total_abc['City'] = 'All' 
        total_abc_classified = classify_abc_dynamic(total_abc.rename(columns={'Total_Metrik': 'Metrik_Penjualan'}), metric_col='Metrik_Penjualan')
        total_abc_classified.rename(columns={'Kategori ABC': 'All_Kategori_ABC', '% kontribusi': 'All_%_Kontribusi'}, inplace=True)
        
        pivot_abc_final = pd.merge(pivot_abc, total_abc_classified[keys + ['All_Kategori_ABC', 'All_%_Kontribusi']], on=keys, how='left')
        
        st.dataframe(pivot_abc_final, use_container_width=True)


elif page == "Dashboard":
    st.title("📈 Dashboard")
    st.markdown("Tampilan ringkasan metrik dan visualisasi data penting.")
    
    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(label="Documents", value="10.5K", delta="125")
    col2.metric(label="Annotations", value="510", delta="-2")
    col3.metric(label="Accuracy", value="87.9%", delta="0.1%")
    col4.metric(label="Training Time", value="1.5 hours", delta="10 mins")
    col5.metric(label="Processing Time", value="3 seconds", delta="-0.1 seconds")
    st.markdown("---")

    st.subheader("Data Extraction")
    chart_data_line = pd.DataFrame(np.random.randn(20, 3), columns=['a', 'b', 'c'])
    st.line_chart(chart_data_line)

    col_a, col_b = st.columns(2)
    with col_a:
        st.subheader("Model Training")
        chart_data_bar = pd.DataFrame(np.random.randn(20, 3), columns=["Series 1", "Series 2", "Series 3"])
        st.bar_chart(chart_data_bar)
    with col_b:
        st.subheader("Data Annotation")
        chart_data_area = pd.DataFrame(np.random.rand(20, 2) / 2 + 0.3, columns=['Actual', 'Predicted'])
        st.area_chart(chart_data_area)


