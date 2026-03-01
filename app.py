import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ thống Luyện Nghe Tiếng Anh", layout="centered", page_icon="🎧")

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
    st.error(f"Lỗi: Không tìm thấy các Tab. {e}")
    st.stop()

# --- HÀM TRỢ GIÚP ---
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

# --- TẢI DỮ LIỆU ---
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
                with st.spinner("Đang tải dữ liệu bài thi..."):
                    st.session_state['audios'] = [get_audio_b64(l) for l in links]
                    st.session_state['ss_info'] = ss_info
                    st.session_state['is_playing'] = True
                st.rerun()

# --- TRÌNH PHÁT NHẠC ---
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
# KHU VỰC 2: APP QUẢN TRỊ DÀNH CHO GIÁO VIÊN
# ==========================================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
with st.expander("🔐 Trạm Quản Trị Giáo Viên", expanded=False):
    pwd = st.text_input("Nhập mã truy cập:", type="password")
    
    if pwd == "Nam2026":
        st.success("Đăng nhập thành công! Chào mừng thầy Nam.")
        
        tab_tao, tab_lop, tab_rp = st.tabs(["📝 Soạn Bài (Sessions)", "👥 Quản Lý Học Sinh", "📊 Báo Cáo & Xóa Lượt"])
        
        # --- TAB 1: SOẠN BÀI NGHE ---
        with tab_tao:
            st.subheader("Tạo phiên nghe mới")
            with st.form("form_session"):
                s_name = st.text_input("Tên Bài Nghe (Session Name):", placeholder="VD: Test 1 - Algebra")
                s_links = st.text_area("Link Google Drive (Cách nhau dấu phẩy):")
                
                c1, c2 = st.columns(2)
                s_mode = c1.selectbox("Chế độ phát:", ["AUTO (Tự động chạy hết)", "MANUAL (Học sinh tự bấm)"])
                s_pause = c2.checkbox("Cho phép tạm dừng (Pause)", value=False)
                
                c3, c4, c5 = st.columns(3)
                s_interval = c3.number_input("Giây nghỉ (nếu AUTO):", min_value=0, value=10)
                s_limit = c4.number_input("Lượt nghe tối đa:", min_value=1, value=1)
                s_deadline = c5.text_input("Hạn chót (YYYY-MM-DD HH:MM):", value="2026-12-31 23:59")
                
                if st.form_submit_button("➕ Thêm Bài Nghe Này"):
                    if s_name and s_links:
                        new_ss = {"TenSession": s_name, "Links": s_links, "CheDo": s_mode.split()[0], "ChoPhepPause": str(s_pause), "ThoiGianNghi": s_interval, "LuotNgheToiDa": s_limit, "HanChot": s_deadline}
                        ss_records.append(new_ss)
                        sync_data(sheet_sessions, ss_records, ["TenSession", "Links", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot"])
                        st.success(f"Đã tạo thành công bài: {s_name}")
                        time.sleep(1)
                        st.rerun()
                    else:
                        st.error("Vui lòng điền tên bài và link Drive!")
            
            st.divider()
            st.write("**Các bài nghe đang hoạt động:**")
            for ss in ss_records:
                with st.container():
                    colA, colB = st.columns([4, 1])
                    colA.markdown(f"**{ss.get('TenSession')}** - Chế độ: `{ss.get('CheDo')}` - Lượt: `{ss.get('LuotNgheToiDa')}`")
                    if colB.button("🗑️ Xóa", key=f"del_{ss.get('TenSession')}"):
                        ss_records = [r for r in ss_records if r.get('TenSession') != ss.get('TenSession')]
                        sync_data(sheet_sessions, ss_records, ["TenSession", "Links", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot"])
                        st.rerun()

        # --- TAB 2: QUẢN LÝ LỚP HỌC ---
        with tab_lop:
            st.subheader("Thêm học sinh mới")
            with st.form("form_hs"):
                c1, c2 = st.columns(2)
                h_lop = c1.text_input("Tên Lớp (VD: Math-01):")
                h_ten = c2.text_input("Họ và Tên:")
                if st.form_submit_button("➕ Thêm Học Sinh"):
                    if h_lop and h_ten:
                        ds_records.append({"Lop": h_lop, "HoTen": h_ten})
                        sync_data(sheet_danh_sach, ds_records, ["Lop", "HoTen"])
                        st.success("Đã thêm!")
                        time.sleep(1)
                        st.rerun()
            
            st.write("---")
            st.write("**Thêm nhanh nhiều học sinh (Bulk Add):**")
            bulk_lop = st.text_input("Lớp sẽ được thêm vào:")
            bulk_names = st.text_area("Dán danh sách tên (Mỗi người 1 dòng):")
            if st.button("Tải danh sách lên"):
                names = [n.strip() for n in bulk_names.split("\n") if n.strip()]
                for n in names: ds_records.append({"Lop": bulk_lop, "HoTen": n})
                sync_data(sheet_danh_sach, ds_records, ["Lop", "HoTen"])
                st.success(f"Đã thêm {len(names)} học sinh vào lớp {bulk_lop}!")
                time.sleep(1)
                st.rerun()

        # --- TAB 3: BÁO CÁO & RESET LƯỢT ---
        with tab_rp:
            st.subheader("Lịch sử làm bài")
            st.dataframe(ls_records, use_container_width=True) # Hiển thị bảng đẹp, chỉ đọc
            
            st.divider()
            st.subheader("🛠️ Cấp lại quyền thi (Reset lượt)")
            st.write("Nếu học sinh bị rớt mạng, bạn có thể xóa lịch sử bài thi đó để em ấy làm lại từ đầu.")
            
            c_lop = st.selectbox("Chọn Lớp:", [""] + list_lop, key="rs_lop")
            if c_lop:
                list_rs_ten = [str(r["HoTen"]) for r in ds_records if str(r.get("Lop")) == c_lop]
                c_ten = st.selectbox("Chọn Học Sinh:", [""] + list_rs_ten, key="rs_ten")
                if c_ten:
                    c_bai = st.selectbox("Chọn Bài Cần Hủy Lượt:", [""] + list_ss, key="rs_bai")
                    if c_bai and st.button("🚨 Hủy lượt bài này", type="primary"):
                        ls_records = [r for r in ls_records if not (str(r.get('Lop')) == c_lop and str(r.get('HoTen')) == c_ten and str(r.get('TenSession')) == c_bai)]
                        sync_data(sheet_lich_su, ls_records, ["Lop", "HoTen", "TenSession", "SoLanNghe", "ThoiGianCuoi"])
                        st.success(f"Đã xóa lịch sử bài {c_bai} của em {c_ten}!")
                        time.sleep(1)
                        st.rerun()
