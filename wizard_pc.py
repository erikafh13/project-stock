import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="Sistem Bundling PC - Pro", layout="wide")

# CSS untuk membuat tampilan kartu lebih modern dan interaktif
st.markdown("""
<style>
    .bundle-card {
        border: 1px solid #e1e4e8;
        border-radius: 12px;
        padding: 20px;
        background-color: #ffffff;
        margin-bottom: 24px;
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    .bundle-card:hover {
        box-shadow: 0 8px 24px rgba(0,0,0,0.12);
        border-color: #1E88E5;
        transform: translateY(-5px);
    }
    .price-text {
        color: #1E88E5;
        font-size: 24px;
        font-weight: 800;
        margin: 12px 0;
    }
    .bundle-title {
        color: #2c3e50;
        font-size: 18px;
        font-weight: 700;
        margin-bottom: 8px;
        line-height: 1.3;
        min-height: 48px;
    }
    .badge-stock {
        background-color: #e3f2fd;
        color: #1976d2;
        padding: 4px 12px;
        border-radius: 20px;
        font-size: 11px;
        font-weight: 700;
        margin-bottom: 12px;
        display: inline-block;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .part-count {
        color: #7f8c8d;
        font-size: 13px;
        margin-bottom: 10px;
    }
    section[data-testid="stSidebar"] {
        background-color: #f8f9fa;
        border-right: 1px solid #eee;
    }
</style>
""", unsafe_allow_html=True)

# --- KONSTANTA ---
BRANCH_MAP = {
    "Surabaya (Gabungan)": "Stock_SBY_Combined",
    "C6": "Stock C6",
    "Semarang": "Stock D - SMG",
    "Jogja": "Stock E - JOG",
    "Malang": "Stock F - MLG",
    "Bali": "Stock H - BALI"
}

ASSEMBLY_FEES = {
    "Office": 100000,
    "Gaming Standard / Design 2D": 150000,
    "Gaming Advanced / Design 3D": 200000
}

DISPLAY_ORDER = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'VGA', 'Casing PC', 'Power Supply', 'CPU Cooler']

# --- 2. LOGIKA HELPER ---

def get_cpu_info(name):
    """Mendeteksi informasi generasi dan socket processor."""
    name = name.upper()
    info = {"gen": None, "socket": None}
    intel_match = re.search(r'I[3579]-(\d{1,2})', name)
    if intel_match:
        info["gen"] = int(intel_match.group(1))
    elif "ULTRA" in name:
        info["gen"] = "ULTRA"
    if "RYZEN" in name:
        if any(x in name for x in ["7000", "8000", "9000"]) or "AM5" in name:
            info["socket"] = "AM5"
        else:
            info["socket"] = "AM4"
    return info

def get_ddr_type(name):
    """Mendeteksi tipe DDR dari nama produk."""
    name = name.upper()
    if 'DDR5' in name or ' D5' in name: return 'DDR5'
    if 'DDR4' in name or ' D4' in name: return 'DDR4'
    return None

def is_compatible(cpu_row, mobo_row):
    """Menentukan kompatibilitas antara Motherboard dan Processor."""
    gen = cpu_row['CPU_Gen']
    socket = cpu_row['CPU_Socket']
    series = mobo_row['Mobo_Series']
    if gen == 10: return series in ['H410', 'H510']
    if gen == 11: return series in ['H510']
    if gen in [12, 13, 14]: return series in ['H610', 'B660', 'B760', 'Z790']
    if gen == "ULTRA": return series in ['H810', 'B860', 'Z890']
    if socket == "AM4": return series in ['A520', 'B450', 'B550']
    if socket == "AM5": return series in ['A620', 'B650', 'B840', 'B850', 'X870']
    return True

# --- 3. PUSAT LOGIKA PEMROSESAN DATA ---

def process_data(df):
    """Pusat kontrol untuk semua aturan filter dan klasifikasi barang."""
    df.columns = df.columns.str.strip()
    
    # Gabungkan Stok Surabaya
    df['Stock_SBY_Combined'] = (
        df.get('Stock A - ITC', 0).fillna(0) + 
        df.get('Stock B', 0).fillna(0) + 
        df.get('Stock Y - SBY', 0).fillna(0)
    )
    
    # Pembersihan data dasar
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('').str.strip()
    df['Kategori'] = df['Kategori'].fillna('').str.strip()
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Normalisasi Kategori
    cat_up = df['Kategori'].str.upper()
    df.loc[cat_up.str.contains('PROCESSOR'), 'Kategori'] = 'Processor'
    df.loc[cat_up.str.contains('MOTHERBOARD'), 'Kategori'] = 'Motherboard'
    df.loc[cat_up.str.contains('MEMORY RAM|RAM'), 'Kategori'] = 'Memory RAM'
    df.loc[cat_up.str.contains('SSD'), 'Kategori'] = 'SSD Internal'
    df.loc[cat_up.str.contains('VGA|GRAPHIC CARD'), 'Kategori'] = 'VGA'
    df.loc[cat_up.str.contains('CASING'), 'Kategori'] = 'Casing PC'
    df.loc[cat_up.str.contains('POWER SUPPLY|PSU'), 'Kategori'] = 'Power Supply'
    df.loc[cat_up.str.contains('COOLER|COOLING|FAN PROCESSOR|HEATSINK'), 'Kategori'] = 'CPU Cooler'
    
    # Inisialisasi Kolom Flag
    for col in ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']:
        df[col] = False
    df['NeedVGA'] = 0
    df['HasPSU'] = 0
    df['NeedCooler'] = 0
    df['CPU_Gen'] = None
    df['CPU_Socket'] = None
    df['Mobo_Series'] = None
    df['DDR_Type'] = None

    for idx, row in df.iterrows():
        name = row['Nama Accurate'].upper()
        price = row['Web']
        cat = row['Kategori']

        # 1. Aturan Processor
        if cat == 'Processor':
            if re.search(r'\d+[0-9]F\b', name): df.at[idx, 'NeedVGA'] = 1
            if 'TRAY' in name or 'NO FAN' in name: df.at[idx, 'NeedCooler'] = 1
            
            # Klasifikasi Penggunaan
            if 'I3' in name or 'I5' in name:
                df.at[idx, 'Office'] = True
                df.at[idx, 'Gaming Standard / Design 2D'] = True
            
            # REVISI: Gaming Advanced hanya untuk seri F saja
            if any(x in name for x in ['I5', 'I7', 'I9', 'ULTRA', 'RYZEN']):
                if df.at[idx, 'NeedVGA'] == 1:
                    df.at[idx, 'Gaming Advanced / Design 3D'] = True
            
            cpu_info = get_cpu_info(name)
            df.at[idx, 'CPU_Gen'] = cpu_info['gen']
            df.at[idx, 'CPU_Socket'] = cpu_info['socket']

        # 2. Aturan Motherboard
        elif cat == 'Motherboard':
            series_list = ['H410', 'H510', 'H610', 'H810', 'B660', 'B760', 'B860', 'Z790', 'Z890', 
                           'A520', 'A620', 'B450', 'B550', 'B650', 'B840', 'B850', 'X870']
            for s in series_list:
                if s in name: 
                    df.at[idx, 'Mobo_Series'] = s
                    break
            if any(x in name for x in ['H410', 'H510', 'H610', 'H810', 'A520', 'A620']):
                df.at[idx, 'Office'] = True
            df.at[idx, 'Gaming Standard / Design 2D'] = True
            df.at[idx, 'Gaming Advanced / Design 3D'] = True
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)

        # 3. Aturan RAM (Kapasitas & Pengecualian SODIMM)
        elif cat == 'Memory RAM':
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            if 'SODIMM' not in name:
                match_gb = re.search(r'(\d+)\s*GB', name)
                if match_gb:
                    size = int(match_gb.group(1))
                    if 8 <= size <= 16: df.at[idx, 'Office'] = True
                    if 16 <= size <= 32: df.at[idx, 'Gaming Standard / Design 2D'] = True
                    if 32 <= size <= 64: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 4. Aturan SSD (REVISI: Kecualikan WDS120G2G0B)
        elif cat == 'SSD Internal':
            if 'WDS120G2G0B' in name:
                continue # Abaikan produk ini
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D']] = True
            if 'M.2 NVME' in name:
                df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 5. Aturan VGA
        elif cat == 'VGA':
            if any(x in name for x in ['GT710', 'GT730']): df.at[idx, 'Office'] = True
            df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # 6. Aturan Casing PC (Pengecualian Armaggeddon)
        elif cat == 'Casing PC':
            if 'ARMAGGEDDON' not in name:
                if 'PSU' in name or 'VALCAS' in name:
                    df.at[idx, 'Office'], df.at[idx, 'HasPSU'] = True, 1
                else:
                    df.at[idx, 'Office'] = True
                df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # 7. Aturan Power Supply (PSU)
        elif cat == 'Power Supply':
            if price <= 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 8. Aturan CPU Cooler
        elif cat == 'CPU Cooler':
            if price <= 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced / Design 3D'] = True
            
    return df

# --- 4. ENGINE REKOMENDASI ---

def generate_bundles(df, branch_col, usage_cat, target_min, target_max):
    """Menghasilkan berbagai jenis rekomendasi bundling."""
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    bundle_types = [
        {"name": "Utama Stok Tinggi", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 0, "tag": "STOK TERBAIK"},
        {"name": "Pilihan Populer", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 1, "tag": "POPULAR"},
        {"name": "Pilihan Stabil", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 2, "tag": "STABLE"},
        {"name": "Budget Ekstrem", "sort": ['Web', branch_col], "asc": [True, False], "idx": 0, "tag": "HARGA TERENDAH"},
        {"name": "Smart Value", "sort": ['Web', branch_col], "asc": [True, False], "idx": 1, "tag": "DIREKOMENDASIKAN"},
        {"name": "Sweet Spot Seimbang", "sort": ['Web', branch_col], "asc": [True, False], "idx": "mid", "tag": "BALANCED"},
        {"name": "Performa Mid-Range", "sort": ['Web', branch_col], "asc": [False, False], "idx": 2, "tag": "PERFORMA"},
        {"name": "Premium Enthusiast", "sort": ['Web', branch_col], "asc": [False, False], "idx": 1, "tag": "PREMIUM"},
        {"name": "Luxury Flagship", "sort": ['Web', branch_col], "asc": [False, False], "idx": 0, "tag": "ELITE"}
    ]

    results = []
    for bt in bundle_types:
        bundle, total = {}, 0
        
        # 1. Pilih Processor
        procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=bt['sort'], ascending=bt['asc'])
        if procs.empty: continue
        p_idx = bt['idx'] if bt['idx'] != "mid" else len(procs)//2
        pick_proc = procs.iloc[min(p_idx if isinstance(p_idx, int) else 0, len(procs)-1)]
        bundle['Processor'] = pick_proc
        total += pick_proc['Web']
        
        # 2. Pilih Motherboard Kompatibel
        mobos = available_df[available_df['Kategori'] == 'Motherboard']
        comp = mobos[mobos.apply(lambda m: is_compatible(pick_proc, m), axis=1)].sort_values(by=bt['sort'], ascending=bt['asc'])
        if comp.empty: continue
        bundle['Motherboard'] = comp.iloc[0]
        total += bundle['Motherboard']['Web']
        
        # 3. Pilih RAM (Ikut DDR Motherboard)
        mobo_ddr = bundle['Motherboard'].get('DDR_Type')
        rams = available_df[available_df['Kategori'] == 'Memory RAM'].sort_values(by=bt['sort'], ascending=bt['asc'])
        if mobo_ddr:
            rams = rams[rams['DDR_Type'] == mobo_ddr]
        if not rams.empty:
            bundle['Memory RAM'] = rams.iloc[0]
            total += bundle['Memory RAM']['Web']

        # 4. Produk Utama Lainnya
        for cat in ['SSD Internal', 'Casing PC']:
            items = available_df[available_df['Kategori'] == cat].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not items.empty:
                bundle[cat] = items.iloc[0]
                total += bundle[cat]['Web']

        # 5. Syarat Khusus (VGA, PSU, Cooler)
        if pick_proc['NeedVGA'] == 1:
            vgas = available_df[available_df['Kategori'] == 'VGA'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not vgas.empty:
                bundle['VGA'] = vgas.iloc[0]
                total += bundle['VGA']['Web']

        needs_psu = not (usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1)
        if needs_psu:
            psus = available_df[available_df['Kategori'] == 'Power Supply'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not psus.empty:
                bundle['Power Supply'] = psus.iloc[0]
                total += bundle['Power Supply']['Web']

        if pick_proc['NeedCooler'] == 1:
            coolers = available_df[available_df['Kategori'] == 'CPU Cooler'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not coolers.empty:
                bundle['CPU Cooler'] = coolers.iloc[0]
                total += bundle['CPU Cooler']['Web']
        
        if target_min <= total <= target_max:
            results.append({"name": bt['name'], "parts": bundle, "total": total, "tag": bt['tag']})
    return results

# --- 5. UI LAYER (STREAMLIT) ---

st.title("🖥️ PC Wizard Pro - Sistem Bundling Pintar")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal (CSV atau XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    st.sidebar.header("⚙️ Konfigurasi Utama")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]
    u_cat = st.sidebar.radio("Kategori Penggunaan:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    rel_df = data[(data[u_cat] == True) & (data[b_col] > 0)]
    min_p = rel_df.groupby('Kategori')['Web'].min().sum() if not rel_df.empty else 0
    max_p = rel_df.groupby('Kategori')['Web'].max().sum() if not rel_df.empty else 0
    
    st.sidebar.markdown(f"**Rentang Harga Sistem di {sel_branch}:**")
    st.sidebar.caption(f"Rp {min_p:,.0f} - Rp {max_p:,.0f}")
    p_min = st.sidebar.number_input("Harga Minimum", value=float(min_p), step=100000.0)
    p_max = st.sidebar.number_input("Harga Maksimum", value=float(max_p), step=100000.0)

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi Bundling ({u_cat})")
        st.caption(f"Menampilkan variasi bundling terbaik berdasarkan stok di {sel_branch}")
        
        recs = generate_bundles(data, b_col, u_cat, p_min, p_max)
        if not recs: 
            st.warning("⚠️ Tidak ada bundling yang sesuai. Silakan sesuaikan rentang harga di sidebar.")
        else:
            for i in range(0, len(recs), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(recs):
                        res = recs[i+j]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="bundle-card">
                                <div>
                                    <span class="badge-stock">{res['tag']}</span>
                                    <div class="bundle-title">{res['name']}</div>
                                    <div class="part-count">{len(res['parts'])} Komponen Termasuk</div>
                                    <div class="price-text">Rp {res['total']:,.0f}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button("Pilih & Sesuaikan", key=f"btn_{i+j}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                if 'temp_parts' in st.session_state: del st.session_state.temp_parts
                                st.session_state.view = 'detail'
                                st.rerun()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        if 'temp_parts' not in st.session_state: st.session_state.temp_parts = bundle['parts'].copy()
        upd = st.session_state.temp_parts

        st.button("⬅️ Kembali ke Rekomendasi", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Sesuaikan Bundling: {bundle['name']}")
        
        c_parts, c_sum = st.columns([2, 1])
        with c_parts:
            available_detail = data[(data[b_col] > 0) & (data[u_cat] == True)]
            for cat in DISPLAY_ORDER:
                is_mandatory = cat in ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'Casing PC']
                current_p = upd.get('Processor')
                current_m = upd.get('Motherboard')
                
                if cat == 'VGA' and current_p is not None and current_p['NeedVGA'] == 1: is_mandatory = True
                if cat == 'CPU Cooler' and current_p is not None and current_p['NeedCooler'] == 1: is_mandatory = True
                if cat == 'Power Supply' and not (u_cat == "Office" and upd.get('Casing PC', {}).get('HasPSU', 0) == 1): is_mandatory = True

                cat_options = available_detail[available_detail['Kategori'] == cat]
                if cat == 'Motherboard' and current_p is not None:
                    cat_options = cat_options[cat_options.apply(lambda m: is_compatible(current_p, m), axis=1)]
                if cat == 'Memory RAM' and current_m is not None:
                    mobo_ddr = current_m.get('DDR_Type')
                    if mobo_ddr: cat_options = cat_options[cat_options['DDR_Type'] == mobo_ddr]

                if cat not in upd and is_mandatory:
                    if not cat_options.empty: 
                        upd[cat] = cat_options.sort_values(b_col, ascending=False).iloc[0]

                if cat in upd:
                    item = upd[cat]
                    if cat_options.empty: 
                        st.error(f"⚠️ Tidak ada pilihan {cat} yang kompatibel/tersedia.")
                        continue

                    with st.expander(f"📦 **[{cat}]** {item['Nama Accurate']} - Rp {item['Web']:,.0f}", expanded=(cat == 'Processor')):
                        opt_list = cat_options.sort_values('Web')
                        labels = opt_list['Nama Accurate'] + " (Rp " + opt_list['Web'].map('{:,.0f}'.format) + ")"
                        try: idx = opt_list['Nama Accurate'].tolist().index(item['Nama Accurate'])
                        except: idx = 0
                        
                        new_pick = st.selectbox(f"Ubah {cat}:", labels, index=idx, key=f"sel_{cat}")
                        new_item = opt_list[opt_list['Nama Accurate'] == new_pick.split(" (Rp ")[0]].iloc[0]
                        if new_item['Nama Accurate'] != item['Nama Accurate']:
                            upd[cat] = new_item
                            st.rerun()
                        
                        if not is_mandatory and st.button(f"Hapus {cat}", key=f"del_{cat}"):
                            del upd[cat]
                            st.rerun()
                st.divider()

        with c_sum:
            st.markdown("### 📋 Ringkasan Pesanan")
            asm_fee = ASSEMBLY_FEES[u_cat]
            rakit = st.checkbox(f"Biaya Perakitan PC ({u_cat}: Rp {asm_fee:,.0f})", value=True)
            
            st.markdown("---")
            total_items = sum(x['Web'] for x in upd.values())
            grand = total_items + (asm_fee if rakit else 0)
            
            for k, v in upd.items():
                st.markdown(f"**{k}**")
                st.caption(v['Nama Accurate'])
                st.write(f"Rp {v['Web']:,.0f}")
                st.divider()
            
            if rakit:
                st.markdown(f"**Jasa Rakit ({u_cat})**")
                st.write(f"Rp {asm_fee:,.0f}")
                st.divider()
            
            st.subheader(f"Total: Rp {grand:,.0f}")
            
            # Validasi akhir
            if 'Processor' in upd:
                p = upd['Processor']
                if p['NeedVGA'] == 1 and 'VGA' not in upd: st.warning("⚠️ Kartu Grafis (VGA) diperlukan.")
                if p['NeedCooler'] == 1 and 'CPU Cooler' not in upd: st.warning("⚠️ CPU Cooler diperlukan.")

            if st.button("✅ Konfirmasi Bundling", use_container_width=True, type="primary"):
                st.balloons()
                st.success("Konfigurasi Berhasil Disimpan!")

else:
    st.info("👋 Silakan upload file Data Portal (CSV/Excel) untuk memulai.")
