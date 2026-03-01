import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
import time
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ thống Luyện Nghe Tiếng Anh", layout="centered", page_icon="🎧")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0" 
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_danh_sach = gc.worksheet("DanhSach")
    sheet_sessions = gc.worksheet("Sessions")
    sheet_lich_su = gc.worksheet("LichSu")
except Exception as e:
    st.error(f"Lỗi: Không tìm thấy các Tab. {e}")
    st.stop()

def get_audio_b64(url):
    try:
        f_id = url.split("/d/")[1].split("/")[0]
        d_url = f"https://drive.google.com/uc?export=download&id={f_id}"
        return base64.b64encode(requests.get(d_url).content).decode()
    except: return None

def update_history(lop, name, session_name):
    records = sheet_lich_su.get_all_records()
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for i, r in enumerate(records):
        if str(r.get('Lop')) == str(lop) and str(r.get('HoTen')) == str(name) and str(r.get('TenSession')) == str(session_name):
            sheet_lich_su.update_cell(i + 2, 4, str(int(r.get('SoLanNghe', 0)) + 1))
            sheet_lich_su.update_cell(i + 2, 5, now_str)
            return
    sheet_lich_su.append_row([lop, name, session_name, "1", now_str])

def sync_data(sheet, records, headers):
    sheet.clear()
    if records:
        sheet.update(values=[headers] + [[r.get(h, "") for h in headers] for r in records], range_name="A1")
    else:
        sheet.update(values=[headers], range_name="A1")

ds_records = sheet_danh_sach.get_all_records()
ss_records = sheet_sessions.get_all_records()
ls_records = sheet_lich_su.get_all_records()

# ==========================================================
# KHU VỰC 1: GIAO DIỆN HỌC SINH 
# ==========================================================
st.title("🎧 Hệ Thống Làm Bài Nghe")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    list_lop = sorted(list(set([str(r.get("Lop", "")) for r in ds_records if r.get("Lop")])))
    chon_lop = st.selectbox("1. Chọn Lớp:", ["-- Chọn Lớp --"] + list_lop)

with col2:
    if chon_lop != "-- Chọn Lớp --":
        list_ten = [str(r["HoTen"]) for r in ds_records if str(r.get("Lop")) == chon_lop]
        chon_ten = st.selectbox("2. Chọn Tên Của Em:", ["-- Chọn Tên --"] + list_ten)
    else:
        chon_ten = st.selectbox("2. Chọn Tên Của Em:", ["-- Chờ chọn Lớp --"], disabled=True)

if chon_ten not in ["-- Chọn Tên --", "-- Chờ chọn Lớp --"]:
    list_ss = [str(r["TenSession"]) for r in ss_records if r.get("TenSession")]
    chon_session = st.selectbox("3. Chọn Bài Nghe (Session):", ["-- Chọn Bài --"] + list_ss)

    if chon_session != "-- Chọn Bài --":
        ss_info = next((item for item in ss_records if str(item.get("TenSession")) == chon_session), None)
        try:
            deadline = datetime.strptime(str(ss_info.get("HanChot", "2099-12-31 23:59")), "%Y-%m-%d %H:%M")
            is_expired = datetime.now() > deadline
        except: is_expired = False
            
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
                update_history(chon_lop, chon_ten, chon_session)
                links = [l.strip() for l in str(ss_info.get("Links", "")).split(",") if l.strip()]
                with st.spinner("Đang tải và mã hóa dữ liệu..."):
                    st.session_state['audios'] = [get_audio_b64(l) for l in links]
                    st.session_state['ss_info'] = ss_info
                    st.session_state['is_playing'] = True
                st.rerun()

# --- TRÌNH PHÁT NHẠC CUSTOM KHÔNG DÙNG NATIVE PLAYER ---
if st.session_state.get('is_playing') and st.session_state.get('ss_info'):
    st.divider()
    ss = st.session_state['ss_info']
    audios = st.session_state['audios']
    che_do = str(ss.get("CheDo", "AUTO")).upper()
    cho_phep_pause = str(ss.get("ChoPhepPause", "FALSE")).upper() == "TRUE"
    interval = int(ss.get("ThoiGianNghi", 10))
    toc_do = float(ss.get("TocDo", 1.0)) # Đọc tốc độ từ Sheets
    
    st.subheader(f"📖 Đang làm bài: {ss['TenSession']}")

    if che_do == "MANUAL":
        st.write("👉 *Chế độ tự chọn: Em có thể nghe từng file theo ý muốn.*")
        for i, b64 in enumerate(audios):
            if not b64: continue
            st.markdown(f"**🔈 File {i+1}**")
            
            # GIAO DIỆN CUSTOM PLAYER CHO MANUAL
            html = f"""
                <div style="background:#202124; padding:20px; border-radius:12px; margin-bottom:15px; text-align:center; color:white; font-family:sans-serif;">
                    <audio id="audio_{i}" style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>
                    
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:14px; color:#9aa0a6;">
                        <span id="time_{i}">00:00 / 00:00</span>
                        <span>Đang khóa tua</span>
                    </div>
                    
                    <div style="width:100%; background:#3c4043; height:8px; border-radius:4px; margin-bottom:15px; position:relative;">
                        <div id="prog_{i}" style="width:0%; background:#8ab4f8; height:8px; border-radius:4px; position:absolute; top:0; left:0;"></div>
                    </div>
                    
                    <button id="btn_{i}" onclick="playManual({i})" style="padding:12px 25px; background:#8ab4f8; color:#202124; border:none; border-radius:6px; cursor:pointer; font-weight:bold; letter-spacing:0.5px;">▶️ NGHE FILE {i+1}</button>
                </div>
                
                <script>
                    function formatTime(secs) {{
                        if (isNaN(secs)) return "00:00";
                        var m = Math.floor(secs / 60); var s = Math.floor(secs % 60);
                        return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
                    }}
                    function playManual(id) {{
                        var a = document.getElementById('audio_' + id);
                        var b = document.getElementById('btn_' + id);
                        var p = document.getElementById('prog_' + id);
                        var t = document.getElementById('time_' + id);
                        
                        a.playbackRate = {toc_do}; // Ép tốc độ
                        a.play();
                        b.disabled = true; b.innerText = '🎧 ĐANG PHÁT...'; b.style.background = '#5f6368';
                        
                        a.ontimeupdate = function() {{
                            p.style.width = (a.currentTime / a.duration) * 100 + "%";
                            t.innerText = formatTime(a.currentTime) + " / " + formatTime(a.duration);
                        }};
                    }}
                </script>
            """
            components.html(html, height=170)

    else:
        st.write("👉 *Chế độ Tự động: Hệ thống sẽ tự chuyển file. Vui lòng tập trung!*")
        js_data = {"audios": audios, "interval": interval, "pause": cho_phep_pause, "speed": toc_do, "total": len([a for a in audios if a])}
        
        # GIAO DIỆN CUSTOM PLAYER CHO AUTO
        components.html(f"""
        <div style="background:#202124; color:white; padding:30px; border-radius:12px; text-align:center; font-family:sans-serif; box-shadow: 0 4px 6px rgba(0,0,0,0.1);">
            <h3 id="status" style="margin-top:0; color:#8ab4f8;">Sẵn sàng</h3>
            
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:14px; color:#9aa0a6;">
                <span id="timer_txt">00:00 / 00:00</span>
                <span id="info">Tiến trình: 0 / {js_data['total']}</span>
            </div>
            
            <div style="width:100%; background:#3c4043; height:10px; border-radius:5px; margin-bottom:25px; position:relative; overflow:hidden;">
                <div id="prog" style="width:0%; background:#34a853; height:10px; border-radius:5px; position:absolute; top:0; left:0; transition: width 0.1s linear;"></div>
            </div>
            
            <button id="btn" onclick="startAuto()" style="padding:15px 35px; background:#e8eaed; color:#202124; font-weight:bold; font-size:16px; border:none; border-radius:8px; cursor:pointer; letter-spacing:1px; box-shadow: 0 2px 4px rgba(0,0,0,0.2);">▶️ BẤM VÀO ĐÂY ĐỂ BẮT ĐẦU</button>
            <audio id="player" style="display:none;"></audio>
        </div>
        
        <script>
            var data = {json.dumps(js_data)}; 
            var player = document.getElementById('player'); 
            var btn = document.getElementById('btn');
            
            function formatTime(secs) {{
                if (isNaN(secs)) return "00:00";
                var m = Math.floor(secs / 60); var s = Math.floor(secs % 60);
                return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
            }}

            function startAuto() {{ btn.style.display = 'none'; playFile(0); }}
            
            function playFile(idx) {{
                if(idx >= data.audios.length) {{ 
                    document.getElementById('status').innerText = "✅ HOÀN THÀNH TOÀN BỘ BÀI NGHE"; 
                    document.getElementById('info').innerText = ""; 
                    document.getElementById('timer_txt').innerText = "";
                    return; 
                }}
                if(!data.audios[idx]) {{ playFile(idx+1); return; }}
                
                document.getElementById('status').innerText = "🔊 Đang phát File " + (idx+1);
                document.getElementById('info').innerText = "Tiến trình: File " + (idx+1) + " / " + data.total;
                
                player.src = "data:audio/mp3;base64," + data.audios[idx];
                player.playbackRate = data.speed; // Ép tốc độ từ giáo viên
                player.play();
                
                player.ontimeupdate = () => {{ 
                    document.getElementById('prog').style.width = (player.currentTime / player.duration) * 100 + "%"; 
                    document.getElementById('timer_txt').innerText = formatTime(player.currentTime) + " / " + formatTime(player.duration);
                }};
                
                player.onended = () => {{
                    if(idx < data.audios.length - 1) {{
                        let timer = data.interval; 
                        document.getElementById('status').innerText = "⏳ Thời gian nghỉ";
                        document.getElementById('status').style.color = "#fbbc04";
                        
                        var cd = setInterval(() => {{
                            document.getElementById('timer_txt').innerText = "Chuyển tiếp sau: " + timer + "s";
                            timer--;
                            if(timer < 0) {{ 
                                clearInterval(cd); 
                                document.getElementById('status').style.color = "#8ab4f8";
                                playFile(idx+1); 
                            }}
                        }}, 1000);
                    }} else {{ playFile(idx+1); }}
                }};
            }}
        </script>
        """, height=250)

# ==========================================================
# KHU VỰC 2: APP QUẢN TRỊ DÀNH CHO GIÁO VIÊN
# ==========================================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
with st.expander("🔐 Trạm Quản Trị Giáo Viên", expanded=False):
    pwd = st.text_input("Nhập mã truy cập:", type="password")
    
    if pwd == "Nam2026":
        st.success("Đăng nhập thành công! Chào mừng thầy Nam.")
        
        tab_tao, tab_lop, tab_rp = st.tabs(["📝 Soạn Bài (Sessions)", "👥 Quản Lý Học Sinh", "📊 Báo Cáo & Xóa Lượt"])
        
        with tab_tao:
            st.subheader("Tạo phiên nghe mới")
            with st.form("form_session"):
                s_name = st.text_input("Tên Bài Nghe (Session Name):")
                s_links = st.text_area("Link Google Drive (Cách nhau dấu phẩy):")
                
                c1, c2, c_spd = st.columns(3)
                s_mode = c1.selectbox("Chế độ phát:", ["AUTO (Chạy hết)", "MANUAL (Tự bấm)"])
                s_pause = c2.checkbox("Cho phép tạm dừng", value=False)
                s_speed = c_spd.number_input("Tốc độ phát (VD: 0.8, 1.2):", value=1.0, step=0.1) # Thêm cột Tốc độ
                
                c3, c4, c5 = st.columns(3)
                s_interval = c3.number_input("Giây nghỉ (AUTO):", min_value=0, value=10)
                s_limit = c4.number_input("Lượt nghe tối đa:", min_value=1, value=1)
                s_deadline = c5.text_input("Hạn chót (YYYY-MM-DD HH:MM):", value="2026-12-31 23:59")
                
                if st.form_submit_button("➕ Thêm Bài Nghe Này"):
                    if s_name and s_links:
                        new_ss = {"TenSession": s_name, "Links": s_links, "CheDo": s_mode.split()[0], "ChoPhepPause": str(s_pause), "ThoiGianNghi": s_interval, "LuotNgheToiDa": s_limit, "HanChot": s_deadline, "TocDo": s_speed}
                        ss_records.append(new_ss)
                        sync_data(sheet_sessions, ss_records, ["TenSession", "Links", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot", "TocDo"])
                        st.success("Đã tạo thành công!")
                        time.sleep(1)
                        st.rerun()
                    else: st.error("Vui lòng điền đủ tên bài và link!")
            
            st.divider()
            st.write("**Các bài nghe đang hoạt động:**")
            for ss in ss_records:
                with st.container():
                    colA, colB = st.columns([4, 1])
                    colA.markdown(f"**{ss.get('TenSession')}** - Chế độ: `{ss.get('CheDo')}` - Tốc độ: `{ss.get('TocDo', 1.0)}x`")
                    if colB.button("🗑️ Xóa", key=f"del_{ss.get('TenSession')}"):
                        ss_records = [r for r in ss_records if r.get('TenSession') != ss.get('TenSession')]
                        sync_data(sheet_sessions, ss_records, ["TenSession", "Links", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot", "TocDo"])
                        st.rerun()

        with tab_lop:
            st.write("**Thêm nhanh nhiều học sinh (Bulk Add):**")
            bulk_lop = st.text_input("Lớp sẽ được thêm vào:")
            bulk_names = st.text_area("Dán danh sách tên (Mỗi người 1 dòng):")
            if st.button("Tải danh sách lên"):
                names = [n.strip() for n in bulk_names.split("\n") if n.strip()]
                for n in names: ds_records.append({"Lop": bulk_lop, "HoTen": n})
                sync_data(sheet_danh_sach, ds_records, ["Lop", "HoTen"])
                st.success(f"Đã thêm {len(names)} học sinh!")
                time.sleep(1)
                st.rerun()

        with tab_rp:
            st.dataframe(ls_records, use_container_width=True)
            st.divider()
            st.subheader("🛠️ Cấp lại quyền thi (Reset lượt)")
            c_lop = st.selectbox("Chọn Lớp:", [""] + list_lop, key="rs_lop")
            if c_lop:
                list_rs_ten = [str(r["HoTen"]) for r in ds_records if str(r.get("Lop")) == c_lop]
                c_ten = st.selectbox("Chọn Học Sinh:", [""] + list_rs_ten, key="rs_ten")
                if c_ten:
                    c_bai = st.selectbox("Chọn Bài Cần Hủy Lượt:", [""] + [str(r["TenSession"]) for r in ss_records], key="rs_bai")
                    if c_bai and st.button("🚨 Hủy lượt bài này", type="primary"):
                        ls_records = [r for r in ls_records if not (str(r.get('Lop')) == c_lop and str(r.get('HoTen')) == c_ten and str(r.get('TenSession')) == c_bai)]
                        sync_data(sheet_lich_su, ls_records, ["Lop", "HoTen", "TenSession", "SoLanNghe", "ThoiGianCuoi"])
                        st.success("Đã xóa lịch sử thành công!")
                        time.sleep(1)
                        st.rerun()
