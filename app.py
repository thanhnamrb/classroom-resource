import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="LMS - Hệ thống Luyện Nghe", layout="centered")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # THAY LINK SHEET MỚI CỦA BẠN VÀO ĐÂY
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0" 
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_danh_sach = gc.worksheet("DanhSach")
    sheet_sessions = gc.worksheet("Sessions")
    sheet_lich_su = gc.worksheet("LichSu")
except Exception as e:
    st.error(f"Lỗi: Không tìm thấy các Tab (DanhSach, Sessions, LichSu). Hãy tạo đúng tên tab! Lỗi chi tiết: {e}")
    st.stop()

# --- HÀM TẢI AUDIO TRỰC TIẾP TỪ DRIVE ---
def get_audio_b64(url):
    try:
        f_id = url.split("/d/")[1].split("/")[0]
        d_url = f"https://drive.google.com/uc?export=download&id={f_id}"
        return base64.b64encode(requests.get(d_url).content).decode()
    except: return None

# --- HÀM GHI LỊCH SỬ ---
def update_history(lop, name, session_name):
    records = sheet_lich_su.get_all_records()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i, r in enumerate(records):
        if str(r.get('Lop')) == str(lop) and str(r.get('HoTen')) == str(name) and str(r.get('TenSession')) == str(session_name):
            row_idx = i + 2
            new_count = int(r.get('SoLanNghe', 0)) + 1
            sheet_lich_su.update_cell(row_idx, 4, str(new_count))
            sheet_lich_su.update_cell(row_idx, 5, now_str)
            return new_count
    # Nếu chưa từng nghe, tạo dòng mới
    sheet_lich_su.append_row([lop, name, session_name, "1", now_str])
    return 1

# --- GIAO DIỆN HỌC SINH ---
st.title("🎧 Hệ Thống Làm Bài Nghe")
st.markdown("---")

# 1. Load dữ liệu
ds_records = sheet_danh_sach.get_all_records()
ss_records = sheet_sessions.get_all_records()
ls_records = sheet_lich_su.get_all_records()

if not ds_records or not ss_records:
    st.warning("Hệ thống chưa có dữ liệu Danh sách hoặc Session.")
    st.stop()

# 2. Quy trình Chọn Lớp -> Tên -> Session
col1, col2 = st.columns(2)
with col1:
    list_lop = sorted(list(set([str(r["Lop"]) for r in ds_records])))
    chon_lop = st.selectbox("1. Chọn Lớp:", ["-- Chọn Lớp --"] + list_lop)

with col2:
    if chon_lop != "-- Chọn Lớp --":
        list_ten = [str(r["HoTen"]) for r in ds_records if str(r["Lop"]) == chon_lop]
        chon_ten = st.selectbox("2. Chọn Tên Của Em:", ["-- Chọn Tên --"] + list_ten)
    else:
        chon_ten = st.selectbox("2. Chọn Tên Của Em:", ["-- Chờ chọn Lớp --"], disabled=True)

if chon_ten not in ["-- Chọn Tên --", "-- Chờ chọn Lớp --"]:
    list_ss = [str(r["TenSession"]) for r in ss_records]
    chon_session = st.selectbox("3. Chọn Bài Nghe (Session):", ["-- Chọn Bài --"] + list_ss)

    if chon_session != "-- Chọn Bài --":
        # Lấy luật của Session này
        ss_info = next((item for item in ss_records if str(item["TenSession"]) == chon_session), None)
        
        # Kiểm tra hạn chót
        try:
            deadline = datetime.strptime(str(ss_info["HanChot"]), "%Y-%m-%d %H:%M")
            is_expired = datetime.now() > deadline
        except:
            is_expired = False
            
        # Kiểm tra số lần đã nghe
        lan_da_nghe = 0
        for r in ls_records:
            if str(r.get('Lop')) == chon_lop and str(r.get('HoTen')) == chon_ten and str(r.get('TenSession')) == chon_session:
                lan_da_nghe = int(r.get('SoLanNghe', 0))
                
        max_luot = int(ss_info.get("LuotNgheToiDa", 1))

        if is_expired:
            st.error(f"🔴 Bài nghe này đã đóng lúc {ss_info['HanChot']}.")
        elif lan_da_nghe >= max_luot:
            st.error(f"🚫 Em đã hết lượt nghe bài này ({lan_da_nghe}/{max_luot} lần).")
        else:
            st.info(f"Em còn **{max_luot - lan_da_nghe}** lượt nghe bài này.")
            if st.button("🚀 XÁC NHẬN VÀ BẮT ĐẦU NGHE", use_container_width=True):
                # Ghi lịch sử
                update_history(chon_lop, chon_ten, chon_session)
                
                # Tải audio
                links = [l.strip() for l in str(ss_info["Links"]).split(",") if l.strip()]
                with st.spinner("Đang tải dữ liệu, vui lòng không chuyển trang..."):
                    st.session_state['audios'] = [get_audio_b64(l) for l in links]
                    st.session_state['ss_info'] = ss_info
                    st.session_state['is_playing'] = True
                st.rerun()

# --- KHU VỰC PHÁT NHẠC (RENDER THEO LUẬT CỦA SESSION) ---
if st.session_state.get('is_playing') and st.session_state.get('ss_info'):
    st.divider()
    ss = st.session_state['ss_info']
    audios = st.session_state['audios']
    
    che_do = str(ss.get("CheDo", "AUTO")).upper()
    cho_phep_pause = str(ss.get("ChoPhepPause", "FALSE")).upper() == "TRUE"
    interval = int(ss.get("ThoiGianNghi", 10))
    
    st.subheader(f"📖 Đang làm bài: {ss['TenSession']}")

    if che_do == "MANUAL":
        # CHẾ ĐỘ MANUAL: Hiện danh sách file cho hs tự bấm
        st.write("👉 *Chế độ tự chọn: Em có thể nghe từng file theo ý muốn.*")
        for i, b64 in enumerate(audios):
            st.markdown(f"**🔈 File {i+1}**")
            ctrls = "controls" if cho_phep_pause else ""
            html = f"""
                <div style="background:#f1f3f4; padding:10px; border-radius:8px; margin-bottom:15px; text-align:center;">
                    <audio id="audio_{i}" {ctrls} style="width:100%"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>
                    <br>
                    <button id="btn_{i}" onclick="playManual({i})" style="padding:10px 20px; background:#1a73e8; color:white; border:none; border-radius:5px; cursor:pointer;">▶️ Nghe File {i+1}</button>
                </div>
                <script>
                    function playManual(id) {{
                        var a = document.getElementById('audio_' + id);
                        var b = document.getElementById('btn_' + id);
                        a.play();
                        b.disabled = true; b.innerText = 'Đang phát...';
                    }}
                </script>
            """
            components.html(html, height=120)

    else:
        # CHẾ ĐỘ AUTO: Khóa cứng, chạy liên tục từ đầu đến cuối
        st.write("👉 *Chế độ Tự động: Hệ thống sẽ tự chuyển file. Vui lòng tập trung!*")
        js_data = {"audios": audios, "interval": interval, "pause": cho_phep_pause, "total": len(audios)}
        
        ctrl_attr = "controls" if cho_phep_pause else ""
        
        player_html = f"""
        <div style="background:#1a1a1a; color:white; padding:25px; border-radius:10px; text-align:center; font-family:sans-serif;">
            <h3 id="status">Sẵn sàng</h3>
            <div style="width:100%; background:#444; height:10px; border-radius:5px; margin:15px 0;">
                <div id="prog" style="width:0%; background:#28a745; height:10px; border-radius:5px; transition:width 0.1s;"></div>
            </div>
            <p id="info">Tiến trình: 0 / {js_data['total']}</p>
            <button id="btn" onclick="startAuto()" style="padding:15px 30px; background:#fff; color:#000; font-weight:bold; border-radius:5px; cursor:pointer;">▶️ BẤM VÀO ĐÂY ĐỂ BẮT ĐẦU</button>
            <audio id="player" {ctrl_attr}></audio>
        </div>
        <script>
            var data = {json.dumps(js_data)};
            var player = document.getElementById('player');
            var btn = document.getElementById('btn');
            
            function startAuto() {{ btn.style.display = 'none'; playFile(0); }}

            function playFile(idx) {{
                if(idx >= data.audios.length) {{
                    document.getElementById('status').innerText = "✅ HOÀN THÀNH TOÀN BỘ BÀI NGHE";
                    document.getElementById('info').innerText = "";
                    return;
                }}
                
                document.getElementById('status').innerText = "🔊 Đang phát File " + (idx+1);
                document.getElementById('info').innerText = "Tiến trình: File " + (idx+1) + " / " + data.total;
                
                player.src = "data:audio/mp3;base64," + data.audios[idx];
                player.play();

                player.ontimeupdate = () => {{
                    document.getElementById('prog').style.width = (player.currentTime / player.duration) * 100 + "%";
                }};

                player.onended = () => {{
                    if(idx < data.audios.length - 1) {{
                        let timer = data.interval;
                        document.getElementById('status').innerText = "⏳ Thời gian nghỉ";
                        var cd = setInterval(() => {{
                            document.getElementById('info').innerText = "Chuẩn bị File " + (idx+2) + " sau: " + timer + "s";
                            timer--;
                            if(timer < 0) {{ clearInterval(cd); playFile(idx+1); }}
                        }}, 1000);
                    }} else {{ playFile(idx+1); }}
                }};
            }}
        </script>
        """
        components.html(player_html, height=280)
