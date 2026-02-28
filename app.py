import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import io
import base64
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ thống Luyện nghe", layout="centered")

@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0"
    return client.open_by_url(sheet_url)

# Đọc cấu hình từ Sheets
try:
    gc = get_google_sheet()
    sheet_data = gc.sheet1
    sheet_settings = gc.worksheet("Settings")
    settings_raw = sheet_settings.get_all_values()
    
    links_raw = settings_raw[0][1] if len(settings_raw) > 0 else ""
    can_pause = (settings_raw[1][1].upper() == "TRUE") if len(settings_raw) > 1 else False
    links = [l.strip() for l in links_raw.split(",") if l.strip()]
except:
    st.error("Lỗi: Kiểm tra tab 'Settings' hoặc quyền chia sẻ Sheets!")
    st.stop()

def get_audio_base64(url):
    """Tải file từ Drive và chuyển sang Base64 để phát chắc chắn 100%"""
    if "drive.google.com" in url:
        file_id = url.split("/d/")[1].split("/")[0] if "/d/" in url else ""
        direct_url = f"https://drive.google.com/uc?export=download&id={file_id}"
        try:
            response = requests.get(direct_url)
            return base64.b64encode(response.content).decode()
        except:
            return None
    return None

st.title("🎧 Bài Tập Luyện Nghe")

# Logic chọn tên học sinh (Giữ nguyên)
records = sheet_data.get_all_records()
chua_nghe = [r["HoTen"] for r in records if str(r["DaNghe"]).upper() == "FALSE"]

if not chua_nghe:
    st.success("🎉 Đã hoàn thành bài tập!")
else:
    name = st.selectbox("Chọn đúng tên của em:", ["-- Chọn tên --"] + chua_nghe)
    if name != "-- Chọn tên --" and st.button("Xác nhận & Nghe bài"):
        idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
        sheet_data.update_cell(idx, 2, "TRUE")
        st.session_state['user'] = name
        st.rerun()

if st.session_state.get('user'):
    st.info(f"Đang phát bài cho: {st.session_state['user']}")
    for i, link in enumerate(links):
        with st.spinner(f"Đang tải file {i+1}..."):
            b64_data = get_audio_base64(link)
            
        if b64_data:
            ctrls = "controls" if can_pause else ""
            st.markdown(f"**Bài nghe {i+1}:**")
            components.html(f"""
                <audio id="a{i}" {ctrls} style="width:100%">
                    <source src="data:audio/mp3;base64,{b64_data}" type="audio/mp3">
                </audio>
                <button id="b{i}" onclick="document.getElementById('a{i}').play();this.disabled=true;this.innerText='Đang phát...';" 
                style="width:100%; padding:12px; background:#1a1a1a; color:white; border-radius:5px; cursor:pointer;">▶️ Bấm để nghe</button>
            """, height=100)
        else:
            st.error(f"Không thể tải file {i+1}. Hãy kiểm tra lại link Drive!")
