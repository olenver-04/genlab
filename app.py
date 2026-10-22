from __future__ import annotations

import csv
import hmac
import html
import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from io import BytesIO, StringIO
from pathlib import Path

import qrcode
import streamlit as st
import streamlit.components.v1 as components

st.set_page_config(
    page_title="GENETIC GARDEN | Генетикалық бақ",
    page_icon="🌸",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_PATH = Path(__file__).with_name("genetics_lab.db")
# Decorative palette only; colors no longer indicate topics or answers.
FLOWER_COLORS = ["#F7A8C7", "#A8D8FF", "#D3B4FF", "#FFD58C", "#B6EDBA", "#FFAB91", "#F7C0EF"]




@contextmanager
def db():
    conn = sqlite3.connect(DB_PATH, timeout=20)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=20000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db():
    # Compatible with the original genlab discoveries schema.
    with db() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS discoveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT NOT NULL,
            section_key TEXT NOT NULL,
            fact_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")


def add_feedback(name: str, feedback: str):
    name = " ".join(name.split())
    feedback = feedback.strip()
    if not (2 <= len(name) <= 40) or not (3 <= len(feedback) <= 500):
        raise ValueError("invalid fields")
    with db() as conn:
        # Reuse the existing table, so old genlab data won't be deleted.
        # Store a fixed internal key for new feedback (not a category).
        conn.execute("BEGIN IMMEDIATE")
        existing = any(row["student_name"].casefold() == name.casefold()
                       for row in conn.execute("SELECT student_name FROM discoveries"))
        if existing:
            raise FileExistsError("duplicate name")
        conn.execute(
            "INSERT INTO discoveries(student_name, section_key, fact_text, created_at) VALUES(?,?,?,?)",
            (name, "feedback", feedback, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def all_discoveries(limit: int = 1000):
    with db() as conn:
        return [dict(r) for r in conn.execute(
            "SELECT * FROM discoveries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()]


# Note: the existing database schema is intentionally maintained for migration.


def esc(s):
    return html.escape(str(s), quote=True)


def qr_bytes(address: str):
    qr = qrcode.QRCode(box_size=10, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(address)
    qr.make(fit=True)
    image = qr.make_image(fill_color="#10241d", back_color="#ffffff")
    out = BytesIO()
    image.save(out, format="PNG")
    return out.getvalue()


def urls():
    base = st.context.url.split("?", 1)[0].rstrip("/") + "/"
    return base, base + "?view=student", base + "?view=admin"


def export_csv(rows):
    s = StringIO()
    w = csv.writer(s)
    w.writerow(["ID", "Аты", "Сабақ туралы пікірі", "Уақыты (UTC)"])
    for r in rows:
        def safe(v):
            v = str(v)
            return "'" + v if v.lstrip().startswith(("=", "+", "-", "@")) else v
        w.writerow([r["id"], safe(r["student_name"]), safe(r["fact_text"]), r["created_at"]])
    return s.getvalue().encode("utf-8-sig")


APP_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Nunito:wght@400;500;600;700;800;900&display=swap');
html, body, .stApp, input, textarea, button {font-family: 'Nunito', sans-serif !important;}
.stApp {
  background:
   radial-gradient(ellipse at 83% 5%,rgba(152,218,168,.14),transparent 38%),
   radial-gradient(ellipse at 10% 40%,rgba(165,134,204,.12),transparent 45%),
   linear-gradient(145deg,#101f27,#132b2b 60%,#142924);
  color:#ecf9ec;
}
[data-testid="stHeader"] {background:transparent;}
#MainMenu,footer {visibility:hidden;}
.block-container {max-width:1360px;padding-top:1.5rem;padding-bottom:2rem;}
.garden-mark {display:flex;align-items:center;gap:13px;color:#a1e6c6;font-weight:900;letter-spacing:.13em;text-transform:uppercase;font-size:.82rem;margin-bottom:16px;}
.garden-mark i {width:12px;height:12px;background:#96e6b5;border-radius:50%;display:block;box-shadow:0 0 19px #80d5a4;}
.garden-hero {background:linear-gradient(120deg,rgba(25,57,47,.92),rgba(41,56,72,.87));border:1px solid rgba(191,241,207,.19);padding:28px 30px;border-radius:26px;margin-bottom:18px;box-shadow:0 24px 38px rgba(3,17,15,.19);}
.garden-hero h1 {font-size:clamp(2.25rem,5vw,4.25rem);line-height:1.1;font-weight:900;margin:0 0 10px;color:#f4fff2;letter-spacing:-.045em;}
.garden-hero h1 span {color:#ffbccc;}
.garden-hero p {font-size:1rem;color:#d0e9df;line-height:1.7;max-width:920px;margin-bottom:0;}
.pillbar {display:flex;gap:10px;flex-wrap:wrap;margin-top:16px;}
.pill {padding:7px 12px;border-radius:999px;border:1px solid rgba(255,255,255,.14);background:rgba(255,255,255,.07);font-size:.78rem;color:#e7f4e9;font-weight:800;}
.statline {display:grid;grid-template-columns:repeat(2,1fr);gap:12px;margin-bottom:16px;}
.stat {background:rgba(14,40,37,.76);border:1px solid rgba(177,237,202,.16);border-radius:19px;padding:14px 17px;}
.stat .n {font-size:1.7rem;color:#fff;font-weight:900;line-height:1.2;}
.stat .l {font-size:.77rem;color:#b0d6c5;font-weight:800;margin-top:5px;}
.form-blurb {background:rgba(28,55,50,.72);padding:17px 20px;border-radius:20px;border:1px solid rgba(205,243,209,.15);margin:12px 0 22px;color:#d6f1df;line-height:1.7;}
div[data-testid="stTextInput"] input,div[data-testid="stTextArea"] textarea,div[data-baseweb="select"]>div {border:1px solid rgba(190,241,202,.20)!important;background:#1b3537!important;color:white!important;border-radius:13px!important;}
[data-testid="stWidgetLabel"] p {color:#e6f5ed;font-weight:800;}
[data-testid="stFormSubmitButton"] button,.stButton button[kind="primary"] {background:linear-gradient(110deg,#a2e3b7,#ffbfd0)!important;color:#183229!important;border:0!important;font-weight:900!important;min-height:3.1rem;border-radius:14px;}
.stButton button, .stLinkButton a,.stDownloadButton button {border-radius:13px;font-weight:800;}
.qr-card {border-radius:22px;padding:15px 16px;background:rgba(23,50,47,.78);border:1px solid rgba(184,245,202,.17);text-align:center;}
.qr-card h3 {font-size:1.05rem;color:#d5fbe1;margin:3px 0 5px;}
.qr-card p {font-size:.82rem;color:#badbc9;}
.section-legend {background:rgba(21,48,45,.70);border-radius:19px;padding:17px 21px;color:#d6f2e1;line-height:2;border:1px solid rgba(184,245,202,.12);}
.section-legend h3 {color:#fff;margin:0 0 6px;font-size:1.1rem;}
.live-mark {color:#b6f1cf;font-size:.9rem;font-weight:800;letter-spacing:.01em;margin:3px 0 8px;}
@media(max-width:780px){.statline{grid-template-columns:repeat(2,1fr)}.garden-hero{padding:20px}.block-container{padding-top:1rem}}
</style>
"""


def header(section: str):
    st.markdown(
        f'<div class="garden-mark"><i></i> GENETIC GARDEN <span style="color:#8fad9f">/ {esc(section)}</span></div>',
        unsafe_allow_html=True,
    )


def info_html():
    return ("<div class='section-legend'>"
            "<h3>🌷 Сенің пікірің маңызды!</h3>"
            "<p>Сабақ туралы ойыңды еркін жаз: не ұнады, не қызық болды, "
            "қандай сұрақ қалды?</p>"
            "<p>Сенің жауабың бақта ерекше гүлге айналады. "
            "Гүлдердің түстері мен пішіндері әртүрлі — олар жауапты бағаламайды.</p>"
            "</div>")


def garden_document(rows):
    """Single responsive interactive SVG: each bloom opens its author's answer."""
    # 10 columns x 4 layers means a legible 40-flower classroom wall.
    positions = []
    cols = 10
    for i in range(40):
        row, col = divmod(i, cols)
        offset = (row % 2) * 26
        x = 72 + col * 116 + offset
        y = 235 + row * 98
        positions.append((x, y, row))

    # Backmost plants first. Choose order by the submission ID for stable positions.
    visible = sorted(rows, key=lambda r: int(r["id"]))[:40]
    flower_nodes = []
    for i, r in enumerate(visible):
        x, y, depth = positions[i]
        stable_id = int(r["id"])
        color = FLOWER_COLORS[(stable_id * 11 + stable_id // 5) % len(FLOWER_COLORS)]
        size = (0.72, 0.82, 0.92, 1.02)[depth] * (0.94 + (stable_id % 5) * .025)
        stalk = 58 + (stable_id % 4) * 9
        shape = 5 + stable_id % 3
        petals = []
        for p in range(shape):
            ang = p * 360 / shape
            petals.append(f'<ellipse cx="0" cy="-17" rx="11" ry="18" fill="{color}" opacity=".96" transform="rotate({ang:.1f})"/>')
        flower_nodes.append(f'''<g class="flower" transform="translate({x},{y})" data-name="{esc(r["student_name"])}" data-note="{esc(r["fact_text"])}" data-color="{color}" tabindex="0" role="button" aria-label="{esc(r["student_name"])} пікірін ашу">
          <g transform="scale({size:.3f})">
            <path d="M0 0 Q{-14 if stable_id%2 else 12} {-stalk//2} 0 {-stalk}" stroke="#72bd85" stroke-width="5" fill="none" stroke-linecap="round"/>
            <ellipse cx="-13" cy="{-stalk//2+8}" rx="19" ry="8" fill="#5ab47b" transform="rotate(-26 -13 {-stalk//2+8})"/>
            <ellipse cx="14" cy="{-stalk//3}" rx="19" ry="8" fill="#8aca80" transform="rotate(25 14 {-stalk//3})"/>
            <g class="flower-head" transform="translate(0,{-stalk})">{''.join(petals)}
                <circle r="12" fill="#ffe9a6" stroke="#fff2c8" stroke-width="2"/>
                <circle r="4" fill="#f8ba5f"/>
            </g>
          </g>
          <text x="0" y="20" class="nametag">{esc(r["student_name"][:16])}</text>
        </g>''')

    if not visible:
        empty_label = '''<g class="empty-label"><text x="600" y="310" text-anchor="middle" font-size="32">🌱 Бақ әзірге бос</text><text x="600" y="349" text-anchor="middle" font-size="21">Алғашқы гүлді өсіру үшін QR-кодты сканерле!</text></g>'''
    else:
        empty_label = ""

    other = max(0, len(rows) - 40)
    extra_message = f'<div class="limit-message">Тағы {other} гүл тіркелді — барлығы {len(rows)} пікір</div>' if other else ''
    return f'''<!doctype html><html lang="kk"><head><meta charset="utf-8"/><meta name="viewport" content="width=device-width, initial-scale=1"/>
    <style>
    * {{box-sizing:border-box}} html,body{{padding:0;margin:0;background:transparent;font-family:system-ui,sans-serif;color:white}}
    .scene {{position:relative; width:100%; background:linear-gradient(180deg,#152c3d 0%,#244b56 35%,#37775e 74%,#315e45 100%);border-radius:25px;overflow:hidden;border:1px solid rgba(194,250,198,.2); box-shadow:inset 0 0 60px rgba(12,35,29,.3);}}
    .scene:before{{content:'';position:absolute;inset:0;background:radial-gradient(circle at 68% 17%,rgba(255,251,189,.26),transparent 25%),radial-gradient(circle at 13% 29%,rgba(165,228,253,.16),transparent 28%);pointer-events:none}}
    svg{{display:block;width:100%;height:auto;min-height:390px}}
    .flower{{cursor:pointer;outline:none}}
    .flower-head{{filter:drop-shadow(0 0 9px rgba(255,255,255,.3));animation:sway 3.6s ease-in-out infinite;transform-origin:center bottom;transform-box:fill-box}}
    .flower:nth-of-type(3n) .flower-head{{animation-delay:-1.3s}}
    .flower:hover .flower-head,.flower:focus .flower-head{{filter:drop-shadow(0 0 15px rgba(255,255,255,.9));}}
    .flower:focus .flower-head{{stroke:white;stroke-width:1.5}}
    .nametag{{fill:#f8fff2;font-size:13px;font-weight:700;text-anchor:middle;paint-order:stroke;stroke:#244e42;stroke-width:3px;letter-spacing:.01em}}
    .empty-label{{fill:#f8fff2;font-weight:700;paint-order:stroke;stroke:#235046;stroke-width:3px}}
    .stars circle{{animation:glimmer 2.7s ease-in-out infinite alternate}}
    @keyframes glimmer{{to{{opacity:.16;transform:scale(.6)}}}}
    @keyframes sway{{50%{{transform:rotate(7deg)}}}}
    .modal{{position:absolute;inset:0;display:none;justify-content:center;align-items:center;padding:22px;background:rgba(11,35,35,.55);backdrop-filter:blur(4px);z-index:10}}
    .modal.active{{display:flex}}
    .modal-card{{background:#effbef;color:#193a35;max-width:470px;width:100%;padding:24px;border-radius:23px;box-shadow:0 20px 55px rgba(0,0,0,.32);border-top:8px solid var(--flower-color,#ff9bbe)}}
    .modal-card h2{{font-size:1.35rem;margin:0 0 8px}}
    .modal-card p{{font-size:1rem;line-height:1.65;white-space:pre-wrap;word-break:break-word}}
    .modal-card .topic{{font-size:.85rem;font-weight:800;color:#3d695a}}
    .close{{float:right;border:0;border-radius:12px;background:#dbeedd;font-weight:900;font-size:1rem;cursor:pointer;padding:8px 12px}}
    .limit-message{{font-size:.84rem;position:absolute;right:15px;bottom:9px;color:#e4f7df;text-shadow:0 1px 6px black}}
    .title{{position:absolute;top:15px;left:20px;font-weight:800;color:#f5ffdc;letter-spacing:.11em;font-size:clamp(.65rem,1.4vw,.9rem);z-index:1}}
    .hint{{position:absolute;top:42px;left:20px;color:#e3f4da;font-size:clamp(.67rem,1.3vw,.9rem);z-index:1}}
    </style></head><body>
    <div class="scene">
    <div class="title">✦ GENETIC GARDEN · LIVE</div><div class="hint">Гүлді басып, студенттің пікірін оқы</div>
    <svg viewBox="0 0 1200 635" xmlns="http://www.w3.org/2000/svg" aria-label="Оқушылардың генетикалық бағы">
      <defs><linearGradient id="hill" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#4a886d"/><stop offset="1" stop-color="#1f4e39"/></linearGradient></defs>
      <circle cx="965" cy="110" r="53" fill="#fcf5c6" opacity=".50"/>
      <path d="M0 330 Q250 230 480 335 T970 304 T1200 332 V635 H0Z" fill="#3c7763"/>
      <path d="M0 440 Q200 360 470 448 T1020 424 T1200 443 V635 H0Z" fill="url(#hill)"/>
      <g class="stars" opacity=".63">{''.join(f'<circle cx="{(j*147+59)%1170+12}" cy="{(j*57+41)%202+35}" r="{2+j%3}" fill="#dff9cd" style="animation-delay:-{(j%7)*.5}s"/>' for j in range(34))}</g>
      {''.join(flower_nodes)}
      {empty_label}
      <path d="M0 587 Q270 557 550 590 T1200 582 V635 H0" fill="#244d3c" opacity=".45"/>
    </svg>{extra_message}
    <div class="modal" id="modal" aria-hidden="true"><div class="modal-card" id="modalCard"><button class="close" id="close" aria-label="Жабу">✕</button><div class="topic" id="topic"></div><h2 id="who"></h2><p id="note"></p></div></div>
    </div>
    <script>
      const popup=document.getElementById('modal');
      function reveal(el){{
        document.getElementById('who').textContent='🌸 '+el.dataset.name;
        document.getElementById('topic').textContent='Сабақ туралы пікір';
        document.getElementById('note').textContent=el.dataset.note;
        document.getElementById('modalCard').style.setProperty('--flower-color',el.dataset.color);
        popup.classList.add('active');popup.setAttribute('aria-hidden','false');
      }}
      function hide(){{popup.classList.remove('active');popup.setAttribute('aria-hidden','true')}}
      document.querySelectorAll('.flower').forEach(el=>{{
        el.addEventListener('click',()=>reveal(el));
        el.addEventListener('keydown',ev=>{{if(ev.key==='Enter'||ev.key===' '){{ev.preventDefault();reveal(el)}}}});
      }});
      document.getElementById('close').addEventListener('click',hide);
      popup.addEventListener('click',e=>{{if(e.target===popup)hide()}});
      document.addEventListener('keydown',e=>{{if(e.key==='Escape')hide()}});
    </script></body></html>'''


def stats_html(total: int):
    return (f'<div class="statline"><div class="stat"><div class="n">{total}</div>'
            '<div class="l">🌸 Бақтағы гүлдер саны</div></div>'
            '<div class="stat"><div class="n">LIVE</div>'
            '<div class="l">🌱 Әр пікірден жаңа гүл өседі</div></div></div>')


def wall_page(student_url):
    header("ОРТАҚ БАҒЫМЫЗ")
    a, b = st.columns([4.5, 1.2], gap="large")
    with a:
        st.markdown('''<div class="garden-hero"><h1>Genetic <span>Garden</span> 🌸</h1>
        <p>Әр пікір — бір гүл! Сабақ туралы ойыңды бөліс, ал біздің ортақ бағымызда
        сенің атыңмен жаңа гүл пайда болады.</p>
        <div class="pillbar"><span class="pill">🌱 Атыңды жаз</span>
        <span class="pill">💬 Пікіріңді қалдыр</span>
        <span class="pill">🌸 Гүліңді өсір</span></div></div>''', unsafe_allow_html=True)
    with b:
        st.markdown('<div class="qr-card"><h3>📱 Баққа қатысу</h3><p>QR-кодты сканерле</p></div>', unsafe_allow_html=True)
        st.image(qr_bytes(student_url), use_container_width=True)
        st.link_button("🌱 Гүл отырғызу", student_url, use_container_width=True)

    @st.fragment(run_every="3s")
    def live_garden():
        rows = all_discoveries()
        st.markdown('<div class="live-mark">🟢 LIVE · Жаңа гүлдер автоматты түрде пайда болады</div>', unsafe_allow_html=True)
        st.markdown(stats_html(len(rows)), unsafe_allow_html=True)
        components.html(garden_document(rows), height=700, scrolling=False)
        with st.expander("💬 Барлық пікірлерді оқу"):
            if not rows:
                st.info("Бақ әзірге бос. Алғашқы гүлді күтеміз!")
            for r in rows:
                st.markdown(f'**🌼 {esc(r["student_name"])}**')
                st.write(r["fact_text"])

    live_garden()


def student_page(wall_url):
    header("СТУДЕНТ ПАРАҒЫ")
    st.markdown('''<div class="garden-hero"><h1>Өз гүліңді <span>өсір!</span> 🌷</h1>
    <p>Бүгінгі сабақ туралы пікіріңді жаз. Әр жауап бақта әдемі гүлге айналады!</p></div>''', unsafe_allow_html=True)
    left, right = st.columns([1.8, 1], gap="large")
    with left:
        st.markdown('<div class="form-blurb">🌱 Атыңды жаз, сабақ туралы ойыңмен бөліс және өз гүліңді отырғыз!</div>', unsafe_allow_html=True)
        with st.form("seed_form", clear_on_submit=True):
            name = st.text_input("👤 Атың кім?", max_chars=40, placeholder="Мысалы: Айдана")
            feedback = st.text_area("💬 Сабақ туралы пікірің", max_chars=500, height=165,
                                    placeholder="Сабақ маған ұнады, себебі... / Мен үшін ең қызығы... / Мен әлі де ... білгім келеді.")
            clicked = st.form_submit_button("🌱 Гүл отырғызу", use_container_width=True)
        if clicked:
            try:
                add_feedback(name, feedback)
            except FileExistsError:
                st.warning("Бұл атпен гүл бар екен. Пікіріңді өзгерткің келсе, мұғалімге айт.")
            except ValueError:
                st.warning("Атың 2–40, ал пікірің 3–500 таңба болуы керек.")
            except sqlite3.Error:
                st.error("Пікір сақталмады. Қайта көріп көр немесе мұғалімге айт.")
            else:
                st.success(f"🎉 {name.strip()}, сенің гүлің бақта пайда болды!")
                st.balloons()
        st.link_button("🌼 Ортақ бақты көру", wall_url, use_container_width=True)
    with right:
        st.markdown(info_html(), unsafe_allow_html=True)


def admin_page(wall_url):
    header("МҰҒАЛІМ ПАНЕЛІ")
    try:
        secret = str(st.secrets.get("ADMIN_PASSWORD", ""))
    except Exception:
        secret = ""  # No local .streamlit/secrets.toml in development.
    secret = secret or os.environ.get("ADMIN_PASSWORD", "")
    if not secret:
        st.error("Алдымен Streamlit Cloud → App settings → Secrets ішінде ADMIN_PASSWORD орнат.")
        return
    if not st.session_state.get("garden_admin_ok", False):
        with st.form("admin_login"):
            password = st.text_input("🔐 Құпиясөз", type="password")
            submit = st.form_submit_button("Кіру")
        if submit:
            if hmac.compare_digest(password, secret):
                st.session_state["garden_admin_ok"] = True
                st.rerun()
            else:
                st.error("Құпиясөз қате.")
        return

    rows = all_discoveries()
    st.markdown(stats_html(len(rows)), unsafe_allow_html=True)
    st.download_button("⬇️ Пікірлерді CSV ретінде сақтау", data=export_csv(rows),
                       file_name="genetic_garden_feedback.csv", mime="text/csv", disabled=not rows)
    st.caption("Маңызды: Streamlit Cloud-та жергілікті SQLite деректері қайта іске қосылғанда жоғалуы мүмкін.")

    st.subheader("🌸 Бір гүлді өшіру")
    if rows:
        by_id = {r["id"]:r for r in rows}
        choice = st.selectbox("Гүлді таңда", list(by_id),
                              format_func=lambda k: f'#{k} · {by_id[k]["student_name"]} · {by_id[k]["fact_text"][:65]}')
        if st.button("Таңдалған гүлді өшіру"):
            with db() as conn:
                conn.execute("DELETE FROM discoveries WHERE id=?", (choice,))
            st.rerun()
    else:
        st.info("Әзірге гүл жоқ.")

    st.divider()
    st.subheader("🧹 Бақтың деректерін тазалау")
    if st.checkbox("Барлық пікірді жоюды растаймын"):
        if st.button("Бақтағы барлық гүлді өшіру", type="primary"):
            with db() as conn:
                conn.execute("DELETE FROM discoveries")
            st.rerun()
    st.link_button("↗ Ортақ баққа өту", wall_url)


def main():
    init_db()
    st.markdown(APP_CSS, unsafe_allow_html=True)
    wall_url, student_url, _ = urls()
    view = st.query_params.get("view", "wall")
    if view == "student":
        student_page(wall_url)
    elif view == "admin":
        admin_page(wall_url)
    else:
        wall_page(student_url)


if __name__ == "__main__":
    main()
