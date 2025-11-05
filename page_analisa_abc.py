import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import utils # Impor file utilitas Anda

# --- FUNGSI SPESIFIK UNTUK ANALISA ABC ---

def classify_abc_by_metric(df_input, metric_col_name, output_col_name):
    """
    Melakukan klasifikasi ABCDE berdasarkan grup Kota & Kategori Barang
    untuk METRIK SPESIFIK (Total_Kuantitas, Rata_Rata_Kuantitas, atau Kuantitas_WMA).
    """
    df = df_input.copy()
    max_metric_col = f'Max_{metric_col_name}_in_Group'
    df[max_metric_col] = df.groupby(['City', 'Kategori Barang'])[metric_col_name].transform('max')
    
    def get_category(row):
        metric_value = row[metric_col_name]
        max_metric = row[max_metric_col]
        if metric_value == 0: return 'E'
        if max_metric == 0: return 'E'  
        ratio = metric_value / max_metric
        if ratio > 0.75: return 'A'
        elif ratio > 0.50: return 'B'
        elif ratio > 0.25: return 'C'
        else: return 'D'

    df[output_col_name] = df.apply(get_category, axis=1)
    df.drop(columns=[max_metric_col], inplace=True)
    return df

def highlight_kategori_abc(val):
    warna = {
        'A': 'background-color: #cce5ff',  
        'B': 'background-color: #d4edda',  
        'C': 'background-color: #fff3cd',  
        'D': 'background-color: #f8d7da',
        'E': 'background-color: #e2e3e5'
    }
    return warna.get(val, '')

def create_dashboard_view(df, abc_col, metric_col, metric_name):
    """
    Membuat satu set lengkap komponen dashboard (metrik + 4 chart)
    """
    if abc_col not in df.columns or metric_col not in df.columns:
        st.error(f"Kolom yang diperlukan ('{abc_col}' atau '{metric_col}') tidak ditemukan.")
        return

    abc_summary = df.groupby(abc_col)[metric_col].agg(['count', 'sum'])
    total_metric_sum = abc_summary['sum'].sum()
    abc_summary['sum_perc'] = (abc_summary['sum'] / total_metric_sum) * 100 if total_metric_sum > 0 else 0
    abc_summary = abc_summary.reindex(['A', 'B', 'C', 'D', 'E']).fillna(0)
        
    st.markdown("---")
    
    # 2. Metrik 5 Kolom
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric(f"Produk Kelas A", f"{abc_summary.loc['A', 'count']:.0f} SKU", f"{abc_summary.loc['A', 'sum_perc']:.1f}% {metric_name}")
    col2.metric(f"Produk Kelas B", f"{abc_summary.loc['B', 'count']:.0f} SKU", f"{abc_summary.loc['B', 'sum_perc']:.1f}% {metric_name}")
    col3.metric(f"Produk Kelas C", f"{abc_summary.loc['C', 'count']:.0f} SKU", f"{abc_summary.loc['C', 'sum_perc']:.1f}% {metric_name}")
    col4.metric(f"Produk Kelas D", f"{abc_summary.loc['D', 'count']:.0f} SKU", f"{abc_summary.loc['D', 'sum_perc']:.1f}% {metric_name}")
    col5.metric(f"Produk Kelas E", f"{abc_summary.loc['E', 'count']:.0f} SKU", "Metrik 0")

    st.markdown("---")
    
    # 3. Chart Komposisi & Kontribusi
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.subheader("Komposisi Produk per Kelas ABCDE")
        fig1, ax1 = plt.subplots()
        colors = ['#cce5ff', '#d4edda', '#fff3cd', '#f8d7da', '#e2e3e5']
        pie_data = abc_summary[abc_summary['count'] > 0]
        if not pie_data.empty:
            ax1.pie(pie_data['count'], labels=pie_data.index, autopct='%1.1f%%', startangle=90, colors=[colors[abc_summary.index.get_loc(i)] for i in pie_data.index])
            ax1.axis('equal')
        else:
            ax1.text(0.5, 0.5, "Tidak ada data", horizontalalignment='center', verticalalignment='center')
        st.pyplot(fig1)
        
    with col_chart2:
        st.subheader(f"Kontribusi {metric_name} per Kelas ABCDE")
        st.bar_chart(abc_summary[['sum_perc']].rename(columns={'sum_perc': f'Kontribusi {metric_name} (%)'}))
        
    st.markdown("---")
    
    # 4. Chart Top 10 & Per Kota
    col_top1, col_top2 = st.columns(2)
    with col_top1:
        st.subheader(f"Top 10 Produk Terlaris (by {metric_name})")
        top_products = df.groupby('Nama Barang')[metric_col].sum().nlargest(10)
        st.bar_chart(top_products)
        
    with col_top2:
        st.subheader(f"Performa {metric_name} per Kota")
        city_sales = df.groupby('City')[metric_col].sum().sort_values(ascending=False)
        st.bar_chart(city_sales)


# --- FUNGSI UTAMA UNTUK MENJALANKAN ANALISIS (dipanggil oleh tombol) ---
@st.cache_data
# [DIUBAH] portal_df dihapus dari argumen
def run_abc_analysis(so_df_processed, produk_ref, _start_date_bln1, _end_date_bln1, _start_date_bln2, _end_date_bln2, _start_date_bln3, _end_date_bln3):
    """Fungsi ini berisi logika inti analisis ABC Anda."""
    
    so_df = so_df_processed.copy()
    
    # 1. Filter 3 DataFrame
    mask1 = (so_df['Tgl Faktur'].dt.date >= _start_date_bln1) & (so_df['Tgl Faktur'].dt.date <= _end_date_bln1)
    so_df_bln1 = so_df.loc[mask1]
    mask2 = (so_df['Tgl Faktur'].dt.date >= _start_date_bln2) & (so_df['Tgl Faktur'].dt.date <= _end_date_bln2)
    so_df_bln2 = so_df.loc[mask2]
    mask3 = (so_df['Tgl Faktur'].dt.date >= _start_date_bln3) & (so_df['Tgl Faktur'].dt.date <= _end_date_bln3)
    so_df_bln3 = so_df.loc[mask3]

    # 2. Agregasi Kuantitas
    agg_bln1 = so_df_bln1.groupby(['City', 'No. Barang', 'Platform'])['Kuantitas'].sum().reset_index(name='Kuantitas_Bulan_1')
    agg_bln2 = so_df_bln2.groupby(['City', 'No. Barang', 'Platform'])['Kuantitas'].sum().reset_index(name='Kuantitas_Bulan_2')
    agg_bln3 = so_df_bln3.groupby(['City', 'No. Barang', 'Platform'])['Kuantitas'].sum().reset_index(name='Kuantitas_Bulan_3')

    # 3. Siapkan daftar produk master
    produk_ref.rename(columns={'Keterangan Barang': 'Nama Barang', 'Nama Kategori Barang': 'Kategori Barang'}, inplace=True, errors='ignore')
    barang_list = produk_ref[['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']].drop_duplicates()
    city_list = so_df['City'].dropna().unique()
    platform_list = so_df['Platform'].dropna().unique()
    
    if len(city_list) == 0 or len(platform_list) == 0:
        st.warning("Data penjualan ada, namun tidak memiliki informasi 'City' atau 'Platform' yang valid.")
        return pd.DataFrame()

    kombinasi = pd.MultiIndex.from_product(
        [city_list, barang_list['No. Barang'], platform_list], 
        names=['City', 'No. Barang', 'Platform']
    ).to_frame(index=False)
    kombinasi = pd.merge(kombinasi, barang_list, on='No. Barang', how='left')
    
    # 4. Gabungkan (merge) data bulanan
    grouped = pd.merge(kombinasi, agg_bln1, on=['City', 'No. Barang', 'Platform'], how='left')
    grouped = pd.merge(grouped, agg_bln2, on=['City', 'No. Barang', 'Platform'], how='left')
    grouped = pd.merge(grouped, agg_bln3, on=['City', 'No. Barang', 'Platform'], how='left')
    
    # 5. Isi NaN
    grouped.fillna({'Kuantitas_Bulan_1': 0, 'Kuantitas_Bulan_2': 0, 'Kuantitas_Bulan_3': 0}, inplace=True)
    
    # 6. Hitung Metrik Kuantitas
    grouped['Total_Kuantitas'] = grouped['Kuantitas_Bulan_1'] + grouped['Kuantitas_Bulan_2'] + grouped['Kuantitas_Bulan_3']
    grouped['Rata_Rata_Kuantitas'] = grouped['Total_Kuantitas'] / 3
    grouped['Kuantitas_WMA'] = ((grouped['Kuantitas_Bulan_1'] * 1) + (grouped['Kuantitas_Bulan_2'] * 2) + (grouped['Kuantitas_Bulan_3'] * 3)) / 6
    
    # 7. Jalankan klasifikasi ABCDE
    result_df = classify_abc_by_metric(grouped, 'Total_Kuantitas', 'Kategori ABC')
    result_df = classify_abc_by_metric(result_df, 'Rata_Rata_Kuantitas', 'ABC_Rata_Rata')
    result_df = classify_abc_by_metric(result_df, 'Kuantitas_WMA', 'ABC_WMA')

    # 8. [DIHAPUS] Blok perhitungan margin telah dihapus seluruhnya

    return result_df


# --- FUNGSI RENDER HALAMAN UTAMA ---

def render_page():
    st.title("📊 Analisis ABC Berdasarkan Kuantitas 3 Bulan Terakhir (Metode Kuartal)")
    tab1_abc, tab2_abc = st.tabs(["Hasil Tabel", "Dashboard"])

    with tab1_abc:
        # --- Pengecekan Data Awal ---
        # [DIUBAH] Pengecekan df_portal dihapus
        if st.session_state.df_penjualan.empty or st.session_state.produk_ref.empty:
            st.warning("⚠️ Harap muat file **Penjualan** dan **Produk Referensi** di halaman **'Input Data'** terlebih dahulu.")
            st.stop()
            
        all_so_df = st.session_state.df_penjualan.copy()
        produk_ref = st.session_state.produk_ref.copy()
        # [DIHAPUS] portal_df = st.session_state.df_portal.copy()
        
        # [DIUBAH] portal_df dihapus dari loop
        for df in [all_so_df, produk_ref]:
            if 'No. Barang' in df.columns:
                df['No. Barang'] = df['No. Barang'].astype(str).str.strip()
                
        so_df = all_so_df.copy()
        so_df.rename(columns={'Qty': 'Kuantitas'}, inplace=True, errors='ignore')

        # --- Pengecekan Kuantitas & Revenue ---
        if 'Kuantitas' not in so_df.columns:
            st.error("❌ ANALISIS GAGAL: Kolom 'Kuantitas' tidak ditemukan.")
            st.stop()
        
        # [DIUBAH] Blok ini disederhanakan, karena 'Harga Sat' tidak lagi wajib
        # Kita hanya perlu memastikan Kuantitas itu numerik
        so_df['Kuantitas'] = pd.to_numeric(so_df['Kuantitas'], errors='coerce')
        so_df.fillna({'Kuantitas': 0}, inplace=True)
        st.session_state.revenue_available = False # Setel ke False
        
        if 'Harga Sat' in so_df.columns:
            st.info("Info: Kolom 'Harga Sat' terdeteksi, namun tidak digunakan dalam analisis ABC ini.")
        
        # --- Preprocessing Data ---
        so_df['Nama Dept'] = so_df.apply(utils.map_nama_dept, axis=1)
        so_df['City'] = so_df['Nama Dept'].apply(utils.map_city)
        so_df['Platform'] = so_df.apply(utils.map_platform, axis=1)
        so_df['Tgl Faktur'] = pd.to_datetime(so_df['Tgl Faktur'], dayfirst=True, errors='coerce')
        so_df.dropna(subset=['Tgl Faktur'], inplace=True)
        
        with st.expander("Lihat Data Penjualan Siap Analisis (Setelah Preprocessing)"):
            st.dataframe(so_df)
            st.download_button(
                label="📥 Unduh Data Penjualan (Hasil Preprocessing)",
                data=utils.convert_df_to_excel(so_df),
                file_name="data_penjualan_preprocessed.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        # --- Filter Rentang Waktu ---
        st.header("Filter Rentang Waktu Analisis")
        st.info("Pilih tanggal akhir. Analisis akan mengambil data 3 blok 30-hari (total 90 hari) mundur dari tanggal yang Anda pilih.")

        today = datetime.now().date()
        selected_end_date = st.date_input("Pilih Tanggal Akhir Analisis", value=today)
        end_date_bln3 = selected_end_date
        start_date_bln3 = end_date_bln3 - timedelta(days=29)
        end_date_bln2 = start_date_bln3 - timedelta(days=1)
        start_date_bln2 = end_date_bln2 - timedelta(days=29)
        end_date_bln1 = start_date_bln2 - timedelta(days=1)
        start_date_bln1 = end_date_bln1 - timedelta(days=29)

        st.markdown(f"**Bulan 3 (Terkini):** `{start_date_bln3.strftime('%Y-%m-%d')}` s/d `{end_date_bln3.strftime('%Y-%m-%d')}`")
        st.markdown(f"**Bulan 2:** `{start_date_bln2.strftime('%Y-%m-%d')}` s/d `{end_date_bln2.strftime('%Y-%m-%d')}`")
        st.markdown(f"**Bulan 1 (Terlama):** `{start_date_bln1.strftime('%Y-%m-%d')}` s/d `{end_date_bln1.strftime('%Y-%m-%d')}`")
            
        if st.button("Jalankan Analisa ABC (Metode Baru)"):
            with st.spinner("Melakukan perhitungan analisis ABC berbasis Kuantitas..."):
                # [DIUBAH] portal_df dihapus dari panggilan fungsi
                result_df = run_abc_analysis(
                    so_df, produk_ref,
                    start_date_bln1, end_date_bln1,
                    start_date_bln2, end_date_bln2,
                    start_date_bln3, end_date_bln3
                )
                st.session_state.abc_analysis_result = result_df
                st.success("Analisis ABC (3 metode berbasis Kuantitas) berhasil dijalankan!")

        # --- Tampilkan Hasil Analisis ---
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
                    
            st.header("Hasil Analisis ABC per Kota")
            
            number_format = '{:,.0f}'
            # [DIHAPUS] percent_format = '{:.1%}'
            
            for city in sorted(result_display['City'].unique()):
                with st.expander(f"🏙️ Lihat Hasil ABC untuk Kota: {city}"):
                    city_df = result_display[result_display['City'] == city]
                    city_df_sorted = city_df.sort_values(by=['Total_Kuantitas', 'Platform'], ascending=[False, True])
                        
                    # [DIUBAH] Kolom margin dihapus
                    display_cols_order = [
                        'No. Barang', 'Nama Barang', 'BRAND Barang', 'Kategori Barang', 'Platform', 
                        'Kuantitas_Bulan_1', 'Kuantitas_Bulan_2', 'Kuantitas_Bulan_3',
                        'Total_Kuantitas', 'Rata_Rata_Kuantitas', 'Kuantitas_WMA',
                        'Kategori ABC', 'ABC_Rata_Rata', 'ABC_WMA'
                        # 'Margin Harga', 'Margin Persen' <-- DIHAPUS
                    ]
                    display_cols_order = [col for col in display_cols_order if col in city_df_sorted.columns]
                    df_display = city_df_sorted[display_cols_order]
                    
                    # [DIUBAH] Format margin dihapus
                    styler_obj = df_display.style.format({
                        'Kuantitas_Bulan_1': number_format,
                        'Kuantitas_Bulan_2': number_format,
                        'Kuantitas_Bulan_3': number_format,
                        'Total_Kuantitas': number_format,
                        'Rata_Rata_Kuantitas': number_format,
                        'Kuantitas_WMA': number_format
                        # 'Margin Harga': number_format, <-- DIHAPUS
                        # 'Margin Persen': percent_format <-- DIHAPUS
                    }).map(highlight_kategori_abc, subset=['Kategori ABC', 'ABC_Rata_Rata', 'ABC_WMA'])
                    
                    st.markdown(styler_obj.to_html(), unsafe_allow_html=True)

            # --- Logika Unduh ---
            st.header("💾 Unduh Hasil Analisis ABC")
            df_to_download = result_display if (selected_kategori_abc or selected_brand_abc) else st.session_state.abc_analysis_result
            excel_data_final = utils.convert_df_to_excel(df_to_download)
            st.download_button(
                "📥 Unduh Hasil Analisis ABC Lengkap (Excel)",
                data=excel_data_final,
                file_name=f"Hasil_Analisis_ABC_3Bulan_{today.strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        elif st.session_state.abc_analysis_result is not None:
                st.info("Tidak ada data untuk ditampilkan. Harap periksa filter tanggal atau data input Anda.")


    # --- TAB 2: DASHBOARD ---
    with tab2_abc:
        if 'abc_analysis_result' in st.session_state and st.session_state.abc_analysis_result is not None and not st.session_state.abc_analysis_result.empty:
            result_display_dash = st.session_state.abc_analysis_result.copy()
            
            sub_tab_total, sub_tab_avg, sub_tab_wma = st.tabs([
                "📈 Analisis by Total Kuantitas",  
                "📊 Analisis by Rata-Rata",  
                "📉 Analisis by WMA"
            ])

            with sub_tab_total:
                create_dashboard_view(result_display_dash, 'Kategori ABC', 'Total_Kuantitas', 'Total Kuantitas')
            with sub_tab_avg:
                create_dashboard_view(result_display_dash, 'ABC_Rata_Rata', 'Rata_Rata_Kuantitas', 'Rata-Rata Kuantitas')
            with sub_tab_wma:
                create_dashboard_view(result_display_dash, 'ABC_WMA', 'Kuantitas_WMA', 'WMA Kuantitas')
        else:
            st.info("Tidak ada data untuk ditampilkan di dashboard. Jalankan analisis di tab 'Hasil Tabel' terlebih dahulu.")
