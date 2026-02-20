import streamlit as st
import pandas as pd
import re

# --- KONFIGURASI HALAMAN ---
st.set_page_config(page_title="Sistem Bundling PC - Pro", layout="wide")

# --- CSS CUSTOM UNTUK TAMPILAN CARD ---
st.markdown("""
<style>
    .bundle-card {
        border: 1px solid #ddd;
        border-radius: 10px;
        padding: 15px;
        background-color: white;
        margin-bottom: 20px;
        transition: 0.3s;
    }
    .bundle-card:hover {
        box-shadow: 0 4px 8px 0 rgba(0,0,0,0.2);
    }
    .price-text {
        color: #1E88E5;
        font-size: 20px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI PEMROSESAN DATA (ATURAN KATEGORI TETAP SAMA) ---
def process_data(df):
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    df['Office'] = False
    df['Gaming Standard / Design 2D'] = False
    df['Gaming Advanced / Design 3D'] = False
    df['NeedVGA'] = 0
    df['HasPSU'] = 0

    # 1. PROCESSOR
    proc_mask = df['Kategori'] == 'Processor'
    def map_processor(row):
        name = row['Nama Accurate'].upper()
        if re.search(r'\d+[0-9]F\b', name): row['NeedVGA'] = 1
        if 'I3' in name or 'I5' in name:
            row['Office'] = True
            row['Gaming Standard / Design 2D'] = True
        if 'I5' in name or 'I7' in name or 'I9' in name:
            row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # 2. MOTHERBOARD
    mb_mask = df['Kategori'] == 'Motherboard'
    h_intel = ['H410', 'H510', 'H610', 'H810', 'H81', 'H110', 'H310']
    b_intel, z_intel = ['B660', 'B760', 'B860'], ['Z790', 'Z890']
    a_amd, b_amd, x_amd = ['A520', 'A620'], ['B450', 'B550', 'B650', 'B840', 'B850'], ['X870']
    
    def map_mobo(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if any(x in name for x in h_intel) or any(x in name for x in a_amd): row['Office'] = True
        if (any(x in name for x in b_intel) and price < 2000000) or any(x in name for x in b_amd):
            row['Gaming Standard / Design 2D'] = True
        if (any(x in name for x in b_intel) and price >= 2000000) or any(x in name for x in z_intel) or \
           any(x in name for x in b_amd) or any(x in name for x in x_amd):
            row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # 3. RAM
    ram_mask = df['Kategori'] == 'Memory RAM'
    def map_ram(row):
        name = re.sub(r'\(.*?\)', '', row['Nama Accurate'].upper())
        match = re.search(r'(\d+)\s*GB', name)
        if match:
            size = int(match.group(1))
            if 8 <= size <= 16: row['Office'] = True
            if 16 <= size <= 32: row['Gaming Standard / Design 2D'] = True
            if 32 <= size <= 128: row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[ram_mask] = df[ram_mask].apply(map_ram, axis=1)

    # 4. SSD
    df.loc[df['Kategori'] == 'SSD Internal', ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 5. VGA
    vga_mask = df['Kategori'] == 'VGA'
    gt_off = ['GT710', 'GT730']
    vga_std = ['GT1030', 'GTX1650', 'RTX3050', 'RTX3060', 'RTX5050', 'RTX4060']
    vga_adv = ['RTX5060', 'RTX5070', 'RTX5080', 'RTX5090']
    def map_vga(row):
        name = row['Nama Accurate'].upper()
        if any(x in name for x in gt_off): row['Office'] = True
        if any(x in name for x in vga_std): row['Gaming Standard / Design 2D'] = True
        if any(x in name for x in vga_adv) or 'TI' in name: row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[vga_mask] = df[vga_mask].apply(map_vga, axis=1)

    # 6. CASING
    case_mask = df['Kategori'] == 'Casing PC'
    def map_case(row):
        if 'PSU' in row['Nama Accurate'].upper():
            row['Office'], row['HasPSU'] = True, 1
        else:
            row['Gaming Standard / Design 2D'], row['Gaming Advanced / Design 3D'] = True, True
        return row
    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # 7. PSU
    psu_mask = df['Kategori'] == 'Power Supply'
    certs = ['BRONZE', 'SILVER', 'GOLD', 'PLATINUM', 'TITANIUM']
    def map_psu(row):
        name, price = row['Nama Accurate'].upper(), row['Web']
        if price < 500000: row['Office'] = True
        if price >= 500000: row['Gaming Standard / Design 2D'] = True
        if any(c in name for c in certs): row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[psu_mask] = df[psu_mask].apply(map_psu, axis=1)
    
    return df

# --- FUNGSI GENERATE REKOMENDASI ---
def generate_bundles(df, branch_col, usage_cat, target_price_min, target_price_max):
    # Filter stok di cabang tersebut
    available_df = df[df[branch_col] > 0].copy()
    available_df = available_df[available_df[usage_cat] == True]
    
    categories = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'Casing PC']
    
    # Kumpulkan opsi per kategori, urutkan berdasarkan stok tertinggi
    options = {}
    for cat in categories:
        cat_items = available_df[available_df['Kategori'] == cat].sort_values(by=[branch_col, 'Web'], ascending=[False, True])
        if not cat_items.empty:
            options[cat] = cat_items

    # Logika pembuatan 2 tipe rekomendasi utama
    recommendations = []
    
    # Rekomendasi 1: Prioritas Stok Tertinggi (Best Seller)
    bundle1 = {}
    total1 = 0
    for cat, items in options.items():
        pick = items.iloc[0]
        bundle1[cat] = pick
        total1 += pick['Web']
    
    if target_price_min <= total1 <= target_price_max:
        recommendations.append({"name": "Stock Priority Bundle", "parts": bundle1, "total": total1})

    # Rekomendasi 2: Value Bundle (Termurah dari Stok yang Tersedia)
    bundle2 = {}
    total2 = 0
    for cat, items in options.items():
        pick = items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
        bundle2[cat] = pick
        total2 += pick['Web']
    
    if target_price_min <= total2 <= target_price_max:
        recommendations.append({"name": "Value Bundle", "parts": bundle2, "total": total2})

    return recommendations

# --- MAIN APP ---
st.title("🖥️ PC Wizard Pro - Bundling System")

if 'view' not in st.session_state:
    st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state:
    st.session_state.selected_bundle = None

# Update: Mendukung CSV dan Excel
uploaded_file = st.file_uploader("Upload Data Portal (CSV atau XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    # Logic membaca file berdasarkan extension
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)
        
    data = process_data(raw_df)
    
    # Sidebar Filters
    st.sidebar.header("⚙️ Konfigurasi Utama")
    
    branch_map = {
        "ITC": "Stock A - ITC",
        "SBY": "Stock B",
        "C6": "Stock C6",
        "Semarang": "Stock D - SMG",
        "Jogja": "Stock E - JOG",
        "Malang": "Stock F - MLG",
        "Bali": "Stock H - BALI",
        "Surabaya (Y)": "Stock Y - SBY"
    }
    selected_branch_label = st.sidebar.selectbox("Pilih Cabang:", list(branch_map.keys()))
    branch_col = branch_map[selected_branch_label]
    
    usage_cat = st.sidebar.radio("Kategori Penggunaan:", 
        ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Hitung Batas Harga Dinamis
    relevant_df = data[(data[usage_cat] == True) & (data[branch_col] > 0)]
    required_cats = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'Casing PC']
    
    min_price_sum = 0
    max_price_sum = 0
    for cat in required_cats:
        cat_prices = relevant_df[relevant_df['Kategori'] == cat]['Web']
        if not cat_prices.empty:
            min_price_sum += cat_prices.min()
            max_price_sum += cat_prices.max()

    st.sidebar.subheader("💰 Rentang Harga")
    st.sidebar.info(f"Batas Sistem: Rp{min_price_sum:,.0f} - Rp{max_price_sum:,.0f}")
    
    price_min = st.sidebar.number_input("Harga Minimum", min_value=float(min_price_sum), value=float(min_price_sum))
    price_max = st.sidebar.number_input("Harga Maksimum", max_value=float(max_price_sum), value=float(max_price_sum))

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi Bundling ({usage_cat})")
        
        recs = generate_bundles(data, branch_col, usage_cat, price_min, price_max)
        
        if not recs:
            st.warning("Tidak ditemukan kombinasi produk yang sesuai dengan rentang harga di cabang ini.")
        else:
            cols = st.columns(3)
            for i, res in enumerate(recs):
                with cols[i % 3]:
                    st.markdown(f"""
                    <div class="bundle-card">
                        <h3>{res['name']}</h3>
                        <p><b>{len(res['parts'])} Produk dalam bundle</b></p>
                        <p class="price-text">Rp {res['total']:,.0f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Lihat Detail {i+1}", key=f"btn_{i}"):
                        st.session_state.selected_bundle = res.copy()
                        st.session_state.view = 'detail'
                        st.rerun()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        st.button("⬅️ Kembali ke Rekomendasi", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        
        st.subheader(f"🛠️ Sesuaikan Bundling: {bundle['name']}")
        
        col_parts, col_summary = st.columns([2, 1])
        
        with col_parts:
            updated_parts = {}
            for cat, item in bundle['parts'].items():
                c1, c2 = st.columns([4, 1])
                c1.write(f"**{cat}**: {item['Nama Accurate']}")
                c1.caption(f"Stok di {selected_branch_label}: {item[branch_col]} | Harga: Rp{item['Web']:,.0f}")
                
                if c2.button("➖", key=f"del_{cat}"):
                    continue
                else:
                    updated_parts[cat] = item
            
            st.session_state.selected_bundle['parts'] = updated_parts

        with col_summary:
            st.markdown("### 🧾 Ringkasan Pesanan")
            
            is_assembled = st.checkbox("Gunakan Jasa Rakit (Rp 200,000)?")
            assembly_fee = 200000 if is_assembled else 0
            
            total_items = 0
            for cat, item in updated_parts.items():
                st.write(f"- {item['Nama Accurate'][:30]}...")
                total_items += item['Web']
            
            if is_assembled:
                st.write("- Jasa Perakitan PC")
            
            grand_total = total_items + assembly_fee
            st.divider()
            st.subheader(f"Total: Rp{grand_total:,.0f}")
            
            if st.button("✅ Konfirmasi & Cetak"):
                st.balloons()
                st.success("Pesanan telah dikonfirmasi!")

else:
    st.info("Silakan upload file CSV atau Excel Data Portal untuk memulai.")
