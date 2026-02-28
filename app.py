import streamlit as st
import streamlit.components.v1 as components
import json
import os

# --- CẤU HÌNH GIAO DIỆN TỐI GIẢN ---
st.set_page_config(page_title="Luyện nghe Tiếng Anh", page_icon="🎧")

hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            .stApp {background-color: #ffffff;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

st.title("🎧 Bài tập luyện nghe")
st.markdown("---")

# --- HÀM 1: CHUYỂN ĐỔI LINK GOOGLE DRIVE ---
def get_drive_direct_link(drive_url):
    if "drive.google.com/file/d/" in drive_url:
        file_id = drive_url.split("/file/d/")[1].split("/")[0]
        return f"https://drive.google.com/uc?export=download&id={file_id}"
    return drive_url 

# --- HÀM 2: TRÌNH PHÁT BẢO MẬT ---
def play_secure_media(direct_link, media_type="audio"):
    if media_type == "video":
        media_tag = f"""
            <video id="myMedia" width="100%" style="pointer-events: none; border-radius: 8px;" oncontextmenu="return false;">
                <source src="{direct_link}" type="video/mp4">
            </video>
        """
    else:
        media_tag = f"""
            <audio id="myMedia">
                <source src="{direct_link}" type="audio/mp3">
            </audio>
        """

    html_code = f"""
        <div style="text-align: center; margin-top: 10px;">
            {media_tag}
            <br>
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
    components.html(html_code, height=450 if media_type=="video" else 100)

# --- QUẢN LÝ DANH SÁCH HỌC SINH (FILE JSON CHUNG) ---
DB_FILE = "danh_sach.json"
# Bạn điền tên học sinh của lớp vào danh sách này:
DANH_SACH_GOC = ["Nguyễn Thành Nam", "Trần Thị B", "Lê Văn C", "Phạm Văn D"]

def load_data():
    # Nếu file chưa tồn tại (lần chạy đầu tiên), tạo mới danh sách với trạng thái False (chưa nghe)
    if not os.path.exists(DB_FILE):
        data = {ten: False for ten in DANH_SACH_GOC}
        with open(DB_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
        return data
    # Nếu file đã có, đọc dữ liệu ra
    with open(DB_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data):
    # Lưu lại trạng thái mới nhất vào file
    with open(DB_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)

data = load_data()

# Lọc ra những học sinh có trạng thái là False (chưa nghe)
hoc_sinh_chua_nghe = [ten for ten, da_nghe in data.items() if not da_nghe]

if len(hoc_sinh_chua_nghe) == 0:
    st.success("🎉 Tất cả học sinh trong lớp đã hoàn thành bài nghe!")
    st.stop() # Dừng vẽ giao diện phía dưới

# --- GIAO DIỆN CHỌN TÊN ---
st.write("Vui lòng chọn tên của em. **Lưu ý: Mỗi người chỉ được nghe 1 lần duy nhất.**")
chon_ten = st.selectbox("👤 Chọn tên:", ["-- Chọn tên --"] + hoc_sinh_chua_nghe)

link_goc = "https://drive.google.com/file/d/1X2Y3Z_Vi_du_ID_cua_ban_4W5V/view?usp=sharing"
direct_link = get_drive_direct_link(link_goc)

# Xử lý logic khi bấm nút
if chon_ten != "-- Chọn tên --":
    if st.button("Xác nhận & Tải bài nghe"):
        # 1. Cập nhật trạng thái thành True (Đã nghe) và lưu lại vào file JSON
        data[chon_ten] = True
        save_data(data)
        
        # 2. Cấp quyền hiển thị Audio cho phiên làm việc hiện tại
        st.session_state['duoc_nghe'] = True
        st.rerun() # Tải lại trang ngay lập tức để tên biến mất khỏi Dropdown

# Chỉ hiển thị khối phát nhạc nếu đã được cấp quyền
if st.session_state.get('duoc_nghe', False):
    st.info("⚠️ Đã tải dữ liệu thành công. Tuyệt đối không tải lại trang (F5) để tránh mất quyền nghe!")
    play_secure_media(direct_link, media_type="audio")
