"""
Onboarding Hub — Streamlit dashboard with login and a persistent database.

Run locally:
    pip install -r requirements.txt
    streamlit run app.py

Local accounts and (optionally) a live database connection are read from
.streamlit/secrets.toml — see secrets.toml.example for the format.
"""
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st
from sqlalchemy import (
    MetaData, Table, Column, Integer, String, Boolean, Text,
    ForeignKey, UniqueConstraint, create_engine, text,
)
from sqlalchemy.exc import IntegrityError

PASS_THRESHOLD = 0.8  # 80% to pass the quiz

st.set_page_config(page_title="Onboarding Hub", page_icon="🧭", layout="wide")

# =========================================================
# DATABASE ENGINE
# Uses a real Postgres database if a "db_url" secret is set (production);
# otherwise falls back to a local SQLite file (fine for local testing).
# =========================================================
@st.cache_resource
def get_engine():
    db_url = st.secrets.get("db_url", "").strip() if hasattr(st, "secrets") else ""
    if db_url:
        return create_engine(db_url, pool_pre_ping=True)
    db_path = os.path.join(os.path.dirname(__file__), "onboarding.db")
    return create_engine(f"sqlite:///{db_path}")


metadata = MetaData()

modules_t = Table(
    "modules", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), unique=True, nullable=False),
    Column("category", String(50), nullable=False),
    Column("has_import_template", Boolean, nullable=False, default=False),
    Column("description", Text),
)
employees_t = Table(
    "employees", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("name", String(200), unique=True, nullable=False),
    Column("start_date", String(20), nullable=False),
)
tracker_t = Table(
    "tracker", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("employee_id", Integer, ForeignKey("employees.id"), nullable=False),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("video_watched", Boolean, nullable=False, default=False),
    Column("video_watch_date", String(20)),
    Column("template_reviewed", String(10), nullable=False, default="No"),
    Column("faq_reviewed", Boolean, nullable=False, default=False),
    Column("notes", Text),
    UniqueConstraint("employee_id", "module_id", name="uq_tracker_emp_mod"),
)
videos_t = Table(
    "videos", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("title", String(300), nullable=False),
    Column("duration", String(30)),
    Column("link", String(500)),
    Column("description", Text),
    Column("sort_order", Integer, default=0),
)
quiz_questions_t = Table(
    "quiz_questions", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("question", Text, nullable=False),
    Column("option_a", String(300)), Column("option_b", String(300)),
    Column("option_c", String(300)), Column("option_d", String(300)),
    Column("correct_answer", String(1), nullable=False),
)
quiz_attempts_t = Table(
    "quiz_attempts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("employee_id", Integer, ForeignKey("employees.id"), nullable=False),
    Column("question_id", Integer, ForeignKey("quiz_questions.id"), nullable=False),
    Column("answer_given", String(1), nullable=False),
    Column("is_correct", Boolean, nullable=False),
    Column("attempted_at", String(40), nullable=False),
)
faqs_t = Table(
    "faqs", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("question", Text, nullable=False),
    Column("answer", Text, nullable=False),
    Column("category", String(50)),
)
import_templates_t = Table(
    "import_templates", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("module_id", Integer, ForeignKey("modules.id"), nullable=False),
    Column("file_name", String(200)),
    Column("location", String(500)),
    Column("required_fields", Text),
    Column("last_updated", String(20)),
    Column("notes", Text),
)
demo_scripts_t = Table(
    "demo_scripts", metadata,
    Column("id", Integer, primary_key=True, autoincrement=True),
    Column("scenario", String(200), nullable=False),
    Column("title", String(300), nullable=False),
    Column("talking_points", Text),
    Column("audience", String(200)),
    Column("last_updated", String(20)),
)

engine = get_engine()
metadata.create_all(engine)


def read_df(query, params=None):
    return pd.read_sql_query(text(query), engine, params=params or {})


def run(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def seed_if_empty():
    if read_df("SELECT COUNT(*) AS n FROM modules").iloc[0]["n"] > 0:
        return

    modules = [
        ("Entities", "Core", True, "The backbone module — every filing, document, bank account, and form ties back to an entity."),
        ("Filings", "Core", True, "Tracks regulatory/compliance filings and their due dates."),
        ("Documents", "Core", True, "Central document repository linked to entities."),
        ("Org Chart", "Core", True, "Visual ownership/management structure for each entity."),
        ("Users & Permissions", "Core", False, "User accounts, roles, and access control. Set up manually per client."),
        ("Bank & Bank Accounts", "Core", True, "Tracks banking relationships and accounts tied to entities."),
        ("Forms", "Core", True, "Tracks required forms per entity/filing."),
        ("Calendar", "Cross-Cutting", False, "Rolls up key dates from filings, forms, and other date-driven modules."),
        ("Tasks", "Side", False, "Task management and assignment."),
        ("Personnel", "Side", False, "Personnel records tied to entities/org chart."),
        ("Setup", "Side", False, "Client/tenant configuration."),
        ("Audit", "Side", False, "Change history and audit trail."),
    ]
    with engine.begin() as conn:
        for name, cat, tpl, desc in modules:
            conn.execute(
                text("INSERT INTO modules (name, category, has_import_template, description) VALUES (:n,:c,:t,:d)"),
                {"n": name, "c": cat, "t": tpl, "d": desc},
            )
    mod_ids = {r["name"]: r["id"] for _, r in read_df("SELECT id, name FROM modules").iterrows()}

    employees = [("Jane Smith", "2026-09-08"), ("Alex Ramirez", "2026-09-15")]
    with engine.begin() as conn:
        for name, sd in employees:
            conn.execute(text("INSERT INTO employees (name, start_date) VALUES (:n,:s)"), {"n": name, "s": sd})
    emp_ids = {r["name"]: r["id"] for _, r in read_df("SELECT id, name FROM employees").iterrows()}

    with engine.begin() as conn:
        for eid in emp_ids.values():
            for mid in mod_ids.values():
                conn.execute(
                    text("INSERT INTO tracker (employee_id, module_id, video_watched, template_reviewed, faq_reviewed) "
                         "VALUES (:e,:m,:vw,:tr,:fr) "
                         "ON CONFLICT (employee_id, module_id) DO NOTHING"),
                    {"e": eid, "m": mid, "vw": False, "tr": "No", "fr": False},
                )

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
    with engine.begin() as conn:
        for m, t, d, l, desc, o in videos:
            conn.execute(
                text("INSERT INTO videos (module_id, title, duration, link, description, sort_order) "
                     "VALUES (:m,:t,:d,:l,:desc,:o)"),
                {"m": mod_ids[m], "t": t, "d": d, "l": l, "desc": desc, "o": o},
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
    with engine.begin() as conn:
        for m, q, a, b, c, d, ans in questions:
            conn.execute(
                text("INSERT INTO quiz_questions (module_id, question, option_a, option_b, option_c, option_d, correct_answer) "
                     "VALUES (:m,:q,:a,:b,:c,:d,:ans)"),
                {"m": mod_ids[m], "q": q, "a": a, "b": b, "c": c, "d": d, "ans": ans},
            )

    faqs = [
        ("Entities", "What's the difference between an entity and a filing?", "An entity is the legal organization itself; a filing is a compliance document/deadline tied to that entity.", "General"),
        ("Entities", "Can I bulk import entities?", "Yes — use the Entities import template.", "Technical"),
        ("Filings", "How are filing due dates set?", "Set when the filing record is created; they automatically appear on the Calendar.", "General"),
        ("Documents", "What file types can I upload?", "PDF, DOCX, XLSX, and common image formats.", "Technical"),
        ("Users & Permissions", "Why can't I bulk import users?", "Intentionally manual for security — each user is set up individually.", "General"),
        ("Calendar", "Can I filter the calendar by module?", "Yes, use the module filter at the top of the Calendar view.", "Technical"),
    ]
    with engine.begin() as conn:
        for m, q, a, c in faqs:
            conn.execute(
                text("INSERT INTO faqs (module_id, question, answer, category) VALUES (:m,:q,:a,:c)"),
                {"m": mod_ids[m], "q": q, "a": a, "c": c},
            )

    templates = [
        ("Entities", "Entities_Import_Template.xlsx", "Help Center > Entities > Bulk Import", "Entity Name, Entity Type, Jurisdiction, Status"),
        ("Filings", "Filings_Import_Template.xlsx", "Help Center > Filings > Bulk Import", "Entity, Filing Type, Due Date, Status"),
        ("Documents", "Documents_Import_Template.xlsx", "Help Center > Documents > Bulk Import", "Entity, Document Type, File Reference, Tags"),
        ("Org Chart", "OrgChart_Import_Template.xlsx", "Help Center > Org Chart > Bulk Import", "Entity, Parent Entity, Ownership %, Role"),
        ("Bank & Bank Accounts", "BankAccounts_Import_Template.xlsx", "Help Center > Bank Accounts > Bulk Import", "Entity, Bank Name, Account Number, Account Type"),
        ("Forms", "Forms_Import_Template.xlsx", "Help Center > Forms > Bulk Import", "Entity, Form Type, Due Date, Status"),
    ]
    with engine.begin() as conn:
        for m, f, l, rf in templates:
            conn.execute(
                text("INSERT INTO import_templates (module_id, file_name, location, required_fields, last_updated, notes) "
                     "VALUES (:m,:f,:l,:rf,:lu,'')"),
                {"m": mod_ids[m], "f": f, "l": l, "rf": rf, "lu": "2026-08-01"},
            )

    scripts = [
        ("Entities", "Why Entities is the backbone", "Every filing, document, bank account, and form ties back to an entity — one system of record instead of scattered spreadsheets.", "Prospective clients"),
        ("Filings", "Never miss a deadline", "Filings auto-populate the Calendar, so nothing falls through the cracks — show the calendar view live.", "Prospective clients"),
        ("Documents", "One place for every document", "Documents link directly to entities and filings, eliminating shared-drive hunting.", "Prospective clients"),
        ("Bulk Import (all modules)", "Fast migration story", "Most modules support a bulk-import template, so switching from spreadsheets takes days, not months.", "Prospective clients"),
    ]
    with engine.begin() as conn:
        for s, t, tp, a in scripts:
            conn.execute(
                text("INSERT INTO demo_scripts (scenario, title, talking_points, audience, last_updated) "
                     "VALUES (:s,:t,:tp,:a,:lu)"),
                {"s": s, "t": t, "tp": tp, "a": a, "lu": "2026-08-01"},
            )


seed_if_empty()


# =========================================================
# LOGIN
# =========================================================
def require_login():
    if st.session_state.get("auth"):
        return st.session_state["auth"]

    st.title("🔒 Onboarding Hub")
    st.caption("Sign in to continue.")
    users = dict(st.secrets.get("users", {}))
    if not users:
        st.error(
            "No accounts are set up yet. Add a [users] section to your secrets "
            "(see secrets.toml.example) with at least one admin account, then reload this page."
        )
        st.stop()

    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Sign in")

    if submitted:
        user = users.get(username)
        if user and password == user.get("password"):
            st.session_state["auth"] = {
                "username": username,
                "name": user.get("name", username),
                "role": user.get("role", "employee"),
                "employee_name": user.get("employee_name"),
            }
            st.rerun()
        else:
            st.error("Incorrect username or password.")
    st.stop()


auth = require_login()
is_admin = auth["role"] == "admin"


# =========================================================
# DATA HELPERS
# =========================================================
def modules_df():
    return read_df("SELECT * FROM modules ORDER BY category, name")


def module_names():
    return modules_df()["name"].tolist()


def employees_df():
    return read_df("SELECT * FROM employees ORDER BY start_date")


def ensure_tracker_rows(employee_id):
    mods = read_df("SELECT id FROM modules")
    with engine.begin() as conn:
        for mid in mods["id"]:
            conn.execute(
                text("INSERT INTO tracker (employee_id, module_id, video_watched, template_reviewed, faq_reviewed) "
                     "VALUES (:e,:m,:vw,:tr,:fr) "
                     "ON CONFLICT (employee_id, module_id) DO NOTHING"),
                {"e": int(employee_id), "m": int(mid), "vw": False, "tr": "No", "fr": False},
            )


def tracker_df_for_employee(employee_id):
    q = """
    SELECT t.id, m.name AS module, m.category, m.has_import_template,
           t.video_watched, t.video_watch_date, t.template_reviewed,
           t.faq_reviewed, t.notes
    FROM tracker t JOIN modules m ON m.id = t.module_id
    WHERE t.employee_id = :e
    ORDER BY m.category, m.name
    """
    d = read_df(q, {"e": int(employee_id)})
    if d.empty:
        return d
    d["video_watched"] = d["video_watched"].astype(bool)
    d["faq_reviewed"] = d["faq_reviewed"].astype(bool)
    d["has_import_template"] = d["has_import_template"].astype(bool)

    def status(row):
        template_ok = row["template_reviewed"] == "Yes" or not row["has_import_template"]
        return "Complete" if row["video_watched"] and template_ok and row["faq_reviewed"] else "In Progress"

    d["status"] = d.apply(status, axis=1)
    return d


def quiz_score(employee_id):
    row = read_df(
        "SELECT COUNT(*) AS attempted, SUM(CASE WHEN is_correct THEN 1 ELSE 0 END) AS correct "
        "FROM quiz_attempts WHERE employee_id = :e",
        {"e": int(employee_id)},
    ).iloc[0]
    attempted = int(row["attempted"] or 0)
    correct = int(row["correct"] or 0)
    pct = correct / attempted if attempted else None
    return attempted, correct, pct


def overall_progress_df(employee_filter_id=None):
    emps = employees_df()
    if employee_filter_id is not None:
        emps = emps[emps["id"] == employee_filter_id]
    rows = []
    for _, e in emps.iterrows():
        t = tracker_df_for_employee(e["id"])
        total = len(t)
        complete = (t["status"] == "Complete").sum() if total else 0
        pct_complete = complete / total if total else 0
        attempted, correct, quiz_pct = quiz_score(e["id"])
        quiz_status = "Not started" if quiz_pct is None else ("Pass" if quiz_pct >= PASS_THRESHOLD else "Fail")
        overall = "Onboarding Complete" if pct_complete == 1 and quiz_status == "Pass" else "In Progress"
        days = (date.today() - datetime.strptime(e["start_date"], "%Y-%m-%d").date()).days
        rows.append(
            {
                "Employee": e["name"], "Start Date": e["start_date"],
                "Modules Complete": f"{complete}/{total}", "% Complete": pct_complete,
                "Quiz Score": "—" if quiz_pct is None else f"{quiz_pct:.0%}",
                "Quiz Status": quiz_status, "Overall Status": overall, "Days Since Start": days,
            }
        )
    return pd.DataFrame(rows)


# ---- generic admin edit-grid sync (insert / update / delete in one save) ----
def sync_editor(table, orig_df, edited_df, fk_map=None):
    """
    orig_df / edited_df: DataFrames with an 'id' column plus editable columns
    matching the target table's column names, EXCEPT any column named in fk_map,
    which holds a human-readable value (e.g. a module name) to be translated
    into a foreign key id before writing.

    fk_map: {display_col_name: (lookup_df, name_col, id_col, target_fk_column)}
    """
    fk_map = fk_map or {}
    orig_ids = set(int(x) for x in orig_df["id"].dropna()) if "id" in orig_df.columns and not orig_df.empty else set()
    edited_ids = set(int(x) for x in edited_df["id"].dropna()) if "id" in edited_df.columns else set()
    deleted_ids = orig_ids - edited_ids

    with engine.begin() as conn:
        for did in deleted_ids:
            conn.execute(text(f"DELETE FROM {table} WHERE id = :id"), {"id": did})

        for _, row in edited_df.iterrows():
            data = row.to_dict()
            rid = data.pop("id", None)
            for disp_col, (lookup_df, name_col, id_col2, target_col) in fk_map.items():
                val = data.pop(disp_col, None)
                if val is not None and not (isinstance(val, float) and pd.isna(val)):
                    match = lookup_df[lookup_df[name_col] == val]
                    if not match.empty:
                        data[target_col] = int(match.iloc[0][id_col2])
                elif target_col not in data:
                    data[target_col] = None
            clean = {k: (None if (isinstance(v, float) and pd.isna(v)) else v) for k, v in data.items()}

            if rid is None or (isinstance(rid, float) and pd.isna(rid)):
                cols = ", ".join(clean.keys())
                placeholders = ", ".join(f":{k}" for k in clean.keys())
                conn.execute(text(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})"), clean)
            else:
                set_clause = ", ".join(f"{k} = :{k}" for k in clean.keys())
                clean["id"] = int(rid)
                conn.execute(text(f"UPDATE {table} SET {set_clause} WHERE id = :id"), clean)


def admin_editor_section(label, table, query, fk_map=None, key=None, column_config=None, on_success=None):
    """Renders a full add/edit/delete grid for admins, read-only table otherwise."""
    orig = read_df(query)
    if not is_admin:
        st.dataframe(orig.drop(columns=["id"]) if "id" in orig.columns else orig,
                      width='stretch', hide_index=True)
        return
    st.caption(f"Admin mode — add, edit, or delete {label.lower()} directly. Use the ⋮ menu or the + row to add.")
    cfg = {"id": st.column_config.NumberColumn("ID", disabled=True, width="small")}
    cfg.update(column_config or {})
    edited = st.data_editor(
        orig, num_rows="dynamic", width='stretch', hide_index=True,
        column_config=cfg, key=key,
    )
    if st.button(f"💾 Save {label}", key=f"save_{key}"):
        try:
            sync_editor(table, orig, edited, fk_map=fk_map)
            if on_success:
                on_success()
            st.success("Saved.")
            st.rerun()
        except IntegrityError as e:
            st.error(f"Couldn't save — check for duplicate/blank required fields. ({e.orig})")
        except Exception as e:
            st.error(f"Couldn't save: {e}")


def backfill_tracker_rows():
    """After modules or employees change, make sure every employee has a tracker row for every module."""
    for eid in read_df("SELECT id FROM employees")["id"]:
        ensure_tracker_rows(int(eid))


# =========================================================
# SIDEBAR
# =========================================================
st.sidebar.title("🧭 Onboarding Hub")
st.sidebar.caption(f"Signed in as **{auth['name']}** ({auth['role']})")
if st.sidebar.button("Log out"):
    st.session_state["auth"] = None
    st.rerun()

pages = [
    "🏠 Home", "🧩 Module Reference", "✅ Onboarding Tracker", "🎥 Training Videos",
    "🧠 Knowledge Quiz", "❓ FAQ", "📥 Import Templates", "🎤 Demo Scripts", "📊 Overall Progress",
]
page = st.sidebar.radio("Go to", pages)

emps = employees_df()
st.sidebar.divider()

if is_admin:
    st.sidebar.subheader("Viewing employee")
    if emps.empty:
        st.sidebar.info("Add an employee below.")
        selected_emp_id, emp_name = None, None
    else:
        emp_name = st.sidebar.selectbox("Viewing as", emps["name"])
        selected_emp_id = int(emps.loc[emps["name"] == emp_name, "id"].iloc[0])

    with st.sidebar.expander("➕ Add new employee"):
        new_name = st.text_input("Name", key="new_emp_name")
        new_start = st.date_input("Start date", value=date.today(), key="new_emp_start")
        if st.button("Add employee"):
            if new_name.strip():
                try:
                    run("INSERT INTO employees (name, start_date) VALUES (:n,:s)",
                        {"n": new_name.strip(), "s": new_start.isoformat()})
                    eid = read_df("SELECT id FROM employees WHERE name=:n", {"n": new_name.strip()}).iloc[0]["id"]
                    ensure_tracker_rows(eid)
                    st.success(f"Added {new_name}.")
                    st.rerun()
                except IntegrityError:
                    st.error("That name already exists.")
            else:
                st.warning("Enter a name first.")
else:
    # employee role: locked to their own record
    emp_name = auth.get("employee_name")
    match = emps[emps["name"] == emp_name] if not emps.empty else emps
    selected_emp_id = int(match.iloc[0]["id"]) if not match.empty else None
    if selected_emp_id is None:
        st.sidebar.warning("Your account isn't linked to an employee record yet — ask an admin to check your `employee_name` in secrets.")


# =========================================================
# PAGES
# =========================================================
if page == "🏠 Home":
    st.title("Onboarding Hub")
    st.caption("The single onboarding home for new hires — replaces the onboarding workbook.")
    st.markdown(
        """
        **How to use it:** work through *Onboarding Tracker* module by module, watching videos and
        reviewing import templates as you go, then take the *Knowledge Quiz*. Admins can edit any
        table directly and check *Overall Progress* for a live view of every hire.
        """
    )
    prog = overall_progress_df(None if is_admin else selected_emp_id)
    if not prog.empty:
        c1, c2, c3 = st.columns(3)
        c1.metric("Employees onboarding" if is_admin else "Modules complete", len(prog) if is_admin else prog.iloc[0]["Modules Complete"])
        c2.metric("Avg. % modules complete" if is_admin else "% complete", f"{prog['% Complete'].mean():.0%}")
        if is_admin:
            completed = (prog["Overall Status"] == "Onboarding Complete").sum()
            c3.metric("Fully onboarded", f"{completed}/{len(prog)}")
        else:
            c3.metric("Quiz status", prog.iloc[0]["Quiz Status"])

elif page == "🧩 Module Reference":
    st.title("Module Reference")
    st.caption("Master list of every module. Add a row here when the software adds a module — it flows everywhere else automatically.")
    admin_editor_section(
        "modules", "modules", "SELECT * FROM modules ORDER BY category, name",
        key="modules_editor",
        column_config={
            "name": st.column_config.TextColumn("Module Name", required=True),
            "category": st.column_config.SelectboxColumn("Category", options=["Core", "Side", "Cross-Cutting"], required=True),
            "has_import_template": st.column_config.CheckboxColumn("Has Import Template?"),
            "description": st.column_config.TextColumn("Description", width="large"),
        },
        on_success=backfill_tracker_rows,
    )

elif page == "✅ Onboarding Tracker":
    st.title("Onboarding Tracker")
    if selected_emp_id is None:
        st.info("Add an employee in the sidebar to get started." if is_admin else "Ask an admin to set up your account.")
    else:
        st.caption(f"Checklist for **{emp_name}** — tick off as each module is covered.")
        t = tracker_df_for_employee(selected_emp_id)
        edited = st.data_editor(
            t[["module", "category", "has_import_template", "video_watched", "video_watch_date",
               "template_reviewed", "faq_reviewed", "notes", "status"]],
            column_config={
                "module": st.column_config.TextColumn("Module", disabled=True),
                "category": st.column_config.TextColumn("Category", disabled=True, help="Set on the Module Reference page."),
                "has_import_template": st.column_config.CheckboxColumn("Has Template?", disabled=True, help="Set on the Module Reference page."),
                "video_watched": st.column_config.CheckboxColumn("Video Watched?"),
                "video_watch_date": st.column_config.TextColumn("Video Watch Date (YYYY-MM-DD)"),
                "template_reviewed": st.column_config.SelectboxColumn("Template Reviewed?", options=["Yes", "No", "N/A"]),
                "faq_reviewed": st.column_config.CheckboxColumn("FAQ Reviewed?"),
                "notes": st.column_config.TextColumn("Notes", width="large"),
                "status": st.column_config.TextColumn("Status (auto)", disabled=True),
            },
            hide_index=True, width='stretch', key="tracker_editor",
        )
        if st.button("💾 Save changes"):
            with engine.begin() as conn:
                for i, row in edited.iterrows():
                    tid = int(t.iloc[i]["id"])
                    conn.execute(
                        text("UPDATE tracker SET video_watched=:vw, video_watch_date=:vd, "
                             "template_reviewed=:tr, faq_reviewed=:fr, notes=:n WHERE id=:id"),
                        {"vw": bool(row["video_watched"]), "vd": row["video_watch_date"],
                         "tr": row["template_reviewed"], "fr": bool(row["faq_reviewed"]),
                         "n": row["notes"], "id": tid},
                    )
            st.success("Saved.")
            st.rerun()

elif page == "🎥 Training Videos":
    st.title("Training Videos")
    mods_df = modules_df()
    q = """SELECT v.id, m.name AS module, v.title, v.duration, v.link, v.description, v.sort_order
           FROM videos v JOIN modules m ON m.id = v.module_id ORDER BY v.sort_order"""
    admin_editor_section(
        "training videos", "videos", q,
        fk_map={"module": (mods_df, "name", "id", "module_id")},
        key="videos_editor",
        column_config={
            "module": st.column_config.SelectboxColumn("Module", options=module_names(), required=True),
            "title": st.column_config.TextColumn("Video Title", required=True, width="large"),
            "duration": st.column_config.TextColumn("Duration"),
            "link": st.column_config.TextColumn("Link / Location", width="large"),
            "description": st.column_config.TextColumn("Description", width="large"),
            "sort_order": st.column_config.NumberColumn("Order"),
        },
    )
    if not is_admin:
        pick = st.selectbox("Filter by module", ["All"] + module_names())
        d = read_df(q)
        if pick != "All":
            d = d[d["module"] == pick]
        st.dataframe(d.drop(columns=["id"]), width='stretch', hide_index=True)

elif page == "🧠 Knowledge Quiz":
    st.title("Knowledge Quiz")
    if is_admin:
        with st.expander("🛠️ Admin: edit the question bank"):
            mods_df = modules_df()
            qb_q = """SELECT id, module_id, question, option_a, option_b, option_c, option_d, correct_answer
                      FROM quiz_questions"""
            orig_qb = read_df(qb_q)
            orig_qb = orig_qb.merge(mods_df[["id", "name"]], left_on="module_id", right_on="id", suffixes=("", "_mod"))
            orig_qb = orig_qb.rename(columns={"name": "module"}).drop(columns=["module_id", "id_mod"])
            edited_qb = st.data_editor(
                orig_qb, num_rows="dynamic", width='stretch', hide_index=True,
                column_config={
                    "id": st.column_config.NumberColumn("ID", disabled=True, width="small"),
                    "module": st.column_config.SelectboxColumn("Module", options=module_names(), required=True),
                    "question": st.column_config.TextColumn("Question", required=True, width="large"),
                    "option_a": st.column_config.TextColumn("Option A"),
                    "option_b": st.column_config.TextColumn("Option B"),
                    "option_c": st.column_config.TextColumn("Option C"),
                    "option_d": st.column_config.TextColumn("Option D"),
                    "correct_answer": st.column_config.SelectboxColumn("Correct", options=["A", "B", "C", "D"], required=True),
                },
                key="quiz_bank_editor",
            )
            if st.button("💾 Save question bank"):
                try:
                    sync_editor("quiz_questions", orig_qb, edited_qb,
                                fk_map={"module": (mods_df, "name", "id", "module_id")})
                    st.success("Saved.")
                    st.rerun()
                except Exception as e:
                    st.error(f"Couldn't save: {e}")

    if selected_emp_id is None:
        st.info("Add/select an employee to take the quiz.")
    else:
        st.caption(f"Taking the quiz as **{emp_name}**. {int(PASS_THRESHOLD*100)}% needed to pass.")
        questions = read_df(
            """SELECT q.id, m.name AS module, q.question, q.option_a, q.option_b,
                      q.option_c, q.option_d, q.correct_answer
               FROM quiz_questions q JOIN modules m ON m.id = q.module_id ORDER BY m.name, q.id"""
        )
        answers = {}
        with st.form("quiz_form"):
            for _, r in questions.iterrows():
                label = f"**[{r['module']}]** {r['question']}"
                answers[r["id"]] = st.radio(
                    label, options=["A", "B", "C", "D"],
                    format_func=lambda x, row=r: f"{x}. {row[f'option_{x.lower()}']}",
                    key=f"q_{r['id']}", index=None,
                )
            submitted = st.form_submit_button("Submit quiz")
        if submitted:
            now = datetime.now().isoformat()
            correct_count, attempted = 0, 0
            with engine.begin() as conn:
                for _, r in questions.iterrows():
                    ans = answers.get(r["id"])
                    if ans is None:
                        continue
                    attempted += 1
                    is_correct = ans == r["correct_answer"]
                    correct_count += int(is_correct)
                    conn.execute(
                        text("INSERT INTO quiz_attempts (employee_id, question_id, answer_given, is_correct, attempted_at) "
                             "VALUES (:e,:q,:a,:c,:t)"),
                        {"e": selected_emp_id, "q": int(r["id"]), "a": ans, "c": is_correct, "t": now},
                    )
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
    mods_df = modules_df()
    q = """SELECT f.id, m.name AS module, f.question, f.answer, f.category
           FROM faqs f JOIN modules m ON m.id = f.module_id"""
    admin_editor_section(
        "FAQs", "faqs", q,
        fk_map={"module": (mods_df, "name", "id", "module_id")},
        key="faq_editor",
        column_config={
            "module": st.column_config.SelectboxColumn("Module", options=module_names(), required=True),
            "question": st.column_config.TextColumn("Question", required=True, width="large"),
            "answer": st.column_config.TextColumn("Answer", required=True, width="large"),
            "category": st.column_config.SelectboxColumn("Category", options=["General", "Technical"]),
        },
    )
    if not is_admin:
        pick = st.selectbox("Filter by module", ["All"] + module_names())
        search = st.text_input("Search")
        d = read_df(q)
        if pick != "All":
            d = d[d["module"] == pick]
        if search:
            mask = d["question"].str.contains(search, case=False) | d["answer"].str.contains(search, case=False)
            d = d[mask]
        st.dataframe(d.drop(columns=["id"]), width='stretch', hide_index=True)

elif page == "📥 Import Templates":
    st.title("Import Templates")
    mods_df = modules_df()
    q = """SELECT t.id, m.name AS module, t.file_name, t.location, t.required_fields, t.last_updated, t.notes
           FROM import_templates t JOIN modules m ON m.id = t.module_id ORDER BY m.name"""
    admin_editor_section(
        "import templates", "import_templates", q,
        fk_map={"module": (mods_df, "name", "id", "module_id")},
        key="templates_editor",
        column_config={
            "module": st.column_config.SelectboxColumn("Module", options=module_names(), required=True),
            "file_name": st.column_config.TextColumn("File Name"),
            "location": st.column_config.TextColumn("Location / Link", width="large"),
            "required_fields": st.column_config.TextColumn("Required Fields", width="large"),
            "last_updated": st.column_config.TextColumn("Last Updated (YYYY-MM-DD)"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

elif page == "🎤 Demo Scripts":
    st.title("Demo Scripts")
    st.caption("BD talking points — onboarding employees should be able to explain these to a prospect.")
    q = """SELECT id, scenario, title, talking_points, audience, last_updated FROM demo_scripts"""
    admin_editor_section(
        "demo scripts", "demo_scripts", q,
        key="scripts_editor",
        column_config={
            "scenario": st.column_config.TextColumn("Module / Scenario", required=True),
            "title": st.column_config.TextColumn("Script Title", required=True),
            "talking_points": st.column_config.TextColumn("Key Talking Points", width="large"),
            "audience": st.column_config.TextColumn("Audience"),
            "last_updated": st.column_config.TextColumn("Last Updated (YYYY-MM-DD)"),
        },
    )

elif page == "📊 Overall Progress":
    st.title("Overall Progress")
    prog = overall_progress_df(None if is_admin else selected_emp_id)
    if prog.empty:
        st.info("Add employees to see progress here.")
    else:
        st.dataframe(
            prog, width='stretch', hide_index=True,
            column_config={"% Complete": st.column_config.ProgressColumn("% Complete", format="%.0f%%", min_value=0, max_value=1)},
        )
        if is_admin and len(prog) > 1:
            st.subheader("Module completion by employee")
            st.bar_chart(prog.set_index("Employee")["% Complete"])
