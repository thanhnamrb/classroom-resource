import streamlit as st
import streamlit.components.v1 as components
import gspread
import time
from google.oauth2.service_account import Credentials

# --- 1. CẤU HÌNH TRANG (MẶC ĐỊNH) ---
st.set_page_config(page_title="Hệ thống Luyện nghe English", layout="centered")

# --- 2. KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # Link sheet của bạn
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0"
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_data = gc.sheet1
    sheet_settings = gc.worksheet("Settings")
except Exception as e:
    st.error(f"Lỗi kết nối Sheets: {e}. Vui lòng kiểm tra tab 'Settings' và quyền chia sẻ.")
    st.stop()

# --- 3. ĐỌC CẤU HÌNH AN TOÀN ---
settings_data = sheet_settings.get_all_values()

def get_config_val(row_idx, col_idx, default):
    try:
        val = settings_data[row_idx][col_idx]
        return val if val else default
    except:
        return default

config = {
    "links": get_config_val(0, 1, "").split(","),
    "can_pause": get_config_val(1, 1, "FALSE").upper() == "TRUE",
    "interval": int(get_config_val(2, 1, 0)),
    "admin_pw": get_config_val(3, 1, "Nam2026")
}

# --- 4. HÀM XỬ LÝ LINK DRIVE ---
def get_direct_link(url):
    url = url.strip()
    if "drive.google.com" in url:
        try:
            file_id = url.split("/d/")[1].split("/")[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except:
            return url
    return url

# --- 5. GIAO DIỆN CHÍNH (STREAMLIT NATIVE) ---
st.title("🎧 Hệ thống Luyện nghe")

# Sử dụng Sidebar mặc định cho phần Quản trị để giao diện chính gọn gàng
with st.sidebar:
    st.header("⚙️ Quản trị viên")
    pwd = st.text_input("Nhập mật khẩu:", type="password")
    
    if pwd == config["admin_pw"]:
        st.success("Xác thực thành công!")
        with st.form("settings_form"):
            new_links = st.text_area("Link Drive (cách nhau dấu phẩy):", value=",".join(config["links"]))
            new_pause = st.checkbox("Cho phép tạm dừng", value=config["can_pause"])
            new_int = st.number_input("Khoảng cách nghỉ (giây):", value=config["interval"])
            if st.form_submit_button("Lưu cài đặt"):
                sheet_settings.update_cell(1, 2, new_links)
                sheet_settings.update_cell(2, 2, str(new_pause).upper())
                sheet_settings.update_cell(3, 2, str(new_int))
                st.rerun()
        
        if st.button("🔄 Reset lượt nghe cả lớp"):
            records = sheet_data.get_all_records()
            for i in range(2, len(records) + 2):
                sheet_data.update_cell(i, 2, "FALSE")
            st.warning("Đã reset!")
            st.rerun()
    else:
        st.info("Vui lòng nhập mật khẩu để vào chế độ quản lý.")

# --- 6. GIAO DIỆN HỌC SINH ---
records = sheet_data.get_all_records()
list_chua_nghe = [r["HoTen"] for r in records if str(r["DaNghe"]).upper() == "FALSE"]

if not list_chua_nghe:
    st.success("🎉 Tất cả học sinh đã hoàn thành bài tập!")
else:
    name = st.selectbox("👤 Chọn tên của em:", ["-- Chọn tên --"] + list_chua_nghe)
    
    if name != "-- Chọn tên --":
        if st.button("Xác nhận bắt đầu nghe"):
            idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
            sheet_data.update_cell(idx, 2, "TRUE")
            st.session_state['user_verified'] = name
            st.rerun()

if st.session_state.get('user_verified'):
    st.divider()
    st.subheader(f"Đang phát bài cho: {st.session_state['user_verified']}")
    
    for i, link in enumerate(config["links"]):
        if not link.strip(): continue
        
        st.write(f"**Bài nghe số {i+1}**")
        d_link = get_direct_link(link)
        ctrls = "controls" if config["can_pause"] else ""
        
        audio_html = f"""
            <div style="text-align:center; padding:10px; border:1px solid #ddd; border-radius:5px;">
                <audio id="audio_{i}" {ctrls} style="width:100%;"><source src="{d_link}" type="audio/mp3"></audio>
                <br><br>
                <button id="btn_{i}" onclick="document.getElementById('audio_{i}').play();this.disabled=true;this.innerText='Đang phát...';" 
                    style="width:100%; padding:10px; cursor:pointer;">▶️ Bấm để nghe</button>
            </div>
        """
        components.html(audio_html, height=130)
        
        if i < len(config["links"]) - 1 and config["interval"] > 0:
            st.caption(f"⏱ Nghỉ {config['interval']} giây...")
            time.sleep(0.1)
