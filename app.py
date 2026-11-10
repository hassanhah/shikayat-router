import os, json, sqlite3, uuid, hashlib
from datetime import datetime
import pandas as pd
import streamlit as st

DB = "shikayat.db"
MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
DEPARTMENTS = {
    "Pani": "Public Health Engineering (PHED)",
    "Gas": "SNGPL / Gas Department",
    "Bijli": "PESCO",
    "Sadak": "Communication & Works (C&W)",
    "Safai": "Water & Sanitation Services (WSSC)",
    "Other": "District Administration",
}

# ---------- Database ----------
def db():
    con = sqlite3.connect(DB)
    con.execute("""CREATE TABLE IF NOT EXISTS complaints(
        id TEXT PRIMARY KEY, created TEXT, text TEXT, category TEXT,
        department TEXT, urgency TEXT, location TEXT, summary TEXT, status TEXT)""")
    con.execute("CREATE TABLE IF NOT EXISTS settings(key TEXT PRIMARY KEY, value TEXT)")
    return con

def hash_pw(p):
    return hashlib.sha256(p.encode()).hexdigest()

def stored_pw_hash():
    con = db()
    row = con.execute("SELECT value FROM settings WHERE key='admin_pass'").fetchone()
    con.close()
    return row[0] if row else hash_pw(os.getenv("DASH_PASS", "admin123"))

def set_pw(new):
    con = db()
    con.execute("INSERT OR REPLACE INTO settings VALUES ('admin_pass', ?)", (hash_pw(new),))
    con.commit(); con.close()

# ---------- AI classification ----------
PROMPT = """You classify citizen complaints from Khyber Pakhtunkhwa written in Pashto, Urdu, Roman Urdu or English.
Return ONLY JSON with keys:
category (one of: Pani, Gas, Bijli, Sadak, Safai, Other),
urgency (High, Medium, Low),
location (place mentioned, or "Unknown"),
summary (one short English sentence).
Complaint: """

def keyword_fallback(text):
    t = text.lower()
    rules = {"Pani": ["pani", "پاني", "پانی", "water"], "Gas": ["gas", "گیس", "ګاز"],
             "Bijli": ["bijli", "light", "بجلی", "electric"], "Sadak": ["sadak", "road", "سڑک", "سړک"],
             "Safai": ["safai", "kachra", "گندگی", "waste", "gutter", "nali"]}
    for cat, words in rules.items():
        if any(w in t for w in words):
            return {"category": cat, "urgency": "Medium", "location": "Unknown", "summary": text[:100]}
    return {"category": "Other", "urgency": "Low", "location": "Unknown", "summary": text[:100]}

def classify(text):
    key = os.getenv("ANTHROPIC_API_KEY")
    if not key:
        return keyword_fallback(text)
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key)
        r = client.messages.create(model=MODEL, max_tokens=300,
                                   messages=[{"role": "user", "content": PROMPT + text}])
        raw = r.content[0].text.strip().replace("```json", "").replace("```", "")
        data = json.loads(raw)
        if data.get("category") not in DEPARTMENTS:
            data["category"] = "Other"
        return data
    except Exception:
        return keyword_fallback(text)

# ---------- UI ----------
st.set_page_config(page_title="Shikayat Router", page_icon="📮", layout="wide")
STYLE = """
<link href="https://fonts.googleapis.com/css2?family=Baloo+2:wght@500;700;800&family=Nunito:wght@400;600;700&display=swap" rel="stylesheet">
<style>
:root{--ink:#10262B;--teal:#0E4B4F;--mint:#EAF4F1;--gold:#F4B223;--red:#D9482B;--paper:#FFFFFF;}
html, body, [class*="css"], .stApp{font-family:'Nunito',sans-serif;color:var(--ink);}
.stApp{background:linear-gradient(180deg,#EAF4F1 0%,#F7FBFA 60%);}
h1,h2,h3,.hero h1{font-family:'Baloo 2',sans-serif !important;}
.block-container{padding-top:1.2rem;max-width:980px;}
header[data-testid="stHeader"]{background:transparent;}

/* Hero with truck-art stripe */
.hero{background:var(--teal);color:#fff;border-radius:22px;padding:28px 28px 22px;position:relative;overflow:hidden;margin-bottom:18px;}
.hero:before{content:"";position:absolute;left:0;right:0;bottom:0;height:12px;
 background:repeating-linear-gradient(90deg,var(--gold) 0 18px,var(--red) 18px 36px,#fff 36px 54px,var(--teal) 54px 72px);}
.hero h1{margin:0;font-size:2.3rem;line-height:1.1;color:#fff;}
.hero p{margin:8px 0 6px;font-size:1.05rem;opacity:.92;max-width:560px;}
.hero .steps{display:flex;gap:10px;flex-wrap:wrap;margin-top:12px;font-size:.92rem;}
.hero .steps span{background:rgba(255,255,255,.14);padding:5px 12px;border-radius:999px;}

/* Tabs */
.stTabs [data-baseweb="tab-list"]{gap:8px;}
.stTabs [data-baseweb="tab"]{background:#fff;border-radius:12px 12px 0 0;padding:10px 18px;font-weight:700;border:1px solid #D5E5E1;border-bottom:none;}
.stTabs [aria-selected="true"]{background:var(--gold) !important;color:var(--ink) !important;}
.stTabs [data-baseweb="tab-highlight"]{display:none;}

/* Inputs & buttons */
textarea, input{border-radius:14px !important;}
.stButton>button{background:var(--teal);color:#fff;border:none;border-radius:14px;padding:.6rem 1.4rem;font-weight:700;font-family:'Baloo 2',sans-serif;font-size:1.05rem;}
.stButton>button:hover{background:var(--red);color:#fff;}
.stButton>button:focus-visible{outline:3px solid var(--gold);}

/* Ticket (result after submit) */
.ticket{display:flex;background:#fff;border-radius:18px;border:2px dashed var(--teal);margin:14px 0;overflow:hidden;}
.ticket .stub{background:var(--gold);padding:18px 20px;text-align:center;min-width:170px;display:flex;flex-direction:column;justify-content:center;}
.ticket .stub small{font-weight:700;}
.ticket .stub b{font-family:'Baloo 2',sans-serif;font-size:1.55rem;letter-spacing:1px;}
.ticket .body{padding:16px 20px;flex:1;}
.ticket .row{display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;}
.chip{padding:4px 12px;border-radius:999px;font-weight:700;font-size:.9rem;background:var(--mint);color:var(--teal);}
.chip.High{background:#FCE3DD;color:var(--red);}
.chip.Medium{background:#FFF1CF;color:#8A5B00;}
.chip.Low{background:#E1F3E7;color:#1E6B3A;}
@media (max-width:640px){.ticket{flex-direction:column}.hero h1{font-size:1.8rem}}

/* Metrics */
[data-testid="stMetric"]{background:#fff;border-radius:16px;padding:14px 18px;border-top:6px solid var(--gold);box-shadow:0 2px 10px rgba(16,38,43,.06);}
[data-testid="stSidebar"]{background:var(--teal);}
[data-testid="stSidebar"] *{color:#fff !important;}
</style>
"""
# blank lines break Streamlit's HTML block, so remove them
STYLE = "\n".join(l for l in STYLE.splitlines() if l.strip())
st.markdown(STYLE, unsafe_allow_html=True)
st.markdown("""
<div class="hero">
  <h1>📮 Shikayat Router</h1>
  <p>Apni shikayat apni zubaan mein likhein. Hum usay sahi mehkame tak pohanchate hain.</p>
  <div class="steps"><span>1. Shikayat likhein</span><span>2. AI mehkama chunta hai</span><span>3. ID se track karein</span></div>
</div>
""", unsafe_allow_html=True)

ICONS = {"Pani": "💧", "Gas": "🔥", "Bijli": "⚡", "Sadak": "🛣️", "Safai": "🧹", "Other": "📋"}

mode = st.sidebar.radio("Mode", ["Shehri (Citizen)", "Mehkama (Department)"])

def citizen_view():
    tab1, tab2 = st.tabs(["Shikayat Bhejein", "Track Karein"])
    with tab1:
        text = st.text_area("Aap ki shikayat", height=140,
                            placeholder="Misal: Pir Sabaq mein 3 din se pani nahi aa raha...")
        if st.button("Bhejein", type="primary") and text.strip():
            with st.spinner("AI shikayat samajh raha hai..."):
                r = classify(text)
            cid = "KP-" + uuid.uuid4().hex[:6].upper()
            con = db()
            con.execute("INSERT INTO complaints VALUES (?,?,?,?,?,?,?,?,?)",
                        (cid, datetime.now().strftime("%Y-%m-%d %H:%M"), text, r["category"],
                         DEPARTMENTS[r["category"]], r["urgency"], r["location"], r["summary"], "Pending"))
            con.commit(); con.close()
            st.markdown(f"""
<div class="ticket">
  <div class="stub"><small>Tracking ID</small><b>{cid}</b><small>Isay save kar lein</small></div>
  <div class="body">
    <b>Shikayat darj ho gayi</b><br>{r['summary']}
    <div class="row">
      <span class="chip">{ICONS[r['category']]} {r['category']}</span>
      <span class="chip">{DEPARTMENTS[r['category']]}</span>
      <span class="chip {r['urgency']}">Urgency: {r['urgency']}</span>
      <span class="chip">📍 {r['location']}</span>
    </div>
  </div>
</div>""", unsafe_allow_html=True)
    with tab2:
        tid = st.text_input("Tracking ID", placeholder="KP-XXXXXX").strip().upper()
        if tid:
            df = pd.read_sql("SELECT * FROM complaints WHERE id=?", db(), params=(tid,))
            if df.empty:
                st.warning("Yeh ID nahi mili.")
            else:
                row = df.iloc[0]
                st.markdown(f"""
<div class="ticket">
  <div class="stub"><small>Status</small><b>{row['status']}</b></div>
  <div class="body"><b>{row['id']}</b><br>{row['summary']}
    <div class="row"><span class="chip">{ICONS.get(row['category'], '📋')} {row['category']}</span>
    <span class="chip">{row['department']}</span></div></div>
</div>""", unsafe_allow_html=True)

def department_view():
    pwd = st.sidebar.text_input("Mehkama password", type="password")
    if hash_pw(pwd) != stored_pw_hash():
        st.info("Dashboard dekhne ke liye sidebar mein password likhein (demo password: admin123).")
        return
    st.subheader("Dashboard (Mehkama)")
    with st.expander("Password badlein"):
        old = st.text_input("Purana password", type="password", key="old_pw")
        new1 = st.text_input("Naya password", type="password", key="new_pw1")
        new2 = st.text_input("Naya password dobara", type="password", key="new_pw2")
        if st.button("Password change karein"):
            if hash_pw(old) != stored_pw_hash():
                st.error("Purana password ghalat hai.")
            elif len(new1) < 6:
                st.error("Naya password kam az kam 6 characters ka ho.")
            elif new1 != new2:
                st.error("Dono naye password match nahi karte.")
            else:
                set_pw(new1)
                st.success("Password badal gaya. Sidebar mein ab naya password likhein.")
    df = pd.read_sql("SELECT * FROM complaints ORDER BY created DESC", db())
    if df.empty:
        st.info("Abhi koi shikayat nahi.")
        return
    c1, c2, c3 = st.columns(3)
    c1.metric("Kul shikayat", len(df))
    c2.metric("Pending", int((df.status == "Pending").sum()))
    c3.metric("High urgency", int((df.urgency == "High").sum()))
    st.bar_chart(df["category"].value_counts())
    dept = st.selectbox("Mehkama filter", ["Sab"] + sorted(df.department.unique()))
    view = df if dept == "Sab" else df[df.department == dept]
    st.dataframe(view[["id", "created", "category", "urgency", "location", "summary", "status"]],
                 use_container_width=True)
    cid = st.selectbox("Status badlein (ID)", view["id"].tolist())
    new = st.selectbox("Naya status", ["Pending", "In Progress", "Resolved"])
    if st.button("Update"):
        con = db(); con.execute("UPDATE complaints SET status=? WHERE id=?", (new, cid))
        con.commit(); con.close(); st.rerun()

if mode.startswith("Shehri"):
    citizen_view()
else:
    department_view()
