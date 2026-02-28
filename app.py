import streamlit as st
import streamlit.components.v1 as components
import gspread
import time
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="Hệ thống Luyện nghe English", layout="centered")
st.markdown("""
    <style>
    #MainMenu, footer, header {visibility: hidden;}
    .stApp {background-color: #f8f9fa;}
    .stButton>button {width: 100%; border-radius: 10px; height: 3em; background-color: #1a73e8; color: white;}
    </style>
""", unsafe_allow_html=True)

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # Link sheet của bạn đã được cập nhật vào đây
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0"
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_data = gc.sheet1 # Sheet chứa tên học sinh
    sheet_settings = gc.worksheet("Settings") # Sheet cấu hình
except Exception as e:
    st.error(f"Lỗi kết nối Sheets: {e}. Hãy đảm bảo bạn đã tạo tab 'Settings'.")
    st.stop()

# --- ĐỌC CẤU HÌNH (Bản an toàn chống lỗi Index) ---
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

# --- HÀM XỬ LÝ LINK DRIVE ---
def get_direct_link(url):
    url = url.strip()
    if "drive.google.com" in url:
        try:
            file_id = url.split("/d/")[1].split("/")[0]
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        except:
            return url
    return url

# --- GIAO DIỆN TABS ---
tab_student, tab_admin = st.tabs(["📖 Dành cho Học sinh", "⚙️ Quản trị viên"])

# --- 1. GIAO DIỆN HỌC SINH ---
with tab_student:
    st.title("🎧 Bài tập Nghe Tiếng Anh")
    
    records = sheet_data.get_all_records()
    list_chua_nghe = [r["HoTen"] for r in records if str(r["DaNghe"]).upper() == "FALSE"]

    if not list_chua_nghe:
        st.success("🎉 Tuyệt vời! Tất cả các em đã hoàn thành bài tập.")
    else:
        name = st.selectbox("👤 Em hãy chọn đúng tên mình:", ["-- Chọn tên --"] + list_chua_nghe)
        
        if name != "-- Chọn tên --":
            if st.button("Xác nhận và Bắt đầu nghe"):
                # Cập nhật trạng thái đã nghe ngay lập tức
                idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
                sheet_data.update_cell(idx, 2, "TRUE")
                st.session_state['user_verified'] = name
                st.rerun()

    if st.session_state.get('user_verified'):
        st.info(f"Học sinh: **{st.session_state['user_verified']}** đang làm bài.")
        
        for i, link in enumerate(config["links"]):
            if not link.strip(): continue
            
            st.markdown(f"#### 🔈 File nghe số {i+1}")
            d_link = get_direct_link(link)
            ctrls = "controls" if config["can_pause"] else ""
            
            # Trình phát nhạc tùy chỉnh
            audio_html = f"""
                <div style="background:#eee; padding:15px; border-radius:10px; text-align:center;">
                    <audio id="audio_{i}" {ctrls} style="width:100%;">
                        <source src="{d_link}" type="audio/mp3">
                    </audio>
                    <br><br>
                    <button id="btn_{i}" onclick="playAudio({i})" 
                        style="padding:10px 20px; background:#28a745; color:white; border:none; border-radius:5px; cursor:pointer;">
                        ▶️ Bắt đầu nghe File {i+1}
                    </button>
                </div>
                <script>
                    function playAudio(id) {{
                        var player = document.getElementById('audio_' + id);
                        var btn = document.getElementById('btn_' + id);
                        player.play();
                        btn.disabled = true;
                        btn.style.background = '#6c757d';
                        btn.innerText = '🎧 Đang phát...';
                    }}
                </script>
            """
            components.html(audio_html, height=130)
            
            # Khoảng cách nghỉ giữa các file
            if i < len(config["links"]) - 1 and config["interval"] > 0:
                st.caption(f"⏱ Nghỉ {config['interval']} giây trước khi đến file tiếp theo...")
                time.sleep(0.1) 

# --- 2. GIAO DIỆN QUẢN TRỊ ---
with tab_admin:
    st.header("Cài đặt hệ thống")
    pwd = st.text_input("Nhập mật khẩu Admin:", type="password")
    
    if pwd == config["admin_pw"]:
        st.success("Xác thực thành công!")
        
        with st.form("settings_form"):
            new_links = st.text_area("Danh sách Link Drive (cách nhau bằng dấu phẩy):", value=",".join(config["links"]))
            new_pause = st.checkbox("Cho phép học sinh tạm dừng bài nghe", value=config["can_pause"])
            new_int = st.number_input("Khoảng cách nghỉ giữa các file (giây):", value=config["interval"])
            
            if st.form_submit_button("Lưu cấu hình"):
                sheet_settings.update_cell(1, 2, new_links)
                sheet_settings.update_cell(2, 2, str(new_pause).upper())
                sheet_settings.update_cell(3, 2, str(new_int))
                st.toast("Đã lưu cấu hình mới!")
                time.sleep(1)
                st.rerun()
        
        if st.button("🔄 Reset toàn bộ lượt nghe của lớp"):
            for i in range(2, len(records) + 2):
                sheet_data.update_cell(i, 2, "FALSE")
            st.warning("Đã reset danh sách!")
            st.rerun()
