import streamlit as st
import streamlit.components.v1 as components
import gspread
import requests
import base64
import json
import pandas as pd
from datetime import datetime
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="Hệ Thống Học Online", layout="centered", page_icon="🏛️")

# --- KẾT NỐI CƠ SỞ DỮ LIỆU ---
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
    st.error(f"Lỗi truy xuất dữ liệu: {e}")
    st.stop()

# --- HÀM XỬ LÝ HỆ THỐNG ---
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
        sheet.update(values=[headers] + [[str(r.get(h, "")) for h in headers] for r in records], range_name="A1")
    else:
        sheet.update(values=[headers], range_name="A1")

# Đọc dữ liệu
ds_records = sheet_danh_sach.get_all_records()
ss_records = sheet_sessions.get_all_records()
ls_records = sheet_lich_su.get_all_records()

# ==========================================================
# GIAO DIỆN HỌC VIÊN
# ==========================================================
st.title("🏛️ Hệ Thống Học Online")
st.markdown("---")

col1, col2 = st.columns(2)
with col1:
    list_lop = sorted(list(set([str(r.get("Lop", "")) for r in ds_records if r.get("Lop")])))
    chon_lop = st.selectbox("1. Lớp học phần:", ["-- Chọn Lớp --"] + list_lop)

with col2:
    if chon_lop != "-- Chọn Lớp --":
        list_ten = [str(r["HoTen"]) for r in ds_records if str(r.get("Lop")) == chon_lop]
        chon_ten = st.selectbox("2. Họ và tên học viên:", ["-- Chọn Họ Tên --"] + list_ten)
    else:
        chon_ten = st.selectbox("2. Họ và tên học viên:", ["-- Vui lòng chọn lớp trước --"], disabled=True)

if chon_ten not in ["-- Chọn Họ Tên --", "-- Vui lòng chọn lớp trước --"]:
    # LỌC SESSION THEO LỚP HỌC
    list_ss = []
    for s in ss_records:
        lop_duoc_giao = [l.strip() for l in str(s.get("LopDuocGiao", "")).split(",")]
        if chon_lop in lop_duoc_giao or not str(s.get("LopDuocGiao", "")).strip():
            list_ss.append(str(s.get("TenSession")))

    if not list_ss:
        st.info("Hiện tại chưa có bài tập nào được giao cho lớp của bạn.")
    else:
        chon_session = st.selectbox("3. Chọn Phiên học (Session):", ["-- Chọn Phiên Học --"] + list_ss)

        if chon_session != "-- Chọn Phiên Học --":
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
                st.error(f"Phiên học này đã kết thúc vào lúc {ss_info['HanChot']}.")
            elif lan_da_nghe >= max_luot:
                st.error(f"Học viên đã vượt quá số lần truy cập cho phép ({lan_da_nghe}/{max_luot} lần).")
            else:
                st.info(f"Số lượt truy cập còn lại: **{max_luot - lan_da_nghe}**.")
                if st.button("XÁC NHẬN TRUY CẬP", use_container_width=True):
                    update_history(chon_lop, chon_ten, chon_session)
                    links = [l.strip() for l in str(ss_info.get("Links", "")).split("\n") if l.strip()]
                    with st.spinner("Hệ thống đang tải dữ liệu học tập..."):
                        st.session_state['audios'] = [get_audio_b64(l) for l in links]
                        st.session_state['ss_info'] = ss_info
                        st.session_state['is_playing'] = True
                    st.rerun()

# --- TRÌNH PHÁT NHẠC ĐỘC QUYỀN ---
if st.session_state.get('is_playing') and st.session_state.get('ss_info'):
    st.divider()
    ss = st.session_state['ss_info']
    audios = st.session_state['audios']
    che_do = str(ss.get("CheDo", "AUTO")).upper()
    cho_phep_pause = str(ss.get("ChoPhepPause", "FALSE")).upper() == "TRUE"
    interval = int(ss.get("ThoiGianNghi", 10))
    toc_do = float(ss.get("TocDo", 1.0))
    
    names = [n.strip() for n in str(ss.get("TenFiles", "")).split("\n")]
    notes = [n.strip() for n in str(ss.get("GhiChuFiles", "")).split("\n")]
    
    # Đồng bộ độ dài danh sách
    while len(names) < len(audios): names.append(f"Tập tin {len(names)+1}")
    while len(notes) < len(audios): notes.append("")

    st.subheader(f"📖 Phiên học: {ss['TenSession']}")
    
    if ss.get("GhiChuChung"):
        st.info(f"**Ghi chú từ Giảng viên:**\n{ss['GhiChuChung']}")

    if che_do == "MANUAL":
        st.markdown("*Chế độ tùy chọn: Hệ thống chỉ cho phép phát một tập tin tại một thời điểm.*")
        for i, b64 in enumerate(audios):
            if not b64: continue
            
            st.markdown(f"**{names[i]}**")
            if notes[i]:
                st.caption(f"📝 *{notes[i]}*")
            
            html = f"""
                <div style="background:#f8f9fa; padding:15px; border:1px solid #dee2e6; border-radius:8px; margin-bottom:15px; font-family:sans-serif;">
                    <audio id="audio_{i}" style="display:none;"><source src="data:audio/mp3;base64,{b64}" type="audio/mp3"></audio>
                    
                    <div style="display:flex; justify-content:space-between; margin-bottom:10px; font-size:13px; color:#495057;">
                        <span id="time_{i}">00:00 / 00:00</span>
                        <span>Trạng thái: Bắt buộc nghe tuần tự</span>
                    </div>
                    
                    <div style="width:100%; background:#e9ecef; height:6px; border-radius:3px; margin-bottom:15px; position:relative;">
                        <div id="prog_{i}" style="width:0%; background:#0d6efd; height:6px; border-radius:3px; position:absolute; top:0; left:0;"></div>
                    </div>
                    
                    <button id="btn_{i}" onclick="playManual({i})" style="padding:10px 20px; background:#0d6efd; color:white; border:none; border-radius:4px; cursor:pointer; font-weight:600; width:100%;">▶️ PHÁT TẬP TIN NÀY</button>
                </div>
                
                <script>
                    function formatTime(secs) {{
                        if (isNaN(secs)) return "00:00";
                        var m = Math.floor(secs / 60); var s = Math.floor(secs % 60);
                        return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
                    }}
                    function playManual(id) {{
                        var allow_pause = {'true' if cho_phep_pause else 'false'};
                        var total_files = {len(audios)};
                        
                        // Khóa 1 file tại 1 thời điểm
                        for(let j=0; j<total_files; j++) {{
                            if(j !== id) {{
                                let other_a = document.getElementById('audio_' + j);
                                let other_b = document.getElementById('btn_' + j);
                                if(other_a) {{
                                    other_a.pause();
                                    other_b.innerText = '▶️ PHÁT TẬP TIN NÀY';
                                    other_b.style.background = '#0d6efd';
                                }}
                            }}
                        }}
                        
                        var a = document.getElementById('audio_' + id);
                        var b = document.getElementById('btn_' + id);
                        var p = document.getElementById('prog_' + id);
                        var t = document.getElementById('time_' + id);
                        
                        if(a.paused) {{
                            a.playbackRate = {toc_do};
                            a.play();
                            b.innerText = '⏸ ĐANG PHÁT';
                            b.style.background = '#6c757d';
                        }} else {{
                            if(allow_pause) {{
                                a.pause();
                                b.innerText = '▶️ TIẾP TỤC';
                                b.style.background = '#0d6efd';
                            }}
                        }}
                        
                        a.ontimeupdate = function() {{
                            p.style.width = (a.currentTime / a.duration) * 100 + "%";
                            t.innerText = formatTime(a.currentTime) + " / " + formatTime(a.duration);
                        }};
                    }}
                </script>
            """
            components.html(html, height=140)

    else:
        st.markdown("*Chế độ Tự động: Hệ thống sẽ kiểm soát tiến trình phát tuần tự.*")
        js_data = {"audios": audios, "names": names, "notes": notes, "interval": interval, "pause": cho_phep_pause, "speed": toc_do, "total": len([a for a in audios if a])}
        
        components.html(f"""
        <div style="background:#ffffff; color:#212529; border: 1px solid #ced4da; padding:30px; border-radius:8px; text-align:center; font-family:sans-serif;">
            <h4 id="file_name" style="margin-top:0; color:#0d6efd;">Sẵn sàng tiến hành</h4>
            <p id="file_note" style="font-size:14px; font-style:italic; color:#6c757d;"></p>
            
            <div style="display:flex; justify-content:space-between; margin-bottom:8px; font-size:13px; color:#6c757d;">
                <span id="timer_txt">00:00 / 00:00</span>
                <span id="info">Tiến trình: 0 / {js_data['total']}</span>
            </div>
            
            <div style="width:100%; background:#e9ecef; height:8px; border-radius:4px; margin-bottom:25px; position:relative; overflow:hidden;">
                <div id="prog" style="width:0%; background:#198754; height:8px; border-radius:4px; position:absolute; top:0; left:0; transition: width 0.1s linear;"></div>
            </div>
            
            <button id="btn" onclick="startAuto()" style="padding:12px 30px; background:#0d6efd; color:white; font-weight:600; border:none; border-radius:6px; cursor:pointer;">BẮT ĐẦU PHIÊN HỌC</button>
            <audio id="player" style="display:none;"></audio>
        </div>
        
        <script>
            var data = {json.dumps(js_data)}; 
            var player = document.getElementById('player'); 
            var btn = document.getElementById('btn');
            var is_playing = false;
            
            function formatTime(secs) {{
                if (isNaN(secs)) return "00:00";
                var m = Math.floor(secs / 60); var s = Math.floor(secs % 60);
                return (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
            }}

            function startAuto() {{ 
                btn.style.display = data.pause ? 'inline-block' : 'none'; 
                if(data.pause) {{ btn.innerText = "TẠM DỪNG"; btn.onclick = togglePause; }}
                playFile(0); 
            }}
            
            function togglePause() {{
                if(player.paused) {{
                    player.play();
                    btn.innerText = "TẠM DỪNG";
                    btn.style.background = "#6c757d";
                }} else {{
                    player.pause();
                    btn.innerText = "TIẾP TỤC";
                    btn.style.background = "#0d6efd";
                }}
            }}

            function playFile(idx) {{
                if(idx >= data.audios.length) {{ 
                    document.getElementById('file_name').innerText = "Đã hoàn thành phiên học"; 
                    document.getElementById('file_note').innerText = "";
                    document.getElementById('info').innerText = ""; 
                    document.getElementById('timer_txt').innerText = "";
                    btn.style.display = 'none';
                    return; 
                }}
                if(!data.audios[idx]) {{ playFile(idx+1); return; }}
                
                document.getElementById('file_name').innerText = data.names[idx];
                document.getElementById('file_note').innerText = data.notes[idx];
                document.getElementById('info').innerText = "Tập tin: " + (idx+1) + " / " + data.total;
                
                player.src = "data:audio/mp3;base64," + data.audios[idx];
                player.playbackRate = data.speed;
                player.play();
                if(data.pause) {{ btn.innerText = "TẠM DỪNG"; btn.style.background = "#6c757d"; }}
                
                player.ontimeupdate = () => {{ 
                    document.getElementById('prog').style.width = (player.currentTime / player.duration) * 100 + "%"; 
                    document.getElementById('timer_txt').innerText = formatTime(player.currentTime) + " / " + formatTime(player.duration);
                }};
                
                player.onended = () => {{
                    if(idx < data.audios.length - 1) {{
                        let timer = data.interval; 
                        document.getElementById('file_name').innerText = "Thời gian chuyển tiếp...";
                        document.getElementById('file_note').innerText = "";
                        btn.style.display = 'none';
                        
                        var cd = setInterval(() => {{
                            document.getElementById('timer_txt').innerText = "Tiếp tục sau: " + timer + "s";
                            timer--;
                            if(timer < 0) {{ 
                                clearInterval(cd); 
                                if(data.pause) btn.style.display = 'inline-block';
                                playFile(idx+1); 
                            }}
                        }}, 1000);
                    }} else {{ playFile(idx+1); }}
                }};
            }}
        </script>
        """, height=260)


# ==========================================================
# KHU VỰC QUẢN TRỊ (DÀNH CHO GIẢNG VIÊN)
# ==========================================================
st.markdown("<br><br><br>", unsafe_allow_html=True)
with st.expander("🔐 Khu Vực Quản Trị Hệ Thống", expanded=False):
    pwd = st.text_input("Mã định danh Giảng viên:", type="password")
    
    # Truy xuất mật khẩu từ vùng an toàn của Streamlit
    if pwd == st.secrets["ADMIN_PASSWORD"]: 
        st.success("Xác thực thành công.")
        
        tab_tao, tab_lop, tab_rp = st.tabs(["📝 Khởi Tạo Phiên Học", "👥 Quản Lý Học Viên", "📊 Dữ Liệu Truy Cập"])
        
        with tab_tao:
            st.write("Thiết lập thông số cho Phiên học mới:")
            with st.form("form_session"):
                s_name = st.text_input("Tên Phiên Học:")
                s_class = st.multiselect("Giao cho lớp (Bỏ trống để giao toàn bộ):", list_lop)
                s_note_chung = st.text_area("Ghi chú chung cho phiên học:")
                
                st.write("**Dữ liệu tập tin (Mỗi dòng tương ứng 1 tập tin):**")
                colA, colB, colC = st.columns(3)
                s_links = colA.text_area("Link Google Drive (Enter xuống dòng):")
                s_names = colB.text_area("Tên từng tập tin (Enter xuống dòng):")
                s_notes = colC.text_area("Ghi chú từng tập tin (Enter xuống dòng):")
                
                c1, c2, c_spd = st.columns(3)
                s_mode = c1.selectbox("Quy trình phát:", ["AUTO (Tự động chuyển tiếp)", "MANUAL (Học viên tùy chọn)"])
                s_pause = c2.checkbox("Cấp quyền tạm dừng (Pause)")
                s_speed = c_spd.number_input("Tốc độ phát (Mặc định 1.0):", value=1.0, step=0.1)
                
                c3, c4, c5 = st.columns(3)
                s_interval = c3.number_input("Thời gian chờ (giây, dùng cho AUTO):", min_value=0, value=10)
                s_limit = c4.number_input("Giới hạn lượt truy cập:", min_value=1, value=1)
                s_deadline = c5.text_input("Hạn chót truy cập (YYYY-MM-DD HH:MM):", value="2026-12-31 23:59")
                
                if st.form_submit_button("Lưu Phiên Học"):
                    if s_name and s_links:
                        new_ss = {
                            "TenSession": s_name, 
                            "LopDuocGiao": ",".join(s_class),
                            "GhiChuChung": s_note_chung,
                            "Links": s_links, 
                            "TenFiles": s_names,
                            "GhiChuFiles": s_notes,
                            "CheDo": s_mode.split()[0], 
                            "ChoPhepPause": str(s_pause), 
                            "ThoiGianNghi": s_interval, 
                            "LuotNgheToiDa": s_limit, 
                            "HanChot": s_deadline, 
                            "TocDo": s_speed
                        }
                        ss_records.append(new_ss)
                        sync_data(sheet_sessions, ss_records, ["TenSession", "LopDuocGiao", "GhiChuChung", "Links", "TenFiles", "GhiChuFiles", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot", "TocDo"])
                        st.success("Khởi tạo phiên học thành công.")
                        st.rerun()
                    else: st.error("Lỗi: Tên phiên học và Link tập tin không được để trống.")
            
            st.divider()
            st.write("**Danh sách Phiên học hiện hành:**")
            for ss in ss_records:
                with st.container():
                    cA, cB = st.columns([4, 1])
                    cA.markdown(f"**{ss.get('TenSession')}** - Lớp: `{ss.get('LopDuocGiao', 'Tất cả')}` - Quy trình: `{ss.get('CheDo')}`")
                    if cB.button("🗑️ Hủy Phiên", key=f"del_{ss.get('TenSession')}"):
                        ss_records = [r for r in ss_records if r.get('TenSession') != ss.get('TenSession')]
                        sync_data(sheet_sessions, ss_records, ["TenSession", "LopDuocGiao", "GhiChuChung", "Links", "TenFiles", "GhiChuFiles", "CheDo", "ChoPhepPause", "ThoiGianNghi", "LuotNgheToiDa", "HanChot", "TocDo"])
                        st.rerun()

        with tab_lop:
            st.write("**Nhập danh sách học viên hàng loạt:**")
            bulk_lop = st.text_input("Nhập mã Lớp học phần:")
            bulk_names = st.text_area("Dán danh sách Họ và tên (Mỗi dòng một học viên):")
            if st.button("Tiến hành nạp dữ liệu"):
                names = [n.strip() for n in bulk_names.split("\n") if n.strip()]
                for n in names: ds_records.append({"Lop": bulk_lop, "HoTen": n})
                sync_data(sheet_danh_sach, ds_records, ["Lop", "HoTen"])
                st.success(f"Cập nhật thành công {len(names)} học viên.")
                st.rerun()

        with tab_rp:
            st.dataframe(ls_records, use_container_width=True)
            st.divider()
            st.subheader("Cấp lại quyền truy cập")
            c_lop = st.selectbox("Chọn Lớp phần:", [""] + list_lop, key="rs_lop")
            if c_lop:
                list_rs_ten = [str(r["HoTen"]) for r in ds_records if str(r.get("Lop")) == c_lop]
                c_ten = st.selectbox("Chọn Học viên:", [""] + list_rs_ten, key="rs_ten")
                if c_ten:
                    c_bai = st.selectbox("Chọn Phiên học cần khôi phục:", [""] + [str(r["TenSession"]) for r in ss_records], key="rs_bai")
                    if c_bai and st.button("🚨 Thực thi Khôi phục", type="primary"):
                        ls_records = [r for r in ls_records if not (str(r.get('Lop')) == c_lop and str(r.get('HoTen')) == c_ten and str(r.get('TenSession')) == c_bai)]
                        sync_data(sheet_lich_su, ls_records, ["Lop", "HoTen", "TenSession", "SoLanNghe", "ThoiGianCuoi"])
                        st.success("Thực thi thành công.")
                        st.rerun()
