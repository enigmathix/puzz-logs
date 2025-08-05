# 🚀 Puzz Lighter Logs

**Puzz Lighter Logs** is a companion tool to [Puzz Lighter](https://github.com/enigmathix/puzz-lighter) for monitoring its logs.

While Google Cloud provides a logging interface, it can be cumbersome, unintuitive, and not tailored to app-specific logs. **Puzz Lighter Logs** fills that gap by offering a simple, focused interface to monitor a puzzle hunt.

---

## 📦 Installation

- Requirement: **Python 3**
- Install the [gcloud SDK](https://cloud.google.com/sdk/docs/install)
- Clone this repo:

  ```bash
  git clone https://github.com/enigmathix/puzz-lighter-logs.git
  cd puzz-lighter-logs
  pip install -r requirements.txt
  ```

---

## ⚙️ Configuration

### 🔑 Service Account

Although this code *could* run in the main server project, the Google Logging API libraries consume significant memory and CPU. To avoid penalizing your hunt server, it's best to create a **separate Google Cloud project** just for monitoring.

To allow this monitoring project to access logs from your main hunt project:

1. In your **hunt project**, go to **IAM & Admin → Service Accounts**.
2. Use your existing App Engine default service account, or create one.
3. This step shouldn't be necessary if you use the default service account, but if you run into permissions issues: under the **Permissions** tab, ensure it has access to logs.
   - Set its role to **Owner** (for simplicity, though more specific roles can be configured).
4. Go to the **Keys** tab → click **Add Key → Create New Key**.
5. Download the JSON key file and save it as `service_account.json` in your project directory.

### ☁️ Google App Engine

You’ll now create a project for Puzz Lighter Logs:

1. Run `gcloud init` to set up your account and select/create the logging project.
2. In the [Google Cloud Console](https://console.cloud.google.com/), create a **Python Standard App Engine** (not Flexible).

Edit the `app` script and configure:

- `GOOGLE_CLOUD_PROJECT`: your **new logging project** ID
- Ensure paths to Python 3 and `dev_appserver.py` are correct

Edit `app.yaml` and fill in the `env_variables` section:

- `SECRET_KEY`: used by Flask for session handling
- `PROJECT`: the **hunt project** ID (i.e., where logs originate)
- `DOMAIN`: your domain
- `CDN`: your hunt project’s CDN URL (if applicable)

---

## ▶️ Running

To run the server locally:

```bash
./app run
```

To deploy to Google Cloud:

```bash
./app deploy
```

---

### 🖥️ Default View

The interface shows a paginated table of all events logged by your app:

| Time                  | Hunt           | Team    | IP         | URL     | Agent            | Message                          |
|-----------------------|----------------|---------|------------|---------|------------------|----------------------------------|
| 8/5/2025, 10:08:22 EDT | 2025truzzlehunt | Team A | 192.0.2.1  | /guess? | Windows Firefox  | Solved Puzzle 12                |
| 8/5/2025, 10:08:15 EDT | 2025truzzlehunt | Team A | 192.0.2.1  | /guess? | Windows Firefox  | Guessed "thirteen" on Puzzle 12 |

These logs include app-specific fields like `Hunt` and `Team`. Log entries are color-coded by severity, and you can filter them by level: **Debug**, **Info**, **Warning**, **Error**, **Critical**.

---

### 🔍 Engine View

The **Engine** view shows logs from Google App Engine itself — including backend events such as instance scaling.

It also adds performance data such as:

- Request latency in milliseconds
- Queue time in milliseconds
- Data transfer size in bytes

Example:

| Time                  | IP         | URL                    | Lat | Wait | Len  | Agent            | Message                               |
|-----------------------|------------|------------------------|-----|------|------|------------------|----------------------------------------|
| 8/5/2025, 10:08:15 EDT | 192.0.2.1  | /guess?                | 33  | 0    | 2349 | Windows Firefox  |                                        |
| 8/5/2025, 10:08:01 EDT | 192.0.2.1  | /puzzle/puzzle-12      | 138 | 0    | 3462 | Windows Firefox  | This request caused a new process...  |

---

### 🔎 Search

Use the search field to filter logs by any substring across all fields.

⚠️ **Note:** The Logs API returns results only after a minimum number of entries (default is 100). If your search term is too rare, the API might timeout with an error.

### 🧭 Typical Usage

Click on ⏩ to refresh the view to the latest time.  
Note: the search field is still applied when refreshing — you may want to clear it first.

---

## 🧹 Gotchas: Clean Up Artifact Registry

Google Cloud uses **Docker** internally to deploy App Engine apps. The Docker artifacts are stored in the **Artifact Registry** under a repository named `gae-standard`.

By default, these deployments are **not cleaned up**, and can slowly accumulate — costing you storage fees (even if just cents/month).

To set up a cleanup policy:

1. Go to **Artifact Registry** in the Cloud Console.
2. Select the `gae-standard` repository.
3. Click **Edit Repository**.
4. Scroll to **Cleanup Policies**.
5. Click **Add a cleanup policy**.
6. Set a name and choose:
   - **Policy type:** `Conditional delete`
   - **Older than:** `3600s` (i.e., one hour)
7. Save the policy.

This will keep your storage clean and avoid unnecessary charges.