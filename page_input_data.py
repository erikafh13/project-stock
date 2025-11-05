import streamlit as st
import pandas as pd
import utils # Impor file utilitas Anda

# Definisikan ID folder di sini agar mudah diganti
FOLDER_PENJUALAN = "1Okgw8qHVM8HyBwnTUFHbmYkNKqCcswNZ"
# FOLDER_PORTAL DIHAPUS
FOLDER_PRODUK = "1UdGbFzZ2Wv83YZLNwdU-rgY-LXlczsFv"

def render_page(drive_service, DRIVE_AVAILABLE):
    st.title("📥 Input Data")
    st.markdown("Muat atau muat ulang data yang diperlukan dari Google Drive.")

    if not DRIVE_AVAILABLE:
        st.warning("Tidak dapat melanjutkan karena koneksi ke Google Drive gagal. Periksa log di sidebar.")
        st.stop()

    # --- [BLOK 1: PENJUALAN] ---
    st.header("1. Data Penjualan")
    with st.spinner("Mencari file penjualan..."):
        penjualan_files_list = utils.list_files_in_folder(drive_service, FOLDER_PENJUALAN)
        st.info(f"Ditemukan {len(penjualan_files_list)} file di folder Penjualan.")
        
    if st.button("Muat / Muat Ulang Data Penjualan"):
        if penjualan_files_list: 
            with st.spinner(f"Menggabungkan {len(penjualan_files_list)} file penjualan..."):
                list_of_dfs = [utils.download_and_read(drive_service, f['id'], f['name']) for f in penjualan_files_list]
                df_penjualan = pd.concat(list_of_dfs, ignore_index=True) 
                st.session_state.df_penjualan = df_penjualan
                st.success(f"Data penjualan ({len(penjualan_files_list)} file) berhasil dimuat ulang.")
        else:
            st.warning("⚠️ Tidak ada file penjualan ditemukan di folder Google Drive (Penjualan).")

    if not st.session_state.df_penjualan.empty:
        st.success(f"✅ Data penjualan telah dimuat. ({len(st.session_state.df_penjualan)} baris)")
        st.dataframe(st.session_state.df_penjualan.head())
        excel_data_penjualan = utils.convert_df_to_excel(st.session_state.df_penjualan)
        st.download_button(
            label="📥 Unduh Data Penjualan Gabungan (Excel)",
            data=excel_data_penjualan,
            file_name="data_penjualan_gabungan.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    st.markdown("---")

    # --- [BLOK 2: PRODUK REFERENSI] ---
    st.header("2. Produk Referensi")
    with st.spinner("Mencari file produk di Google Drive..."):
        produk_files_list = utils.list_files_in_folder(drive_service, FOLDER_PRODUK)
    
    selected_produk_file = st.selectbox(
        "Pilih file Produk dari Google Drive (pilih 1 file):",
        options=[None] + produk_files_list,
        format_func=lambda x: x['name'] if x else "Pilih file"
    )
    if selected_produk_file:
        with st.spinner(f"Memuat file {selected_produk_file['name']}..."):
            st.session_state.produk_ref = utils.read_produk_file(drive_service, selected_produk_file['id'])
            st.success(f"File produk referensi '{selected_produk_file['name']}' berhasil dimuat.")
    
    if 'produk_ref' in st.session_state and not st.session_state.produk_ref.empty:
        st.dataframe(st.session_state.produk_ref.head())
    st.markdown("---")

    # --- [BLOK 3: DATA PORTAL] TELAH DIHAPUS ---
