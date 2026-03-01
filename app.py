import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="LMS - Hệ thống Luyện Nghe", layout="centered", page_icon="🎧")

# --- KẾT NỐI GOOGLE SHEETS ---
@st.cache_resource
def get_google_sheet():
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scopes)
    client = gspread.authorize(creds)
    # THAY LINK SHEET CỦA BẠN VÀO ĐÂY
    sheet_url = "https://docs.google.com/spreadsheets/d/1jw0qbjaTl9PqjR_cqncSBOXdsDezlNx86cRrBo8aG0U/edit#gid=0" 
    return client.open_by_url(sheet_url)

try:
    gc = get_google_sheet()
    sheet_danh_sach = gc.worksheet("DanhSach")
    sheet_sessions = gc.worksheet("Sessions")
    sheet_lich_su = gc.worksheet("LichSu")
except Exception as e:
    st.error(f"Lỗi: Không tìm thấy các Tab (DanhSach, Sessions, LichSu). {e}")
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
            row_idx = i + 2
            new_count = int(r.get('SoLanNghe', 0)) + 1
            sheet_lich_su.update_cell(row_idx, 4, str(new_count))
            sheet_lich_su.update_cell(row_idx, 5, now_str)
            return new_count
    sheet_lich_su.append_row([lop, name, session_name, "1", now_str])
    return 1

# --- LOAD DỮ LIỆU CHUNG ---
try:
    ds_records = sheet_danh_sach.get_all_records()
    ss_records = sheet_sessions.get_all_records()
    ls_records = sheet_lich_su.get_all_records()
except:
    ds_records, ss_records, ls_records = [], [], []

# ==========================================================
# KHU VỰC 1: GIAO DIỆN HỌC SINH (NỬA TRÊN)
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
                with st.spinner("Đang tải dữ liệu bài thi..."):
                    st.session_state['audios'] = [get_audio_b64(l) for l in links]
                    st.session_state['ss_info'] = ss_info
                    st.session_state['is_playing'] = True
                st.rerun()

# --- KHU VỰC PHÁT NHẠC HỌC SINH ---
if st.session_state.get('is_playing') and st.session_state.get('ss_info'):
    st.divider()
    ss = st.session_state['ss_info']
    audios = st.session_state['audios']
    che_do = str(ss.get("CheDo", "AUTO")).upper()
    cho_phep_pause = str(ss.get("ChoPhepPause", "FALSE")).upper() == "TRUE"
    interval = int(ss.get("ThoiGianNghi", 10))
    
    st.subheader(f"📖 Đang làm bài: {ss['TenSession']}")

    if che_do == "MANUAL":
        st.write("👉 *Chế độ tự chọn: Em có thể nghe từng file theo ý muốn.*")
        for i, b64 in enumerate(audios):
            if not b64: continue
            st.markdown(f"**🔈 File {i+1}**")
            ctrls = "controls" if cho_phep_pause else ""
            components.html(f"""
                <div style="background:#f1f3f4; padding:10px; border-radius:8px; margin-bottom:15px; text-align:center;">
                    <audio id="audio_{i}" {ctrls} style="width:100%"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>
                    <button id="btn_{i}" onclick="document.getElementById('audio_{i}').play(); this.disabled=true; this.innerText='Đang phát...';" style="padding:10px 20px; background:#1a73e8; color:white; border:none; border-radius:5px; cursor:pointer; margin-top:10px;">▶️ Nghe File {i+1}</button>
                </div>
            """, height=120)
    else:
        st.write("👉 *Chế độ Tự động: Hệ thống sẽ tự chuyển file. Vui lòng tập trung!*")
        js_data = {"audios": audios, "interval": interval, "pause": cho_phep_pause, "total": len([a for a in audios if a])}
        ctrl_attr = "controls" if cho_phep_pause else ""
        components.html(f"""
        <div style="background:#1a1a1a; color:white; padding:25px; border-radius:10px; text-align:center; font-family:sans-serif;">
            <h3 id="status">Sẵn sàng</h3>
            <div style="width:100%; background:#444; height:10px; border-radius:5px; margin:15px 0;"><div id="prog" style="width:0%; background:#28a745; height:10px; border-radius:5px; transition:width 0.1s;"></div></div>
            <p id="info">Tiến trình: 0 / {js_data['total']}</p>
            <button id="btn" onclick="startAuto()" style="padding:15px 30px; background:#fff; color:#000; font-weight:bold; border-radius:5px; cursor:pointer;">▶️ BẤM VÀO ĐÂY ĐỂ BẮT ĐẦU</button>
            <audio id="player" {ctrl_attr}></audio>
        </div>
        <script>
            var data = {json.dumps(js_data)}; var player = document.getElementById('player'); var btn = document.getElementById('btn');
            function startAuto() {{ btn.style.display = 'none'; playFile(0); }}
            function playFile(idx) {{
                if(idx >= data.audios.length) {{ document.getElementById('status').innerText = "✅ HOÀN THÀNH TOÀN BỘ BÀI NGHE"; document.getElementById('info').innerText = ""; return; }}
                if(!data.audios[idx]) {{ playFile(idx+1); return; }}
                document.getElementById('status').innerText = "🔊 Đang phát File " + (idx+1);
                document.getElementById('info').innerText = "Tiến trình: File " + (idx+1) + " / " + data.total;
                player.src = "data:audio/mp3;base64," + data.audios[idx];
                player.play();
                player.ontimeupdate = () => {{ document.getElementById('prog').style.width = (player.currentTime / player.duration) * 100 + "%"; }};
                player.onended = () => {{
                    if(idx < data.audios.length - 1) {{
                        let timer = data.interval; document.getElementById('status').innerText = "⏳ Thời gian nghỉ";
                        var cd = setInterval(() => {{
                            document.getElementById('info').innerText = "Chuẩn bị File " + (idx+2) + " sau: " + timer + "s";
                            timer--;
                            if(timer < 0) {{ clearInterval(cd); playFile(idx+1); }}
                        }}, 1000);
                    }} else {{ playFile(idx+1); }}
                }};
            }}
        </script>
        """, height=280)


# ==========================================================
# KHU VỰC 2: CÁNH CỬA BÍ MẬT DÀNH CHO GIÁO VIÊN (NỬA DƯỚI)
# ==========================================================
st.markdown("<br><br><br><br><br>", unsafe_allow_html=True) # Tạo khoảng trống

with st.expander("🛠️ (Dành cho nội bộ)", expanded=False):
    st.write("Khu vực quản trị hệ thống. Vui lòng xác thực.")
    pwd = st.text_input("Mật mã:", type="password", key="admin_pwd")
    
    if pwd == "Nam2026": # Đổi mật khẩu của bạn ở đây
        st.success("🔓 Đã mở khóa hệ thống quản trị!")
        
        tab_hs, tab_ss, tab_ls = st.tabs(["👥 QL Học Sinh", "⚙️ QL Bài Nghe (Session)", "📊 QL Lịch Sử"])
        
        def save_to_sheet(sheet_obj, dataframe):
            """Hàm lưu bảng pandas ngược lại vào Google Sheets"""
            sheet_obj.clear()
            sheet_obj.update(values=[dataframe.columns.values.tolist()] + dataframe.values.tolist(), range_name="A1")
            
        # --- TAB QUẢN LÝ HỌC SINH ---
        with tab_hs:
            st.write("Bạn có thể Thêm/Sửa/Xóa học sinh trực tiếp vào bảng dưới đây:")
            df_hs = pd.DataFrame(ds_records) if ds_records else pd.DataFrame(columns=["Lop", "HoTen"])
            edited_hs = st.data_editor(df_hs, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Lưu Danh Sách Học Sinh"):
                with st.spinner("Đang đồng bộ lên Google Sheets..."):
                    save_to_sheet(sheet_danh_sach, edited_hs)
                st.success("Đã cập nhật danh sách lớp!")
                time.sleep(1)
                st.rerun()

        # --- TAB QUẢN LÝ SESSION ---
        with tab_ss:
            st.write("Tạo bài nghe mới, cài đặt luật (AUTO/MANUAL, Pause, Nghỉ, Lượt tối đa...):")
            df_ss = pd.DataFrame(ss_records) if ss_records else pd.DataFrame(columns=["TenSession", "Links", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot"])
            edited_ss = st.data_editor(df_ss, num_rows="dynamic", use_container_width=True)
            if st.button("💾 Lưu Cài Đặt Session"):
                with st.spinner("Đang đồng bộ lên Google Sheets..."):
                    save_to_sheet(sheet_sessions, edited_ss)
                st.success("Đã cập nhật các Session bài nghe!")
                time.sleep(1)
                st.rerun()

        # --- TAB QUẢN LÝ LỊCH SỬ ---
        with tab_ls:
            st.write("Bảng theo dõi số lần nghe. Bạn có thể xóa dòng để reset lượt nghe cho 1 học sinh.")
            df_ls = pd.DataFrame(ls_records) if ls_records else pd.DataFrame(columns=["Lop", "HoTen", "TenSession", "SoLanNghe", "ThoiGianCuoi"])
            edited_ls = st.data_editor(df_ls, num_rows="dynamic", use_container_width=True)
            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("💾 Lưu chỉnh sửa Lịch Sử"):
                    with st.spinner("Đang đồng bộ..."):
                        save_to_sheet(sheet_lich_su, edited_ls)
                    st.success("Đã cập nhật lịch sử!")
                    time.sleep(1)
                    st.rerun()
            with col_b:
                if st.button("🚨 XÓA TRẮNG TOÀN BỘ LỊCH SỬ LỚP"):
                    sheet_lich_su.clear()
                    sheet_lich_su.update(values=[["Lop", "HoTen", "TenSession", "SoLanNghe", "ThoiGianCuoi"]], range_name="A1")
                    st.warning("Đã reset toàn bộ lượt nghe của tất cả mọi người về 0.")
                    time.sleep(1)
                    st.rerun()
