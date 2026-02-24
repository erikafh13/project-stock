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

# --- FUNGSI IDENTIFIKASI CPU (GENERASI & SOCKET) ---
def get_cpu_info(name):
    name = name.upper()
    info = {"gen": None, "socket": None, "brand": "INTEL"}
    
    # Intel Core iX-Generation
    intel_match = re.search(r'I[3579]-(\d{1,2})', name)
    if intel_match:
        info["gen"] = int(intel_match.group(1))
    elif "ULTRA" in name:
        info["gen"] = "ULTRA"
    
    # AMD Ryzen
    if "RYZEN" in name:
        info["brand"] = "AMD"
        if any(x in name for x in ["7000", "8000", "9000"]) or "AM5" in name:
            info["socket"] = "AM5"
        else:
            info["socket"] = "AM4"
            
    return info

# --- FUNGSI PEMROSESAN DATA (LOGIKA REVISI FIRMAN) ---
def process_data(df):
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Inisialisasi Kolom Penanda
    df['Office'] = False
    df['Gaming Standard / Design 2D'] = False
    df['Gaming Advanced / Design 3D'] = False
    df['NeedVGA'] = 0
    df['HasPSU'] = 0
    df['NeedCooler'] = 0
    df['CPU_Gen'] = None
    df['CPU_Socket'] = None
    df['Mobo_Series'] = None

    # 1. PROCESSOR (F-Series, Tray vs Box, Gen/Socket)
    proc_mask = df['Kategori'] == 'Processor'
    def map_processor(row):
        name = row['Nama Accurate'].upper()
        # Wajib VGA jika seri 'F'
        if re.search(r'\d+[0-9]F\b', name): row['NeedVGA'] = 1
        # Wajib Cooler jika Tray / No Fan
        if 'TRAY' in name or 'NO FAN' in name: row['NeedCooler'] = 1
        
        # Usage Mapping
        if 'I3' in name or 'I5' in name:
            row['Office'] = True
            row['Gaming Standard / Design 2D'] = True
        if 'I5' in name or 'I7' in name or 'I9' in name or 'ULTRA' in name or 'RYZEN' in name:
            row['Gaming Advanced / Design 3D'] = True
            
        cpu_info = get_cpu_info(name)
        row['CPU_Gen'] = cpu_info['gen']
        row['CPU_Socket'] = cpu_info['socket']
        return row
    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # 2. MOTHERBOARD (Mapping Seri untuk Kompatibilitas)
    mb_mask = df['Kategori'] == 'Motherboard'
    def map_mobo(row):
        name = row['Nama Accurate'].upper()
        series_list = ['H410', 'H510', 'H610', 'H810', 'B660', 'B760', 'B860', 'Z790', 'Z890', 
                       'A520', 'A620', 'B450', 'B550', 'B650', 'B840', 'B850', 'X870']
        for s in series_list:
            if s in name:
                row['Mobo_Series'] = s
                break
        
        # Dasar Kategori
        if any(x in name for x in ['H410', 'H510', 'H610', 'H810', 'A520', 'A620']):
            row['Office'] = True
        row['Gaming Standard / Design 2D'] = True
        row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # 3. RAM, SSD (Semua masuk)
    df.loc[df['Kategori'].isin(['Memory RAM', 'SSD Internal']), ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 4. VGA (Usage)
    vga_mask = df['Kategori'] == 'VGA'
    df.loc[vga_mask & df['Nama Accurate'].str.upper().str.contains('GT710|GT730'), 'Office'] = True
    df.loc[vga_mask, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 5. CASING (Logic: "PSU" -> Office Only)
    case_mask = df['Kategori'] == 'Casing PC'
    def map_case(row):
        name = row['Nama Accurate'].upper()
        if 'PSU' in name:
            row['Office'], row['HasPSU'] = True, 1
            # Gaming Std/Adv bisa masuk tapi wajib PSU luar
        else:
            row['Office'] = True
        row['Gaming Standard / Design 2D'], row['Gaming Advanced / Design 3D'] = True, True
        return row
    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # 6. PSU
    psu_mask = df['Kategori'] == 'Power Supply'
    df.loc[psu_mask & (df['Web'] < 500000), 'Office'] = True
    df.loc[psu_mask, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 7. CPU COOLER (Range Harga)
    cooler_mask = df['Kategori'] == 'CPU Cooler'
    def map_cooler(row):
        price = row['Web']
        if price <= 300000: row['Office'] = True
        if 250000 <= price <= 1000000: row['Gaming Standard / Design 2D'] = True
        if price > 500000: row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[cooler_mask] = df[cooler_mask].apply(map_cooler, axis=1)
    
    return df

# --- VALIDASI KOMPATIBILITAS MOBO & CPU ---
def is_compatible(cpu, mobo):
    gen = cpu['CPU_Gen']
    socket = cpu['CPU_Socket']
    series = mobo['Mobo_Series']
    
    # Intel Logic
    if gen == 10: return series in ['H410', 'H510']
    if gen == 11: return series in ['H510']
    if gen in [12, 13, 14]: return series in ['H610', 'B660', 'B760', 'Z790']
    if gen == "ULTRA": return series in ['H810', 'B860', 'Z890']
    
    # AMD Logic
    if socket == "AM4": return series in ['A520', 'B450', 'B550']
    if socket == "AM5": return series in ['A620', 'B650', 'B840', 'B850', 'X870']
    
    return True

# --- GENERATE MULTIPLE BUNDLES (9 VARIASI) ---
def generate_bundles(df, branch_col, usage_cat, target_min, target_max):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    bundle_types = [
        {"name": "Ultra Stock Priority", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 0, "tag": "BEST STOCK"},
        {"name": "Popular Choice", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 1, "tag": "POPULAR"},
        {"name": "Stable Choice", "sort": [branch_col, 'Web'], "asc": [False, True], "idx": 2, "tag": "STABLE"},
        {"name": "Extreme Budget", "sort": ['Web', branch_col], "asc": [True, False], "idx": 0, "tag": "BEST PRICE"},
        {"name": "Smart Value", "sort": ['Web', branch_col], "asc": [True, False], "idx": 1, "tag": "RECOMMENDED"},
        {"name": "Balanced Sweet Spot", "sort": ['Web', branch_col], "asc": [True, False], "idx": "mid", "tag": "BALANCED"},
        {"name": "Advanced Mid-Range", "sort": ['Web', branch_col], "asc": [False, False], "idx": 2, "tag": "PERFORMANCE"},
        {"name": "Premium Enthusiast", "sort": ['Web', branch_col], "asc": [False, False], "idx": 1, "tag": "PREMIUM"},
        {"name": "Luxury Flagship", "sort": ['Web', branch_col], "asc": [False, False], "idx": 0, "tag": "ELITE"}
    ]

    results = []
    for bt in bundle_types:
        bundle = {}
        total = 0
        
        # 1. Processor
        procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=bt['sort'], ascending=bt['asc'])
        if procs.empty: continue
        p_idx = bt['idx'] if bt['idx'] != "mid" else len(procs)//2
        pick_proc = procs.iloc[min(p_idx if isinstance(p_idx, int) else 0, len(procs)-1)]
        bundle['Processor'] = pick_proc
        total += pick_proc['Web']
        
        # 2. Motherboard Compatible
        mobos = available_df[available_df['Kategori'] == 'Motherboard']
        compatible = mobos[mobos.apply(lambda m: is_compatible(pick_proc, m), axis=1)].sort_values(by=bt['sort'], ascending=bt['asc'])
        if compatible.empty: continue
        bundle['Motherboard'] = compatible.iloc[0]
        total += bundle['Motherboard']['Web']
        
        # 3. Core Parts
        for cat in ['Memory RAM', 'SSD Internal', 'Casing PC']:
            items = available_df[available_df['Kategori'] == cat].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not items.empty:
                bundle[cat] = items.iloc[0]
                total += bundle[cat]['Web']

        # 4. VGA (Kondisional F-Series)
        if pick_proc['NeedVGA'] == 1:
            vgas = available_df[available_df['Kategori'] == 'VGA'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not vgas.empty:
                bundle['VGA'] = vgas.iloc[0]
                total += bundle['VGA']['Web']

        # 5. PSU (Kondisional Office w/ PSU Case)
        needs_psu = True
        if usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1:
            needs_psu = False
        if needs_psu:
            psus = available_df[available_df['Kategori'] == 'Power Supply'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not psus.empty:
                bundle['Power Supply'] = psus.iloc[0]
                total += bundle['Power Supply']['Web']

        # 6. CPU Cooler (Kondisional Tray)
        if pick_proc['NeedCooler'] == 1:
            coolers = available_df[available_df['Kategori'] == 'CPU Cooler'].sort_values(by=bt['sort'], ascending=bt['asc'])
            if not coolers.empty:
                bundle['CPU Cooler'] = coolers.iloc[0]
                total += bundle['CPU Cooler']['Web']
        
        if target_min <= total <= target_max:
            results.append({"name": bt['name'], "parts": bundle, "total": total, "tag": bt['tag']})

    return results

# --- MAIN APP ---
st.title("🖥️ PC Wizard Pro - Sistem Multi-Bundling")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal (CSV atau XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    # Sidebar
    st.sidebar.header("⚙️ Konfigurasi")
    branch_map = {"ITC": "Stock A - ITC", "SBY": "Stock B", "C6": "Stock C6", "Semarang": "Stock D - SMG", "Jogja": "Stock E - JOG", "Malang": "Stock F - MLG", "Bali": "Stock H - BALI", "Surabaya (Y)": "Stock Y - SBY"}
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(branch_map.keys()))
    b_col = branch_map[sel_branch]
    u_cat = st.sidebar.radio("Kategori:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Biaya Rakit
    asm_fee = {"Office": 100000, "Gaming Standard / Design 2D": 150000, "Gaming Advanced / Design 3D": 200000}[u_cat]

    # Price Calculation
    rel_df = data[(data[u_cat] == True) & (data[b_col] > 0)]
    min_p = rel_df.groupby('Kategori')['Web'].min().sum()
    max_p = rel_df.groupby('Kategori')['Web'].max().sum()
    st.sidebar.info(f"Rentang Sistem: Rp{min_p:,.0f} - Rp{max_p:,.0f}")
    p_min = st.sidebar.number_input("Harga Min", min_value=0.0, value=float(min_p))
    p_max = st.sidebar.number_input("Harga Max", min_value=0.0, value=float(max_p))

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi ({u_cat})")
        recs = generate_bundles(data, b_col, u_cat, p_min, p_max)
        if not recs: st.warning("Sesuaikan rentang harga.")
        else:
            for i in range(0, len(recs), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(recs):
                        res = recs[i+j]
                        with cols[j]:
                            st.markdown(f"""<div class="bundle-card"><div><span class="badge-stock">{res['tag']}</span><div class="bundle-title">{res['name']}</div><div class="price-text">Rp {res['total']:,.0f}</div></div></div>""", unsafe_allow_html=True)
                            if st.button("Pilih & Sesuaikan", key=f"btn_{i+j}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                st.session_state.view = 'detail'
                                st.rerun()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        st.button("⬅️ Kembali", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Penyesuaian: {bundle['name']}")
        
        c_parts, c_sum = st.columns([2, 1])
        with c_parts:
            # URUTAN TAMPILAN SESUAI PERMINTAAN
            ord = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'VGA', 'Casing PC', 'Power Supply', 'CPU Cooler']
            upd = {}
            for cat in ord:
                if cat in bundle['parts']:
                    item = bundle['parts'][cat]
                    col1, col2 = st.columns([5, 1])
                    col1.write(f"**[{cat}]** {item['Nama Accurate']}")
                    col1.caption(f"Harga: Rp{item['Web']:,.0f}")
                    if not col2.button("➖", key=f"del_{cat}"): upd[cat] = item
            st.session_state.selected_bundle['parts'] = upd

        with c_sum:
            st.markdown("### 🧾 Ringkasan")
            rakit = st.checkbox(f"Jasa Rakit (Rp {asm_fee:,.0f})?", value=False)
            t_items = sum(x['Web'] for x in upd.values())
            grand = t_items + (asm_fee if rakit else 0)
            for k, v in upd.items(): st.text(f"• {v['Nama Accurate'][:35]}...")
            if rakit: st.text(f"• Jasa Rakit {u_cat}")
            st.divider()
            st.subheader(f"Total: Rp{grand:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True): st.balloons()
