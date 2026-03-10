import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="PC Wizard Pro - Marketplace", layout="wide")

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
    
    /* Styling for Detail View */
    .product-row {
        padding: 10px 0;
        border-bottom: 1px solid #eee;
    }
    .placeholder-text {
        color: #95a5a6;
        font-style: italic;
        font-size: 14px;
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
    "Gaming Standard": 150000,
    "Gaming Advanced": 200000
}

PRICE_THRESHOLDS = {
    "Office": {"min": 0, "max": 10000000},
    "Gaming Standard": {"min": 10000000, "max": 20000000},
    "Gaming Advanced": {"min": 20000000, "max": 1000000000}
}

DISPLAY_ORDER = ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'VGA', 'Casing PC', 'Power Supply', 'CPU Cooler']

# --- 2. LOGIKA HELPER ---

def get_cpu_info(name):
    name = name.upper()
    info = {"gen": None, "socket": None}
    intel_match = re.search(r'I[3579]-(\d{4,5})', name)
    if intel_match:
        num = intel_match.group(1)
        gen = int(num[0]) if len(num) == 4 else int(num[:2])
        info["gen"] = gen
        if gen >= 12: info["socket"] = "LGA1700"
        elif gen >= 10: info["socket"] = "LGA1200"
        elif gen >= 8: info["socket"] = "LGA1151"
    elif "ULTRA" in name:
        info["gen"] = "ULTRA"
        info["socket"] = "LGA1851"
    elif "RYZEN" in name:
        ryzen_match = re.search(r'RYZEN\s[3579]\s(\d{4})', name)
        if ryzen_match:
            series = int(ryzen_match.group(1))
            info["socket"] = "AM5" if series >= 7000 else "AM4"
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
    return False

# --- 3. PUSAT LOGIKA PEMROSESAN DATA ---

def process_data(df):
    df.columns = df.columns.str.strip()
    df['Stock_SBY_Combined'] = (df.get('Stock A - ITC', 0).fillna(0) + df.get('Stock B', 0).fillna(0) + df.get('Stock Y - SBY', 0).fillna(0))
    df = df[df['Web'] > 1].copy()
    df = df[df['Stock Total'] >= 0].copy()
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
    
    df['NeedVGA'], df['HasPSU'], df['NeedCooler'] = 0, 0, 0
    df['CPU_Gen'], df['CPU_Socket'], df['Mobo_Series'], df['DDR_Type'] = None, None, None, None
    for col in ['Office', 'Gaming Standard', 'Gaming Advanced']: df[col] = False

    for idx, row in df.iterrows():
        name = row['Nama Accurate'].upper()
        price = row['Web']
        cat = row['Kategori']

        if cat == 'Processor':
            is_f = bool(re.search(r'\d+F\b', name))
            if is_f: df.at[idx, 'NeedVGA'] = 1
            if 'TRAY' in name or 'NO FAN' in name: df.at[idx, 'NeedCooler'] = 1
            info = get_cpu_info(name)
            df.at[idx, 'CPU_Gen'], df.at[idx, 'CPU_Socket'] = info['gen'], info['socket']
            
            # Office: i3 / i5
            if 'I3' in name or 'I5' in name: df.at[idx, 'Office'] = True
            
            # Gaming Standard: i3 / i5 (biasanya butuh VGA diskrit jika suffix F)
            if ('I3' in name or 'I5' in name) and is_f: df.at[idx, 'Gaming Standard'] = True
            
            # Gaming Advanced: i7 / i9 / Ultra atau Ryzen 7 / 9 (Suffix F tidak wajib)
            if (any(x in name for x in ['I7', 'I9', 'ULTRA'])) or ('RYZEN 7' in name or 'RYZEN 9' in name): 
                df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'Motherboard':
            series_list = ['H410','H510','H610','H810','B660','B760','B860','Z790','Z890','A520','A620','B450','B550','B650','B840','B850','X870']
            for s in series_list:
                if s in name: 
                    df.at[idx,'Mobo_Series'] = s
                    break
            df.at[idx,'DDR_Type'] = get_ddr_type(name)
            series = df.at[idx,'Mobo_Series']
            if series in ['H410','H510','H610','H810','A520','A620']: df.at[idx,'Office'] = True
            if (series in ['B660','B760','B860'] and price < 2000000) or (series in ['B450','B550','B650','B840','B850']): df.at[idx,'Gaming Standard'] = True
            if (series in ['B660','B760','B860'] and price >= 2000000) or (series in ['Z790','Z890','B450','B550','B650','B840','B850','X870']): df.at[idx,'Gaming Advanced'] = True
        
        elif cat == 'Memory RAM':
            if 'SODIMM' in name: continue 
            df.at[idx, 'DDR_Type'] = get_ddr_type(name)
            match_gb = re.search(r'(\d+)\s*GB', name)
            if match_gb:
                sz = int(match_gb.group(1))
                if 8 <= sz <= 16: df.at[idx, 'Office'] = True
                if 16 <= sz <= 32: df.at[idx, 'Gaming Standard'] = True
                if 32 <= sz <= 64: df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'SSD Internal':
            if 'WDS120G2G0B' in name: continue 
            df.loc[idx, ['Office', 'Gaming Standard']] = True
            if 'NVME' in name: df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'VGA':
            if any(x in name for x in ['GT710', 'GT730']): 
                df.at[idx, 'Office'] = True
            elif any(x in name for x in ['GT1030', 'GTX1650', 'RTX3050', 'RTX3060', 'RTX5050', 'RTX4060']): 
                df.at[idx, 'Gaming Standard'] = True
            # Gaming Advanced mencakup seri 3070+, 4070+, dan 50-series
            elif any(x in name for x in ['3070', '3080', '3090', '4070', '4080', '4090', 'RTX50']): 
                df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'Casing PC':
            if 'ARMAGGEDDON' in name: continue
            if any(x in name for x in ['PSU', 'OFFICE', 'VALCAS']):
                df.at[idx, 'Office'] = True
                if 'PSU' in name or 'VALCAS' in name: df.at[idx, 'HasPSU'] = 1
            if 300000 <= price <= 600000: df.at[idx, 'Gaming Standard'] = True
            if price > 600000: df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'Power Supply':
            if price < 500000: df.at[idx, 'Office'] = True
            if price >= 500000: df.at[idx, 'Gaming Standard'] = True
            if any(x in name.lower() for x in ['bronze', 'titanium', 'gold', 'platinum', 'silver']): df.at[idx, 'Gaming Advanced'] = True

        elif cat == 'CPU Cooler':
            if price < 300000: df.at[idx, 'Office'] = True
            if 250000 <= price <= 1000000: df.at[idx, 'Gaming Standard'] = True
            if price > 500000: df.at[idx, 'Gaming Advanced'] = True
    return df

# --- 4. ENGINE REKOMENDASI ---

def pick_component(items, strategy, branch_col):
    if items.empty: return None
    if strategy == "Harga Termurah": return items.sort_values(by=['Web', branch_col], ascending=[True, False]).iloc[0]
    elif strategy == "Stok Terbanyak": return items.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]
    elif strategy == "Smart Pick":
        min_p = items['Web'].min()
        pool = items[items['Web'] <= (min_p + 100000)]
        return pool.sort_values(by=[branch_col, 'Web'], ascending=[False, True]).iloc[0]
    return items.iloc[0]

def assemble_bundle(available_df, pick_p, strategy, branch_col, usage_cat):
    bundle = {'Processor': pick_p}
    missing = []
    total = pick_p['Web']
    def get_part(category, filter_func=None):
        items = available_df[(available_df['Kategori'] == category) & (available_df[usage_cat] == True)]
        if filter_func: items = items[items.apply(filter_func, axis=1)]
        return pick_component(items, strategy, branch_col)
    mobo = get_part('Motherboard', lambda m: is_compatible(pick_p, m))
    if mobo is not None:
        bundle['Motherboard'], total = mobo, total + mobo['Web']
    else: missing.append('Motherboard')
    ram = get_part('Memory RAM', lambda r: r.get('DDR_Type') == (mobo.get('DDR_Type') if mobo is not None else None))
    if ram is not None:
        bundle['Memory RAM'], total = ram, total + ram['Web']
    else: missing.append('Memory RAM')
    ssd = get_part('SSD Internal')
    if ssd is not None:
        bundle['SSD Internal'], total = ssd, total + ssd['Web']
    else: missing.append('SSD Internal')
    if pick_p['NeedVGA'] == 1:
        vga = get_part('VGA')
        if vga is not None:
            bundle['VGA'], total = vga, total + vga['Web']
        else: missing.append('VGA')
    case = get_part('Casing PC')
    if case is not None:
        bundle['Casing PC'], total = case, total + case['Web']
    else: missing.append('Casing PC')
    if case is not None and case.get('HasPSU',0) == 0:
        psu = get_part('Power Supply')
        if psu is not None:
            bundle['Power Supply'], total = psu, total + psu['Web']
        else: missing.append('Power Supply')
    if pick_p['NeedCooler'] == 1:
        cooler = get_part('CPU Cooler')
        if cooler is not None:
            bundle['CPU Cooler'], total = cooler, total + cooler['Web']
        else: missing.append('CPU Cooler')
    return {"parts": bundle, "missing": missing, "total": total}
    
def generate_9_bundles(df, branch_col, usage_cat, p_min_user, p_max_user):
    available_df = df.copy() 
    strategies = [{"label": "Stok Terbanyak", "class": "badge-stock"}, {"label": "Harga Termurah", "class": "badge-cheap"}, {"label": "Smart Pick", "class": "badge-smart"}]
    results = []
    cat_min, cat_max = PRICE_THRESHOLDS[usage_cat]['min'], PRICE_THRESHOLDS[usage_cat]['max']

    for strat in strategies:
        procs = available_df[(available_df['Kategori'] == 'Processor') & (available_df[usage_cat] == True)]
        if strat['label'] == "Harga Termurah": sorted_procs = procs.sort_values('Web')
        elif strat['label'] == "Smart Pick": 
            sorted_procs = procs.sample(frac=1).sort_values('Web', ascending=False) if not procs.empty else procs
        else: sorted_procs = procs.sort_values(branch_col, ascending=False)
        
        found_for_strat = 0
        for i in range(len(sorted_procs)):
            if found_for_strat >= 3: break 
            res = assemble_bundle(available_df, sorted_procs.iloc[i], strat['label'], branch_col, usage_cat)
            if res:
                if (cat_min <= res['total'] <= cat_max) and (p_min_user <= res['total'] <= p_max_user):
                    results.append({"strategy": strat['label'], "badge_class": strat['class'], "parts": res['parts'], "total": res['total'], "missing": res['missing']})
                    found_for_strat += 1
    return results

# --- 5. UI LAYER ---

st.title("🛒 PC Wizard Pro")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal (CSV/XLSX)", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)

    st.sidebar.header("⚙️ Konfigurasi")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]
    u_cat = st.sidebar.radio("Kategori Penggunaan:", ["Office", "Gaming Standard", "Gaming Advanced"])

    st.sidebar.markdown("---")
    st.sidebar.subheader("💰 Filter Budget")
    p_min_user = st.sidebar.number_input("Min (Rp)", value=float(PRICE_THRESHOLDS[u_cat]['min']), step=500000.0)
    p_max_user = st.sidebar.number_input("Max (Rp)", value=float(PRICE_THRESHOLDS[u_cat]['max']), step=500000.0)

    if st.session_state.view == 'main':
        st.info(f"📍 Menampilkan 9 Bundling Terbaik untuk **{u_cat}** di {sel_branch}")
        all_res = generate_9_bundles(data, b_col, u_cat, p_min_user, p_max_user)
        
        if not all_res:
            st.warning(f"Tidak ada paket {u_cat} yang ditemukan. Coba luaskan filter budget.")
        else:
            for i in range(0, len(all_res), 3):
                cols = st.columns(3)
                for j in range(3):
                    idx = i + j
                    if idx < len(all_res):
                        res = all_res[idx]
                        with cols[j]:
                            missing_text = ""
                            if res.get("missing"):
                                missing_text = f"<div style='color:#e74c3c;font-size:11px;margin-top:6px;'>⚠ Missing: {', '.join(res['missing'])}</div>"
                            
                            st.markdown(f"""<div class="bundle-card">
<div>
<span class="badge-strategy {res['badge_class']}">{res['strategy']}</span>
<div class="bundle-title">Paket {u_cat} #{idx+1}</div>
<div class="part-count-text">📦 {len(res['parts'])} Komponen</div>
<div class="price-text">Rp {res['total']:,.0f}</div>
<div class="stock-info">Stok Utama: {res['parts']['Processor'][b_col]:.0f} unit</div>
{missing_text}
</div>
</div>""", unsafe_allow_html=True)
                            if st.button(f"Pilih & Detail", key=f"btn_{idx}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                st.session_state.view = 'detail'
                                if 'temp_parts' in st.session_state: del st.session_state.temp_parts
                                st.rerun()
            st.divider()

    elif st.session_state.view == 'detail':
        bundle = st.session_state.selected_bundle
        if 'temp_parts' not in st.session_state: st.session_state.temp_parts = bundle['parts'].copy()
        upd = st.session_state.temp_parts

        st.button("⬅️ Kembali ke Marketplace", on_click=lambda: setattr(st.session_state, 'view', 'main'))
        st.subheader(f"🛠️ Detail Konfigurasi: {bundle['strategy']}")
        
        c_p, c_s = st.columns([2, 1])
        with c_p:
            available_detail = data.copy() 
            for cat in DISPLAY_ORDER:
                is_mandatory = cat in ['Processor', 'Motherboard', 'Memory RAM', 'SSD Internal', 'Casing PC']
                cur_p = upd.get('Processor')
                cur_m = upd.get('Motherboard')
                
                reason = ""
                if cat == 'VGA' and cur_p is not None and cur_p['NeedVGA'] == 0:
                    reason = "Menggunakan Integrated Graphics (Tidak butuh VGA Card)"
                elif cat == 'CPU Cooler' and cur_p is not None and cur_p['NeedCooler'] == 0:
                    reason = "Sudah termasuk Cooler bawaan Processor"
                elif cat == 'Power Supply' and upd.get('Casing PC', {}).get('HasPSU', 0) == 1:
                    reason = "PSU sudah termasuk dalam paket Casing"
                
                st.markdown(f"#### {cat}")
                
                if cat in upd:
                    item = upd[cat]
                    c1, c2, c3 = st.columns([4, 1, 1])
                    with c1:
                        st.markdown(f"**{item['Nama Accurate']}**")
                        st.markdown(f"<span class='stock-info'>Stok: {item[b_col]:.0f} unit | Harga: Rp {item['Web']:,.0f}</span>", unsafe_allow_html=True)
                    with c2:
                        if st.button("🔄 Ubah", key=f"edit_{cat}"):
                            st.session_state[f"show_edit_{cat}"] = True
                    with c3:
                        if not is_mandatory:
                            if st.button("🗑️ Hapus", key=f"del_{cat}"):
                                del upd[cat]
                                st.rerun()

                    if st.session_state.get(f"show_edit_{cat}", False):
                        cat_opts = available_detail[(available_detail['Kategori'] == cat) & (available_detail[u_cat] == True)]
                        if cat == 'Motherboard' and cur_p is not None:
                            cat_opts = cat_opts[cat_opts.apply(lambda m: is_compatible(cur_p, m), axis=1)]
                        if cat == 'Memory RAM' and cur_m is not None:
                            if cur_m.get('DDR_Type'): cat_opts = cat_opts[cat_opts['DDR_Type'] == cur_m.get('DDR_Type')]
                        
                        s_o = cat_opts.sort_values('Web')
                        lbls = s_o['Nama Accurate'] + " (Rp " + s_o['Web'].map('{:,.0f}'.format) + ")"
                        try: ix = s_o['Nama Accurate'].tolist().index(item['Nama Accurate'])
                        except: ix = 0
                        
                        new_pick = st.selectbox(f"Pilih Pengganti {cat}:", lbls, index=ix, key=f"sel_new_{cat}")
                        if st.button("Konfirmasi Perubahan", key=f"conf_{cat}"):
                            new_it = s_o[s_o['Nama Accurate'] == new_pick.split(" (Rp ")[0]].iloc[0]
                            upd[cat] = new_it
                            st.session_state[f"show_edit_{cat}"] = False
                            st.rerun()
                else:
                    if reason: st.markdown(f"<p class='placeholder-text'>ℹ️ {reason}</p>", unsafe_allow_html=True)
                    elif is_mandatory: st.warning(f"Produk {cat} tidak ditemukan di database.")
                    else: st.markdown("<p class='placeholder-text'>Komponen opsional tidak ditambahkan.</p>", unsafe_allow_html=True)
                st.markdown("---")

        with c_s:
            st.markdown("### 📋 Ringkasan")
            for k, v in upd.items(): st.write(f"- {v['Nama Accurate']}")
            
            st.divider()
            current_total = sum(x['Web'] for x in upd.values())
            rakit_fee = ASSEMBLY_FEES.get(u_cat, 100000)
            rakit = st.checkbox(f"Biaya Rakit (Rp {rakit_fee:,.0f})", value=True)
            grand_total = current_total + (rakit_fee if rakit else 0)
            st.subheader(f"Total: Rp {grand_total:,.0f}")
            if st.button("✅ Konfirmasi", use_container_width=True, type="primary"): st.balloons()
else:
    st.info("👋 Silakan upload file Data Portal untuk memulai sistem bundling pintar.")
