import streamlit as st
import streamlit.components.v1 as components
import gspread
from google.oauth2.service_account import Credentials

# --- CẤU HÌNH GIAO DIỆN ---
st.set_page_config(page_title="LMS - Quản lý học liệu", page_icon="⚙️")
hide_st_style = """<style>#MainMenu {visibility: hidden;} footer {visibility: hidden;} header {visibility: hidden;}</style>"""
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit?gid=0#gid=0"
    return client.open_by_url(sheet_url)

gc = get_google_sheet()
sheet_data = gc.sheet1 # Sheet chứa danh sách HS
sheet_settings = gc.worksheet("Settings") # Sheet chứa link bài học

# --- HÀM TRỢ GIÚP ---
def get_drive_direct_link(drive_url):
    if "drive.google.com/file/d/" in drive_url:
        file_id = drive_url.split("/file/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return drive_url 

# --- GIAO DIỆN CHÍNH ---
tab_student, tab_admin = st.tabs(["📖 Học sinh", "🔐 Quản lý"])

# --- PHẦN 1: GIAO DIỆN HỌC SINH ---
with tab_student:
    st.title("🎧 Bài tập luyện nghe")
    data_records = sheet_data.get_all_records()
    link_bai_hoc = sheet_settings.cell(2, 2).value # Lấy link từ ô B2 của sheet Settings
    
    hoc_sinh_chua_nghe = [row["HoTen"] for row in data_records if str(row["DaNghe"]).upper() == "FALSE"]

    if not hoc_sinh_chua_nghe:
        st.success("🎉 Cả lớp đã hoàn thành bài tập!")
    else:
        chon_ten = st.selectbox("👤 Chọn tên em:", ["-- Chọn tên --"] + hoc_sinh_chua_nghe)
        if chon_ten != "-- Chọn tên --" and st.button("Xác nhận & Tải bài nghe"):
            hs_info = next((item for item in data_records if item["HoTen"] == chon_ten), None)
            row_index = data_records.index(hs_info) + 2 
            sheet_data.update_cell(row_index, 2, "TRUE")
            st.session_state['duoc_nghe'] = True
            st.rerun()

    if st.session_state.get('duoc_nghe', False):
        direct_link = get_drive_direct_link(link_bai_hoc)
        html_code = f"""
            <div style="text-align: center;"><audio id="m"><source src="{direct_link}" type="audio/mp3"></audio>
            <button onclick="document.getElementById('m').play();this.disabled=true;this.innerText='Đang phát...'" 
            style="padding:15px;background:#1a1a1a;color:white;border:none;border-radius:5px;cursor:pointer;">▶️ Bắt đầu nghe</button></div>
        """
        components.html(html_code, height=100)

# --- PHẦN 2: GIAO DIỆN QUẢN LÝ (CHO NAM) ---
with tab_admin:
    st.header("Cài đặt hệ thống")
    password = st.text_input("Nhập mật khẩu Admin:", type="password")
    
    if password == "Nam2026": # Bạn có thể đổi mật khẩu ở đây
        st.success("Chào Nam! Bạn có quyền chỉnh sửa.")
        
        # 1. Cài đặt link bài học
        new_link = st.text_input("Dán link Google Drive mới vào đây:", value=link_bai_hoc)
        if st.button("Cập nhật bài học"):
            sheet_settings.update_cell(2, 2, new_link)
            st.toast("Đã cập nhật link mới thành công!")
            
        # 2. Reset danh sách lớp
        if st.button("🔄 Đặt lại lượt nghe (Reset cả lớp)"):
            for i in range(2, len(data_records) + 2):
                sheet_data.update_cell(i, 2, "FALSE")
            st.warning("Đã reset toàn bộ danh sách về chưa nghe.")
