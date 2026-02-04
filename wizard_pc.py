import streamlit as st
import pandas as pd
import re

# -------------------------------------------------
# KONFIGURASI HALAMAN
# -------------------------------------------------
st.set_page_config(page_title="Sistem Bundling PC", layout="wide")
st.title("🖥️ Sistem Bundling PC")
st.markdown("Pilih komponen PC berdasarkan kategori kebutuhan.")

# -------------------------------------------------
# FUNGSI PEMROSESAN DATA
# -------------------------------------------------
def process_data(df):
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)

    # Kolom kategori
    df['Office'] = 0
    df['Gaming Standard / Design 2D'] = 0
    df['Gaming Advanced / Design 3D'] = 0
    df['NeedVGA'] = 0
    df['HasPSU'] = 0

    # -------------------------
    # 1. PROCESSOR
    # -------------------------
    proc_mask = df['Kategori'] == 'Processor'

    def map_processor(row):
        name = row['Nama Accurate'].upper()

        if re.search(r'\d+[0-9]F\b', name):
            row['NeedVGA'] = 1

        if 'I3' in name or 'I5' in name:
            row['Office'] = 1
            row['Gaming Standard / Design 2D'] = 1

        if 'I5' in name or 'I7' in name or 'I9' in name:
            row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # -------------------------
    # 2. MOTHERBOARD
    # -------------------------
    mb_mask = df['Kategori'] == 'Motherboard'

    h_intel = ['H410', 'H510', 'H610', 'H810', 'H81', 'H110', 'H310']
    b_intel = ['B660', 'B760', 'B860']
    z_intel = ['Z790', 'Z890']

    a_amd = ['A520', 'A620']
    b_amd = ['B450', 'B550', 'B650', 'B840', 'B850']
    x_amd = ['X870']

    def map_mobo(row):
        name = row['Nama Accurate'].upper()
        price = row['Web']

        if any(x in name for x in h_intel) or any(x in name for x in a_amd):
            row['Office'] = 1

        if (any(x in name for x in b_intel) and price < 2_000_000) or any(x in name for x in b_amd):
            row['Gaming Standard / Design 2D'] = 1

        if (
            (any(x in name for x in b_intel) and price >= 2_000_000)
            or any(x in name for x in z_intel)
            or any(x in name for x in x_amd)
        ):
            row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # -------------------------
    # 3. RAM
    # -------------------------
    ram_mask = df['Kategori'] == 'Memory RAM'

    def map_ram(row):
        name = re.sub(r'\(.*?\)', '', row['Nama Accurate'].upper())
        match = re.search(r'(\d+)\s*GB', name)

        if match:
            size = int(match.group(1))

            if 8 <= size <= 16:
                row['Office'] = 1
            if 16 <= size <= 32:
                row['Gaming Standard / Design 2D'] = 1
            if size >= 32:
                row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[ram_mask] = df[ram_mask].apply(map_ram, axis=1)

    # -------------------------
    # 4. SSD
    # -------------------------
    ssd_mask = df['Kategori'] == 'SSD Internal'
    df.loc[ssd_mask, ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = 1

    # -------------------------
    # 5. VGA
    # -------------------------
    vga_mask = df['Kategori'] == 'VGA'

    gt_off = ['GT710', 'GT730']
    vga_std = ['GT1030', 'GTX1650', 'RTX3050', 'RTX3060', 'RTX4060', 'RTX5050']
    vga_adv = ['RTX5060', 'RTX5070', 'RTX5080', 'RTX5090']

    def map_vga(row):
        name = row['Nama Accurate'].upper()

        if any(x in name for x in gt_off):
            row['Office'] = 1
        if any(x in name for x in vga_std):
            row['Gaming Standard / Design 2D'] = 1
        if any(x in name for x in vga_adv) or 'TI' in name:
            row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[vga_mask] = df[vga_mask].apply(map_vga, axis=1)

    # -------------------------
    # 6. CASING
    # -------------------------
    case_mask = df['Kategori'] == 'Casing PC'

    def map_case(row):
        name = row['Nama Accurate'].upper()

        if 'PSU' in name:
            row['Office'] = 1
            row['HasPSU'] = 1
        else:
            row['Gaming Standard / Design 2D'] = 1
            row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # -------------------------
    # 7. PSU
    # -------------------------
    psu_mask = df['Kategori'] == 'Power Supply'
    certs = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'TITANIUM']

    def map_psu(row):
        name = row['Nama Accurate'].upper()
        price = row['Web']

        if price < 500_000:
            row['Office'] = 1
        if price >= 500_000:
            row['Gaming Standard / Design 2D'] = 1
        if any(c in name for c in certs):
            row['Gaming Advanced / Design 3D'] = 1

        return row

    df.loc[psu_mask] = df[psu_mask].apply(map_psu, axis=1)

    return df


# -------------------------------------------------
# INPUT FILE
# -------------------------------------------------
uploaded_file = st.file_uploader("Upload Data Portal (CSV)", type="csv")

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    data = process_data(raw_df)

    # -------------------------------------------------
    # TABEL STOK & HASIL PENGKATEGORIAN (DITAMPILKAN AWAL)
    # -------------------------------------------------
    st.subheader("📦 Data Stok & Hasil Pengkategorian")

    display_cols = [
        'Nama Accurate',
        'Kategori',
        'Stock Total',
        'Web',
        'Office',
        'Gaming Standard / Design 2D',
        'Gaming Advanced / Design 3D'
    ]

    st.dataframe(
        data[display_cols].sort_values('Stock Total', ascending=False),
        use_container_width=True
    )

    st.caption("Keterangan: 1 = Direkomendasikan, 0 = Tidak")

    # -------------------------------------------------
    # PILIH KATEGORI BUNDLE
    # -------------------------------------------------
    st.divider()

    bundle_type = st.radio(
        "Pilih Kategori PC:",
        ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"]
    )

    filtered_data = data[data[bundle_type] == 1].sort_values('Web')
    selected_bundle = {}

    # -------------------------------------------------
    # PROSES BUNDLING
    # -------------------------------------------------
    def select_component(label, df, key):
        options = df['Nama Accurate'] + " - Rp" + df['Web'].map('{:,.0f}'.format)
        choice = st.selectbox(label, options)
        if choice:
            name = choice.split(" - Rp")[0]
            selected_bundle[key] = df[df['Nama Accurate'] == name].iloc[0]

    select_component("1. Pilih Processor", filtered_data[filtered_data['Kategori'] == 'Processor'], 'Processor')
    select_component("2. Pilih Motherboard", filtered_data[filtered_data['Kategori'] == 'Motherboard'], 'Motherboard')
    select_component("3. Pilih Memory RAM", filtered_data[filtered_data['Kategori'] == 'Memory RAM'], 'RAM')
    select_component("4. Pilih SSD Internal", filtered_data[filtered_data['Kategori'] == 'SSD Internal'], 'SSD')

    # VGA Logic
    if selected_bundle.get('Processor') is not None:
        if selected_bundle['Processor']['NeedVGA'] == 1:
            select_component(
                "5. Pilih VGA (Wajib – CPU Seri F)",
                filtered_data[filtered_data['Kategori'] == 'VGA'],
                'VGA'
            )
        else:
            if st.checkbox("Tambah VGA Tambahan?"):
                select_component(
                    "5. Pilih VGA",
                    filtered_data[filtered_data['Kategori'] == 'VGA'],
                    'VGA'
                )

    # Casing
    select_component("6. Pilih Casing PC", filtered_data[filtered_data['Kategori'] == 'Casing PC'], 'Casing')

    # PSU Logic
    if selected_bundle.get('Casing') is not None:
        if selected_bundle['Casing']['HasPSU'] == 0:
            select_component(
                "7. Pilih Power Supply",
                filtered_data[filtered_data['Kategori'] == 'Power Supply'],
                'PSU'
            )
        else:
            st.success("Casing sudah termasuk PSU")

    # -------------------------------------------------
    # RINGKASAN
    # -------------------------------------------------
    st.divider()
    st.subheader("📋 Ringkasan Bundling")

    total_price = 0
    for part, row in selected_bundle.items():
        st.write(f"**{part}**: {row['Nama Accurate']} - Rp{row['Web']:,.0f}")
        total_price += row['Web']

    st.markdown(f"### 💰 Total Harga: **Rp{total_price:,.0f}**")

else:
    st.warning("Silakan upload file CSV Data Portal untuk memulai.")
