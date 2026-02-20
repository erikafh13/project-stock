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
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    .bundle-card:hover {
        box-shadow: 0 4px 12px 0 rgba(0,0,0,0.15);
        border-color: #1E88E5;
        transform: translateY(-5px);
    }
    .price-text {
        color: #1E88E5;
        font-size: 22px;
        font-weight: bold;
        margin: 10px 0;
    }
    .bundle-title {
        color: #333;
        font-size: 18px;
        font-weight: bold;
        margin-bottom: 5px;
        min-height: 50px;
    }
    .badge-stock {
        background-color: #E3F2FD;
        color: #1976D2;
        padding: 2px 8px;
        border-radius: 12px;
        font-size: 10px;
        font-weight: bold;
        margin-bottom: 8px;
        display: inline-block;
    }
</style>
""", unsafe_allow_html=True)

# --- FUNGSI PEMROSESAN DATA (ATURAN FIRMAN) ---
def process_data(df):
    df = df[df['Stock Total'] > 0].copy()
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

# --- FUNGSI GENERATE MULTIPLE REKOMENDASI (EXPANDED TO 9) ---
def generate_multiple_bundles(df, branch_col, usage_cat, target_price_min, target_price_max):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    all_available_categories = sorted(available_df['Kategori'].unique().tolist())
    
    options = {}
    for cat in all_available_categories:
        options[cat] = available_df[available_df['Kategori'] == cat].sort_values(by=[branch_col, 'Web'], ascending=[False, True])

    results = []
    
    # Logic untuk membuat hingga 9 variasi bundel
    bundle_types = [
        {"name": "Ultra Stock Priority", "sort_by": [branch_col, 'Web'], "ascending": [False, True], "idx": 0, "tag": "BEST STOCK"},
        {"name": "Popular High Stock", "sort_by": [branch_col, 'Web'], "ascending": [False, True], "idx": 1, "tag": "POPULAR"},
        {"name": "Stable Choice", "sort_by": [branch_col, 'Web'], "ascending": [False, True], "idx": 2, "tag": "STABLE"},
        {"name": "Extreme Budget", "sort_by": ['Web', branch_col], "ascending": [True, False], "idx": 0, "tag": "BEST PRICE"},
        {"name": "Smart Value", "sort_by": ['Web', branch_col], "ascending": [True, False], "idx": 1, "tag": "RECOMMENDED"},
        {"name": "Balanced Sweet Spot", "sort_by": ['Web', branch_col], "ascending": [True, False], "idx": "mid", "tag": "BALANCED"},
        {"name": "Advanced Mid-Range", "sort_by": ['Web', branch_col], "ascending": [False, False], "idx": 2, "tag": "PERFORMANCE"},
        {"name": "Premium Enthusiast", "sort_by": ['Web', branch_col], "ascending": [False, False], "idx": 1, "tag": "PREMIUM"},
        {"name": "Luxury Flagship", "sort_by": ['Web', branch_col], "ascending": [False, False], "idx": 0, "tag": "ELITE"}
    ]

    for bt in bundle_types:
        bundle = {}
        total = 0
        
        for cat in all_available_categories:
            items = options[cat].sort_values(by=bt['sort_by'], ascending=bt['ascending'])
            
            idx = bt['idx']
            if idx == "mid":
                idx = len(items) // 2
            
            # Pengamanan index agar tidak out of bounds
            if idx < len(items):
                pick = items.iloc[idx]
            else:
                pick = items.iloc[0]
                
            bundle[cat] = pick
            total += pick['Web']
        
        # Cek apakah masuk dalam rentang harga
        if target_price_min <= total <= target_price_max:
            results.append({"name": bt['name'], "parts": bundle, "total": total, "tag": bt['tag']})

    return results

# --- MAIN APP ---
st.title("🖥️ PC Wizard Pro - Sistem Multi-Bundling")

if 'view' not in st.session_state:
    st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state:
    st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal (CSV atau XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    if uploaded_file.name.endswith('.csv'):
        raw_df = pd.read_csv(uploaded_file)
    else:
        raw_df = pd.read_excel(uploaded_file)
        
    data = process_data(raw_df)
    
    # Sidebar Filters
    st.sidebar.header("⚙️ Konfigurasi Utama")
    
    branch_map = {
        "SBY - ITC": "Stock A - ITC", "JAKARTA": "Stock B", "SBY - LEBAK": "Stock C6",
        "SEMARANG": "Stock D - SMG", "JOGJA": "Stock E - JOG",
        "MALANG": "Stock F - MLG", "BALI": "Stock H - BALI", "SBY - TENGGILIS": "Stock Y - SBY"
    }
    selected_branch_label = st.sidebar.selectbox("Pilih Cabang:", list(branch_map.keys()))
    branch_col = branch_map[selected_branch_label]
    
    usage_cat = st.sidebar.radio("Kategori Penggunaan:", 
        ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Hitung Batas Harga Dinamis
    relevant_df = data[(data[usage_cat] == True) & (data[branch_col] > 0)]
    all_cats = relevant_df['Kategori'].unique()
    
    min_price_sum = 0
    max_price_sum = 0
    for cat in all_cats:
        cat_prices = relevant_df[relevant_df['Kategori'] == cat]['Web']
        if not cat_prices.empty:
            min_price_sum += cat_prices.min()
            max_price_sum += cat_prices.max()

    st.sidebar.subheader("💰 Rentang Harga")
    st.sidebar.info(f"Batas {len(all_cats)} Kategori: Rp{min_price_sum:,.0f} - Rp{max_price_sum:,.0f}")
    
    price_min = st.sidebar.number_input("Harga Minimum User", min_value=0.0, value=float(min_price_sum))
    price_max = st.sidebar.number_input("Harga Maksimum User", min_value=0.0, value=float(max_price_sum))

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi Bundling ({usage_cat})")
        st.caption(f"Menampilkan variasi bundling cerdas di {selected_branch_label}")
        
        recs = generate_multiple_bundles(data, branch_col, usage_cat, price_min, price_max)
        
        if not recs:
            st.warning("Tidak ada kombinasi otomatis yang masuk dalam rentang harga. Coba sesuaikan rentang harga di sidebar.")
        else:
            # Grid Tampilan Card (3 kolom)
            for i in range(0, len(recs), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(recs):
                        res = recs[i + j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="bundle-card">
                                <div>
                                    <span class="badge-stock">{res['tag']}</span>
                                    <div class="bundle-title">{res['name']}</div>
                                    <p style="color:gray; font-size:12px; margin-bottom:0px;">{len(res['parts'])} produk dalam bundle</p>
                                    <div class="price-text">Rp {res['total']:,.0f}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button(f"Pilih & Sesuaikan", key=f"btn_{i+j}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                st.session_state.view = 'detail'
                                st.rerun()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        st.button("⬅️ Kembali ke Rekomendasi", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        
        st.subheader(f"🛠️ Rincian & Penyesuaian: {bundle['name']}")
        
        col_parts, col_summary = st.columns([2, 1])
        
        with col_parts:
            updated_parts = {}
            for cat in sorted(bundle['parts'].keys()):
                item = bundle['parts'][cat]
                with st.container():
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"**[{cat}]** {item['Nama Accurate']}")
                    c1.caption(f"Stok: {item[branch_col]} | Harga: Rp{item['Web']:,.0f}")
                    
                    if c2.button("➖", key=f"del_{cat}"):
                        st.toast(f"{cat} dihapus.")
                        continue
                    else:
                        updated_parts[cat] = item
                st.divider()
            
            st.session_state.selected_bundle['parts'] = updated_parts

        with col_summary:
            st.markdown("### 🧾 Ringkasan Bundling")
            
            is_assembled = st.checkbox("Gunakan Jasa Rakit (Rp 200,000)?", value=False)
            assembly_fee = 200000 if is_assembled else 0
            
            item_total = 0
            for cat, item in updated_parts.items():
                st.text(f"• {item['Nama Accurate'][:40]}...")
                item_total += item['Web']
            
            if is_assembled:
                st.text("• Jasa Perakitan Sistem")
                
            grand_total = item_total + assembly_fee
            
            st.markdown("---")
            st.subheader(f"Total: Rp{grand_total:,.0f}")
            
            if st.button("✅ Konfirmasi Pesanan", use_container_width=True):
                st.balloons()
                st.success(f"Bundling berhasil dikonfirmasi untuk cabang {selected_branch_label}!")

else:
    st.info("Silakan upload file Data Portal (CSV/Excel) untuk memulai.")
