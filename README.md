# 🏕️ Summer Camp Milestone Tracker

A Streamlit app for tracking camper milestones during summer camp. Students can sign in with Google/Gmail, view assigned milestones, and see their progress. Teachers and admins can create milestones, assign them to students, and update completion status.

## Features

- Google/Gmail login through Streamlit OpenID Connect (`st.login` / `st.user`)
- Local demo login for development before OAuth is configured
- Student dashboard with assigned milestones, status, notes, and progress metrics
- Teacher dashboard for creating milestones, assigning them to students, and updating progress
- Admin dashboard for changing user roles and archiving milestones
- SQLite persistence for users, milestones, assignments, notes, and completion timestamps

## Local setup

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Start the Streamlit app:

   ```bash
   streamlit run streamlit_app.py
   ```

3. During local development, use **Local demo mode** on the login page. The first user who signs in is automatically made an admin so the app can be bootstrapped.

## Google/Gmail login setup

The app is wired for Streamlit's built-in OpenID Connect support. To enable real Google login:

1. Create a Google Cloud OAuth client for a web application.
2. Add an authorized redirect URI:
   - Local: `http://localhost:8501/oauth2callback`
   - Deployed app: `https://YOUR-APP-URL/oauth2callback`
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`.
4. Fill in the `[auth]` values with your Google OAuth client ID, client secret, redirect URI, and a long random cookie secret.
5. Add known staff emails to `admin_emails` and `teacher_emails`.

Never commit `.streamlit/secrets.toml`; it is ignored by Git.

## Roles

| Role | Capabilities |
| --- | --- |
| Student | View their assigned milestones and progress |
| Teacher | Create milestones, assign milestones to students, and update student progress |
| Admin | All teacher capabilities, plus user role management and milestone archiving |

New users default to `student` unless their email is listed in `admin_emails` or `teacher_emails`. If the database is empty, the first user to sign in becomes an admin.

## Data storage

By default, the app creates a local SQLite database named `camp_tracker.db`. You can change the path with `database_path` in `.streamlit/secrets.toml`.

The local database is best for prototypes, small deployments, or single-server hosting. For a larger production deployment, consider moving the persistence layer to PostgreSQL or Supabase.

## Project structure

```text
streamlit_app.py                  # Main Streamlit app, auth flow, dashboards, and SQLite helpers
requirements.txt                  # Python dependencies
.streamlit/secrets.toml.example   # Example OAuth/database configuration
.gitignore                        # Ignores local secrets, database files, and Python caches
```
