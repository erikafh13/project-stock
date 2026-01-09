import streamlit as st
import pandas as pd
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Bundling PC", layout="wide")

st.title("🖥️ Sistem Bundling PC")
st.markdown("Pilih komponen Anda berdasarkan kategori kebutuhan.")

# --- FUNGSI PEMROSESAN DATA ---
def process_data(df):
    # Filter Stock > 0 dan kolom yang diperlukan
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Mapping Kolom Baru
    df['Office'] = 0
    df['Gaming Standard / Design 2D'] = 0
    df['Gaming Advanced / Design 3D'] = 0
    df['NeedVGA'] = 0
    df['HasPSU'] = 0

    # 1. PROCESSOR
    proc_mask = df['Kategori'] == 'Processor'
    def map_processor(row):
        name = row['Nama Accurate'].upper()
        if re.search(r'\d+[0-9]F\b', name): row['NeedVGA'] = 1
        if 'I3' in name or 'I5' in name:
            row['Office'] = 1
            row['Gaming Standard / Design 2D'] = 1
        if 'I5' in name or 'I7' in name or 'I9' in name:
            row['Gaming Advanced / Design 3D'] = 1
        return row
    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # 2. MOTHERBOARD
    mb_mask = df['Kategori'] == 'Motherboard'
    h_intel = ['H410', 'H510', 'H610', 'H810', 'H81', 'H110', 'H310']
    b_intel, z_intel = ['B660', 'B760', 'B860'], ['Z790', 'Z890']
    a_amd, b_amd, x_amd = ['A520', 'A620'], ['B450', 'B550', 'B650', 'B840', 'B850'], ['X870']
    
    def map_mobo(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if any(x in name for x in h_intel) or any(x in name for x in a_amd): row['Office'] = 1
        if (any(x in name for x in b_intel) and price < 2000000) or any(x in name for x in b_amd):
            row['Gaming Standard / Design 2D'] = 1
        if (any(x in name for x in b_intel) and price >= 2000000) or any(x in name for x in z_intel) or \
           any(x in name for x in b_amd) or any(x in name for x in x_amd):
            row['Gaming Advanced / Design 3D'] = 1
        return row
    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # 3. RAM
    ram_mask = df['Kategori'] == 'Memory RAM'
    def map_ram(row):
        name = re.sub(r'\(.*?\)', '', row['Nama Accurate'].upper())
        match = re.search(r'(\d+)\s*GB', name)
        if match:
            size = int(match.group(1))
            if 8 <= size <= 16: row['Office'] = 1
            if 16 <= size <= 32: row['Gaming Standard / Design 2D'] = 1
            if 32 <= size <= 128: row['Gaming Advanced / Design 3D'] = 1
        return row
    df.loc[ram_mask] = df[ram_mask].apply(map_ram, axis=1)

    # 4. SSD
    df.loc[df['Kategori'] == 'SSD Internal', ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = 1

    # 5. VGA
    vga_mask = df['Kategori'] == 'VGA'
    gt_off = ['GT710', 'GT730']
    vga_std = ['GT1030', 'GTX1650', 'RTX3050', 'RTX3060', 'RTX5050', 'RTX4060']
    vga_adv = ['RTX5060', 'RTX5070', 'RTX5080', 'RTX5090']
    def map_vga(row):
        name = row['Nama Accurate'].upper()
        if any(x in name for x in gt_off): row['Office'] = 1
        if any(x in name for x in vga_std): row['Gaming Standard / Design 2D'] = 1
        if any(x in name for x in vga_adv) or 'TI' in name: row['Gaming Advanced / Design 3D'] = 1
        return row
    df.loc[vga_mask] = df[vga_mask].apply(map_vga, axis=1)

    # 6. CASING
    case_mask = df['Kategori'] == 'Casing PC'
    def map_case(row):
        if 'PSU' in row['Nama Accurate'].upper():
            row['Office'], row['HasPSU'] = 1, 1
        else:
            row['Gaming Standard / Design 2D'], row['Gaming Advanced / Design 3D'] = 1, 1
        return row
    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # 7. PSU
    psu_mask = df['Kategori'] == 'Power Supply'
    certs = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'TITANIUM']
    def map_psu(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if price < 500000: row['Office'] = 1
        if price >= 500000: row['Gaming Standard / Design 2D'] = 1
        if any(c in name for c in certs): row['Gaming Advanced / Design 3D'] = 1
        return row
    df.loc[psu_mask] = df[psu_mask].apply(map_psu, axis=1)
    
    return df

# --- INPUT DATA ---
uploaded_file = st.file_uploader("Upload Data Portal (CSV)", type="csv")

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file)
    data = process_data(raw_df)
    
    # --- PILIH KATEGORI ---
    bundle_type = st.radio("Pilih Kategori PC:", 
                           ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])
    
    st.divider()
    
    # Filter data berdasarkan kategori bundle dan urutkan harga
    filtered_data = data[data[bundle_type] == 1].sort_values('Web')

    selected_bundle = {}

    # 1. PROCESSOR
    procs = filtered_data[filtered_data['Kategori'] == 'Processor']
    p_choice = st.selectbox("1. Pilih Processor:", procs['Nama Accurate'] + " - Rp" + procs['Web'].map('{:,.0f}'.format))
    if p_choice:
        selected_proc_name = p_choice.split(" - Rp")[0]
        selected_proc = procs[procs['Nama Accurate'] == selected_proc_name].iloc[0]
        selected_bundle['Processor'] = selected_proc

    # 2. MOTHERBOARD
    mobs = filtered_data[filtered_data['Kategori'] == 'Motherboard']
    m_choice = st.selectbox("2. Pilih Motherboard:", mobs['Nama Accurate'] + " - Rp" + mobs['Web'].map('{:,.0f}'.format))
    if m_choice:
        selected_bundle['Motherboard'] = mobs[mobs['Nama Accurate'] == m_choice.split(" - Rp")[0]].iloc[0]

    # 3. RAM
    rams = filtered_data[filtered_data['Kategori'] == 'Memory RAM']
    r_choice = st.selectbox("3. Pilih Memory RAM:", rams['Nama Accurate'] + " - Rp" + rams['Web'].map('{:,.0f}'.format))
    if r_choice:
        selected_bundle['RAM'] = rams[rams['Nama Accurate'] == r_choice.split(" - Rp")[0]].iloc[0]

    # 4. SSD
    ssds = filtered_data[filtered_data['Kategori'] == 'SSD Internal']
    s_choice = st.selectbox("4. Pilih SSD Internal:", ssds['Nama Accurate'] + " - Rp" + ssds['Web'].map('{:,.0f}'.format))
    if s_choice:
        selected_bundle['SSD'] = ssds[ssds['Nama Accurate'] == s_choice.split(" - Rp")[0]].iloc[0]

    # 5. VGA (Conditional)
    need_vga = selected_bundle['Processor']['NeedVGA'] == 1
    if need_vga:
        vgas = filtered_data[filtered_data['Kategori'] == 'VGA']
        v_choice = st.selectbox("5. Pilih VGA (Wajib untuk Seri F):", vgas['Nama Accurate'] + " - Rp" + vgas['Web'].map('{:,.0f}'.format))
        if v_choice:
            selected_bundle['VGA'] = vgas[vgas['Nama Accurate'] == v_choice.split(" - Rp")[0]].iloc[0]
    else:
        st.info("Processor ini memiliki IGPU, VGA Opsional.")
        add_vga = st.checkbox("Tambah VGA Tambahan?")
        if add_vga:
            vgas = filtered_data[filtered_data['Kategori'] == 'VGA']
            v_choice = st.selectbox("Pilih VGA:", vgas['Nama Accurate'] + " - Rp" + vgas['Web'].map('{:,.0f}'.format))
            if v_choice:
                selected_bundle['VGA'] = vgas[vgas['Nama Accurate'] == v_choice.split(" - Rp")[0]].iloc[0]

    # 6. CASING
    cases = filtered_data[filtered_data['Kategori'] == 'Casing PC']
    c_choice = st.selectbox("6. Pilih Casing PC:", cases['Nama Accurate'] + " - Rp" + cases['Web'].map('{:,.0f}'.format))
    if c_choice:
        selected_bundle['Casing'] = cases[cases['Nama Accurate'] == c_choice.split(" - Rp")[0]].iloc[0]

    # 7. PSU (Conditional)
    has_psu = selected_bundle['Casing']['HasPSU'] == 1
    if not has_psu:
        psus = filtered_data[filtered_data['Kategori'] == 'Power Supply']
        ps_choice = st.selectbox("7. Pilih Power Supply:", psus['Nama Accurate'] + " - Rp" + psus['Web'].map('{:,.0f}'.format))
        if ps_choice:
            selected_bundle['PSU'] = psus[psus['Nama Accurate'] == ps_choice.split(" - Rp")[0]].iloc[0]
    else:
        st.success("Casing sudah termasuk PSU (Kategori Office).")

    # --- RINGKASAN BUNDLE ---
    st.divider()
    st.subheader("📋 Ringkasan Bundling")
    total_price = 0
    for part, row in selected_bundle.items():
        st.write(f"**{part}**: {row['Nama Accurate']} - Rp{row['Web']:,.0f}")
        total_price += row['Web']
    
    st.markdown(f"### 💰 Total Harga: **Rp{total_price:,.0f}**")
else:
    st.warning("Silakan upload file CSV Data Portal untuk memulai.")
