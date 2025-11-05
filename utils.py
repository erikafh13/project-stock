import streamlit as st
import pandas as pd
from io import BytesIO
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
import os

# --- KONEKSI GOOGLE DRIVE ---
SCOPES = ['https://www.googleapis.com/auth/drive']

@st.cache_resource
def connect_gdrive():
    DRIVE_AVAILABLE = False
    credentials = None
    try:
        if "gcp_service_account" in st.secrets:
            credentials = service_account.Credentials.from_service_account_info(
                st.secrets["gcp_service_account"], scopes=SCOPES
            )
            st.sidebar.success("Terhubung ke Google Drive.", icon="☁️")
        elif os.path.exists("credentials.json"):
            credentials = service_account.Credentials.from_service_account_file(
                'credentials.json', scopes=SCOPES
            )
            st.sidebar.success("Terhubung ke Google Drive.", icon="💻")
        else:
            st.sidebar.error("Kredensial Google Drive tidak ditemukan.")
            
        if credentials:
            drive_service = build('drive', 'v3', credentials=credentials)
            DRIVE_AVAILABLE = True
            return drive_service, DRIVE_AVAILABLE

    except Exception as e:
        st.sidebar.error(f"Gagal terhubung ke Google Drive.")
        st.error(f"Detail Error: {e}")
        
    return None, False

@st.cache_data(ttl=600)
def list_files_in_folder(_drive_service, folder_id):
    if not _drive_service: return []
    query = f"'{folder_id}' in parents and mimeType != 'application/vnd.google-apps.folder'"
    response = _drive_service.files().list(q=query, fields="files(id, name)").execute()
    return response.get('files', [])

@st.cache_data(ttl=600)
def download_file_from_gdrive(_drive_service, file_id):
    request = _drive_service.files().get_media(fileId=file_id)
    fh = BytesIO()
    downloader = MediaIoBaseDownload(fh, request)
    done = False
    while not done: _, done = downloader.next_chunk()
    fh.seek(0)
    return fh

def download_and_read(_drive_service, file_id, file_name, **kwargs):
    fh = download_file_from_gdrive(_drive_service, file_id)
    return pd.read_csv(fh, **kwargs) if file_name.endswith('.csv') else pd.read_excel(fh, **kwargs)

def read_produk_file(_drive_service, file_id):
    fh = download_file_from_gdrive(_drive_service, file_id)
    df = pd.read_excel(fh, sheet_name="Sheet1 (2)", skiprows=6, usecols=[0, 1, 2, 3])
    df.columns = ['No. Barang', 'BRAND Barang', 'Kategori Barang', 'Nama Barang']
    return df

# --- FUNGSI MAPPING DATA ---
def map_nama_dept(row):
    dept = str(row.get('Dept.', '')).strip().upper()
    pelanggan = str(row.get('Nama Pelanggan', '')).strip().upper()
    if dept == 'A':
        if pelanggan in ['A - CASH', 'AIRPAY INTERNATIONAL INDONESIA', 'TOKOPEDIA']: return 'A - ITC'
        else: return 'A - RETAIL'
    mapping = {'B': 'B - JKT', 'C': 'C - PUSAT', 'D': 'D - SMG','E': 'E - JOG', 'F': 'F - MLG', 'G': 'G - PROJECT','H': 'H - BALI', 'X': 'X'}
    return mapping.get(dept, 'X')

def map_city(nama_dept):
    if nama_dept in ['A - ITC', 'A - RETAIL', 'C - PUSAT', 'G - PROJECT']: return 'Surabaya'
    elif nama_dept == 'B - JKT': return 'Jakarta'
    elif nama_dept == 'D - SMG': return 'Semarang'
    elif nama_dept == 'E - JOG': return 'Jogja'
    elif nama_dept == 'F - MLG': return 'Malang'
    elif nama_dept == 'H - BALI': return 'Bali'
    else: return 'Others'

SHOPEE_SET = {
    'AIRPAY INTERNATIONAL INDONESIA', 'AIRPAY.ID', 'AIRPAY - WD',
    'D - SHOPEE', 'F - SHOPEE', 'E - SHOPEE', 'H - SHOPEE'
}
TOKOPEDIA_SET = {'TOKOPEDIA', 'TOKOPEDIA.ID'}
WEBSITE_SET = {'A - CASH', 'D - CASH', 'H - CASH', 'E - CASH', 'F - CASH', 'B - CASH'}

def map_platform(row):
    pelanggan = str(row.get('Nama Pelanggan', '')).strip().upper()
    if pelanggan in SHOPEE_SET: return 'Shopee'
    if pelanggan in TOKOPEDIA_SET: return 'Tokopedia'
    if pelanggan in WEBSITE_SET: return 'Website'
    return 'Offline'

# --- FUNGSI KONVERSI EXCEL ---
@st.cache_data
def convert_df_to_excel(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='Sheet1')
    processed_data = output.getvalue()
    return processed_data
