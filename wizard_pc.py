import streamlit as st
import pandas as pd
import re

# --- 1. KONFIGURASI & CSS CUSTOM ---
st.set_page_config(page_title="Sistem Bundling PC - Pro", layout="wide")

st.markdown("""
<style>
    .block-container { padding-top: 1.5rem !important; }
    
    .tier-section {
        background-color: #f8f9fa;
        padding: 15px;
        border-radius: 10px;
        margin-bottom: 25px;
        border-left: 5px solid #1E88E5;
    }
    
    .bundle-card {
        border: 1px solid #e1e4e8;
        border-radius: 10px;
        padding: 12px;
        background-color: #ffffff;
        margin-bottom: 12px;
        transition: all 0.2s ease;
        height: 100%;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05);
    }
    .bundle-card:hover {
        box-shadow: 0 5px 15px rgba(0,0,0,0.1);
        border-color: #1E88E5;
        transform: translateY(-3px);
    }
    .price-text {
        color: #1E88E5;
        font-size: 18px;
        font-weight: 800;
        margin: 4px 0;
    }
    .bundle-title {
        color: #2c3e50;
        font-size: 15px;
        font-weight: 700;
        margin-bottom: 4px;
        line-height: 1.2;
        min-height: 36px;
    }
    .badge-stock {
        background-color: #e3f2fd;
        color: #1976d2;
        padding: 1px 8px;
        border-radius: 12px;
        font-size: 9px;
        font-weight: 700;
        margin-bottom: 6px;
        display: inline-block;
        text-transform: uppercase;
    }
    .part-count {
        color: #7f8c8d;
        font-size: 11px;
        margin-bottom: 4px;
    }
    div[data-testid="stExpander"] { margin-bottom: -10px !important; }
    hr { margin: 0.5rem 0 !important; }
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
            # Gaming Advanced: Seri F saja
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

# --- 4. ENGINE REKOMENDASI (STRATEGI PENCARIAN LUAS) ---

def generate_tier_bundles(df, branch_col, usage_cat, target_min, target_max, tier_label):
    available_df = df[(df[branch_col] > 0) & (df[usage_cat] == True)].copy()
    
    # Urutkan processor berdasarkan stok (Push Stock)
    procs = available_df[available_df['Kategori'] == 'Processor'].sort_values(by=[branch_col, 'Web'], ascending=[False, True])
    
    results = []
    # Coba bangun bundel dari setiap processor yang tersedia sampai dapat 3
    for _, pick_proc in procs.iterrows():
        if len(results) >= 3: break
        
        bundle = {'Processor': pick_proc}
        
        # Cari komponen pendukung
        # Prioritas 1: Ambil stok tertinggi yang masuk rentang tier
        # Prioritas 2: Ambil barang apa saja (tetap kompatibel) yang masuk rentang tier
        
        def pick_best_fit(category, current_total, compatibility_func=None):
            items = available_df[available_df['Kategori'] == category]
            if compatibility_func:
                items = items[items.apply(compatibility_func, axis=1)]
            
            if items.empty: return None
            
            # Cari yang membuat total harga mendekati titik tengah tier
            target_piece = (target_min + target_max)/2 - current_total
            # Sort berdasarkan kedekatan dengan target sisa budget per kategori sisa
            items['diff'] = (items['Web'] - (target_piece / 4)).abs() # Dibagi sisa kategori utama
            return items.sort_values(by=[branch_col, 'diff'], ascending=[False, True]).iloc[0]

        # Motherboard
        mobo = pick_best_fit('Motherboard', pick_proc['Web'], lambda m: is_compatible(pick_proc, m))
        if mobo is None: continue
        bundle['Motherboard'] = mobo
        
        # RAM
        mobo_ddr = mobo.get('DDR_Type')
        ram = pick_best_fit('Memory RAM', pick_proc['Web'] + mobo['Web'], lambda r: r.get('DDR_Type') == mobo_ddr)
        if ram is None: continue
        bundle['Memory RAM'] = ram
        
        # SSD & Casing
        for cat in ['SSD Internal', 'Casing PC']:
            current_total = sum(x['Web'] for x in bundle.values())
            item = pick_best_fit(cat, current_total)
            if item is not None: bundle[cat] = item

        # VGA (Kondisional)
        if pick_proc['NeedVGA'] == 1:
            vga = pick_best_fit('VGA', sum(x['Web'] for x in bundle.values()))
            if vga is not None: bundle['VGA'] = vga

        # PSU
        if not (usage_cat == "Office" and bundle.get('Casing PC', {}).get('HasPSU', 0) == 1):
            psu = pick_best_fit('Power Supply', sum(x['Web'] for x in bundle.values()))
            if psu is not None: bundle['Power Supply'] = psu

        # Cooler
        if pick_proc['NeedCooler'] == 1:
            cooler = pick_best_fit('CPU Cooler', sum(x['Web'] for x in bundle.values()))
            if cooler is not None: bundle['CPU Cooler'] = cooler
            
        total = sum(x['Web'] for x in bundle.values())
        
        # Simpan jika masuk rentang
        if target_min <= total <= target_max:
            results.append({
                "name": f"Bundle {tier_label} - Opsi {len(results)+1}", 
                "parts": bundle, 
                "total": total
            })
            
    return results

# --- 5. UI LAYER ---

st.title("🖥️ PC Wizard Pro - Sistem Bundling Pintar")

if 'view' not in st.session_state: st.session_state.view = 'main'
if 'selected_bundle' not in st.session_state: st.session_state.selected_bundle = None

uploaded_file = st.file_uploader("Upload Data Portal", type=["csv", "xlsx"])

if uploaded_file:
    raw_df = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
    data = process_data(raw_df)
    
    st.sidebar.header("⚙️ Filter")
    sel_branch = st.sidebar.selectbox("Pilih Cabang:", list(BRANCH_MAP.keys()))
    b_col = BRANCH_MAP[sel_branch]
    u_cat = st.sidebar.radio("Kategori Kebutuhan:", ["Office", "Gaming Standard / Design 2D", "Gaming Advanced / Design 3D"])

    rel_df = data[(data[u_cat] == True) & (data[b_col] > 0)]
    if rel_df.empty:
        st.error("Stok tidak tersedia di cabang ini.")
    else:
        min_p = rel_df.groupby('Kategori')['Web'].min().sum()
        max_p = rel_df.groupby('Kategori')['Web'].max().sum()
        
        price_range = max_p - min_p
        tier_size = price_range / 3
        
        tiers = [
            {"label": "Economy Quartal", "min": min_p, "max": min_p + tier_size},
            {"label": "Standard Quartal", "min": min_p + tier_size, "max": min_p + (2 * tier_size)},
            {"label": "Premium Quartal", "min": min_p + (2 * tier_size), "max": max_p}
        ]

        if st.session_state.view == 'main':
            st.info(f"📍 Menampilkan rekomendasi untuk {sel_branch} (Rentang: Rp {min_p:,.0f} - Rp {max_p:,.0f})")
            
            # GABUNG JADI SATU TAMPILAN (TANPA TABS)
            for i, t in enumerate(tiers):
                st.markdown(f"""<div class="tier-section"><h3>📊 {t['label']}</h3>
                <small>Estimasi: Rp {t['min']:,.0f} - Rp {t['max']:,.0f}</small></div>""", unsafe_allow_html=True)
                
                recs = generate_tier_bundles(data, b_col, u_cat, t['min'], t['max'], t['label'])
                
                if not recs:
                    st.warning(f"Kombinasi otomatis tidak tersedia di rentang {t['label']}. Silakan sesuaikan rincian manual.")
                else:
                    cols = st.columns(3)
                    for j, res in enumerate(recs):
                        with cols[j]:
                            st.markdown(f"""
                            <div class="bundle-card">
                                <div>
                                    <span class="badge-stock">REKOMENDASI STOK</span>
                                    <div class="bundle-title">{res['name']}</div>
                                    <div class="part-count">{len(res['parts'])} Komponen Included</div>
                                    <div class="price-text">Rp {res['total']:,.0f}</div>
                                </div>
                            </div>
                            """, unsafe_allow_html=True)
                            if st.button(f"Pilih & Sesuaikan", key=f"btn_{i}_{j}", use_container_width=True):
                                st.session_state.selected_bundle = res.copy()
                                if 'temp_parts' in st.session_state: del st.session_state.temp_parts
                                st.session_state.view = 'detail'
                                st.rerun()
                st.markdown("<br>", unsafe_allow_html=True)

        elif st.session_state.view == 'detail':
            bundle = st.session_state.selected_bundle
            if 'temp_parts' not in st.session_state: st.session_state.temp_parts = bundle['parts'].copy()
            upd = st.session_state.temp_parts

            st.button("⬅️ Kembali ke Rekomendasi", on_click=lambda: setattr(st.session_state, 'view', 'main'))
            st.subheader(f"🛠️ Sesuaikan: {bundle['name']}")
            
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
                            labels = cat_options.sort_values('Web')['Nama Accurate'] + " (Rp " + cat_options.sort_values('Web')['Web'].map('{:,.0f}'.format) + ")"
                            try: idx = cat_options.sort_values('Web')['Nama Accurate'].tolist().index(item['Nama Accurate'])
                            except: idx = 0
                            new_pick = st.selectbox(f"Ubah {cat}:", labels, index=idx, key=f"sel_{cat}")
                            new_item = cat_options[cat_options['Nama Accurate'] == new_pick.split(" (Rp ")[0]].iloc[0]
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
                total_items = sum(x['Web'] for x in upd.values())
                grand = total_items + (asm_fee if rakit else 0)
                
                for k, v in upd.items():
                    st.markdown(f"**{k}**: {v['Nama Accurate']}  \n`Rp {v['Web']:,.0f}`")
                
                if rakit: st.markdown(f"**Biaya Rakit**: `Rp {asm_fee:,.0f}`")
                st.divider()
                st.subheader(f"Total: Rp {grand:,.0f}")
                if st.button("✅ Konfirmasi", use_container_width=True, type="primary"): st.balloons()
else:
    st.info("👋 Silakan upload file Data Portal untuk memulai.")
