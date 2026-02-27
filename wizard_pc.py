import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="PC Wizard Pro", layout="wide")

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
        margin: 8px 0;
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
        padding: 3px 12px;
        border-radius: 20px;
        font-size: 10px;
        font-weight: 800;
        margin-bottom: 10px;
        display: inline-block;
        text-transform: uppercase;
        letter-spacing: 0.8px;
    }
    .badge-value { background-color: #E8F5E9; color: #2E7D32; border: 1px solid #C8E6C9; }
    .badge-core { background-color: #FFF3E0; color: #EF6C00; border: 1px solid #FFE0B2; }
    .badge-elite { background-color: #E3F2FD; color: #1565C0; border: 1px solid #BBDEFB; }
    
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
    
    # 1. Normalisasi Kategori
    cat_up = df['Kategori'].str.upper()
    df.loc[cat_up.str.contains('PROCESSOR'), 'Kategori'] = 'Processor'
    df.loc[cat_up.str.contains('MOTHERBOARD'), 'Kategori'] = 'Motherboard'
    df.loc[cat_up.str.contains('MEMORY RAM|RAM'), 'Kategori'] = 'Memory RAM'
    df.loc[cat_up.str.contains('SSD'), 'Kategori'] = 'SSD Internal'
    df.loc[cat_up.str.contains('VGA|GRAPHIC CARD'), 'Kategori'] = 'VGA'
    df.loc[cat_up.str.contains('CASING'), 'Kategori'] = 'Casing PC'
    df.loc[cat_up.str.contains('POWER SUPPLY|PSU'), 'Kategori'] = 'Power Supply'
    df.loc[cat_up.str.contains('COOLER|COOLING|FAN PROCESSOR|HEATSINK'), 'Kategori'] = 'CPU Cooler'
    
    # Inisialisasi Flag & Metadata
    for col in ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']:
        df[col] = False
    df['NeedVGA'], df['HasPSU'], df['NeedCooler'] = 0, 0, 0
    df['CPU_Gen'], df['CPU_Socket'], df['Mobo_Series'], df['DDR_Type'] = None, None, None, None

    for idx, row in df.iterrows():
        name = row['Nama Accurate'].upper()
        price = row['Web']
        cat = row['Kategori']

        # A. CPU Rules
        if cat == 'Processor':
            is_f_series = bool(re.search(r'\d+[0-9]F\b', name))
            if is_f_series: df.at[idx, 'NeedVGA'] = 1
            if 'TRAY' in name or 'NO FAN' in name: df.at[idx, 'NeedCooler'] = 1
            cpu_info = get_cpu_info(name)
            df.at[idx, 'CPU_Gen'] = cpu_info['gen']
            df.at[idx, 'CPU_Socket'] = cpu_info['socket']
            
            if 'I3' in name or 'I5' in name:
                df.at[idx, 'Office'] = True
                df.at[idx, 'Gaming Standard / Design 2D'] = True
            if any(x in name for x in ['I5', 'I7', 'I9', 'ULTRA', 'RYZEN']) and is_f_series:
                df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # B. MOBO Rules
        elif cat == 'Motherboard':
            series_list = ['H410', 'H510', 'H610', 'H810', 'B660', 'B760', 'B860', 'Z790', 'Z890', 
                           'A520', 'A620', 'B450', 'B550', 'B650', 'B840', 'B850', 'X870']
            for s in series_list:
                if s in name: 
                    df.at[idx, 'Mobo_Series'] = s
                    break
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            if any(x in name for x in ['H410', 'H510', 'H610', 'H810', 'A520', 'A620']):
                df.at[idx, 'Office'] = True
            df.at[idx, 'Gaming Standard / Design 2D'] = True
            df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # C. RAM Rules (No SODIMM)
        elif cat == 'Memory RAM':
            if 'SODIMM' in name: continue 
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            match_gb = re.search(r'(\d+)\s*GB', name)
            if match_gb:
                sz = int(match_gb.group(1))
                if 8 <= sz <= 16: df.at[idx, 'Office'] = True
                if 16 <= sz <= 32: df.at[idx, 'Gaming Standard / Design 2D'] = True
                if 32 <= sz <= 64: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # D. SSD Rules (No WDS120G2G0B, NVMe for Advanced)
        elif cat == 'SSD Internal':
            if 'WDS120G2G0B' in name: continue 
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D']] = True
            if 'M.2 NVME' in name: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # E. VGA Rules
        elif cat == 'VGA':
            if any(x in name for x in ['GT710', 'GT730']): df.at[idx, 'Office'] = True
            df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # F. CASING Rules (No Armaggeddon)
        elif cat == 'Casing PC':
            if 'ARMAGGEDDON' in name: continue
            if 'PSU' in name or 'VALCAS' in name:
                df.at[idx, 'Office'], df.at[idx, 'HasPSU'] = True, 1
            else:
                df.at[idx, 'Office'] = True
            df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # G. PSU & COOLER Rules
        elif cat in ['Power Supply', 'CPU Cooler']:
            if price <= 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced / Design 3D'] = True
            
    return df

# --- 4. ENGINE REKOMENDASI & HARGA ---

def assemble_single_bundle(available_df, pick_p, strategy_label, branch_col, usage_cat):
    """Fungsi helper untuk merakit satu paket bundling berdasarkan strategi tertentu."""
    bundle, total = {'Processor': pick_p}, pick_p['Web']
    
    def pick_part(category, compatibility_func=None):
        items = available_df[available_df['Kategori'] == category]
        if compatibility_func:
            items = items[items.apply(compatibility_func, axis=1)]
        if items.empty: return None
        
        if strategy_label == "Best Value Selection":
            return items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
        elif strategy_label == "Elite Enthusiast":
            return items.sort_values(by=['Web', branch_col], ascending=[False, False]).iloc[0]
        else: # Core Performance / Default
            return items.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]

    # Perakitan
    mobo = pick_part('Motherboard', lambda m: is_compatible(pick_p, m))
    if mobo is None: return None
    bundle['Motherboard'] = mobo; total += mobo['Web']
    
    ram = pick_part('Memory RAM', lambda r: r.get('DDR_Type') == mobo.get('DDR_Type'))
    if ram is None: return None
    bundle['Memory RAM'] = ram; total += ram['Web']
    
    for cat in ['SSD Internal', 'Casing PC']:
        item = pick_part(cat)
        if item is None: return None
        bundle[cat] = item; total += item['Web']

    if pick_p['NeedVGA'] == 1:
        vga = pick_part('VGA')
        if vga is None: return None
        bundle['VGA'] = vga; total += vga['Web']
        
    if not (usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1):
        psu = pick_part('Power Supply')
        if psu is None: return None
        bundle['Power Supply'] = psu; total += psu['Web']

    if pick_p['NeedCooler'] == 1:
        cooler = pick_part('CPU Cooler')
        if cooler is None: return None
        bundle['CPU Cooler'] = cooler; total += cooler['Web']

    return {"parts": bundle, "total": total}

def generate_market_bundles(df, branch_col, usage_cat, p_min, p_max):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    strategies = [
        {"label": "Best Value Selection", "class": "badge-value"},
        {"label": "Core Performance", "class": "badge-core"},
        {"label": "Elite Enthusiast", "class": "badge-elite"}
    ]
    
    results = []
    for strat in strategies:
        # Sort Processor sesuai strategi
        if strat['label'] == "Best Value Selection":
            procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web', branch_col], ascending=[True, False])
        elif strat['label'] == "Elite Enthusiast":
            procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web', branch_col], ascending=[False, False])
        else: # Core Performance
            procs_all = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=['Web'], ascending=True)
            if procs_all.empty: continue
            mid_idx = len(procs_all) // 2
            procs = procs_all.iloc[max(0, mid_idx-5):] 
            
        found_for_strat = 0
        for i in range(len(procs)):
            if found_for_strat >= 3: break
            
            res = assemble_single_bundle(available_df, procs.iloc[i], strat['label'], branch_col, usage_cat)
            if res and p_min <= res['total'] <= p_max:
                results.append({
                    "strategy": strat['label'],
                    "badge_class": strat['class'],
                    "name": f"{strat['label']} #{found_for_strat + 1}",
                    "parts": res['parts'],
                    "total": res['total']
                })
                found_for_strat += 1
            
    return results

# --- 5. UI LAYER ---

st.title("🛒 PC Wizard Marketplace")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    st.sidebar.header("⚙️ Konfigurasi")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]
    u_cat = st.sidebar.radio("Kategori Kebutuhan:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    # --- HITUNG RANGE HARGA NYATA (DARI PAKET TERURAH) ---
    valid_data = data[(data[u_cat] == True) & (data[b_col] > 0)]
    if not valid_data.empty:
        # Cari paket termurah & termahal nyata (bukan teoritis)
        procs_for_range = valid_data[valid_data['Kategori'] == 'Processor'].sort_values('Web')
        
        # Test Paket Termurah Nyata
        min_bundle = assemble_single_bundle(valid_data, procs_for_range.iloc[0], "Best Value Selection", b_col, u_cat)
        # Test Paket Termahal Nyata
        max_bundle = assemble_single_bundle(valid_data, procs_for_range.iloc[-1], "Elite Enthusiast", b_col, u_cat)
        
        # Fallback jika perakitan gagal
        calc_min = min_bundle['total'] if min_bundle else valid_data.groupby('Kategori')['Web'].min().sum()
        calc_max = max_bundle['total'] if max_bundle else valid_data.groupby('Kategori')['Web'].max().sum()
        
        st.sidebar.markdown("---")
        st.sidebar.subheader("💰 Tentukan Budget")
        st.sidebar.caption(f"Estimasi {u_cat}: Rp {calc_min:,.0f} - Rp {calc_max:,.0f}")
        p_min = st.sidebar.number_input("Budget Minimum (Rp)", value=float(calc_min), step=100000.0)
        p_max = st.sidebar.number_input("Budget Maksimum (Rp)", value=float(calc_max), step=100000.0)
    else:
        p_min, p_max = 0.0, 100000000.0

    if st.session_state.view == 'main':
        st.info(f"📍 Rekomendasi di {sel_branch}")
        all_bundles = generate_market_bundles(data, b_col, u_cat, p_min, p_max)
        
        if not all_bundles:
            st.warning("⚠️ Tidak ada bundling yang sesuai budget atau ketersediaan stok.")
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

        st.button("⬅️ Kembali ke Marketplace", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Sesuaikan {bundle['name']}")
        
        c_p, c_s = st.columns([2, 1])
        with c_p:
            available_detail = data[(data[b_col] > 0) & (data[u_cat] == True)]
            for cat in DISPLAY_ORDER:
                is_mandatory = cat in ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'Casing PC']
                cur_p, cur_m = upd.get('Processor'), upd.get('Motherboard')
                
                if cat == 'VGA' and cur_p is not None and cur_p['NeedVGA'] == 1: is_mandatory = True
                if cat == 'CPU Cooler' and cur_p is not None and cur_p['NeedCooler'] == 1: is_mandatory = True
                if cat == 'Power Supply' and not (u_cat == "Office" and upd.get('Casing PC', {}).get('HasPSU', 0) == 1): is_mandatory = True

                cat_opts = available_detail[available_detail['Kategori'] == cat]
                if cat == 'Motherboard' and cur_p is not None:
                    cat_opts = cat_opts[cat_opts.apply(lambda m: is_compatible(cur_p, m), axis=1)]
                if cat == 'Memory RAM' and cur_m is not None:
                    if cur_m.get('DDR_Type'): cat_opts = cat_opts[cat_opts['DDR_Type'] == cur_m.get('DDR_Type')]

                if cat not in upd and is_mandatory:
                    if not cat_opts.empty: upd[cat] = cat_opts.sort_values(b_col, ascending=False).iloc[0]

                if cat in upd:
                    item = upd[cat]
                    with st.expander(f"📦 **{cat}**: {item['Nama Accurate']}", expanded=(cat == 'Processor')):
                        s_o = cat_opts.sort_values('Web')
                        lbls = s_o['Nama Accurate'] + " (Rp " + s_o['Web'].map('{:,.0f}'.format) + ")"
                        try: ix = s_o['Nama Accurate'].tolist().index(item['Nama Accurate'])
                        except: ix = 0
                        new_pick = st.selectbox(f"Ubah {cat}:", lbls, index=ix, key=f"sel_{cat}")
                        new_it = s_o[s_o['Nama Accurate'] == new_pick.split(" (Rp ")[0]].iloc[0]
                        if new_it['Nama Accurate'] != item['Nama Accurate']:
                            upd[cat] = new_it
                            st.rerun()
                        if not is_mandatory and st.button(f"Hapus {cat}", key=f"del_{cat}"):
                            del upd[cat]
                            st.rerun()
                st.divider()

        with c_s:
            st.markdown("### 📋 Ringkasan")
            rakit_fee = ASSEMBLY_FEES[u_cat]
            rakit = st.checkbox(f"Biaya Rakit ({u_cat}: Rp {rakit_fee:,.0f})", value=True)
            total_it = sum(x['Web'] for x in upd.values())
            grand_total = total_it + (rakit_fee if rakit else 0)
            for k, v in upd.items(): st.markdown(f"**{k}**: {v['Nama Accurate']}  \n`Rp {v['Web']:,.0f}`")
            if rakit: st.markdown(f"**Biaya Rakit**: `Rp {rakit_fee:,.0f}`")
            st.divider()
            st.subheader(f"Total: Rp {grand_total:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True, type="primary"): 
                st.balloons()
else:
    st.info("👋 Silakan upload file Data Portal untuk memulai.")
