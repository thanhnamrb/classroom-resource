import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ thống Khảo thí Tiếng Anh", layout="centered")

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

# --- ĐỌC CẤU HÌNH SÂU ---
def safe_get(r, default):
    try: return settings_raw[r][1]
    except: return default

config = {
    "links": [l.strip() for l in safe_get(0, "").split(",") if l.strip()],
    "speeds": [float(s.strip()) for s in safe_get(1, "1.0").split(",") if s.strip()],
    "intervals": [int(i.strip()) for i in safe_get(2, "10").split(",") if i.strip()],
    "max_repeats": int(safe_get(3, 1)),
    "deadline": safe_get(4, "2099-12-31 23:59"),
    "admin_pw": safe_get(5, "Nam2026")
}

def get_audio_b64(url):
    try:
        f_id = url.split("/d/")[1].split("/")[0]
        d_url = f"https://drive.google.com/uc?export=download&id={f_id}"
        return base64.b64encode(requests.get(d_url).content).decode()
    except: return None

# --- KIỂM TRA HẠN CHÓT ---
now = datetime.now()
deadline_dt = datetime.strptime(config["deadline"], "%Y-%m-%d %H:%M")
is_expired = now > deadline_dt

# --- GIAO DIỆN TABS ---
tab_student, tab_admin = st.tabs(["📖 Khu vực Học sinh", "🔐 Quản lý Giáo viên"])

with tab_admin:
    pwd = st.text_input("Mật khẩu Admin:", type="password")
    if pwd == config["admin_pw"]:
        st.success("Xác thực thành công!")
        st.write(f"⏰ Hạn chót hiện tại: `{config['deadline']}`")
        if st.button("🔄 Reset toàn bộ lớp (Xóa sạch số lượt nghe)"):
            recs = sheet_data.get_all_records()
            for i in range(2, len(recs) + 2):
                sheet_data.update_cell(i, 2, "0") # Reset lượt nghe về 0
            st.rerun()

with tab_student:
    if is_expired:
        st.error(f"🔴 Đã quá hạn chót truy cập ({config['deadline']}). Vui lòng liên hệ thầy Nam.")
    else:
        st.title("🎧 Bài thi nghe tự động")
        records = sheet_data.get_all_records()
        
        # Lọc học sinh chưa vượt quá số lần nghe cho phép (Cột B lưu số lần đã nghe)
        list_hs = [r["HoTen"] for r in records if int(r["DaNghe"]) < config["max_repeats"]]
        
        if not list_hs:
            st.warning("Hết lượt nghe hoặc danh sách trống.")
        else:
            name = st.selectbox("Chọn đúng tên để bắt đầu:", ["-- Chọn tên --"] + list_hs)
            if name != "-- Chọn tên --" and st.button("Xác nhận & Tải bài"):
                # Cập nhật số lần nghe (+1 vào cột B)
                row_idx = [i for i, r in enumerate(records) if r["HoTen"] == name][0] + 2
                current_count = int(records[row_idx-2]["DaNghe"])
                sheet_data.update_cell(row_idx, 2, str(current_count + 1))
                
                with st.spinner("Đang mã hóa bài thi..."):
                    st.session_state['audios'] = [get_audio_b64(l) for l in config["links"]]
                    st.session_state['active_user'] = name
                st.rerun()

    if st.session_state.get('active_user') and st.session_state.get('audios'):
        # Chuẩn bị dữ liệu cho JS
        js_data = {
            "audios": st.session_state['audios'],
            "speeds": config["speeds"],
            "intervals": config["intervals"],
            "total": len(config['links'])
        }
        
        player_html = f"""
        <div style="background:#1a1a1a; color:white; padding:25px; border-radius:15px; text-align:center; font-family:sans-serif;">
            <h2 id="status">Sẵn sàng bài thi</h2>
            <div style="width:100%; background:#333; height:12px; border-radius:6px; margin:20px 0;">
                <div id="prog" style="width:0%; background:#00ff00; height:12px; border-radius:6px; transition:width 0.1s;"></div>
            </div>
            <p id="info" style="color:#aaa;">File 1 / {js_data['total']}</p>
            <button id="btn" onclick="start()" style="padding:15px 40px; background:#fff; color:#000; border:none; border-radius:30px; cursor:pointer; font-weight:bold; font-size:16px;">▶️ BẮT ĐẦU NGAY</button>
            <audio id="player"></audio>
        </div>

        <script>
            var data = {json.dumps(js_data)};
            var audio = document.getElementById('player');
            var btn = document.getElementById('btn');
            
            function start() {{
                btn.style.display = 'none';
                play(0);
            }}

            function play(idx) {{
                if(idx >= data.audios.length) {{
                    document.getElementById('status').innerText = "✅ HOÀN THÀNH BÀI THI";
                    return;
                }}
                
                document.getElementById('status').innerText = "🔊 Đang phát file " + (idx+1);
                document.getElementById('info').innerText = "Tốc độ: " + (data.speeds[idx] || 1.0) + "x";
                
                audio.src = "data:audio/mp3;base64," + data.audios[idx];
                audio.playbackRate = data.speeds[idx] || 1.0;
                audio.play();

                audio.ontimeupdate = () => {{
                    document.getElementById('prog').style.width = (audio.currentTime/audio.duration)*100 + "%";
                }};

                audio.onended = () => {{
                    if(idx < data.audios.length - 1) {{
                        let wait = data.intervals[idx] || 10;
                        let timer = wait;
                        document.getElementById('status').innerText = "⏳ Nghỉ giữa hiệp...";
                        var cd = setInterval(() => {{
                            document.getElementById('info').innerText = "File kế tiếp trong: " + timer + "s";
                            timer--;
                            if(timer < 0) {{
                                clearInterval(cd);
                                play(idx + 1);
                            }}
                        }}, 1000);
                    }} else {{ play(idx + 1); }}
                }};
            }}
        </script>
        """
        components.html(player_html, height=300)
