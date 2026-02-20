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

# --- FUNGSI PEMROSESAN DATA (MENGGUNAKAN ATURAN LAMA FIRMAN) ---
def process_data(df):
    # Filter Stock > 0 dan pembersihan data dasar sesuai kode lama
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Inisialisasi Kolom Kategori Baru
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

# --- FUNGSI GENERATE REKOMENDASI (DINAMIS UNTUK SEMUA KATEGORI) ---
def generate_bundles(df, branch_col, usage_cat, target_price_min, target_price_max):
    # Filter stok tersedia di cabang dan kategori penggunaan
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    # Ambil SEMUA kategori unik yang ada di data tersebut
    all_available_categories = sorted(available_df['Kategori'].unique().tolist())
    
    options = {}
    for cat in all_available_categories:
        # Urutkan berdasarkan stok tertinggi (Push Stock)
        cat_items = available_df[available_df['Kategori'] == cat].sort_values(by=[branch_col, 'Web'], ascending=[False, True])
        if not cat_items.empty:
            options[cat] = cat_items

    recommendations = []
    
    # Rekomendasi 1: Prioritas Stok Tertinggi di Semua Kategori
    bundle_high_stock = {}
    total_high_stock = 0
    for cat, items in options.items():
        pick = items.iloc[0]
        bundle_high_stock[cat] = pick
        total_high_stock += pick['Web']
    
    if target_price_min <= total_high_stock <= target_price_max:
        recommendations.append({"name": "High Stock Priority (All Items)", "parts": bundle_high_stock, "total": total_high_stock})

    # Rekomendasi 2: Value Bundle (Termurah dari stok yang ada di Semua Kategori)
    bundle_value = {}
    total_value = 0
    for cat, items in options.items():
        pick = items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
        bundle_value[cat] = pick
        total_value += pick['Web']
    
    if target_price_min <= total_value <= target_price_max:
        recommendations.append({"name": "Value Bundle (All Items)", "parts": bundle_value, "total": total_value})

    return recommendations

# --- MAIN APP ---
st.title("🖥️ PC Wizard Pro - Sistem Bundling Dinamis")

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
        "ITC": "Stock A - ITC", "SBY": "Stock B", "C6": "Stock C6",
        "Semarang": "Stock D - SMG", "Jogja": "Stock E - JOG",
        "Malang": "Stock F - MLG", "Bali": "Stock H - BALI", "Surabaya (Y)": "Stock Y - SBY"
    }
    selected_branch_label = st.sidebar.selectbox("Pilih Cabang:", list(branch_map.keys()))
    branch_col = branch_map[selected_branch_label]
    
    usage_cat = st.sidebar.radio("Kategori Penggunaan:", 
        ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Hitung Batas Harga Dinamis berdasarkan SEMUA kategori yang ada
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
    
    # Input rentang harga user
    price_min = st.sidebar.number_input("Harga Minimum User", min_value=0.0, value=float(min_price_sum))
    price_max = st.sidebar.number_input("Harga Maksimum User", min_value=0.0, value=float(max_price_sum))

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi Bundling ({usage_cat})")
        st.caption(f"Bundling disusun dari {len(all_cats)} kategori produk yang tersedia di {selected_branch_label}")
        
        recs = generate_bundles(data, branch_col, usage_cat, price_min, price_max)
        
        if not recs:
            st.warning("Tidak ada kombinasi otomatis yang masuk dalam rentang harga. Coba sesuaikan rentang harga di sidebar.")
        else:
            cols = st.columns(len(recs) if len(recs) > 0 else 1)
            for i, res in enumerate(recs):
                with cols[i]:
                    st.markdown(f"""
                    <div class="bundle-card">
                        <h3 style="margin-bottom:0px;">{res['name']}</h3>
                        <p style="color:gray; font-size:12px;">{len(res['parts'])} kategori produk included</p>
                        <p class="price-text">Rp {res['total']:,.0f}</p>
                    </div>
                    """, unsafe_allow_html=True)
                    if st.button(f"Pilih & Sesuaikan {i+1}", key=f"btn_{i}", use_container_width=True):
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
            # Tampilkan semua barang dalam bundle dengan fitur hapus (minus)
            for cat in sorted(bundle['parts'].keys()):
                item = bundle['parts'][cat]
                with st.container():
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"**[{cat}]** {item['Nama Accurate']}")
                    c1.caption(f"Stok: {item[branch_col]} | Harga: Rp{item['Web']:,.0f}")
                    
                    if c2.button("➖", key=f"del_{cat}"):
                        st.toast(f"{cat} dihapus dari bundle.")
                        continue # Lewati item ini agar tidak masuk ke updated_parts
                    else:
                        updated_parts[cat] = item
                st.divider()
            
            st.session_state.selected_bundle['parts'] = updated_parts

        with col_summary:
            st.markdown("### 🧾 Ringkasan Bundling")
            
            # Opsi Rakit
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
    st.info("Silakan upload file Data Portal (CSV/Excel) untuk memulai sistem bundling dinamis.")
