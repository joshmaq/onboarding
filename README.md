# Onboarding Hub (Streamlit)

A dashboard version of the onboarding workbook. Same structure — module reference,
tracker, videos, quiz, FAQ, import templates, demo scripts, progress — but interactive
and shared instead of a spreadsheet each person edits their own copy of.

## Run it locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

It opens at `http://localhost:8501`. On first run it creates `onboarding.db`
(a SQLite file) in the same folder and seeds it with the same example data
that was in the Excel workbook — replace it with your real content from inside the app
(each page has an "Add" form) or by editing the `seed_if_empty()` function in `app.py`.

## How it's organized

- **modules** — the master list. Add a module here and it appears as a dropdown
  option everywhere else (Tracker, Videos, Quiz, FAQ, Import Templates).
- **employees / tracker** — one tracker row per employee × module; the "Status" column
  is computed live from the video/template/FAQ checkboxes, not stored.
- **quiz_questions / quiz_attempts** — the question bank is separate from each
  employee's answers, so retaking the quiz doesn't overwrite the bank.
- **videos / faqs / import_templates / demo_scripts** — straightforward reference tables.

## Moving beyond a single laptop

This works as-is for one person testing locally. To actually roll it out to a team:

1. **Swap SQLite for a real database** once more than one person needs to write
   at the same time (SQLite handles concurrent reads fine, but writes can lock).
   Postgres is the natural next step — swap `sqlite3.connect(...)` for a
   `psycopg2`/SQLAlchemy connection; the SQL is close enough to portable that most
   queries won't need to change.
2. **Add login** — Streamlit doesn't have built-in auth. For an internal tool,
   `streamlit-authenticator` (username/password) is the fastest path; for SSO,
   look at Streamlit's built-in `st.login()` (OIDC) if you're on a recent version,
   or put the app behind your company's SSO proxy.
3. **Deploy it somewhere persistent:**
   - **Streamlit Community Cloud** — free, connects directly to a GitHub repo,
     easiest for an internal tool with a small team. Note the filesystem resets
     on redeploy, so pair it with the Postgres swap above rather than relying on
     the local SQLite file.
   - **A small VM / internal server** — run `streamlit run app.py --server.port 80`
     behind your existing reverse proxy (nginx/Caddy) for something IT already controls.
   - **Docker** — wrap this folder in a container (`FROM python:3.11-slim`, `pip install
     -r requirements.txt`, `CMD ["streamlit", "run", "app.py"]`) if you want it
     deployable anywhere containers run (ECS, Cloud Run, etc.).
4. **Back up the database** on whatever schedule matters — it's the one thing
   that isn't in version control.

## Extending it

- New module: add a row on the Module Reference page (or via the seed function) — no
  code changes needed elsewhere.
- New page/tab: copy one of the `elif page == "...":` blocks in `app.py` as a template.
- Charts: swap `st.bar_chart` for `st.plotly_chart`/Altair if you want more control
  once you add `plotly` or `altair` to `requirements.txt`.
