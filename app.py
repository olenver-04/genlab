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

st.set_page_config(
    page_title="CHROM X | Генетикалық зертхана",
    page_icon="🧬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DB_PATH = Path(__file__).with_name("genetics_lab.db")
SECTIONS = {
    "chromosomal": {
        "emoji": "🧬",
        "title": "Хромосомалық теория",
        "short": "Теория",
        "accent": "#57D6FF",
        "glow": "rgba(87,214,255,.34)",
        "bg": "rgba(32,58,92,.88)",
        "placeholder": "Мысалы: Хромосомалар гендердің тасымалдаушысы болып табылады.",
    },
    "allelic": {
        "emoji": "🧪",
        "title": "Аллельді гендер",
        "short": "Аллельді",
        "accent": "#8CF5C8",
        "glow": "rgba(140,245,200,.34)",
        "bg": "rgba(28,70,66,.90)",
        "placeholder": "Мысалы: Доминантты және рецессивті аллельдер белгінің көрінуіне әсер етеді.",
    },
    "nonallelic": {
        "emoji": "🔬",
        "title": "Аллельді емес гендер",
        "short": "Аллельді емес",
        "accent": "#C8A7FF",
        "glow": "rgba(200,167,255,.34)",
        "bg": "rgba(55,42,84,.92)",
        "placeholder": "Мысалы: Эпистаз кезінде бір ген екіншісінің әсерін басуы мүмкін.",
    },
}
DISPLAY_PER_SECTION = 6


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
    with db() as conn:
        conn.execute(
            """CREATE TABLE IF NOT EXISTS discoveries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_name TEXT NOT NULL,
                section_key TEXT NOT NULL,
                fact_text TEXT NOT NULL,
                created_at TEXT NOT NULL
            )"""
        )


def add_discovery(name: str, section_key: str, fact_text: str):
    name = " ".join(name.split())
    fact_text = " ".join(fact_text.split())
    if section_key not in SECTIONS:
        raise ValueError("Unknown section")
    if not (2 <= len(name) <= 40 and 6 <= len(fact_text) <= 220):
        raise ValueError("Invalid input")
    with db() as conn:
        conn.execute(
            "INSERT INTO discoveries(student_name, section_key, fact_text, created_at) VALUES (?, ?, ?, ?)",
            (name, section_key, fact_text, datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )


def list_discoveries(section_key: str | None = None, limit: int = 1000):
    with db() as conn:
        if section_key and section_key != "all":
            return conn.execute(
                "SELECT * FROM discoveries WHERE section_key=? ORDER BY id DESC LIMIT ?",
                (section_key, limit),
            ).fetchall()
        return conn.execute(
            "SELECT * FROM discoveries ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


def counts():
    data = {key: 0 for key in SECTIONS}
    with db() as conn:
        for row in conn.execute("SELECT section_key, COUNT(*) AS n FROM discoveries GROUP BY section_key"):
            if row["section_key"] in data:
                data[row["section_key"]] = row["n"]
    return data


def delete_discovery(item_id: int):
    with db() as conn:
        conn.execute("DELETE FROM discoveries WHERE id=?", (item_id,))


def clear_discoveries(section_key: str = "all"):
    with db() as conn:
        if section_key == "all":
            conn.execute("DELETE FROM discoveries")
        else:
            conn.execute("DELETE FROM discoveries WHERE section_key=?", (section_key,))


def csv_safe(value: str):
    value = str(value)
    return "'" + value if value.lstrip().startswith(("=", "+", "-", "@")) else value


def export_csv(rows):
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["№", "Оқушының аты", "Секция", "Ашылым / факт", "Уақыты (UTC)"])
    for item in rows:
        section = SECTIONS.get(item["section_key"], {})
        writer.writerow([
            item["id"],
            csv_safe(item["student_name"]),
            section.get("title", item["section_key"]),
            csv_safe(item["fact_text"]),
            item["created_at"],
        ])
    return out.getvalue().encode("utf-8-sig")


def esc(text: str):
    return html.escape(str(text), quote=True)


def qr_image(url: str):
    qr = qrcode.QRCode(box_size=11, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#061222", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def urls():
    base = st.context.url.split("?", 1)[0].rstrip("/") + "/"
    return base, base + "?view=student", base + "?view=admin"


CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700;800&family=Orbitron:wght@500;700;800&display=swap');
:root {
    --bg:#06111f; --bg2:#0c1c30; --text:#e9f2ff; --muted:#96adcc;
    --panel:#102033; --line:rgba(174,214,255,.16); --card:#0f1b2f;
}
html, body, [class*="css"], .stApp, .stApp input, .stApp textarea, .stApp button { font-family:'Manrope', sans-serif; }
.stApp {
    color:var(--text);
    background:
        radial-gradient(700px 460px at 8% 8%, rgba(86,214,255,.10), transparent 65%),
        radial-gradient(720px 500px at 94% 4%, rgba(160,131,255,.12), transparent 65%),
        radial-gradient(620px 420px at 55% 100%, rgba(140,245,200,.08), transparent 70%),
        linear-gradient(180deg, #06111f 0%, #09192b 100%);
}
#MainMenu, footer {visibility:hidden;}
[data-testid="stHeader"] {background:transparent;}
.block-container {max-width:1380px; padding-top:1.15rem; padding-bottom:2.7rem;}
.brandline {color:#9ac7ff; font-size:.82rem; letter-spacing:.16em; font-weight:800; text-transform:uppercase; margin-bottom:14px;}
.hero {
    position:relative; overflow:hidden; border:1px solid rgba(144,195,255,.14);
    border-radius:28px; padding:30px 34px; min-height:250px;
    background:linear-gradient(135deg, rgba(14,29,50,.96), rgba(16,37,66,.94));
    box-shadow:0 20px 44px rgba(0,0,0,.24);
}
.hero::after{
    content:''; position:absolute; inset:auto -60px -100px auto; width:280px; height:280px; border-radius:50%;
    background:radial-gradient(circle, rgba(87,214,255,.24), transparent 65%); filter:blur(6px);
}
.hero h1{font-family:'Orbitron', sans-serif; font-size:clamp(2rem,4.1vw,3.6rem); line-height:1.15; margin:10px 0 12px; color:#f6fbff;}
.hero h1 em{font-style:normal; color:#86eaff;}
.hero p{max-width:920px; color:#bcd0ea; line-height:1.75; font-size:1rem; margin:0;}
.qr-panel{
    border:1px solid rgba(145,200,255,.14); border-radius:26px; background:rgba(10,24,43,.92);
    padding:18px 18px 12px; text-align:center; box-shadow:0 16px 34px rgba(0,0,0,.22);
}
.qr-head{font-size:.78rem; font-weight:800; color:#8cf5c8; letter-spacing:.12em; text-transform:uppercase; margin-bottom:10px;}
.stats{display:grid; grid-template-columns:repeat(4,1fr); gap:12px; margin:18px 0 14px;}
.stat-card{border:1px solid rgba(145,200,255,.14); border-radius:20px; background:rgba(10,24,43,.88); padding:14px 16px;}
.stat-card .k{font-size:.82rem; color:#90aac9; font-weight:700;}
.stat-card .v{font-family:'Orbitron', sans-serif; font-size:1.65rem; margin-top:6px; color:#f8fbff;}
.lab-shell{
    border:1px solid rgba(145,200,255,.15); border-radius:30px; overflow:hidden; padding:18px; background:rgba(8,20,36,.78); box-shadow:0 18px 38px rgba(0,0,0,.23);
}
.lab-board{display:grid; grid-template-columns:1fr 1.1fr 1fr; gap:16px; align-items:stretch;}
.module{
    position:relative; border-radius:26px; border:1px solid rgba(160,215,255,.16); padding:18px 16px 16px;
    min-height:430px; box-shadow:inset 0 0 0 1px rgba(255,255,255,.02), 0 14px 26px rgba(0,0,0,.20);
}
.module::before{
    content:''; position:absolute; inset:0; border-radius:26px; pointer-events:none;
    box-shadow:0 0 0 1px rgba(255,255,255,.02), 0 0 35px var(--glow);
    opacity:.9;
}
.module-head{display:flex; justify-content:space-between; gap:10px; align-items:flex-start; margin-bottom:12px;}
.module-title{font-size:1.02rem; font-weight:800; color:#f4f8ff; line-height:1.35;}
.module-badge{padding:6px 10px; border-radius:999px; background:rgba(255,255,255,.08); color:#dfeeff; font-size:.74rem; font-weight:800; white-space:nowrap;}
.module-sub{font-size:.82rem; color:#aec2dc; line-height:1.5; margin-bottom:12px;}
.discovery-list{display:grid; gap:10px;}
.discovery{
    border:1px solid rgba(255,255,255,.08); background:rgba(7,17,30,.34); border-radius:18px; padding:11px 12px;
}
.discovery.new{outline:2px solid currentColor; box-shadow:0 0 24px currentColor; animation:pulse 1.1s ease-out 1;}
@keyframes pulse {0%{transform:scale(.96); opacity:.6;} 60%{transform:scale(1.02); opacity:1;} 100%{transform:scale(1);}}
.discovery-name{font-size:.78rem; text-transform:uppercase; letter-spacing:.08em; font-weight:800; opacity:.9; margin-bottom:6px;}
.discovery-text{font-size:.93rem; line-height:1.52; color:#eef6ff;}
.empty-box{border:1px dashed rgba(255,255,255,.16); border-radius:18px; padding:18px 14px; color:#a6bed8; text-align:center; font-size:.92rem; background:rgba(7,17,30,.26);}
.center-core{
    position:relative; border-radius:30px; min-height:430px; border:1px solid rgba(145,200,255,.15);
    background:
      radial-gradient(circle at 50% 24%, rgba(87,214,255,.14), transparent 26%),
      radial-gradient(circle at 50% 80%, rgba(200,167,255,.14), transparent 27%),
      linear-gradient(180deg, rgba(15,31,54,.98), rgba(7,18,33,.96));
    overflow:hidden;
}
.core-grid{position:absolute; inset:0; background-image:linear-gradient(rgba(255,255,255,.03) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.03) 1px, transparent 1px); background-size:22px 22px; opacity:.35;}
.lab-label{position:absolute; top:16px; left:20px; font-size:.78rem; letter-spacing:.18em; text-transform:uppercase; color:#85dff6; font-weight:800;}
.core-title{position:absolute; top:44px; left:20px; right:20px; font-family:'Orbitron', sans-serif; font-size:1.4rem; line-height:1.35; color:#f6fbff;}
.core-title span{color:#91f2cb;}
.helix-wrap{position:absolute; inset:120px 18px 120px; display:flex; align-items:center; justify-content:center;}
.helix { width:100%; max-width:250px; height:100%; position:relative; }
.strand{ position:absolute; top:0; bottom:0; width:2px; background:linear-gradient(180deg, transparent, rgba(87,214,255,.85), rgba(200,167,255,.86), transparent); left:50%; transform-origin:center; }
.left-nodes, .right-nodes {position:absolute; inset:0;}
.node{ position:absolute; width:16px; height:16px; border-radius:50%; box-shadow:0 0 18px currentColor; }
.bridge{ position:absolute; height:3px; transform-origin:left center; border-radius:999px; opacity:.88; }
.core-info{position:absolute; left:20px; right:20px; bottom:18px; display:grid; gap:12px;}
.info-chip{border:1px solid rgba(255,255,255,.08); border-radius:18px; background:rgba(7,16,30,.5); padding:12px 14px; color:#c6d7ee;}
.info-chip b{color:#f4fbff;}
.legend{display:flex; flex-wrap:wrap; gap:10px;}
.legend-item{padding:8px 11px; border-radius:999px; background:rgba(255,255,255,.07); font-size:.76rem; font-weight:800; color:#dbeaff; border:1px solid rgba(255,255,255,.08);}
.section-kicker{font-size:.78rem; text-transform:uppercase; letter-spacing:.14em; color:#89cfff; font-weight:800; margin-top:24px; margin-bottom:10px;}
.note-box{border:1px solid rgba(145,200,255,.14); border-radius:22px; background:rgba(10,24,43,.88); padding:18px 20px; color:#bcd0ea; line-height:1.72;}
.form-help{border:1px solid rgba(145,200,255,.14); border-radius:22px; background:rgba(11,24,43,.88); padding:18px 20px; color:#bcd0ea; line-height:1.72; margin-bottom:20px;}
.form-help strong{display:block; color:#f2f8ff; font-size:1.08rem; margin-bottom:8px;}
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea, div[data-baseweb="select"] > div {
    background:#0d1a2c !important; border:1px solid rgba(145,200,255,.16) !important; color:#f0f6ff !important; border-radius:16px !important;
}
[data-testid="stWidgetLabel"] p{color:#d9e8fb; font-weight:700;}
[data-testid="stFormSubmitButton"] button, .stButton button[kind="primary"]{
    background:linear-gradient(90deg, #55d6ff, #8ef2cb); color:#081320; border:0; min-height:3.1rem; border-radius:14px; font-weight:900;
}
.stButton button, .stDownloadButton button, .stLinkButton a {border-radius:14px; font-weight:800;}
.livebar{display:flex; justify-content:space-between; align-items:center; gap:12px; flex-wrap:wrap; margin:12px 0 16px;}
.livebadge{display:inline-flex; align-items:center; gap:9px; padding:8px 13px; border-radius:999px; border:1px solid rgba(145,200,255,.18); background:rgba(255,255,255,.05); font-size:.76rem; font-weight:800; color:#8cf5c8;}
.livebadge::before{content:''; width:8px; height:8px; border-radius:50%; background:#69ecb5; box-shadow:0 0 0 5px rgba(105,236,181,.18);}
.footerline{text-align:center; font-size:.8rem; letter-spacing:.12em; text-transform:uppercase; color:#89a8c8; margin-top:18px;}
@media (max-width:1100px){ .stats{grid-template-columns:repeat(2,1fr);} .lab-board{grid-template-columns:1fr;} .module,.center-core{min-height:unset;} .helix-wrap{position:relative; inset:auto; min-height:280px; margin-top:110px; margin-bottom:20px;} }

/* CHROM X identity — keeps the original three-module classroom layout. */
.site-mark{display:flex;align-items:center;gap:16px;flex-wrap:wrap;margin:3px 0 18px;padding:10px 16px;
  border:1px solid rgba(128,230,231,.14);border-radius:16px;background:linear-gradient(90deg,rgba(16,37,61,.82),rgba(13,23,44,.40));}
.site-wordmark{font-family:'Orbitron','Manrope',sans-serif;letter-spacing:.095em;font-weight:800;font-size:1.25rem;color:#f8fcff;white-space:nowrap}
.site-wordmark span{color:#71e8ec;text-shadow:0 0 20px rgba(96,232,236,.54)}
.site-section{font-size:.72rem;color:#9fb9d3;font-weight:800;letter-spacing:.10em;text-transform:uppercase;flex:1}
.site-indicator{font-family:'Manrope',sans-serif;font-weight:800;font-size:.67rem;letter-spacing:.10em;color:#96ecd1;white-space:nowrap}
.site-indicator i{display:inline-block;width:7px;height:7px;border-radius:50%;background:#71f1c5;box-shadow:0 0 13px #71f1c5;margin-right:8px}
.hero-branded{background:radial-gradient(circle at 100% 30%,rgba(82,213,232,.12),transparent 32%),
   linear-gradient(110deg,#101d35 4%,#142849 64%,#0d2135 100%);border-color:rgba(121,232,226,.25);}
.hero-branded:before{content:'X';position:absolute;right:12px;top:-94px;font-family:'Orbitron',sans-serif;font-weight:800;
   font-size:clamp(10rem,22vw,21rem);line-height:1;color:rgba(110,226,237,.047);pointer-events:none;transform:rotate(-10deg)}
.hero h1.chrom-main{font-family:'Orbitron','Manrope',sans-serif;font-size:clamp(2.9rem,6vw,5.4rem);font-weight:800;
   letter-spacing:.045em;line-height:1.08;color:#f9fbff;position:relative;z-index:1;margin:7px 0 13px}
.hero h1.chrom-main em{color:#70e6e8;text-shadow:0 0 26px rgba(91,238,236,.34)}
.hero-subtitle{color:#e9fbff;font-size:clamp(1.02rem,1.5vw,1.2rem);font-weight:800;margin:0 0 13px;line-height:1.5;position:relative;z-index:1}
.hero-subtitle span{color:#a9bfd9;font-weight:600}
.hero-tech{display:flex;flex-wrap:wrap;gap:8px;margin-top:19px;position:relative;z-index:1}
.hero-tech span{font-size:.63rem;letter-spacing:.085em;color:#91e4de;background:rgba(95,214,220,.08);
   border:1px solid rgba(97,216,221,.18);padding:7px 10px;border-radius:7px;font-weight:800}
.core-title.chrom-core{font-family:'Orbitron',sans-serif;font-size:clamp(1.6rem,2.5vw,2.25rem);font-weight:800;
   letter-spacing:.06em;top:44px;text-shadow:0 0 24px rgba(80,216,240,.20)}
.core-title.chrom-core span{color:#76f0e3}
.core-subtitle{position:absolute;top:105px;left:20px;right:20px;font-size:.83rem;line-height:1.45;color:#b5cae3;font-weight:650}
.helix-wrap{inset:148px 18px 110px}
@media(max-width:1100px){.helix-wrap{position:relative;inset:auto;margin-top:158px}}
@media(max-width:650px){.site-indicator{display:none}.site-section{font-size:.62rem}.hero-tech{gap:5px}.hero-tech span{font-size:.57rem}}
</style>
"""


def header(label: str):
    st.markdown(
        '<div class="site-mark"><div class="site-wordmark">CHROM <span>X</span></div>'
        f'<div class="site-section">/ {esc(label)}</div>'
        '<div class="site-indicator"><i></i> GENETICS LAB · LIVE</div></div>',
        unsafe_allow_html=True,
    )


def discovery_html(item, is_new=False):
    sec = SECTIONS[item["section_key"]]
    cls = "discovery new" if is_new else "discovery"
    style = f'color:{sec["accent"]};'
    return (
        f'<div class="{cls}" style="{style}">'
        f'<div class="discovery-name">{esc(item["student_name"])} · {sec["emoji"]} {esc(sec["short"])}</div>'
        f'<div class="discovery-text">{esc(item["fact_text"])}</div>'
        '</div>'
    )


def render_section_module(key: str, rows, fresh_ids: set[int]):
    sec = SECTIONS[key]
    cards = ''.join(discovery_html(item, int(item['id']) in fresh_ids) for item in rows[:DISPLAY_PER_SECTION])
    if not cards:
        cards = '<div class="empty-box">Әзірге бұл бөлімде ашылым жоқ.<br>Оқушылардың алғашқы ғылыми фактісін күтіңіз.</div>'
    return (
        f'<section class="module" style="--glow:{sec["glow"]}; background:{sec["bg"]};">'
        '<div class="module-head">'
        f'<div><div class="module-title">{sec["emoji"]} {esc(sec["title"])}</div>'
        f'<div class="module-sub">Оқушылардың осы бағыт бойынша жіберген маңызды ойлары мен фактілері.</div></div>'
        f'<div class="module-badge">{len(rows)} жазба</div></div>'
        f'<div class="discovery-list">{cards}</div>'
        '</section>'
    )


def render_center_core(total: int, count_map: dict[str, int]):
    # Prebuilt helix nodes as HTML blocks
    nodes = []
    total_nodes = 12
    left_x, right_x = 34, 66
    top = 8
    gap = 7.2
    colors = ["#57D6FF", "#8CF5C8", "#C8A7FF", "#57D6FF", "#8CF5C8", "#C8A7FF"]
    for i in range(total_nodes):
        y = top + i * gap
        shift = 10 if i % 2 == 0 else -10
        lx = left_x + shift
        rx = right_x - shift
        c = colors[i % len(colors)]
        nodes.append(f'<div class="node" style="left:calc({lx}% - 8px); top:{y}%; color:{c}; background:{c};"></div>')
        nodes.append(f'<div class="node" style="left:calc({rx}% - 8px); top:{y}%; color:{c}; background:{c};"></div>')
        width = abs(rx - lx)
        angle = 10 if i % 2 == 0 else -10
        nodes.append(f'<div class="bridge" style="left:{min(lx, rx)}%; top:calc({y}% + 6px); width:{width}%; background:linear-gradient(90deg, {c}, rgba(255,255,255,.92), {c}); transform:rotate({angle}deg);"></div>')
    legend = ''.join(
        f'<div class="legend-item">{SECTIONS[k]["emoji"]} {esc(SECTIONS[k]["title"])} — <b>{count_map[k]}</b></div>'
        for k in SECTIONS
    )
    return (
        '<section class="center-core">'
        '<div class="core-grid"></div>'
        '<div class="lab-label">CHROM X · LIVE RESEARCH</div>'
        '<div class="core-title chrom-core">CHROM <span>X</span></div>'
        '<div class="core-subtitle">Генетикалық зертхана<br>Жас генетиктердің ғылыми ашылымдары</div>'
        '<div class="helix-wrap"><div class="helix">'
        + ''.join(nodes) +
        '</div></div>'
        '<div class="core-info">'
        f'<div class="info-chip"><b>Ортақ прогресс:</b> Бүгін зертханаға енгізілген ғылыми ашылымдар саны — <b>{total}</b>.</div>'
        '<div class="legend">' + legend + '</div>'
        '</div></section>'
    )


def wall_page(student_url: str):
    header("ИНТЕРАКТИВТІ ЗЕРТХАНА")
    left, right = st.columns([4.7, 1.35], gap="large", vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="hero hero-branded">'
            '<div class="brandline" style="margin-bottom:8px;color:#8cf5c8;">✦ INTERACTIVE GENETICS LAB · ЖАС ГЕНЕТИКТЕР АЛАҢЫ</div>'
            '<h1 class="chrom-main">CHROM <em>X</em></h1>'
            '<div class="hero-subtitle">🧬 Генетикалық зертхана <span>· Жас генетиктердің ғылыми ашылымдары</span></div>'
            '<p>Үш ғылыми бағыттың бірін таңдап, өзің білетін маңызды фактіні бөліс. '
            'Сенің ашылымың тиісті зертханалық модульде бірден пайда болады.</p>'
            '<div class="hero-tech"><span>01 · ХРОМОСОМАЛЫҚ ТЕОРИЯ</span><span>02 · АЛЛЕЛЬДІ ГЕНДЕР</span><span>03 · АЛЛЕЛЬДІ ЕМЕС</span></div>'
            '</div>',
            unsafe_allow_html=True,
        )
    with right:
        st.markdown('<div class="qr-panel"><div class="qr-head">📱 QR-КОД АРҚЫЛЫ ҚАТЫСУ</div></div>', unsafe_allow_html=True)
        st.image(qr_image(student_url), use_container_width=True)
        st.link_button("✍️ Ашылым енгізу", student_url, use_container_width=True)

    @st.fragment(run_every="2s")
    def live_lab():
        all_rows = list_discoveries(limit=300)
        count_map = counts()
        total = len(all_rows)
        prev = st.session_state.get("prev_genetics_ids")
        ids = {int(r["id"]) for r in all_rows}
        fresh = ids - prev if prev is not None else set()
        st.session_state["prev_genetics_ids"] = ids
        st.markdown(
            '<div class="livebar">'
            '<div class="livebadge">LIVE · Жаңа ашылымдар автоматты түрде қосылады</div>'
            f'<div style="color:#b9cfea;font-size:.95rem;font-weight:700;">Жауаптар: <b style="color:#fff">{total}</b></div>'
            '</div>',
            unsafe_allow_html=True,
        )
        stats_html = (
            '<div class="stats">'
            f'<div class="stat-card"><div class="k">Барлық ашылым</div><div class="v">{total}</div></div>'
            f'<div class="stat-card"><div class="k">🧬 Хромосомалық теория</div><div class="v">{count_map["chromosomal"]}</div></div>'
            f'<div class="stat-card"><div class="k">🧪 Аллельді гендер</div><div class="v">{count_map["allelic"]}</div></div>'
            f'<div class="stat-card"><div class="k">🔬 Аллельді емес гендер</div><div class="v">{count_map["nonallelic"]}</div></div>'
            '</div>'
        )
        st.markdown(stats_html, unsafe_allow_html=True)

        grouped = {key: [] for key in SECTIONS}
        for row in all_rows:
            if row["section_key"] in grouped:
                grouped[row["section_key"]].append(row)

        lab_html = (
            '<div class="lab-shell"><div class="lab-board">'
            + render_section_module("chromosomal", grouped["chromosomal"], fresh)
            + render_center_core(total, count_map)
            + render_section_module("allelic", grouped["allelic"], fresh)
            + '</div>'
            + '<div style="margin-top:16px;">'
            + render_section_module("nonallelic", grouped["nonallelic"], fresh)
            + '</div></div>'
        )
        st.markdown(lab_html, unsafe_allow_html=True)
        if total == 0:
            st.markdown('<div class="note-box">🧬 Зертхана әзірге бос тұр. QR-кодты сканерлеп, бірінші ғылыми ашылымды енгізіңіз.</div>', unsafe_allow_html=True)
        else:
            with st.expander("📜 Соңғы ашылымдарды тізіммен көру"):
                for row in all_rows[:20]:
                    sec = SECTIONS[row["section_key"]]
                    st.markdown(f'**{esc(row["student_name"])}** · {sec["emoji"]} {esc(sec["title"])}  \\\n{esc(row["fact_text"])}')
        st.markdown('<div class="footerline">CHROM X · БІР ЗЕРТХАНА · ҮШ БАҒЫТ · ОРТАҚ БІЛІМ</div>', unsafe_allow_html=True)

    live_lab()


def student_page(wall_url: str):
    header("ОҚУШЫ ПАРАҒЫ")
    st.markdown(
        '<div class="hero hero-branded">'
        '<div class="brandline" style="margin-bottom:8px;color:#8cf5c8;">🧪 CHROM X · YOUNG RESEARCHER</div>'
        '<h1 class="chrom-main">CHROM <em>X</em></h1>'
        '<div class="hero-subtitle">🔬 Зертханаға өз ашылымыңды қос!</div>'
        '<p>Үш ғылыми секцияның бірін таңда, содан кейін сабақтан есте қалған бір маңызды фактіні немесе қысқа ойды жібер.</p>'
        '</div>',
        unsafe_allow_html=True,
    )
    left, right = st.columns([1.9, 1], gap="large")
    with left:
        st.markdown(
            '<div class="form-help"><strong>🔬 Қалай қатысамын?</strong>'
            '1. Атыңды енгіз.<br>2. Қажетті ғылыми бағытты таңда.<br>3. Бір маңызды факт немесе қысқа ой жаз.<br>4. «Зертханаға қосу» батырмасын бас.</div>',
            unsafe_allow_html=True,
        )
        with st.form("genetics_form", clear_on_submit=True):
            name = st.text_input("👤 Атың", placeholder="Мысалы: Айдана", max_chars=40)
            section_key = st.selectbox(
                "🧭 Ғылыми секцияны таңда",
                options=list(SECTIONS.keys()),
                format_func=lambda key: f'{SECTIONS[key]["emoji"]} {SECTIONS[key]["title"]}',
            )
            fact_text = st.text_area(
                "💡 Бір маңызды факт немесе ой",
                placeholder=SECTIONS[section_key]["placeholder"],
                max_chars=220,
                height=150,
            )
            submitted = st.form_submit_button("🚀 Зертханаға қосу", use_container_width=True)
        if submitted:
            try:
                add_discovery(name, section_key, fact_text)
            except ValueError:
                st.warning("Атыңды кемі 2 әріппен, ал фактіңді 6–220 таңба аралығында толтыр.")
            except sqlite3.Error:
                st.error("Жауапты сақтау мүмкін болмады. Қайта жіберіп көр.")
            else:
                st.success(f'🎉 Жарайсың, {name.strip()}! Сенің ашылымың {SECTIONS[section_key]["title"]} бөліміне қосылды.')
                st.balloons()
        st.link_button("👀 Ортақ зертхананы көру", wall_url, use_container_width=True)
    with right:
        st.markdown('<div class="note-box"><b>Үш секция:</b><br><br>'
                    '🧬 <b>Хромосомалық теория</b><br>Тұқымқуалаушылықтың хромосомалармен байланысы.<br><br>'
                    '🧪 <b>Аллельді гендер</b><br>Доминанттылық, рецессивтілік, генотип пен фенотип.<br><br>'
                    '🔬 <b>Аллельді емес гендер</b><br>Комплементарлық, эпистаз, полимерия және өзара әрекеттесу.</div>', unsafe_allow_html=True)
        st.markdown('<div class="section-kicker">Үлгі ойлар</div>', unsafe_allow_html=True)
        for key in SECTIONS:
            sec = SECTIONS[key]
            st.markdown(f'<div class="note-box" style="margin-top:8px;"><b>{sec["emoji"]} {esc(sec["title"])}:</b><br>{esc(sec["placeholder"])}</div>', unsafe_allow_html=True)


def admin_page(wall_url: str):
    header("МҰҒАЛІМ ПАНЕЛІ")
    secret = str(st.secrets.get("ADMIN_PASSWORD", os.environ.get("ADMIN_PASSWORD", "")))
    if not secret:
        st.error("ADMIN_PASSWORD Streamlit Secrets ішінде орнатылмаған.")
        return
    if not st.session_state.get("genetics_admin_ok"):
        with st.form("admin_login"):
            pwd = st.text_input("Құпиясөз", type="password")
            ok = st.form_submit_button("Кіру")
        if ok:
            if hmac.compare_digest(pwd, secret):
                st.session_state["genetics_admin_ok"] = True
                st.rerun()
            else:
                st.error("Құпиясөз қате.")
        return

    st.success("Панель ашық. Мұнда жауаптарды басқара аласыз.")
    rows = list_discoveries(limit=1000)
    count_map = counts()
    total = len(rows)
    st.markdown(
        '<div class="stats">'
        f'<div class="stat-card"><div class="k">Барлық ашылым</div><div class="v">{total}</div></div>'
        f'<div class="stat-card"><div class="k">🧬 Теория</div><div class="v">{count_map["chromosomal"]}</div></div>'
        f'<div class="stat-card"><div class="k">🧪 Аллельді</div><div class="v">{count_map["allelic"]}</div></div>'
        f'<div class="stat-card"><div class="k">🔬 Аллельді емес</div><div class="v">{count_map["nonallelic"]}</div></div>'
        '</div>',
        unsafe_allow_html=True,
    )
    st.download_button(
        "⬇️ CSV жүктеу",
        data=export_csv(rows),
        file_name="genetics_lab_discoveries.csv",
        mime="text/csv",
        use_container_width=True,
        disabled=not rows,
    )
    st.caption("CSV ішінде оқушының аты, секциясы, жазған фактісі және уақыты бар.")

    st.divider()
    st.subheader("🗑️ Бір жауапты өшіру")
    if rows:
        by_id = {int(r["id"]): r for r in rows}
        selected = st.selectbox(
            "Жауапты таңда",
            list(by_id.keys()),
            format_func=lambda key: f'#{key} · {by_id[key]["student_name"]} · {SECTIONS[by_id[key]["section_key"]]["short"]} · {by_id[key]["fact_text"][:55]}',
        )
        if st.button("Таңдалған жауапты жою"):
            delete_discovery(int(selected))
            st.rerun()
    else:
        st.info("Әзірге жауап жоқ.")

    st.divider()
    st.subheader("🧹 Тазалау")
    clear_choice = st.radio(
        "Қай бөлімді тазалаймыз?",
        options=["all", *SECTIONS.keys()],
        format_func=lambda key: "Барлық зертхана" if key == "all" else f'{SECTIONS[key]["emoji"]} {SECTIONS[key]["title"]}',
        horizontal=False,
    )
    confirm = st.checkbox("Иә, таңдалған бөлімдегі жазбаларды біржола жойғым келеді.")
    if st.button("Тазалау", disabled=not confirm or not rows):
        clear_discoveries(clear_choice)
        st.rerun()
    st.info("SQLite тегін Streamlit Cloud-та уақытша сақталады. Сабақ соңында CSV сақтап алған дұрыс.")
    st.link_button("↗ Ортақ экран", wall_url)


def main():
    init_db()
    st.markdown(CSS, unsafe_allow_html=True)
    wall_url, student_url, admin_url = urls()
    view = st.query_params.get("view", "wall")
    if view == "student":
        student_page(wall_url)
    elif view == "admin":
        admin_page(wall_url)
    else:
        wall_page(student_url)


if __name__ == "__main__":
    main()

