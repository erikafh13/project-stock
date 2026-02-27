import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="Sistem Bundling PC - Pro", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    
    .bundle-card {
        border: 1px solid #e1e4e8;
        border-radius: 12px;
        padding: 15px;
        background-color: #ffffff;
        margin-bottom: 20px;
        transition: all 0.3s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 2px 5px rgba(0,0,0,0.05);
    }
    .bundle-card:hover {
        box-shadow: 0 8px 20px rgba(0,0,0,0.1);
        border-color: #1E88E5;
        transform: translateY(-5px);
    }
    .price-text {
        color: #1E88E5;
        font-size: 22px;
        font-weight: 800;
        margin: 10px 0;
    }
    .bundle-title {
        color: #2c3e50;
        font-size: 16px;
        font-weight: 700;
        margin-bottom: 4px;
        line-height: 1.3;
        min-height: 42px;
    }
    .badge-strategy {
        padding: 3px 10px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 800;
        margin-bottom: 10px;
        display: inline-block;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .badge-cheapest { background-color: #E8F5E9; color: #2E7D32; }
    .badge-mid { background-color: #FFF3E0; color: #EF6C00; }
    .badge-premium { background-color: #E3F2FD; color: #1565C0; }
    
    .part-count-text {
        color: #7f8c8d;
        font-size: 13px;
        font-weight: 500;
        margin-bottom: 10px;
    }
    .stMarkdown { line-height: 1.2 !important; }
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
    name = name.upper()
    if 'DDR5' in name or ' D5' in name: return 'DDR5'
    if 'DDR4' in name or ' D4' in name: return 'DDR4'
    return None

def is_compatible(cpu_row, mobo_row):
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
    df.columns = df.columns.str.strip()
    df['Stock_SBY_Combined'] = (
        df.get('Stock A - ITC', 0).fillna(0) + 
        df.get('Stock B', 0).fillna(0) + 
        df.get('Stock Y - SBY', 0).fillna(0)
    )
    df = df[df['Stock Total'] > 0].copy()
    df['Nama Accurate'] = df['Nama Accurate'].fillna('').str.strip()
    df['Kategori'] = df['Kategori'].fillna('').str.strip()
    df['Web'] = pd.to_numeric(df['Web'], errors='coerce').fillna(0)
    
    cat_up = df['Kategori'].str.upper()
    df.loc[cat_up.str.contains('PROCESSOR'), 'Kategori'] = 'Processor'
    df.loc[cat_up.str.contains('MOTHERBOARD'), 'Kategori'] = 'Motherboard'
    df.loc[cat_up.str.contains('MEMORY RAM|RAM'), 'Kategori'] = 'Memory RAM'
    df.loc[cat_up.str.contains('SSD'), 'Kategori'] = 'SSD Internal'
    df.loc[cat_up.str.contains('VGA|GRAPHIC CARD'), 'Kategori'] = 'VGA'
    df.loc[cat_up.str.contains('CASING'), 'Kategori'] = 'Casing PC'
    df.loc[cat_up.str.contains('POWER SUPPLY|PSU'), 'Kategori'] = 'Power Supply'
    df.loc[cat_up.str.contains('COOLER|COOLING|FAN PROCESSOR|HEATSINK'), 'Kategori'] = 'CPU Cooler'
    
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

        if cat == 'Processor':
            if re.search(r'\d+[0-9]F\b', name): df.at[idx, 'NeedVGA'] = 1
            if 'TRAY' in name or 'NO FAN' in name: df.at[idx, 'NeedCooler'] = 1
            if 'I3' in name or 'I5' in name:
                df.at[idx, 'Office'] = True
                df.at[idx, 'Gaming Standard / Design 2D'] = True
            # Gaming Advanced: Hanya Seri F (Sesuai Permintaan)
            if any(x in name for x in ['I5', 'I7', 'I9', 'ULTRA', 'RYZEN']):
                if df.at[idx, 'NeedVGA'] == 1:
                    df.at[idx, 'Gaming Advanced / Design 3D'] = True
            cpu_info = get_cpu_info(name)
            df.at[idx, 'CPU_Gen'] = cpu_info['gen']
            df.at[idx, 'CPU_Socket'] = cpu_info['socket']

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

        elif cat == 'Memory RAM':
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            if 'SODIMM' not in name:
                match_gb = re.search(r'(\d+)\s*GB', name)
                if match_gb:
                    size = int(match_gb.group(1))
                    if 8 <= size <= 16: df.at[idx, 'Office'] = True
                    if 16 <= size <= 32: df.at[idx, 'Gaming Standard / Design 2D'] = True
                    if 32 <= size <= 64: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        elif cat == 'SSD Internal':
            if 'WDS120G2G0B' in name: continue 
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D']] = True
            if 'M.2 NVME' in name: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        elif cat == 'VGA':
            if any(x in name for x in ['GT710', 'GT730']): df.at[idx, 'Office'] = True
            df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        elif cat == 'Casing PC':
            if 'ARMAGGEDDON' not in name:
                if 'PSU' in name or 'VALCAS' in name:
                    df.at[idx, 'Office'], df.at[idx, 'HasPSU'] = True, 1
                else:
                    df.at[idx, 'Office'] = True
                df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        elif cat == 'Power Supply':
            if price <= 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        elif cat == 'CPU Cooler':
            if price <= 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced / Design 3D'] = True
            
    return df

# --- 4. ENGINE REKOMENDASI ---

def generate_market_bundles(df, branch_col, usage_cat, p_min, p_max):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    strategies = [
        {"label": "Harga Termurah", "sort_asc": True, "p_idx_type": "head", "class": "badge-cheapest"},
        {"label": "Harga Tengah", "sort_asc": True, "p_idx_type": "mid", "class": "badge-mid"},
        {"label": "Harga Termahal", "sort_asc": False, "p_idx_type": "head", "class": "badge-premium"}
    ]
    
    results = []
    
    for strat in strategies:
        # Sorting processor berdasarkan strategi
        if strat['label'] == "Harga Termurah":
            procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web', branch_col], ascending=[True, False])
        elif strat['label'] == "Harga Termahal":
            procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web', branch_col], ascending=[False, False])
        else: # Harga Tengah
            # Ambil semua processor, cari yang ada di urutan tengah
            procs_all = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web'], ascending=True)
            if procs_all.empty: continue
            mid_start = len(procs_all) // 2 - 1 if len(procs_all) > 2 else 0
            procs = procs_all.iloc[max(0, mid_start):] # Mulai dari tengah
            
        if procs.empty: continue
        
        # Ambil sampai 3 opsi per strategi yang masuk range harga
        count_for_strat = 0
        for i in range(len(procs)):
            if count_for_strat >= 3: break
            
            pick_proc = procs.iloc[i]
            bundle, total = {'Processor': pick_proc}, pick_proc['Web']
            
            def pick_part(category, compatibility_func=None):
                items = available_df[available_df['Kategori'] == category]
                if compatibility_func:
                    items = items[items.apply(compatibility_func, axis=1)]
                if items.empty: return None
                
                # Strategi pemilihan barang pendukung mengikuti tier bundel
                if strat['label'] == "Harga Termurah":
                    return items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
                elif strat['label'] == "Harga Termahal":
                    return items.sort_values(by=['Web', branch_col], ascending=[False, False]).iloc[0]
                else: # Tengah -> Ambil yang stok paling banyak di harga tengah
                    return items.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]

            # Core components
            mobo = pick_part('Motherboard', lambda m: is_compatible(pick_proc, m))
            if mobo is None: continue
            bundle['Motherboard'] = mobo
            total += mobo['Web']
            
            ram = pick_part('Memory RAM', lambda r: r.get('DDR_Type') == mobo.get('DDR_Type'))
            if ram is None: continue
            bundle['Memory RAM'] = ram
            total += ram['Web']
            
            for cat in ['SSD Internal', 'Casing PC']:
                item = pick_part(cat)
                if item is not None: 
                    bundle[cat] = item
                    total += item['Web']

            # Mandatory conditionals
            if pick_proc['NeedVGA'] == 1:
                vga = pick_part('VGA')
                if vga is not None: bundle['VGA'] = vga; total += vga['Web']
                else: continue
                
            if not (usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1):
                psu = pick_part('Power Supply')
                if psu is not None: bundle['Power Supply'] = psu; total += psu['Web']
                else: continue

            if pick_proc['NeedCooler'] == 1:
                cooler = pick_part('CPU Cooler')
                if cooler is not None: bundle['CPU Cooler'] = cooler; total += cooler['Web']
                else: continue

            # Filter Range Harga User
            if p_min <= total <= p_max:
                results.append({
                    "strategy": strat['label'],
                    "badge_class": strat['class'],
                    "name": f"{strat['label']} #{count_for_strat + 1}",
                    "parts": bundle,
                    "total": total
                })
                count_for_strat += 1
            
    return results

# --- 5. UI LAYER ---

st.title("🛒 PC Wizard")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    # Sidebar
    st.sidebar.header("⚙️ Konfigurasi")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]
    u_cat = st.sidebar.radio("Kategori Kebutuhan:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # Price Filter Sidebar
    rel_df = data[(data[u_cat] == True) & (data[b_col] > 0)]
    if not rel_df.empty:
        calc_min = rel_df.groupby('Kategori')['Web'].min().sum()
        calc_max = rel_df.groupby('Kategori')['Web'].max().sum()
        st.sidebar.markdown("---")
        st.sidebar.subheader("💰 Range Harga")
        p_min = st.sidebar.number_input("Harga Minimum (Rp)", value=float(calc_min), step=100000.0)
        p_max = st.sidebar.number_input("Harga Maksimum (Rp)", value=float(calc_max), step=100000.0)
    else:
        p_min, p_max = 0.0, 100000000.0

    if st.session_state.view == 'main':
        st.info(f"📍 Menampilkan pilihan bundling di {sel_branch}")
        
        all_bundles = generate_market_bundles(data, b_col, u_cat, p_min, p_max)
        
        if not all_bundles:
            st.warning("Maaf, tidak ada bundling yang sesuai dengan budget atau ketersediaan stok saat ini.")
        else:
            for i in range(0, len(all_bundles), 3):
                cols = st.columns(3)
                for j in range(3):
                    idx = i + j
                    if idx < len(all_bundles):
                        res = all_bundles[idx]
                        with cols[j]:
                            st.markdown(f"""
                            <div class="bundle-card">
                                <div>
                                    <span class="badge-strategy {res['badge_class']}">{res['strategy']}</span>
                                    <div class="bundle-title">Paket {u_cat} - {res['name']}</div>
                                    <div class="part-count-text">📦 {len(res['parts'])} Komponen Termasuk</div>
                                    <div class="price-text">Rp {res['total']:,.0f}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button(f"Pilih & Sesuaikan", key=f"btn_{idx}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                if 'temp_parts' in st.session_state: del st.session_state.temp_parts
                                st.session_state.view = 'detail'
                                st.rerun()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        if 'temp_parts' not in st.session_state: st.session_state.temp_parts = bundle['parts'].copy()
        upd = st.session_state.temp_parts

        st.button("⬅️ Kembali", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Sesuaikan {bundle['name']}")
        
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
                    if not cat_options.empty: upd[cat] = cat_options.sort_values(b_col, ascending=False).iloc[0]

                if cat in upd:
                    item = upd[cat]
                    with st.expander(f"📦 **{cat}**: {item['Nama Accurate']}", expanded=(cat == 'Processor')):
                        sorted_opts = cat_options.sort_values('Web')
                        labels = sorted_opts['Nama Accurate'] + " (Rp " + sorted_opts['Web'].map('{:,.0f}'.format) + ")"
                        try: idx = sorted_opts['Nama Accurate'].tolist().index(item['Nama Accurate'])
                        except: idx = 0
                        new_pick = st.selectbox(f"Ganti {cat}:", labels, index=idx, key=f"sel_{cat}")
                        new_item = sorted_opts[sorted_opts['Nama Accurate'] == new_pick.split(" (Rp ")[0]].iloc[0]
                        if new_item['Nama Accurate'] != item['Nama Accurate']:
                            upd[cat] = new_item
                            st.rerun()
                        if not is_mandatory and st.button(f"Hapus {cat}", key=f"del_{cat}"):
                            del upd[cat]
                            st.rerun()
                st.divider()

        with c_sum:
            st.markdown("### 📋 Ringkasan")
            asm_fee = ASSEMBLY_FEES[u_cat]
            rakit = st.checkbox(f"Biaya Rakit ({u_cat}: Rp {asm_fee:,.0f})", value=True)
            total_items = sum(x['Web'] for x in upd.values())
            grand = total_items + (asm_fee if rakit else 0)
            
            for k, v in upd.items():
                st.markdown(f"**{k}**: {v['Nama Accurate']}  \n`Rp {v['Web']:,.0f}`")
            if rakit: st.markdown(f"**Biaya Rakit**: `Rp {asm_fee:,.0f}`")
            
            st.divider()
            st.subheader(f"Total: Rp {grand:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True, type="primary"): 
                st.balloons()
                st.success("Berhasil!")
else:
    st.info("👋 Silakan upload file Data Portal (CSV/Excel) untuk memulai sistem bundling pintar.")
