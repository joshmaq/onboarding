"""
Onboarding Hub — Streamlit dashboard version of the onboarding workbook.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py
"""
import os
import sqlite3
from datetime import date, datetime

import pandas as pd
import streamlit as st

DB_PATH = os.path.join(os.path.dirname(__file__), "onboarding.db")
PASS_THRESHOLD = 0.8  # 80% to pass the quiz

st.set_page_config(page_title="Onboarding Hub", page_icon="🧭", layout="wide")

# =========================================================
# DATABASE
# =========================================================
def get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS modules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            category TEXT NOT NULL,
            has_import_template INTEGER NOT NULL DEFAULT 0,
            description TEXT
        );
        CREATE TABLE IF NOT EXISTS employees (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            start_date TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS tracker (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            module_id INTEGER NOT NULL REFERENCES modules(id),
            video_watched INTEGER NOT NULL DEFAULT 0,
            video_watch_date TEXT,
            template_reviewed TEXT NOT NULL DEFAULT 'No',
            faq_reviewed INTEGER NOT NULL DEFAULT 0,
            notes TEXT,
            UNIQUE(employee_id, module_id)
        );
        CREATE TABLE IF NOT EXISTS videos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            title TEXT NOT NULL,
            duration TEXT,
            link TEXT,
            description TEXT,
            sort_order INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS quiz_questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            question TEXT NOT NULL,
            option_a TEXT, option_b TEXT, option_c TEXT, option_d TEXT,
            correct_answer TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS quiz_attempts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            employee_id INTEGER NOT NULL REFERENCES employees(id),
            question_id INTEGER NOT NULL REFERENCES quiz_questions(id),
            answer_given TEXT NOT NULL,
            is_correct INTEGER NOT NULL,
            attempted_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS faqs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            question TEXT NOT NULL,
            answer TEXT NOT NULL,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS import_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module_id INTEGER NOT NULL REFERENCES modules(id),
            file_name TEXT,
            location TEXT,
            required_fields TEXT,
            last_updated TEXT,
            notes TEXT
        );
        CREATE TABLE IF NOT EXISTS demo_scripts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            scenario TEXT NOT NULL,
            title TEXT NOT NULL,
            talking_points TEXT,
            audience TEXT,
            last_updated TEXT
        );
        """
    )
    conn.commit()
    return conn


def seed_if_empty(conn):
    if conn.execute("SELECT COUNT(*) FROM modules").fetchone()[0] > 0:
        return

    modules = [
        ("Entities", "Core", 1, "The backbone module — every filing, document, bank account, and form ties back to an entity."),
        ("Filings", "Core", 1, "Tracks regulatory/compliance filings and their due dates."),
        ("Documents", "Core", 1, "Central document repository linked to entities."),
        ("Org Chart", "Core", 1, "Visual ownership/management structure for each entity."),
        ("Users & Permissions", "Core", 0, "User accounts, roles, and access control. Set up manually per client."),
        ("Bank & Bank Accounts", "Core", 1, "Tracks banking relationships and accounts tied to entities."),
        ("Forms", "Core", 1, "Tracks required forms per entity/filing."),
        ("Calendar", "Cross-Cutting", 0, "Rolls up key dates from filings, forms, and other date-driven modules."),
        ("Tasks", "Side", 0, "Task management and assignment."),
        ("Personnel", "Side", 0, "Personnel records tied to entities/org chart."),
        ("Setup", "Side", 0, "Client/tenant configuration."),
        ("Audit", "Side", 0, "Change history and audit trail."),
    ]
    conn.executemany(
        "INSERT INTO modules (name, category, has_import_template, description) VALUES (?,?,?,?)",
        modules,
    )
    conn.commit()
    mod_ids = {name: mid for mid, name in conn.execute("SELECT id, name FROM modules")}

    employees = [("Jane Smith", "2026-09-08"), ("Alex Ramirez", "2026-09-15")]
    conn.executemany("INSERT INTO employees (name, start_date) VALUES (?,?)", employees)
    conn.commit()
    emp_ids = {name: eid for eid, name in conn.execute("SELECT id, name FROM employees")}

    for eid in emp_ids.values():
        for mid in mod_ids.values():
            conn.execute(
                "INSERT OR IGNORE INTO tracker (employee_id, module_id) VALUES (?,?)", (eid, mid)
            )
    conn.commit()

    videos = [
        ("Entities", "Entities 101: Creating & Managing Entities", "8 min", "Help Center > Entities > Getting Started", "Core walkthrough of creating an entity and its key fields.", 1),
        ("Entities", "Bulk Importing Entities", "6 min", "Help Center > Entities > Bulk Import", "How to use the Entities import template.", 2),
        ("Filings", "Filings Overview", "7 min", "Help Center > Filings", "Tracking filing due dates and statuses.", 3),
        ("Documents", "Document Management Basics", "6 min", "Help Center > Documents", "Uploading, tagging, and linking documents to entities.", 4),
        ("Org Chart", "Building an Org Chart", "5 min", "Help Center > Org Chart", "Visualizing ownership/management structure.", 5),
        ("Bank & Bank Accounts", "Bank Accounts Setup", "5 min", "Help Center > Bank Accounts", "Linking bank accounts to entities.", 6),
        ("Forms", "Managing Forms", "6 min", "Help Center > Forms", "Tracking required forms per entity.", 7),
        ("Users & Permissions", "Users & Permissions", "9 min", "Help Center > Admin > Users", "Setting up roles and access levels.", 8),
        ("Calendar", "Using the Calendar", "4 min", "Help Center > Calendar", "How dates roll up into the calendar.", 9),
        ("Tasks", "Task Management", "5 min", "Help Center > Tasks", "Assigning and tracking tasks.", 10),
        ("Personnel", "Personnel Records", "4 min", "Help Center > Personnel", "Managing personnel tied to entities.", 11),
        ("Audit", "Audit Trail Basics", "3 min", "Help Center > Audit", "Reviewing change history.", 12),
    ]
    conn.executemany(
        "INSERT INTO videos (module_id, title, duration, link, description, sort_order) VALUES (?,?,?,?,?,?)",
        [(mod_ids[m], t, d, l, desc, o) for m, t, d, l, desc, o in videos],
    )

    questions = [
        ("Entities", "What do all filings, documents, and bank accounts link back to?", "Org Chart", "Entities", "Calendar", "Tasks", "B"),
        ("Entities", "Fastest way to add 100 entities at once?", "Enter one by one", "Use the Entities bulk import template", "Email support", "Not possible", "B"),
        ("Filings", "Where do upcoming filing due dates automatically appear?", "Audit tab", "Calendar", "Personnel", "Setup", "B"),
        ("Documents", "Can a document link to more than one entity?", "No", "Yes", "Only PDFs", "Only with approval", "B"),
        ("Org Chart", "What does the Org Chart module visualize?", "Task assignments", "Ownership/management structure", "Bank balances", "Filing deadlines", "B"),
        ("Bank & Bank Accounts", "Does this module have a bulk import template?", "Yes", "No", "Only for savings", "Only for admins", "A"),
        ("Forms", "What does the Forms module track?", "Login history", "Required forms per entity/filing", "Marketing forms", "None of the above", "B"),
        ("Users & Permissions", "Does Users & Permissions have a bulk import template?", "Yes", "No — set up manually", "Only Enterprise", "Only for admins", "B"),
        ("Calendar", "Where do Calendar dates come from?", "Manually entered only", "Rolled up from filings, forms, etc.", "Imported from Outlook only", "They don't sync", "B"),
        ("Tasks", "What is the Tasks module used for?", "Filing taxes", "Assigning and tracking work items", "Storing documents", "Managing bank accounts", "B"),
        ("Audit", "What does the Audit module show?", "Upcoming birthdays", "Change history / audit trail", "Marketing scripts", "Video tutorials", "B"),
        ("Setup", "What is configured in the Setup module?", "User passwords", "Client/tenant configuration", "Bank routing numbers", "Org chart colors", "B"),
    ]
    conn.executemany(
        "INSERT INTO quiz_questions (module_id, question, option_a, option_b, option_c, option_d, correct_answer) VALUES (?,?,?,?,?,?,?)",
        [(mod_ids[m], q, a, b, c, d, ans) for m, q, a, b, c, d, ans in questions],
    )

    faqs = [
        ("Entities", "What's the difference between an entity and a filing?", "An entity is the legal organization itself; a filing is a compliance document/deadline tied to that entity.", "General"),
        ("Entities", "Can I bulk import entities?", "Yes — use the Entities import template.", "Technical"),
        ("Filings", "How are filing due dates set?", "Set when the filing record is created; they automatically appear on the Calendar.", "General"),
        ("Documents", "What file types can I upload?", "PDF, DOCX, XLSX, and common image formats.", "Technical"),
        ("Users & Permissions", "Why can't I bulk import users?", "Intentionally manual for security — each user is set up individually.", "General"),
        ("Calendar", "Can I filter the calendar by module?", "Yes, use the module filter at the top of the Calendar view.", "Technical"),
    ]
    conn.executemany(
        "INSERT INTO faqs (module_id, question, answer, category) VALUES (?,?,?,?)",
        [(mod_ids[m], q, a, c) for m, q, a, c in faqs],
    )

    templates = [
        ("Entities", "Entities_Import_Template.xlsx", "Help Center > Entities > Bulk Import", "Entity Name, Entity Type, Jurisdiction, Status"),
        ("Filings", "Filings_Import_Template.xlsx", "Help Center > Filings > Bulk Import", "Entity, Filing Type, Due Date, Status"),
        ("Documents", "Documents_Import_Template.xlsx", "Help Center > Documents > Bulk Import", "Entity, Document Type, File Reference, Tags"),
        ("Org Chart", "OrgChart_Import_Template.xlsx", "Help Center > Org Chart > Bulk Import", "Entity, Parent Entity, Ownership %, Role"),
        ("Bank & Bank Accounts", "BankAccounts_Import_Template.xlsx", "Help Center > Bank Accounts > Bulk Import", "Entity, Bank Name, Account Number, Account Type"),
        ("Forms", "Forms_Import_Template.xlsx", "Help Center > Forms > Bulk Import", "Entity, Form Type, Due Date, Status"),
    ]
    conn.executemany(
        "INSERT INTO import_templates (module_id, file_name, location, required_fields, last_updated, notes) VALUES (?,?,?,?,?,?)",
        [(mod_ids[m], f, l, rf, "2026-08-01", "") for m, f, l, rf in templates],
    )

    scripts = [
        ("Entities", "Why Entities is the backbone", "Every filing, document, bank account, and form ties back to an entity — one system of record instead of scattered spreadsheets.", "Prospective clients"),
        ("Filings", "Never miss a deadline", "Filings auto-populate the Calendar, so nothing falls through the cracks — show the calendar view live.", "Prospective clients"),
        ("Documents", "One place for every document", "Documents link directly to entities and filings, eliminating shared-drive hunting.", "Prospective clients"),
        ("Bulk Import (all modules)", "Fast migration story", "Most modules support a bulk-import template, so switching from spreadsheets takes days, not months.", "Prospective clients"),
    ]
    conn.executemany(
        "INSERT INTO demo_scripts (scenario, title, talking_points, audience, last_updated) VALUES (?,?,?,?,?)",
        [(s, t, tp, a, "2026-08-01") for s, t, tp, a in scripts],
    )
    conn.commit()


conn = init_db()
seed_if_empty(conn)


# =========================================================
# DATA HELPERS
# =========================================================
def df(query, params=()):
    return pd.read_sql_query(query, conn, params=params)


def modules_df():
    return df("SELECT * FROM modules ORDER BY category, name")


def employees_df():
    return df("SELECT * FROM employees ORDER BY start_date")


def ensure_tracker_rows(employee_id):
    mods = conn.execute("SELECT id FROM modules").fetchall()
    for (mid,) in mods:
        conn.execute(
            "INSERT OR IGNORE INTO tracker (employee_id, module_id) VALUES (?,?)",
            (employee_id, mid),
        )
    conn.commit()


def tracker_df_for_employee(employee_id):
    q = """
    SELECT t.id, m.name AS module, m.category, m.has_import_template,
           t.video_watched, t.video_watch_date, t.template_reviewed,
           t.faq_reviewed, t.notes
    FROM tracker t JOIN modules m ON m.id = t.module_id
    WHERE t.employee_id = ?
    ORDER BY m.category, m.name
    """
    d = df(q, (employee_id,))
    d["video_watched"] = d["video_watched"].astype(bool)
    d["faq_reviewed"] = d["faq_reviewed"].astype(bool)
    d["has_import_template"] = d["has_import_template"].astype(bool)

    def status(row):
        template_ok = row["template_reviewed"] == "Yes" or not row["has_import_template"]
        if row["video_watched"] and template_ok and row["faq_reviewed"]:
            return "Complete"
        return "In Progress"

    d["status"] = d.apply(status, axis=1)
    return d


def quiz_score(employee_id):
    q = """
    SELECT COUNT(*) AS attempted, SUM(is_correct) AS correct
    FROM quiz_attempts WHERE employee_id = ?
    """
    row = df(q, (employee_id,)).iloc[0]
    attempted = int(row["attempted"] or 0)
    correct = int(row["correct"] or 0)
    pct = correct / attempted if attempted else None
    return attempted, correct, pct


def overall_progress_df():
    emps = employees_df()
    rows = []
    for _, e in emps.iterrows():
        t = tracker_df_for_employee(e["id"])
        total = len(t)
        complete = (t["status"] == "Complete").sum()
        pct_complete = complete / total if total else 0
        attempted, correct, quiz_pct = quiz_score(e["id"])
        quiz_status = "Not started" if quiz_pct is None else ("Pass" if quiz_pct >= PASS_THRESHOLD else "Fail")
        overall = "Onboarding Complete" if pct_complete == 1 and quiz_status == "Pass" else "In Progress"
        days = (date.today() - datetime.strptime(e["start_date"], "%Y-%m-%d").date()).days
        rows.append(
            {
                "Employee": e["name"],
                "Start Date": e["start_date"],
                "Modules Complete": f"{complete}/{total}",
                "% Complete": pct_complete,
                "Quiz Score": "—" if quiz_pct is None else f"{quiz_pct:.0%}",
                "Quiz Status": quiz_status,
                "Overall Status": overall,
                "Days Since Start": days,
            }
        )
    return pd.DataFrame(rows)


# =========================================================
# SIDEBAR NAVIGATION
# =========================================================
st.sidebar.title("🧭 Onboarding Hub")
page = st.sidebar.radio(
    "Go to",
    [
        "🏠 Home",
        "🧩 Module Reference",
        "✅ Onboarding Tracker",
        "🎥 Training Videos",
        "🧠 Knowledge Quiz",
        "❓ FAQ",
        "📥 Import Templates",
        "🎤 Demo Scripts",
        "📊 Overall Progress",
    ],
)

emps = employees_df()
st.sidebar.divider()
st.sidebar.subheader("Current employee")
if emps.empty:
    st.sidebar.info("Add an employee on the Onboarding Tracker page.")
    selected_emp_id = None
else:
    emp_name = st.sidebar.selectbox("Viewing as", emps["name"])
    selected_emp_id = int(emps.loc[emps["name"] == emp_name, "id"].iloc[0])

with st.sidebar.expander("➕ Add new employee"):
    new_name = st.text_input("Name", key="new_emp_name")
    new_start = st.date_input("Start date", value=date.today(), key="new_emp_start")
    if st.button("Add employee"):
        if new_name.strip():
            try:
                conn.execute(
                    "INSERT INTO employees (name, start_date) VALUES (?,?)",
                    (new_name.strip(), new_start.isoformat()),
                )
                conn.commit()
                eid = conn.execute(
                    "SELECT id FROM employees WHERE name = ?", (new_name.strip(),)
                ).fetchone()[0]
                ensure_tracker_rows(eid)
                st.success(f"Added {new_name}.")
                st.rerun()
            except sqlite3.IntegrityError:
                st.error("That name already exists.")
        else:
            st.warning("Enter a name first.")


# =========================================================
# PAGES
# =========================================================
if page == "🏠 Home":
    st.title("Onboarding Hub")
    st.caption("The single onboarding home for new hires — replaces the onboarding workbook.")
    st.markdown(
        """
        **How to use it:** work through *Onboarding Tracker* module by module, watching videos and
        reviewing import templates as you go, then take the *Knowledge Quiz*. Managers can check
        *Overall Progress* any time for a live view of every hire.

        **Scaling it up:** add a new module on the *Module Reference* page and it instantly shows up
        as an option everywhere else — Tracker, Videos, Quiz, FAQ, Import Templates, Demo Scripts.
        """
    )
    prog = overall_progress_df()
    if not prog.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Employees onboarding", len(prog))
        c2.metric("Avg. % modules complete", f"{prog['% Complete'].mean():.0%}")
        completed = (prog["Overall Status"] == "Onboarding Complete").sum()
        c3.metric("Fully onboarded", f"{completed}/{len(prog)}")

elif page == "🧩 Module Reference":
    st.title("Module Reference")
    st.caption("Master list of every module. Add a row here when the software adds a module — it flows everywhere else automatically.")
    st.dataframe(modules_df().drop(columns=["id"]), use_container_width=True, hide_index=True)
    with st.expander("➕ Add a module"):
        with st.form("add_module"):
            name = st.text_input("Module name")
            category = st.selectbox("Category", ["Core", "Side", "Cross-Cutting"])
            has_tpl = st.checkbox("Has import template?")
            desc = st.text_area("Description")
            if st.form_submit_button("Add module"):
                if name.strip():
                    try:
                        conn.execute(
                            "INSERT INTO modules (name, category, has_import_template, description) VALUES (?,?,?,?)",
                            (name.strip(), category, int(has_tpl), desc),
                        )
                        conn.commit()
                        mid = conn.execute("SELECT id FROM modules WHERE name=?", (name.strip(),)).fetchone()[0]
                        for (eid,) in conn.execute("SELECT id FROM employees"):
                            conn.execute(
                                "INSERT OR IGNORE INTO tracker (employee_id, module_id) VALUES (?,?)", (eid, mid)
                            )
                        conn.commit()
                        st.success(f"Added {name}.")
                        st.rerun()
                    except sqlite3.IntegrityError:
                        st.error("That module already exists.")

elif page == "✅ Onboarding Tracker":
    st.title("Onboarding Tracker")
    if selected_emp_id is None:
        st.info("Add an employee in the sidebar to get started.")
    else:
        st.caption(f"Checklist for **{emp_name}** — tick off as each module is covered.")
        t = tracker_df_for_employee(selected_emp_id)
        edited = st.data_editor(
            t[["module", "category", "has_import_template", "video_watched", "template_reviewed", "faq_reviewed", "notes", "status"]],
            column_config={
                "module": st.column_config.TextColumn("Module", disabled=True),
                "category": st.column_config.TextColumn("Category", disabled=True),
                "has_import_template": st.column_config.CheckboxColumn("Has Template?", disabled=True),
                "video_watched": st.column_config.CheckboxColumn("Video Watched?"),
                "template_reviewed": st.column_config.SelectboxColumn("Template Reviewed?", options=["Yes", "No", "N/A"]),
                "faq_reviewed": st.column_config.CheckboxColumn("FAQ Reviewed?"),
                "notes": st.column_config.TextColumn("Notes"),
                "status": st.column_config.TextColumn("Status (auto)", disabled=True),
            },
            hide_index=True,
            use_container_width=True,
            key="tracker_editor",
        )
        if st.button("💾 Save changes"):
            for i, row in edited.iterrows():
                tid = int(t.iloc[i]["id"])
                conn.execute(
                    """UPDATE tracker SET video_watched=?, template_reviewed=?, faq_reviewed=?, notes=?
                       WHERE id=?""",
                    (int(row["video_watched"]), row["template_reviewed"], int(row["faq_reviewed"]), row["notes"], tid),
                )
            conn.commit()
            st.success("Saved.")
            st.rerun()

elif page == "🎥 Training Videos":
    st.title("Training Videos")
    mods = ["All"] + modules_df()["name"].tolist()
    pick = st.selectbox("Filter by module", mods)
    q = """SELECT m.name AS Module, v.title AS Title, v.duration AS Duration,
                  v.link AS Location, v.description AS Description
           FROM videos v JOIN modules m ON m.id = v.module_id"""
    params = ()
    if pick != "All":
        q += " WHERE m.name = ?"
        params = (pick,)
    q += " ORDER BY v.sort_order"
    st.dataframe(df(q, params), use_container_width=True, hide_index=True)
    with st.expander("➕ Add a video"):
        with st.form("add_video"):
            mod = st.selectbox("Module", modules_df()["name"])
            title = st.text_input("Video title")
            duration = st.text_input("Duration (e.g. 6 min)")
            link = st.text_input("Link / location")
            desc = st.text_area("Description")
            if st.form_submit_button("Add video"):
                mid = int(modules_df().set_index("name").loc[mod, "id"])
                conn.execute(
                    "INSERT INTO videos (module_id, title, duration, link, description, sort_order) VALUES (?,?,?,?,?,99)",
                    (mid, title, duration, link, desc),
                )
                conn.commit()
                st.success("Added.")
                st.rerun()

elif page == "🧠 Knowledge Quiz":
    st.title("Knowledge Quiz")
    if selected_emp_id is None:
        st.info("Add an employee in the sidebar to take the quiz.")
    else:
        st.caption(f"Taking the quiz as **{emp_name}**. {int(PASS_THRESHOLD*100)}% needed to pass.")
        questions = df(
            """SELECT q.id, m.name AS module, q.question, q.option_a, q.option_b,
                      q.option_c, q.option_d, q.correct_answer
               FROM quiz_questions q JOIN modules m ON m.id = q.module_id ORDER BY m.name, q.id"""
        )
        answers = {}
        with st.form("quiz_form"):
            for _, r in questions.iterrows():
                label = f"**[{r['module']}]** {r['question']}"
                answers[r["id"]] = st.radio(
                    label,
                    options=["A", "B", "C", "D"],
                    format_func=lambda x, row=r: f"{x}. {row[f'option_{x.lower()}']}",
                    key=f"q_{r['id']}",
                    index=None,
                )
            submitted = st.form_submit_button("Submit quiz")
        if submitted:
            now = datetime.now().isoformat()
            correct_count = 0
            attempted = 0
            for _, r in questions.iterrows():
                ans = answers.get(r["id"])
                if ans is None:
                    continue
                attempted += 1
                is_correct = int(ans == r["correct_answer"])
                correct_count += is_correct
                conn.execute(
                    "INSERT INTO quiz_attempts (employee_id, question_id, answer_given, is_correct, attempted_at) VALUES (?,?,?,?,?)",
                    (selected_emp_id, int(r["id"]), ans, is_correct, now),
                )
            conn.commit()
            pct = correct_count / attempted if attempted else 0
            if pct >= PASS_THRESHOLD:
                st.success(f"Score: {correct_count}/{attempted} ({pct:.0%}) — Pass ✅")
            else:
                st.error(f"Score: {correct_count}/{attempted} ({pct:.0%}) — Fail, try again")

        attempted, correct, pct = quiz_score(selected_emp_id)
        if attempted:
            st.divider()
            st.subheader("Latest results on record")
            c1, c2, c3 = st.columns(3)
            c1.metric("Questions attempted", attempted)
            c2.metric("Correct", correct)
            c3.metric("Score", f"{pct:.0%}", delta="Pass" if pct >= PASS_THRESHOLD else "Fail")

elif page == "❓ FAQ":
    st.title("FAQ")
    mods = ["All"] + modules_df()["name"].tolist()
    pick = st.selectbox("Filter by module", mods)
    search = st.text_input("Search")
    q = """SELECT m.name AS Module, f.question AS Question, f.answer AS Answer, f.category AS Category
           FROM faqs f JOIN modules m ON m.id = f.module_id"""
    d = df(q)
    if pick != "All":
        d = d[d["Module"] == pick]
    if search:
        mask = d["Question"].str.contains(search, case=False) | d["Answer"].str.contains(search, case=False)
        d = d[mask]
    st.dataframe(d, use_container_width=True, hide_index=True)
    with st.expander("➕ Add an FAQ"):
        with st.form("add_faq"):
            mod = st.selectbox("Module", modules_df()["name"], key="faq_mod")
            question = st.text_input("Question")
            answer = st.text_area("Answer")
            category = st.selectbox("Category", ["General", "Technical"])
            if st.form_submit_button("Add FAQ"):
                mid = int(modules_df().set_index("name").loc[mod, "id"])
                conn.execute(
                    "INSERT INTO faqs (module_id, question, answer, category) VALUES (?,?,?,?)",
                    (mid, question, answer, category),
                )
                conn.commit()
                st.success("Added.")
                st.rerun()

elif page == "📥 Import Templates":
    st.title("Import Templates")
    q = """SELECT m.name AS Module, t.file_name AS "File Name", t.location AS Location,
                  t.required_fields AS "Required Fields", t.last_updated AS "Last Updated", t.notes AS Notes
           FROM import_templates t JOIN modules m ON m.id = t.module_id ORDER BY m.name"""
    st.dataframe(df(q), use_container_width=True, hide_index=True)
    with st.expander("➕ Add a template entry"):
        with st.form("add_template"):
            mod = st.selectbox("Module", modules_df()["name"], key="tpl_mod")
            fname = st.text_input("File name")
            loc = st.text_input("Location / link")
            fields = st.text_area("Required fields (summary)")
            if st.form_submit_button("Add"):
                mid = int(modules_df().set_index("name").loc[mod, "id"])
                conn.execute(
                    "INSERT INTO import_templates (module_id, file_name, location, required_fields, last_updated, notes) VALUES (?,?,?,?,?,?)",
                    (mid, fname, loc, fields, date.today().isoformat(), ""),
                )
                conn.commit()
                st.success("Added.")
                st.rerun()

elif page == "🎤 Demo Scripts":
    st.title("Demo Scripts")
    st.caption("BD talking points — onboarding employees should be able to explain these to a prospect.")
    q = """SELECT scenario AS "Module / Scenario", title AS "Script Title",
                  talking_points AS "Key Talking Points", audience AS Audience,
                  last_updated AS "Last Updated" FROM demo_scripts"""
    st.dataframe(df(q), use_container_width=True, hide_index=True)
    with st.expander("➕ Add a script"):
        with st.form("add_script"):
            scenario = st.text_input("Module / scenario")
            title = st.text_input("Script title")
            points = st.text_area("Key talking points")
            audience = st.text_input("Audience", value="Prospective clients")
            if st.form_submit_button("Add"):
                conn.execute(
                    "INSERT INTO demo_scripts (scenario, title, talking_points, audience, last_updated) VALUES (?,?,?,?,?)",
                    (scenario, title, points, audience, date.today().isoformat()),
                )
                conn.commit()
                st.success("Added.")
                st.rerun()

elif page == "📊 Overall Progress":
    st.title("Overall Progress")
    prog = overall_progress_df()
    if prog.empty:
        st.info("Add employees to see progress here.")
    else:
        st.dataframe(
            prog,
            use_container_width=True,
            hide_index=True,
            column_config={"% Complete": st.column_config.ProgressColumn("% Complete", format="%.0f%%", min_value=0, max_value=1)},
        )
        st.subheader("Module completion by employee")
        st.bar_chart(prog.set_index("Employee")["% Complete"])
