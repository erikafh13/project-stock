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

# --- FUNGSI PEMBANTU IDENTIFIKASI GENERASI/SOCKET ---
def get_cpu_info(name):
    name = name.upper()
    info = {"gen": None, "socket": None, "type": "INTEL"}
    
    # Intel Core iX-Generation
    intel_match = re.search(r'I[3579]-(\d{1,2})', name)
    if intel_match:
        info["gen"] = int(intel_match.group(1))
    elif "ULTRA" in name:
        info["gen"] = "ULTRA"
    
    # AMD Ryzen
    if "RYZEN" in name:
        info["type"] = "AMD"
        if any(x in name for x in ["7000", "8000", "9000"]) or "AM5" in name:
            info["socket"] = "AM5"
        else:
            info["socket"] = "AM4"
            
    return info

# --- FUNGSI PEMROSESAN DATA (REVISI LOGIKA FIRMAN) ---
def process_data(df):
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('')
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    # Inisialisasi Kolom
    df['Office'] = False
    df['Gaming Standard / Design 2D'] = False
    df['Gaming Advanced / Design 3D'] = False
    df['NeedVGA'] = 0
    df['HasPSU'] = 0
    df['NeedCooler'] = 0
    df['CPU_Gen'] = None
    df['CPU_Socket'] = None
    df['Mobo_Series'] = None

    # 1. PROCESSOR (Logic: F-Series, Tray vs Box, Gen/Socket)
    proc_mask = df['Kategori'] == 'Processor'
    def map_processor(row):
        name = row['Nama Accurate'].upper()
        # Need VGA if 'F' series
        if re.search(r'\d+[0-9]F\b', name): row['NeedVGA'] = 1
        # Need Cooler if Tray
        if 'TRAY' in name or 'NO FAN' in name: row['NeedCooler'] = 1
        
        # Usage Mapping
        if 'I3' in name or 'I5' in name:
            row['Office'] = True
            row['Gaming Standard / Design 2D'] = True
        if 'I5' in name or 'I7' in name or 'I9' in name or 'ULTRA' in name:
            row['Gaming Advanced / Design 3D'] = True
            
        # Get Gen/Socket for Mobo Matching
        cpu_info = get_cpu_info(name)
        row['CPU_Gen'] = cpu_info['gen']
        row['CPU_Socket'] = cpu_info['socket']
        return row
    df.loc[proc_mask] = df[proc_mask].apply(map_processor, axis=1)

    # 2. MOTHERBOARD (Logic: Compatibility Table)
    mb_mask = df['Kategori'] == 'Motherboard'
    def map_mobo(row):
        name = row['Nama Accurate'].upper()
        # Mapping Series
        if 'H410' in name: row['Mobo_Series'] = 'H410'
        elif 'H510' in name: row['Mobo_Series'] = 'H510'
        elif 'H610' in name: row['Mobo_Series'] = 'H610'
        elif 'H810' in name: row['Mobo_Series'] = 'H810'
        elif 'B660' in name: row['Mobo_Series'] = 'B660'
        elif 'B760' in name: row['Mobo_Series'] = 'B760'
        elif 'B860' in name: row['Mobo_Series'] = 'B860'
        elif 'Z790' in name: row['Mobo_Series'] = 'Z790'
        elif 'Z890' in name: row['Mobo_Series'] = 'Z890'
        elif 'A520' in name: row['Mobo_Series'] = 'A520'
        elif 'A620' in name: row['Mobo_Series'] = 'A620'
        elif 'B450' in name: row['Mobo_Series'] = 'B450'
        elif 'B550' in name: row['Mobo_Series'] = 'B550'
        elif 'B650' in name: row['Mobo_Series'] = 'B650'
        elif 'B840' in name: row['Mobo_Series'] = 'B840'
        elif 'B850' in name: row['Mobo_Series'] = 'B850'
        elif 'X870' in name: row['Mobo_Series'] = 'X870'
        
        # Office mapping (H-Series Intel & A-Series AMD)
        if any(x in name for x in ['H410', 'H510', 'H610', 'H810', 'A520', 'A620']):
            row['Office'] = True
        row['Gaming Standard / Design 2D'] = True
        row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[mb_mask] = df[mb_mask].apply(map_mobo, axis=1)

    # 3. RAM, SSD (Default Rules)
    df.loc[df['Kategori'] == 'Memory RAM', ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True
    df.loc[df['Kategori'] == 'SSD Internal', ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 4. VGA (Usage Mapping)
    vga_mask = df['Kategori'] == 'VGA'
    gt_off = ['GT710', 'GT730']
    df.loc[vga_mask & df['Nama Accurate'].str.upper().str.contains('|'.join(gt_off)), 'Office'] = True
    df.loc[vga_mask, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 5. CASING (Logic: "PSU" in Name -> Office Only, HasPSU=1)
    case_mask = df['Kategori'] == 'Casing PC'
    def map_case(row):
        name = row['Nama Accurate'].upper()
        if 'PSU' in name:
            row['Office'], row['HasPSU'] = True, 1
        else:
            row['Office'] = True # Non-PSU cases can also be office
        row['Gaming Standard / Design 2D'], row['Gaming Advanced / Design 3D'] = True, True
        return row
    df.loc[case_mask] = df[case_mask].apply(map_case, axis=1)

    # 6. PSU (Price & Cert Rules)
    psu_mask = df['Kategori'] == 'Power Supply'
    df.loc[psu_mask & (df['Web'] < 500000), 'Office'] = True
    df.loc[psu_mask, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

    # 7. CPU COOLER (Logic: Price Ranges)
    cooler_mask = df['Kategori'] == 'CPU Cooler'
    def map_cooler(row):
        price = row['Web']
        if price <= 300000: row['Office'] = True
        if 250000 <= price <= 1000000: row['Gaming Standard / Design 2D'] = True
        if price > 500000: row['Gaming Advanced / Design 3D'] = True
        return row
    df.loc[cooler_mask] = df[cooler_mask].apply(map_cooler, axis=1)
    
    return df

# --- FUNGSI VALIDASI KOMPATIBILITAS ---
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
    
    return True # Default fallback

# --- FUNGSI GENERATE MULTIPLE REKOMENDASI ---
def generate_multiple_bundles(df, branch_col, usage_cat, target_price_min, target_price_max):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    results = []
    bundle_types = [
        {"name": "Ultra Stock Priority", "sort_by": [branch_col, 'Web'], "asc": [False, True], "idx": 0, "tag": "BEST STOCK"},
        {"name": "Popular High Stock", "sort_by": [branch_col, 'Web'], "asc": [False, True], "idx": 1, "tag": "POPULAR"},
        {"name": "Budget Value", "sort_by": ['Web', branch_col], "asc": [True, False], "idx": 0, "tag": "BEST PRICE"},
        {"name": "Smart Value", "sort_by": ['Web', branch_col], "asc": [True, False], "idx": 1, "tag": "RECOMMENDED"},
        {"name": "Balanced Sweet Spot", "sort_by": ['Web', branch_col], "asc": [True, False], "idx": "mid", "tag": "BALANCED"},
        {"name": "Premium Enthusiast", "sort_by": ['Web', branch_col], "asc": [False, False], "idx": 1, "tag": "PREMIUM"},
        {"name": "Luxury Flagship", "sort_by": ['Web', branch_col], "asc": [False, False], "idx": 0, "tag": "ELITE"}
    ]

    for bt in bundle_types:
        bundle = {}
        total = 0
        
        # 1. Pick Processor First
        procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=bt['sort_by'], ascending=bt['asc'])
        if procs.empty: continue
        
        p_idx = bt['idx'] if bt['idx'] != "mid" else len(procs)//2
        pick_proc = procs.iloc[min(p_idx if isinstance(p_idx, int) else 0, len(procs)-1)]
        bundle['Processor'] = pick_proc
        total += pick_proc['Web']
        
        # 2. Pick Compatible Motherboard
        mobos = available_df[available_df['Kategori'] == 'Motherboard']
        compatible_mobos = mobos[mobos.apply(lambda m: is_compatible(pick_proc, m), axis=1)].sort_values(by=bt['sort_by'], ascending=bt['asc'])
        if compatible_mobos.empty: continue
        bundle['Motherboard'] = compatible_mobos.iloc[0]
        total += bundle['Motherboard']['Web']
        
        # 3. Other Core Categories
        core_cats = ['Memory RAM', 'SSD Internal', 'Casing PC']
        for cat in core_cats:
            items = available_df[available_df['Kategori'] == cat].sort_values(by=bt['sort_by'], ascending=bt['asc'])
            if not items.empty:
                bundle[cat] = items.iloc[0]
                total += bundle[cat]['Web']

        # 4. Conditional: VGA
        if pick_proc['NeedVGA'] == 1:
            vgas = available_df[available_df['Kategori'] == 'VGA'].sort_values(by=bt['sort_by'], ascending=bt['asc'])
            if not vgas.empty:
                bundle['VGA'] = vgas.iloc[0]
                total += bundle['VGA']['Web']

        # 5. Conditional: PSU (If Office & Case has PSU -> Skip, Else -> Need)
        needs_psu = True
        if usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1:
            needs_psu = False
            
        if needs_psu:
            psus = available_df[available_df['Kategori'] == 'Power Supply'].sort_values(by=bt['sort_by'], ascending=bt['asc'])
            if not psus.empty:
                bundle['Power Supply'] = psus.iloc[0]
                total += bundle['Power Supply']['Web']

        # 6. Conditional: CPU Cooler
        if pick_proc['NeedCooler'] == 1:
            coolers = available_df[available_df['Kategori'] == 'CPU Cooler'].sort_values(by=bt['sort_by'], ascending=bt['asc'])
            if not coolers.empty:
                bundle['CPU Cooler'] = coolers.iloc[0]
                total += bundle['CPU Cooler']['Web']
        
        if target_price_min <= total <= target_price_max:
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
    st.sidebar.header("⚙️ Konfigurasi Utama")
    branch_map = {"ITC": "Stock A - ITC", "SBY": "Stock B", "C6": "Stock C6", "Semarang": "Stock D - SMG", "Jogja": "Stock E - JOG", "Malang": "Stock F - MLG", "Bali": "Stock H - BALI", "Surabaya (Y)": "Stock Y - SBY"}
    selected_branch = st.sidebar.selectbox("Pilih Cabang:", list(branch_map.keys()))
    branch_col = branch_map[selected_branch]
    usage_cat = st.sidebar.radio("Kategori Penggunaan:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Dinamis Price Range
    relevant_df = data[(data[usage_cat] == True) & (data[branch_col] > 0)]
    min_sum = relevant_df.groupby('Kategori')['Web'].min().sum()
    max_sum = relevant_df.groupby('Kategori')['Web'].max().sum()

    st.sidebar.info(f"Batas Sistem: Rp{min_sum:,.0f} - Rp{max_sum:,.0f}")
    price_min = st.sidebar.number_input("Harga Min", min_value=0.0, value=float(min_sum))
    price_max = st.sidebar.number_input("Harga Max", min_value=0.0, value=float(max_sum))

    # Biaya Rakit Mapping
    assembly_map = {"Office": 100000, "Gaming Standard / Design 2D": 150000, "Gaming Advanced / Design 3D": 200000}
    assembly_fee_standard = assembly_map[usage_cat]

    if st.session_state.view == 'main':
        st.subheader(f"✨ Rekomendasi Bundling ({usage_cat})")
        recs = generate_multiple_bundles(data, branch_col, usage_cat, price_min, price_max)
        
        if not recs: st.warning("Sesuaikan rentang harga untuk melihat rekomendasi.")
        else:
            for i in range(0, len(recs), 3):
                cols = st.columns(3)
                for j in range(3):
                    if i + j < len(recs):
                        res = recs[i + j]
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
        col_parts, col_summary = st.columns([2, 1])
        
        with col_parts:
            # URUTAN TAMPILAN: Processor, Motherboard, RAM, SSD, VGA, Casing, PSU, CPU Cooler
            display_order = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'VGA', 'Casing PC', 'Power Supply', 'CPU Cooler']
            updated_parts = {}
            for cat in display_order:
                if cat in bundle['parts']:
                    item = bundle['parts'][cat]
                    c1, c2 = st.columns([5, 1])
                    c1.write(f"**[{cat}]** {item['Nama Accurate']}")
                    c1.caption(f"Harga: Rp{item['Web']:,.0f}")
                    if not c2.button("➖", key=f"del_{cat}"): updated_parts[cat] = item
            
            st.session_state.selected_bundle['parts'] = updated_parts

        with col_summary:
            st.markdown("### 🧾 Ringkasan")
            is_assembled = st.checkbox(f"Jasa Rakit ({usage_cat}: Rp {assembly_fee_standard:,.0f})?", value=False)
            total_items = sum(item['Web'] for item in updated_parts.values())
            grand_total = total_items + (assembly_fee_standard if is_assembled else 0)
            
            for cat, item in updated_parts.items(): st.text(f"• {item['Nama Accurate'][:35]}...")
            if is_assembled: st.text(f"• Jasa Rakit {usage_cat}")
            
            st.divider()
            st.subheader(f"Total: Rp{grand_total:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True): st.balloons()
