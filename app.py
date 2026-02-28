import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH GIAO DIỆN TỐI GIẢN ---
st.set_page_config(page_title="Luyện nghe Toán Tiếng Anh", page_icon="🎧")

# Ẩn các thành phần thừa của Streamlit, giữ background tĩnh, phẳng
hide_st_style = """
    <style>
    #MainMenu {visibility: hidden;} 
    footer {visibility: hidden;} 
    header {visibility: hidden;} 
    .stApp {background-color: #ffffff;}
    </style>
"""
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("🎧 Bài tập nghe: Introduction to Algebra")
st.markdown("---")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    
    # THAY LINK GOOGLE SHEETS CỦA BẠN VÀO ĐÂY
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit?gid=0#gid=0"
    return client.open_by_url(sheet_url).sheet1

sheet = get_google_sheet()
data_records = sheet.get_all_records()

# Lọc những em chưa nghe (Cột DaNghe == "FALSE")
hoc_sinh_chua_nghe = [row["HoTen"] for row in data_records if str(row["DaNghe"]).upper() == "FALSE"]

if not hoc_sinh_chua_nghe:
    st.success("🎉 Tất cả học sinh trong danh sách đã hoàn thành bài tập!")
    st.stop()

# --- HÀM PHÁT NHẠC TRỰC TIẾP ---
def get_drive_direct_link(drive_url):
    if "drive.google.com/file/d/" in drive_url:
        file_id = drive_url.split("/file/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return drive_url 

def play_secure_media(direct_link):
    html_code = f"""
        <div style="text-align: center; margin-top: 10px;">
            <audio id="myMedia"><source src="{direct_link}" type="audio/mp3"></audio>
            <button id="playBtn" onclick="startMedia()" 
                    style="padding: 12px 30px; font-size: 16px; cursor: pointer; background-color: #1a1a1a; color: white; border: none; border-radius: 4px; transition: 0.3s;">
                ▶️ Bắt đầu nghe
            </button>
        </div>
        <script>
            function startMedia() {{
                var media = document.getElementById("myMedia");
                var btn = document.getElementById("playBtn");
                media.play();
                btn.disabled = true;
                btn.innerText = "⏳ Đang phát... Không thể tạm dừng!";
                btn.style.backgroundColor = "#e0e0e0";
                btn.style.color = "#666666";
                btn.style.cursor = "not-allowed";
            }}
        </script>
    """
    components.html(html_code, height=100)

# --- GIAO DIỆN CHỌN TÊN ---
st.write("Vui lòng chọn tên để bắt đầu. **Lưu ý: Chỉ được nghe 1 lần duy nhất.**")

chon_ten = st.selectbox("👤 Chọn tên:", ["-- Chọn tên --"] + hoc_sinh_chua_nghe)

# THAY LINK DRIVE CHỨA FILE AUDIO CỦA BẠN VÀO ĐÂY
link_goc_drive = ""
direct_link = get_drive_direct_link(link_goc_drive)

# --- XỬ LÝ LOGIC TRỪ LƯỢT VĨNH VIỄN ---
if chon_ten != "-- Chọn tên --" and st.button("Xác nhận & Tải bài nghe"):
    hs_info = next((item for item in data_records if item["HoTen"] == chon_ten), None)
    
    if hs_info:
        # Vị trí dòng = index của list + 2 (do dòng 1 là tiêu đề trên Sheets)
        row_index = data_records.index(hs_info) + 2 
        
        # Cập nhật cột số 2 (DaNghe) thành TRUE
        sheet.update_cell(row_index, 2, "TRUE")
        
        # Cấp quyền cho giao diện hiện tại
        st.session_state['duoc_nghe'] = True
        st.rerun()

# --- HIỂN THỊ KHỐI ÂM THANH SAU KHI XÁC NHẬN ---
if st.session_state.get('duoc_nghe', False):
    st.info("⚠️ Đã tải dữ liệu. Tuyệt đối không tải lại trang (F5) để tránh mất quyền nghe!")
    play_secure_media(direct_link)
