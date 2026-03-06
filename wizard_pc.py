import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="PC Wizard Pro - Revisi Firman", layout="wide")

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
    .badge-stock { background-color: #E3F2FD; color: #1565C0; border: 1px solid #BBDEFB; }
    .badge-cheap { background-color: #E8F5E9; color: #2E7D32; border: 1px solid #C8E6C9; }
    .badge-smart { background-color: #FFF3E0; color: #EF6C00; border: 1px solid #FFE0B2; }
    
    .stock-info {
        font-size: 12px;
        color: #e67e22;
        font-weight: bold;
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
    
    # REVISI: Filter harga 0 dan 1
    df = df[df['Web'] > 1].copy()
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
    
    # Inisialisasi Flag Kategori Penggunaan
    for col in ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']:
        df[col] = False
    
    # Metadata
    df['NeedVGA'], df['HasPSU'], df['NeedCooler'] = 0, 0, 0
    df['CPU_Gen'], df['CPU_Socket'], df['Mobo_Series'], df['DDR_Type'] = None, None, None, None

    for idx, row in df.iterrows():
        name = row['Nama Accurate'].upper()
        price = row['Web']
        cat = row['Kategori']

        # 1. PROCESSOR RULES
        if cat == 'Processor':
            is_f_series = bool(re.search(r'\d+[0-9]F\b', name))
            if is_f_series: df.at[idx, 'NeedVGA'] = 1
            if 'TRAY' in name or 'NO FAN' in name: df.at[idx, 'NeedCooler'] = 1
            cpu_info = get_cpu_info(name)
            df.at[idx, 'CPU_Gen'], df.at[idx, 'CPU_Socket'] = cpu_info['gen'], cpu_info['socket']
            
            # Labeling Dasar
            if 'I3' in name or 'I5' in name:
                df.at[idx, 'Office'] = True
                df.at[idx, 'Gaming Standard / Design 2D'] = True
            if any(x in name for x in ['I5', 'I7', 'I9', 'ULTRA', 'RYZEN']):
                if is_f_series: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 2. MOTHERBOARD RULES
        elif cat == 'Motherboard':
            series_list = ['H410', 'H510', 'H610', 'H810', 'B660', 'B760', 'B860', 'Z790', 'Z890', 
                           'A520', 'A620', 'B450', 'B550', 'B650', 'B840', 'B850', 'X870']
            for s in series_list:
                if s in name: 
                    df.at[idx, 'Mobo_Series'] = s
                    break
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # 3. RAM RULES (No SODIMM)
        elif cat == 'Memory RAM':
            if 'SODIMM' in name: continue 
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            match_gb = re.search(r'(\d+)\s*GB', name)
            if match_gb:
                sz = int(match_gb.group(1))
                if 8 <= sz <= 16: df.at[idx, 'Office'] = True
                if 16 <= sz <= 32: df.at[idx, 'Gaming Standard / Design 2D'] = True
                if 32 <= sz <= 64: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 4. SSD RULES
        elif cat == 'SSD Internal':
            if 'WDS120G2G0B' in name: continue 
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D']] = True
            if 'M.2 NVME' in name: df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 5. VGA RULES
        elif cat == 'VGA':
            if any(x in name for x in ['GT710', 'GT730']): df.at[idx, 'Office'] = True
            df.loc[idx, ['Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True

        # 6. CASING PC RULES (REVISI FIRMAN)
        elif cat == 'Casing PC':
            if 'ARMAGGEDDON' in name: continue
            
            # Office: nama mengandung psu, office, valcas
            if any(x in name for x in ['PSU', 'OFFICE', 'VALCAS']):
                df.at[idx, 'Office'] = True
                if 'PSU' in name or 'VALCAS' in name: df.at[idx, 'HasPSU'] = 1
            
            # Std: harga 300rb-600rb
            if 300000 <= price <= 600000:
                df.at[idx, 'Gaming Standard / Design 2D'] = True
            
            # Adv: harga > 600rb
            if price > 600000:
                df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 7. POWER SUPPLY RULES (REVISI FIRMAN)
        elif cat == 'Power Supply':
            # Office: < 500rb
            if price < 500000: df.at[idx, 'Office'] = True
            
            # Std: >= 500rb
            if price >= 500000: df.at[idx, 'Gaming Standard / Design 2D'] = True
            
            # Adv: berlabel bronze, titanium, gold, etc
            if any(x in name for x in ['BRONZE', 'TITANIUM', 'GOLD', 'PLATINUM', 'SILVER']):
                df.at[idx, 'Gaming Advanced / Design 3D'] = True

        # 8. CPU COOLER RULES
        elif cat == 'CPU Cooler':
            df.loc[idx, ['Office', 'Gaming Standard / Design 2D', 'Gaming Advanced / Design 3D']] = True
            
    return df

# --- 4. ENGINE REKOMENDASI (STRATEGI REVISI) ---

def pick_component(items, strategy, branch_col):
    """Logika pemilihan barang berdasarkan 3 strategi Firman."""
    if items.empty: return None
    
    if strategy == "Harga Termurah":
        return items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
    
    elif strategy == "Stok Terbanyak":
        return items.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]
    
    elif strategy == "Smart Pick":
        # Aturan: cari harga termurah, ambil range +100rb, cari stok terbanyak
        min_price = items['Web'].min()
        pool = items[items['Web'] <= (min_price + 100000)]
        return pool.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]
    
    return items.iloc[0]

def assemble_bundle(available_df, pick_p, strategy, branch_col, usage_cat):
    bundle, total = {'Processor': pick_p}, pick_p['Web']
    
    def get_part(category, comp_func=None):
        items = available_df[available_df['Kategori'] == category]
        if comp_func: items = items[items.apply(comp_func, axis=1)]
        return pick_component(items, strategy, branch_col)

    # Perakitan
    mobo = get_part('Motherboard', lambda m: is_compatible(pick_p, m))
    if mobo is None: return None
    bundle['Motherboard'] = mobo; total += mobo['Web']
    
    ram = get_part('Memory RAM', lambda r: r.get('DDR_Type') == mobo.get('DDR_Type'))
    if ram is None: return None
    bundle['Memory RAM'] = ram; total += ram['Web']
    
    for cat in ['SSD Internal', 'Casing PC']:
        item = get_part(cat)
        if item is None: return None
        bundle[cat] = item; total += item['Web']

    if pick_p['NeedVGA'] == 1:
        vga = get_part('VGA')
        if vga is None: return None
        bundle['VGA'] = vga; total += vga['Web']
        
    if not (usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1):
        psu = get_part('Power Supply')
        if psu is None: return None
        bundle['Power Supply'] = psu; total += psu['Web']

    if pick_p['NeedCooler'] == 1:
        cooler = get_part('CPU Cooler')
        if cooler is None: return None
        bundle['CPU Cooler'] = cooler; total += cooler['Web']

    return {"parts": bundle, "total": total}

def generate_all_bundles(df, branch_col, usage_cat):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    strategies = [
        {"label": "Stok Terbanyak", "class": "badge-stock"},
        {"label": "Harga Termurah", "class": "badge-cheap"},
        {"label": "Smart Pick", "class": "badge-smart"}
    ]
    
    final_results = []
    
    for strat in strategies:
        # Cari prosesor terbaik untuk strategi ini
        procs = available_df[available_df['Kategori'] == 'Processor']
        if procs.empty: continue
        
        # Urutkan procs sesuai strategi untuk mencari start point
        if strat['label'] == "Harga Termurah": procs = procs.sort_values('Web')
        else: procs = procs.sort_values(branch_col, ascending=False)
        
        # Coba rakit sampai dapat paket valid
        for i in range(len(procs)):
            res = assemble_bundle(available_df, procs.iloc[i], strat['label'], branch_col, usage_cat)
            if res:
                final_results.append({
                    "strategy": strat['label'],
                    "badge_class": strat['class'],
                    "parts": res['parts'],
                    "total": res['total']
                })
                break # 1 card per strategi per kategori penggunaan
                
    return final_results

# --- 5. UI LAYER ---

st.title("🛒 PC Wizard Pro")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    st.sidebar.header("⚙️ Konfigurasi")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]

    if st.session_state.view == 'main':
        st.info(f"📍 Menampilkan Rekomendasi Marketplace untuk {sel_branch}")
        
        # REVISI: Mapping Threshold (Office <10, Std 10-20, Adv >20)
        use_cases = [
            {"label": "Office", "desc": "Budget Bersahabat (< Rp 10 Juta)"},
            {"label": "Gaming Standard / Design 2D", "desc": "Performa Seimbang (Rp 10 - 20 Juta)"},
            {"label": "Gaming Advanced / Design 3D", "desc": "Elite Performance (> Rp 20 Juta)"}
        ]
        
        for uc in use_cases:
            st.subheader(f"✨ {uc['label']}")
            st.caption(uc['desc'])
            
            recs = generate_all_bundles(data, b_col, uc['label'])
            
            # Filter berdasarkan threshold revisi Firman
            if uc['label'] == "Office": 
                recs = [r for r in recs if r['total'] < 10000000]
            elif uc['label'] == "Gaming Standard / Design 2D":
                recs = [r for r in recs if 10000000 <= r['total'] <= 20000000]
            else:
                recs = [r for r in recs if r['total'] > 20000000]

            if not recs:
                st.warning("Tidak ditemukan paket yang sesuai threshold harga atau ketersediaan stok komponen khusus kategori ini.")
            else:
                cols = st.columns(3)
                for idx, res in enumerate(recs):
                    with cols[idx]:
                        st.markdown(f"""
                        <div class="bundle-card">
                            <div>
                                <span class="badge-strategy {res['badge_class']}">{res['strategy']}</span>
                                <div class="bundle-title">Paket {uc['label']}</div>
                                <div class="part-count-text">📦 {len(res['parts'])} Komponen Included</div>
                                <div class="price-text">Rp {res['total']:,.0f}</div>
                            </div>
                        </div>
                        """, unsafe_allow_html=True)
                        if st.button(f"Pilih & Detail", key=f"btn_{uc['label']}_{idx}", use_container_width=True):
                            st.session_state.selected_bundle = res.copy()
                            st.session_state.view = 'detail'
                            st.session_state.current_cat = uc['label']
                            st.rerun()
            st.divider()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        if 'temp_parts' not in st.session_state: st.session_state.temp_parts = bundle['parts'].copy()
        upd = st.session_state.temp_parts
        u_cat = st.session_state.current_cat

        st.button("⬅️ Kembali ke Marketplace", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Detail Konfigurasi: {bundle['strategy']}")
        
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
                        # Tampilkan stok real-time di detail
                        st.markdown(f"<span class='stock-info'>Stok Tersedia: {item[b_col]:.0f} unit</span>", unsafe_allow_html=True)
                        
                        s_o = cat_opts.sort_values('Web')
                        lbls = s_o['Nama Accurate'] + " (Rp " + s_o['Web'].map('{:,.0f}'.format) + " | Stok: " + s_o[b_col].map('{:.0f}'.format) + ")"
                        try: ix = s_o['Nama Accurate'].tolist().index(item['Nama Accurate'])
                        except: ix = 0
                        
                        new_pick = st.selectbox(f"Ganti {cat}:", lbls, index=ix, key=f"sel_{cat}")
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
            for k, v in upd.items(): 
                st.markdown(f"**{k}**")
                st.caption(f"{v['Nama Accurate']}")
                st.write(f"Rp {v['Web']:,.0f} | Stok: {v[b_col]:.0f}")
            if rakit: st.markdown(f"**Biaya Rakit**: `Rp {rakit_fee:,.0f}`")
            st.divider()
            st.subheader(f"Total: Rp {grand_total:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True, type="primary"): st.balloons()
else:
    st.info("👋 Silakan upload file Data Portal (CSV/Excel) untuk memulai sistem bundling pintar.")
