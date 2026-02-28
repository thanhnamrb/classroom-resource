import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ thống Luyện nghe Chuyên sâu", layout="centered")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0"
    return client.open_by_url(sheet_url)

gc = get_google_sheet()
sheet_data = gc.sheet1
sheet_settings = gc.worksheet("Settings")
settings_raw = sheet_settings.get_all_values()

# Đọc cấu hình
links_raw = settings_raw[0][1] if len(settings_raw) > 0 else ""
links = [l.strip() for l in links_raw.split(",") if l.strip()]
interval = int(settings_raw[2][1]) if len(settings_raw) > 2 else 10
admin_pw = settings_raw[3][1] if len(settings_raw) > 3 else "Nam2026"

def get_audio_b64(url):
    try:
        f_id = url.split("/d/")[1].split("/")[0]
        d_url = f"https://drive.google.com/uc?export=download&id={f_id}"
        res = requests.get(d_url)
        return base64.b64encode(res.content).decode()
    except: return None

# --- GIAO DIỆN ---
tab_student, tab_admin = st.tabs(["📖 Học sinh", "⚙️ Quản lý"])

with tab_admin:
    pwd = st.text_input("Mật khẩu Admin:", type="password")
    if pwd == admin_pw:
        st.success("Chào Nam!")
        if st.button("🔄 Reset lượt nghe cả lớp"):
            recs = sheet_data.get_all_records()
            for i in range(2, len(recs) + 2):
                sheet_data.update_cell(i, 2, "FALSE")
            st.rerun()

with tab_student:
    st.title("🎧 Bài tập nghe tự động")
    records = sheet_data.get_all_records()
    chua_nghe = [r["HoTen"] for r in records if str(r["DaNghe"]).upper() == "FALSE"]

    if not chua_nghe:
        st.success("🎉 Đã hoàn thành bài tập!")
    else:
        name = st.selectbox("Chọn tên của em:", ["-- Chọn tên --"] + chua_nghe)
        if name != "-- Chọn tên --" and st.button("Bắt đầu bài thi"):
            idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
            sheet_data.update_cell(idx, 2, "TRUE")
            st.session_state['user'] = name
            
            # Tải toàn bộ audio trước khi bắt đầu để tránh lag giữa chừng
            with st.spinner("Đang chuẩn bị học liệu..."):
                b64_list = []
                for l in links:
                    b64_list.append(get_audio_b64(l))
                st.session_state['audios'] = b64_list
            st.rerun()

    if st.session_state.get('user') and st.session_state.get('audios'):
        st.info(f"Học sinh: {st.session_state['user']}")
        
        # Chuyển list audio sang định dạng JSON để JavaScript đọc được
        audios_json = json.dumps(st.session_state['audios'])
        
        # --- TRÌNH PHÁT TỰ ĐỘNG KHÔNG THỂ CAN THIỆP ---
        player_html = f"""
        <div style="background:#f0f2f6; padding:20px; border-radius:15px; text-align:center; font-family:sans-serif;">
            <h3 id="status">Sẵn sàng bắt đầu</h3>
            <div style="width:100%; background:#ddd; height:10px; border-radius:5px; margin:15px 0;">
                <div id="progress" style="width:0%; background:#28a745; height:10px; border-radius:5px; transition:width 0.1s;"></div>
            </div>
            <p id="timer">File 1 / {len(links)}</p>
            <button id="startBtn" onclick="startApp()" style="padding:15px 30px; background:#1a1a1a; color:white; border:none; border-radius:8px; cursor:pointer; font-weight:bold;">
                BẮT ĐẦU NGHE NGAY
            </button>
            <audio id="mainAudio"></audio>
        </div>

        <script>
            var audios = {audios_json};
            var interval = {interval};
            var currentIndex = 0;
            var player = document.getElementById('mainAudio');
            var startBtn = document.getElementById('startBtn');
            var statusTxt = document.getElementById('status');
            var progress = document.getElementById('progress');
            var timerTxt = document.getElementById('timer');

            function startApp() {{
                startBtn.style.display = 'none';
                playFile(0);
            }}

            function playFile(index) {{
                if(index >= audios.length) {{
                    statusTxt.innerText = "✅ Đã hoàn thành toàn bộ bài nghe!";
                    progress.style.width = "100%";
                    return;
                }}
                
                currentIndex = index;
                statusTxt.innerText = "🔊 Đang phát File " + (index + 1);
                player.src = "data:audio/mp3;base64," + audios[index];
                player.play();
                
                // Cập nhật thanh tiến trình
                player.ontimeupdate = function() {{
                    var per = (player.currentTime / player.duration) * 100;
                    progress.style.width = per + "%";
                }};

                // Khi nghe xong 1 file
                player.onended = function() {{
                    if(index < audios.length - 1) {{
                        startCooldown(interval, index + 1);
                    }} else {{
                        playFile(index + 1);
                    }}
                }};
            }}

            function startCooldown(seconds, nextIndex) {{
                var timeLeft = seconds;
                statusTxt.innerText = "⏳ Nghỉ giữa hiệp...";
                progress.style.width = "0%";
                
                var countdown = setInterval(function() {{
                    timerTxt.innerText = "Sẽ phát File " + (nextIndex + 1) + " sau: " + timeLeft + "s";
                    timeLeft--;
                    if(timeLeft < 0) {{
                        clearInterval(countdown);
                        timerTxt.innerText = "File " + (nextIndex + 1) + " / " + audios.length;
                        playFile(nextIndex);
                    }}
                }}, 1000);
            }}
        </script>
        """
        components.html(player_html, height=250)
