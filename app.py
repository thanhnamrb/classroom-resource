import streamlit as st
import streamlit.components.v1 as components
import gspread
import time
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống Quản lý Học liệu", layout="centered")
st.markdown("<style>#MainMenu, footer, header {visibility: hidden;} .stApp {background-color: #ffffff;}</style>", unsafe_allow_html=True)

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # THAY LINK SHEETS CỦA BẠN VÀO ĐÂY
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit?gid=0#gid=0"
    return client.open_by_url(sheet_url)

gc = get_google_sheet()
sheet_data = gc.sheet1
sheet_settings = gc.worksheet("Settings")

# --- ĐỌC CẤU HÌNH TỪ SHEETS ---
settings_raw = sheet_settings.get_all_values()
config = {
    "links": settings_raw[0][1].split(","), # Ô B1
    "can_pause": settings_raw[1][1].upper() == "TRUE", # Ô B2
    "interval": int(settings_raw[2][1]), # Ô B3
    "admin_pw": settings_raw[3][1] # Ô B4
}

def get_direct(url):
    if "drive.google.com" in url:
        return f"https://drive.google.com/uc?export=download&id={url.split('/d/')[1].split('/')[0]}"
    return url

# --- GIAO DIỆN CHÍNH ---
t_student, t_admin = st.tabs(["📖 Học sinh", "⚙️ Quản lý"])

with t_student:
    st.title("🎧 Bài tập luyện nghe")
    data_records = sheet_data.get_all_records()
    chua_nghe = [r["HoTen"] for r in data_records if str(r["DaNghe"]).upper() == "FALSE"]

    if not chua_nghe:
        st.success("🎉 Lớp đã hoàn thành bài!")
    else:
        name = st.selectbox("👤 Chọn tên:", ["-- Chọn tên --"] + chua_nghe)
        if name != "-- Chọn tên --" and st.button("Xác nhận bắt đầu"):
            row = [i for i, r in enumerate(data_records) if r["HoTen"] == name][0] + 2
            sheet_data.update_cell(row, 2, "TRUE")
            st.session_state['active_user'] = name
            st.rerun()

    if st.session_state.get('active_user'):
        st.warning(f"Đang phát bài nghe cho: {st.session_state['active_user']}")
        
        for idx, link in enumerate(config["links"]):
            st.write(f"**File nghe số {idx + 1}**")
            direct = get_direct(link.strip())
            
            # Logic khóa nút dừng dựa trên cấu hình
            controls = "controls" if config["can_pause"] else ""
            html_player = f"""
                <div style="text-align: center; margin-bottom: 20px;">
                    <audio id="audio_{idx}" {controls}><source src="{direct}" type="audio/mp3"></audio>
                    <button id="btn_{idx}" onclick="play_{idx}()" style="padding:10px 20px; cursor:pointer;">▶️ Phát file {idx+1}</button>
                </div>
                <script>
                    function play_{idx}() {{
                        var a = document.getElementById('audio_{idx}');
                        var b = document.getElementById('btn_{idx}');
                        a.play();
                        b.disabled = true; b.innerText = 'Đang phát...';
                    }}
                </script>
            """
            components.html(html_player, height=100)
            
            # Khoảng cách giữa các file
            if idx < len(config["links"]) - 1:
                st.info(f"Nghỉ {config['interval']} giây trước file tiếp theo...")
                time.sleep(0.1) # Giả lập để UI không bị treo

with t_admin:
    st.header("Cài đặt hệ thống")
    pw = st.text_input("Mật khẩu Admin:", type="password")
    if pw == config["admin_pw"]:
        st.success("Chào Nam!")
        # Form cập nhật nhanh
        new_links = st.text_area("Danh sách link (cách nhau dấu phẩy):", value=settings_raw[0][1])
        new_pause = st.checkbox("Cho phép học sinh tạm dừng", value=config["can_pause"])
        new_int = st.number_input("Khoảng cách giữa các file (giây):", value=config["interval"])
        
        if st.button("Lưu cấu hình"):
            sheet_settings.update_cell(1, 2, new_links)
            sheet_settings.update_cell(2, 2, str(new_pause).upper())
            sheet_settings.update_cell(3, 2, str(new_int))
            st.toast("Đã lưu!")
