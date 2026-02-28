import streamlit as st
import streamlit.components.v1 as components

# --- CẤU HÌNH GIAO DIỆN TỐI GIẢN ---
st.set_page_config(page_title="Hệ thống Học liệu", page_icon="📚")

# CSS ẩn menu, footer của Streamlit và làm giao diện phẳng, tĩnh
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

# --- HÀM 2: TRÌNH PHÁT BẢO MẬT TỐI GIẢN ---
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
                Bắt đầu nghe
            </button>
        </div>

        <script>
            function startMedia() {{
                var media = document.getElementById("myMedia");
                var btn = document.getElementById("playBtn");
                
                media.play();
                btn.disabled = true;
                btn.innerText = "Đang phát...";
                btn.style.backgroundColor = "#e0e0e0";
                btn.style.color = "#666666";
                btn.style.cursor = "not-allowed";
            }}
        </script>
    """
    components.html(html_code, height=450 if media_type=="video" else 100)

# --- KHỞI TẠO BỘ NHỚ TẠM ---
if 'luot_nghe_con_lai' not in st.session_state:
    st.session_state.luot_nghe_con_lai = 3

# --- HIỂN THỊ ---
st.write(f"**Số lượt nghe còn lại:** {st.session_state.luot_nghe_con_lai}/3")

# Thay link Drive của bạn vào đây
link_goc = "https://drive.google.com/file/d/1X2Y3Z_Vi_du_ID_cua_ban_4W5V/view?usp=sharing"
direct_link = get_drive_direct_link(link_goc)

if st.session_state.luot_nghe_con_lai > 0:
    if st.button("Tải dữ liệu bài học"):
        st.session_state.luot_nghe_con_lai -= 1
        st.rerun()

    if 'luot_nghe_con_lai' in st.session_state and st.session_state.luot_nghe_con_lai < 3:
         play_secure_media(direct_link, media_type="audio")
else:
    st.error("Bạn đã hết lượt nghe cho bài tập này.")
