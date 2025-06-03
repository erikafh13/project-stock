import streamlit as st
import pandas as pd
import numpy as np
import calendar
from io import BytesIO
import math


st.set_page_config(layout="wide")
st.title("Perhitungan ROP & PO dengan WMA dan Analisis ABC")

# Input file per bulan
st.header("1. Upload Data Penjualan per Bulan")
uploaded_files = st.file_uploader(
    "Unggah file penjualan (CSV atau Excel), satu per bulan", 
    type=["xlsx", "xls", "csv"], 
    accept_multiple_files=True,
    key="file_uploader"
)

# Input file kategori barang
st.header("2. Upload Data Referensi Barang")
produk_file = st.file_uploader(
    "Unggah file referensi barang (Excel)", 
    type=["xlsx", "xls"],
    key="produk_file"
)

# Input file kategori barang
st.header("3. Upload Data Stock Barang")
stock_file = st.file_uploader(
    "Unggah file referensi barang (Excel)", 
    type=["xlsx", "xls"],
    key="file"
)

def highlight_kategori(val):
    warna = {
        'A': 'background-color: #b6e4b6',   # Hijau
        'B': 'background-color: #fff3b0',   # Kuning
        'C': 'background-color: #ffd6a5',   # Oranye
        'D': 'background-color: #f4bbbb'    # Merah
    }
    return warna.get(val, '')

def calculate_min_stock(avg_wma):
    return avg_wma * 0.7

def remove_outliers(data, threshold=2):
    avg = np.mean(data)
    return [x for x in data if abs(x - avg) <= threshold * avg]

def get_z_score(category, volatility):
    base_z = {'A': 1.65, 'B': 1.0, 'C': 0.0, 'D': 0.0}.get(category, 0.0)
    if volatility > 1.5:
        return base_z + 0.2
    elif volatility < 0.5:
        return base_z - 0.2
    return base_z

def calculate_safety_stock_from_series(penjualan_bulanan, category, lead_time=0.7):
    clean_data = remove_outliers(penjualan_bulanan)
    if len(clean_data) < 2:
        return 0  # Tidak cukup data untuk deviasi
    std_dev = np.std(clean_data)
    mean = np.mean(clean_data)
    volatility = std_dev / (mean + 1e-6)
    z = get_z_score(category, volatility)
    return round(z * std_dev * math.sqrt(lead_time), 2)

def calculate_rop(min_stock, safety_stock):
    return min_stock + safety_stock

# Tentukan Status Stock
def get_status_stock(row):
    if row['Kategori ABC'] == 'D':
        if row['Stock'] > 2:
            return 'Overstock D'
        else:
            return 'Balance'
    elif row['Stock'] > row['Max Stock']:
        return 'Overstock no D'
    elif row['Stock'] >= row['ROP'] and row['Stock'] <= row['Max Stock']:
        return 'Balance'
    elif row['Stock'] < row['ROP']:
        return 'Understock'
    else:
        return '-'

def highlight_status_stock(val):
    colors = {
        'Understock': 'background-color: #fff3b0',     # Kuning
        'Balance': 'background-color: #b6e4b6',        # Hijau
        'Overstock no D': 'background-color: #ffd6a5', # Oranye
        'Overstock D': 'background-color: #f4bbbb'     # Merah
    }
    return colors.get(val, '')

def highlight_restock(val):
    if val == 'YES':
        return 'background-color: #add8e6'  # Biru
    return ''

# Tambahkan kolom Max Stock
def calculate_max_stock(avg_wma, category):
    multiplier = {'A': 2, 'B': 1, 'C': 0.5, 'D': 0}
    return avg_wma * multiplier.get(category, 0)

# Fungsi untuk menghitung Suggested PO Cabang
def hitung_po_cabang(stock_surabaya, add_stock_cabang, stock_cabang, so_cabang, stock_total, so_total):
    try:
        if stock_surabaya < add_stock_cabang:
            return 0

        kebutuhan_20hari = so_cabang / 30 * 20

        if stock_total < so_total and stock_cabang < kebutuhan_20hari:
            ideal_po = ((stock_cabang + add_stock_cabang) / stock_total * stock_surabaya) - stock_cabang
            return max(0, round(ideal_po))
        else:
            return round(add_stock_cabang)

    except (ZeroDivisionError, TypeError):
        return 0


if uploaded_files and produk_file:
    # Gabungkan data penjualan dari semua file
    penjualan_list = []
    for file in uploaded_files:
        if file.name.endswith(".csv"):
            df = pd.read_csv(file)
        else:
            df = pd.read_excel(file)
        df['source_file'] = file.name
        penjualan_list.append(df)
    penjualan = pd.concat(penjualan_list, ignore_index=True)

    produk_ref = pd.read_excel(produk_file)

    # Normalisasi kolom
    produk_ref.rename(columns={
        'Nama Kategori Barang Barang': 'Kategori Barang',
        'Keterangan Barang': 'Nama Barang'
    }, inplace=True)

    penjualan['City'] = penjualan['City'].replace('Project', 'Surabaya')
    penjualan = penjualan[penjualan['City'].notnull() & (penjualan['City'] != 0) & (penjualan['City'].str.lower() != 'others')]

    penjualan['Tgl Faktur'] = pd.to_datetime(penjualan['Tgl Faktur'])
    penjualan['Bulan'] = penjualan['Tgl Faktur'].dt.to_period('M')
    penjualan['Bulan Nama'] = penjualan['Tgl Faktur'].dt.strftime('%b-%Y')

    # Bobot bulan (terbaru ke lama): 0.5, 0.3, 0.2
    bulan_unik = sorted(penjualan['Bulan'].unique(), reverse=True)[:3]
    bobot_nilai = [0.5, 0.3, 0.2]
    bobot_dict = {bulan: bobot_nilai[i] for i, bulan in enumerate(bulan_unik)}
    penjualan = penjualan[penjualan['Bulan'].isin(bobot_dict.keys())]
    penjualan['Bobot'] = penjualan['Bulan'].map(bobot_dict)
    penjualan['WMA_Kuantitas'] = penjualan['Kuantitas'] * penjualan['Bobot']

    # Hitung WMA per City + No Barang
    wma_grouped = penjualan.groupby(['City', 'No. Barang'])[['WMA_Kuantitas']].sum().reset_index()
    wma_grouped['AVG WMA'] = wma_grouped['WMA_Kuantitas']
    wma_grouped.drop(columns='WMA_Kuantitas', inplace=True)

    # Kombinasi City x Produk
    barang_list = produk_ref[['Kategori Barang', 'No. Barang', 'Nama Barang']].drop_duplicates()
    city_list = penjualan['City'].unique()
    kombinasi = pd.MultiIndex.from_product(
        [city_list, barang_list.itertuples(index=False)],
        names=['City', 'Produk']
    ).to_frame(index=False)
    kombinasi[['Kategori Barang', 'No. Barang', 'Nama Barang']] = pd.DataFrame(kombinasi['Produk'].tolist(), index=kombinasi.index)
    kombinasi.drop(columns='Produk', inplace=True)

    full_data = pd.merge(kombinasi, wma_grouped, on=['City', 'No. Barang'], how='left')
    full_data['AVG WMA'] = full_data['AVG WMA'].fillna(0)

    # Kuantitas per bulan
    monthly_sales = penjualan.groupby(['City', 'No. Barang', 'Bulan Nama'])['Kuantitas'].sum().unstack(fill_value=0).reset_index()
    bulan_columns = sorted([col for col in monthly_sales.columns if col not in ['City', 'No. Barang']], key=lambda x: pd.to_datetime(x, format='%b-%Y'))
    monthly_sales = monthly_sales[['City', 'No. Barang'] + bulan_columns]
    monthly_sales['AVG no WMA'] = monthly_sales[bulan_columns].mean(axis=1)
    monthly_sales['STD DEV'] = monthly_sales[bulan_columns].std(axis=1)

    # Gabung semua data
    full_data = pd.merge(full_data, monthly_sales, on=['City', 'No. Barang'], how='left')
    full_data.fillna(0, inplace=True)

    full_data['Total Kuantitas'] = full_data['AVG WMA']

    def classify_abc(city_df):
        city_df = city_df.sort_values(by='Total Kuantitas', ascending=False).reset_index(drop=True)
        total = city_df['Total Kuantitas'].sum()
        if total == 0:
            city_df['% kontribusi'] = 0
            city_df['% Kumulatif'] = 0
            city_df['Kategori ABC'] = 'D'
        else:
            city_df['% kontribusi'] = 100 * city_df['Total Kuantitas'] / total
            city_df['% Kumulatif'] = city_df['% kontribusi'].cumsum()
            city_df['Kategori ABC'] = city_df['% Kumulatif'].apply(
                lambda x: 'A' if x <= 70 else ('B' if x <= 90 else 'C')
            )
        return city_df

    terjual = full_data[full_data['Total Kuantitas'] > 0].copy()
    tidak_terjual = full_data[full_data['Total Kuantitas'] == 0].copy()
    abc_data = terjual.groupby('City').apply(classify_abc).reset_index(drop=True)
    tidak_terjual['% kontribusi'] = 0
    tidak_terjual['% Kumulatif'] = 0
    tidak_terjual['Kategori ABC'] = 'D'

    final_result = pd.concat([abc_data, tidak_terjual], ignore_index=True)
    final_result = final_result.sort_values(by=['City', 'Kategori ABC', 'Kategori Barang', 'AVG WMA'], ascending=[True, True, True, False])
    
    # Tambahkan kolom ROP
    final_result['Min Stock'] = final_result['AVG WMA'].apply(calculate_min_stock)
    def calculate_safety_stock_dynamic(row):
        monthly_values = row[bulan_columns].tolist()
        return calculate_safety_stock_from_series(monthly_values, row['Kategori ABC'])

    final_result['Safety Stock'] = final_result.apply(calculate_safety_stock_dynamic, axis=1)
    final_result['ROP'] = final_result.apply(lambda row: calculate_rop(row['Min Stock'], row['Safety Stock']), axis=1)

    # Tambahkan kolom Max Stock
    final_result['Max Stock'] = final_result.apply(lambda row: calculate_max_stock(row['AVG WMA'], row['Kategori ABC']), axis=1)
    # Pembulatan akhir
    int_cols = ['Feb-2025', 'Mar-2025', 'Apr-2025', 'AVG no WMA', 'AVG WMA', 'STD DEV', 'Min Stock', 'Max Stock', 'Safety Stock', 'ROP']
    final_result[int_cols] = final_result[int_cols].round(0).astype(int)
    final_result['% kontribusi'] = final_result['% kontribusi'].round(1)
    final_result['% Kumulatif'] = final_result['% Kumulatif'].round(1)

    # Urutkan kolom
    ordered_cols = (['City', 'No. Barang', 'Nama Barang', 'Kategori Barang'] + 
                    bulan_columns + ['AVG no WMA', 'AVG WMA', '% kontribusi', 
                                     '% Kumulatif', 'Kategori ABC', 'Min Stock', 
                                     'Safety Stock', 'ROP','Max Stock'])
    final_result = final_result[ordered_cols]

if stock_file is not None:
    st.header("4. Analisis Kebutuhan PO (Purchase Order)")

    # Load and unpivot (melt) the stock data
    stock_df = pd.read_excel(stock_file)

    # Ubah nama kolom agar konsisten jika perlu
    stock_df.rename(columns=lambda x: x.strip(), inplace=True)  # Hilangkan spasi ekstra
    stock_melted = stock_df.melt(
        id_vars=['No. Barang'],
        value_vars=[
            'Stock_Bali', 'Stock_Jakarta', 'Stock_Jogja',
            'Stock_Malang', 'Stock_Semarang', 'Stock_Surabaya'
        ],
        var_name='City',
        value_name='Stock'
    )

    # Pembulatan Stock
    stock_melted['Stock'] = stock_melted['Stock'].round(0).astype(int)

    # Ubah 'Stock_Bali' → 'Bali', dst
    stock_melted['City'] = stock_melted['City'].str.replace('Stock_', '', regex=False)

    # Gabungkan dengan final_result
    final_result = pd.merge(final_result, stock_melted, on=['City', 'No. Barang'], how='left')
    final_result['Stock Cabang'] = final_result['Stock'].fillna(0).round(0).astype(int)

    # Hitung selisih
    final_result['Selisih'] = final_result['Stock Cabang'] - final_result['ROP']

    final_result['Status Stock'] = final_result.apply(get_status_stock, axis=1)

    # Kolom Add Stock
    final_result['Add Stock'] = final_result['ROP'] - final_result['Stock Cabang']
    final_result['Add Stock'] = final_result['Add Stock'].apply(lambda x: int(x) if x > 0 else '-')

    # Kolom Stock Surabaya
    stock_surabaya = stock_melted[stock_melted['City'] == 'Surabaya'][['No. Barang', 'Stock']].rename(columns={'Stock': 'Stock Surabaya'})
    stock_surabaya['Stock Surabaya'] = stock_surabaya['Stock Surabaya'].fillna(0).round(0).astype(int)
    # Gabungkan ke final_result berdasarkan 'No. Barang'
    final_result = final_result.merge(stock_surabaya, on='No. Barang', how='left')
    # Isi NaN jika ada barang yang tidak punya stok Surabaya
    final_result['Stock Surabaya'] = final_result['Stock Surabaya'].fillna(0).round(0).astype(int)

    # Pindahkan kolom Stock Total setelah Stock Surabaya
    # Pindahkan kolom Stock Total setelah Stock Surabaya (jika dua-duanya ada)
    if 'Stock Surabaya' in final_result.columns and 'Stock Total' in final_result.columns:
        ordered_cols = list(final_result.columns)
        stock_total_col = ordered_cols.pop(ordered_cols.index('Stock Total'))
        surabaya_idx = ordered_cols.index('Stock Surabaya') + 1
        ordered_cols.insert(surabaya_idx, stock_total_col)
        final_result = final_result[ordered_cols]

    # Hitung Stock Total
    stock_total = stock_melted.groupby('No. Barang')['Stock'].sum().reset_index().rename(columns={'Stock': 'Stock Total'})
    final_result = final_result.merge(stock_total, on='No. Barang', how='left')
    final_result['Stock Total'] = final_result['Stock Total'].fillna(0).round(0).astype(int)

    # Hitung SO Total
    so_total = final_result.groupby('No. Barang')['AVG WMA'].sum().reset_index().rename(columns={'AVG WMA': 'SO Total'})
    final_result = final_result.merge(so_total, on='No. Barang', how='left')
    final_result['SO Total'] = final_result['SO Total'].fillna(0).round(0).astype(int)

    # Hitung Suggested PO Cabang
    # Terapkan fungsi ke setiap baris
    final_result['Suggested PO'] = final_result.apply(
        lambda row: hitung_po_cabang(
            stock_surabaya=row['Stock Surabaya'],
            add_stock_cabang=row['Add Stock'],
            stock_cabang=row['Stock'],
            so_cabang=row['AVG WMA'],
            stock_total=row['Stock Total'],
            so_total=row['SO Total']
        ), axis=1
    )

    # Hitung total Suggested PO per barang
    po_total = final_result.groupby('Nama Barang')['Suggested PO'].sum().reset_index()
    po_total.rename(columns={'Suggested PO': 'Suggested PO Total'}, inplace=True)

    # Gabungkan ke final_result
    final_result = final_result.merge(po_total, on='Nama Barang', how='left')

    # Kolom Restock 1 Bulan apakah YES or NO
    final_result['Restock 1 Bulan'] = final_result.apply(
        lambda row: 'PO' if row['Stock Total'] < row['SO Total'] else 'NO',
        axis=1
    )

    # Hapus kolom sementara
    final_result.drop(columns=['Selisih'], inplace=True)
 
    # Tampilkan
    for city in sorted(final_result['City'].unique()):
        st.subheader(f"📍 Kota: {city}")
        city_df = final_result[final_result['City'] == city].copy()
        styled_df = city_df.style\
            .applymap(highlight_kategori, subset=['Kategori ABC'])\
            .applymap(highlight_status_stock, subset=['Status Stock'])\

        st.dataframe(styled_df, use_container_width=True)

    # Unduh Excel
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        for city, city_df in final_result.groupby('City'):
            city_df.to_excel(writer, sheet_name=city[:31], index=False)
        final_result.to_excel(writer, sheet_name="All Cities", index=False)

    st.download_button(
        label="📥 Unduh Hasil Excel",
        data=output.getvalue(),
        file_name="Hasil Analisis.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    
else:
    st.info("Silakan unggah semua file yang dibutuhkan terlebih dahulu.")


