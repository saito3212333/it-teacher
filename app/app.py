import re
import streamlit as st
import yaml
import gspread
from pathlib import Path
from datetime import datetime
from google.oauth2.service_account import Credentials
import streamlit.components.v1 as components

APP_DIR = Path(__file__).resolve().parent


def check_password():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    if st.session_state.authenticated:
        return True

    st.title("パソコン教室")
    pw = st.text_input("パスワードを入力してください", type="password")
    if pw:
        try:
            correct = st.secrets["password"]
        except Exception:
            correct = ""
        if pw == correct:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("パスワードが違います")
    st.stop()
LESSONS_DIR = APP_DIR.parent / "lessons"
QUIZ_DATA_DIR = APP_DIR / "quiz_data"

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def get_sheet():
    creds = Credentials.from_service_account_info(
        st.secrets["gcp_service_account"], scopes=SCOPES
    )
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["sheet_id"]).sheet1


def save_answers(session_date: str, answers: dict, questions: list):
    try:
        sheet = get_sheet()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        rows = [
            [
                timestamp,
                session_date,
                q["id"],
                answers.get(q["id"], ""),
                "○" if answers.get(q["id"]) == q["answer"] else "×",
            ]
            for q in questions
        ]
        sheet.append_rows(rows)
    except Exception as e:
        st.warning(f"回答の保存に失敗しました: {e}")


def render_mermaid(diagram: str):
    height = 450 if "sequenceDiagram" in diagram else 300
    html = f"""
    <!DOCTYPE html><html><body style="margin:0;padding:10px;">
    <script src="https://cdn.jsdelivr.net/npm/mermaid@10/dist/mermaid.min.js"></script>
    <div class="mermaid">{diagram}</div>
    <script>mermaid.initialize({{startOnLoad:true,theme:'default'}});</script>
    </body></html>
    """
    components.html(html, height=height)


def render_lesson(content: str):
    parts = re.split(r"```mermaid\n(.*?)\n```", content, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if i % 2 == 0:
            if part.strip():
                st.markdown(part)
        else:
            render_mermaid(part.strip())


# ---- App ----

st.set_page_config(page_title="パソコン教室", layout="wide")
check_password()
st.title("パソコン教室")

sessions = sorted([f.stem for f in LESSONS_DIR.glob("*.md")], reverse=True)
if not sessions:
    st.warning("授業ノートがありません。")
    st.stop()

labels = {s: f"第{len(sessions) - i}回　{s}" for i, s in enumerate(sessions)}
selected = st.sidebar.selectbox("授業を選ぶ", sessions, format_func=lambda s: labels[s])

tab1, tab2 = st.tabs(["授業ノート", "クイズ"])

# ---- 授業ノート ----
with tab1:
    lesson_path = LESSONS_DIR / f"{selected}.md"
    if lesson_path.exists():
        render_lesson(lesson_path.read_text(encoding="utf-8"))
    else:
        st.warning("授業ノートが見つかりません。")

# ---- クイズ ----
with tab2:
    quiz_path = QUIZ_DATA_DIR / f"{selected}.yaml"
    if not quiz_path.exists():
        st.info("このセッションのクイズはまだありません。")
        st.stop()

    with open(quiz_path, encoding="utf-8") as f:
        quiz = yaml.safe_load(f)

    questions = quiz["questions"]
    st.subheader(f"クイズ：{selected}")

    answers = {}
    with st.form("quiz_form"):
        for q in questions:
            st.markdown(f"**Q{q['id']}. {q['question']}**")
            options = [f"{k}. {v}" for k, v in q["options"].items()]
            choice = st.radio("選択肢", options, key=f"q{q['id']}", label_visibility="collapsed")
            answers[q["id"]] = choice[0]
            st.markdown("---")

        submitted = st.form_submit_button("提出する", use_container_width=True)

    if submitted:
        score = sum(1 for q in questions if answers.get(q["id"]) == q["answer"])
        total = len(questions)

        st.subheader(f"結果：{score} / {total} 問正解")

        for q in questions:
            user = answers.get(q["id"])
            is_ok = user == q["answer"]
            icon = "○" if is_ok else "×"
            st.markdown(f"{icon} **Q{q['id']}** — あなたの答え: **{user}** / 正解: **{q['answer']}**")
            if not is_ok:
                st.caption(q.get("explanation", ""))

        save_answers(selected, answers, questions)
        st.success("回答を保存しました。")
