import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import time
from google.oauth2.service_account import Credentials

# --- 1. CẤU HÌNH TRANG ---
st.set_page_config(page_title="LMS - Quản lý học liệu", layout="centered")

# --- 2. KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0"
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_data = gc.sheet1
    sheet_settings = gc.worksheet("Settings")
    settings_raw = sheet_settings.get_all_values()
except Exception as e:
    st.error(f"Lỗi kết nối: {e}")
    st.stop()

# --- 3. ĐỌC CẤU HÌNH TỪ SHEETS ---
def get_conf(r, c, default):
    try: return settings_raw[r][c] if settings_raw[r][c] else default
    except: return default

config = {
    "links": get_conf(0, 1, "").split(","),
    "can_pause": get_conf(1, 1, "FALSE").upper() == "TRUE",
    "interval": int(get_conf(2, 1, 0)),
    "admin_pw": get_conf(3, 1, "Nam2026")
}

# --- 4. HÀM TẢI ÂM THANH (FIX LỖI KHÔNG TIẾNG) ---
def get_audio_b64(url):
    if "drive.google.com" in url:
        try:
            f_id = url.split("/d/")[1].split("/")[0]
            d_url = f"https://drive.google.com/uc?export=download&id={f_id}"
            res = requests.get(d_url)
            return base64.b64encode(res.content).decode()
        except: return None
    return None

# --- 5. GIAO DIỆN TABS (QUAN TRỌNG: PHẦN ADMIN Ở ĐÂY) ---
tab_student, tab_admin = st.tabs(["📖 Học sinh", "⚙️ Quản trị viên"])

# --- PHẦN ADMIN (DÀNH CHO NAM) ---
with tab_admin:
    st.header("Cài đặt hệ thống")
    pwd = st.text_input("Mật khẩu Admin:", type="password")
    
    if pwd == config["admin_pw"]:
        st.success("Chào Nam! Bạn có thể chỉnh sửa hệ thống.")
        
        with st.form("admin_settings"):
            new_links = st.text_area("Danh sách Link Drive (cách nhau dấu phẩy):", value=",".join(config["links"]))
            new_pause = st.checkbox("Cho phép học sinh tạm dừng", value=config["can_pause"])
            new_int = st.number_input("Khoảng cách nghỉ giữa các file (giây):", value=config["interval"])
            
            if st.form_submit_button("Lưu cấu hình xuống Sheets"):
                sheet_settings.update_cell(1, 2, new_links)
                sheet_settings.update_cell(2, 2, str(new_pause).upper())
                sheet_settings.update_cell(3, 2, str(new_int))
                st.toast("Đã lưu!")
                time.sleep(1)
                st.rerun()

        if st.button("🔄 Reset toàn bộ lượt nghe của lớp"):
            recs = sheet_data.get_all_records()
            for i in range(2, len(recs) + 2):
                sheet_data.update_cell(i, 2, "FALSE")
            st.warning("Đã reset danh sách!")
            st.rerun()
    else:
        st.info("Nhập mật khẩu để mở khóa phần quản lý.")

# --- PHẦN HỌC SINH ---
with tab_student:
    st.title("🎧 Bài tập luyện nghe")
    records = sheet_data.get_all_records()
    chua_nghe = [r["HoTen"] for r in records if str(r["DaNghe"]).upper() == "FALSE"]

    if not chua_nghe:
        st.success("🎉 Tất cả học sinh đã hoàn thành bài tập!")
    else:
        name = st.selectbox("Chọn tên của em:", ["-- Chọn tên --"] + chua_nghe)
        if name != "-- Chọn tên --" and st.button("Xác nhận & Bắt đầu"):
            idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
            sheet_data.update_cell(idx, 2, "TRUE")
            st.session_state['user'] = name
            st.rerun()

    if st.session_state.get('user'):
        st.info(f"Đang phát bài cho: {st.session_state['user']}")
        for i, link in enumerate(config["links"]):
            if not link.strip(): continue
            st.write(f"**File {i+1}:**")
            
            with st.spinner(f"Đang tải dữ liệu file {i+1}..."):
                b64 = get_audio_b64(link)
            
            if b64:
                ctrls = "controls" if config["can_pause"] else ""
                components.html(f"""
                    <audio id="a{i}" {ctrls} style="width:100%"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>
                    <button id="b{i}" onclick="document.getElementById('a{i}').play();this.disabled=true;this.innerText='Đang phát...';" 
                    style="width:100%; padding:12px; background:#1a1a1a; color:white; border-radius:5px; cursor:pointer;">▶️ Bấm để nghe</button>
                """, height=100)
                
                if i < len(config["links"]) - 1 and config["interval"] > 0:
                    st.caption(f"Nghỉ {config['interval']} giây...")
                    time.sleep(0.1)
            else:
                st.error(f"Lỗi tải file {i+1}. Kiểm tra link Drive!")
