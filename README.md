# 🏕️ Summer Camp Milestone Tracker

A Streamlit app for tracking student progress through summer camp milestones. Students can sign in with a Google/Gmail account, view their assigned milestones, and see progress. Teachers and admins can create milestones, assign them to students, and update completion status.

## Features

- Google/Gmail-ready login with Streamlit OIDC authentication and Authlib
- Local demo login mode when OAuth secrets are not configured
- Student dashboard with progress bar and assigned milestones
- Teacher dashboard for milestone creation, assignment, and progress updates
- Admin dashboard for promoting accounts to `student`, `teacher`, or `admin`
- SQLite persistence in `camp_tracker.db`

## Quick start

1. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```

2. Run the app:

   ```bash
   streamlit run streamlit_app.py
   ```

3. If Google login is not configured, use local demo mode. Use `teacher@example.com` for teacher tools or `admin@example.com` for admin tools.

## Google/Gmail login setup

This app uses Streamlit's built-in OpenID Connect support through `st.login`, `st.user`, and `st.logout`. Streamlit requires the `Authlib` package for authentication, which is included in `requirements.txt`.

1. Create OAuth credentials in the Google Cloud Console.
2. Add this authorized redirect URI for local development:

   ```text
   http://localhost:8501/oauth2callback
   ```

3. Copy the example secrets file:

   ```bash
   cp .streamlit/secrets.toml.example .streamlit/secrets.toml
   ```

4. Fill in your real Google OAuth values in `.streamlit/secrets.toml`:

   ```toml
   [auth]
   redirect_uri = "http://localhost:8501/oauth2callback"
   cookie_secret = "your-random-cookie-secret"
   client_id = "your-google-client-id.apps.googleusercontent.com"
   client_secret = "your-google-client-secret"
   server_metadata_url = "https://accounts.google.com/.well-known/openid-configuration"

   [app]
   bootstrap_admin_email = "director@example.com"
   ```

5. Make sure none of the `[auth]` values are still placeholders such as `replace-with-*`, `your-*`, or `xxx`.
6. Restart Streamlit.

> Do not commit `.streamlit/secrets.toml`. Only the example file belongs in git.

## Roles

| Role | Capabilities |
| --- | --- |
| Student | View assigned milestones and progress |
| Teacher | Create milestones, assign milestones, and update student progress |
| Admin | All teacher capabilities plus account role management |

New Google/Gmail users are created as students by default. Set `[app].bootstrap_admin_email` in secrets to promote your first trusted account to admin automatically.

## Project files

- `streamlit_app.py` — Streamlit UI, authentication flow, and role-aware pages
- `database.py` — SQLite schema and data access helpers
- `.streamlit/secrets.toml.example` — safe template for Google login secrets
- `requirements.txt` — Python dependencies

## Deployment notes

When deploying to Streamlit Community Cloud or another host:

1. Add the deployed callback URL to Google Cloud as an authorized redirect URI:

   ```text
   https://your-app-url/oauth2callback
   ```

2. Store secrets in the host's secret manager, not in git.
3. Update `[auth].redirect_uri` to the deployed callback URL.
4. Use a persistent database service such as Supabase/PostgreSQL if you need data to survive redeployments or multiple server instances.
