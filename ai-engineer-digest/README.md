# Signal — a daily digest for the AI Engineer YouTube channel

Every day, this scans youtube.com/@aiDotEngineer for new uploads, pulls the transcript,
samples key frames (slides/code), and asks Grok to turn each video into a structured
"is this worth my time" briefing instead of a summary. Results land in `docs/results.json`,
and `docs/index.html` renders them as a dashboard hosted free on GitHub Pages.

You do not need to know how to code to set this up — just follow the steps below in order.
Budget about 20 minutes.

---

## Step 1 — Get a YouTube Data API key (free)

1. Go to https://console.cloud.google.com/
2. Top left, click the project dropdown → **New Project** → name it `signal-digest` → **Create**
3. Once it's created and selected, go to https://console.cloud.google.com/apis/library/youtube.googleapis.com
4. Click **Enable**
5. Go to https://console.cloud.google.com/apis/credentials
6. Click **+ Create Credentials** → **API key**
7. Copy the key somewhere safe — you'll need it in Step 3
8. Key: AIzaSyADn2crBA8GBO1QhqC_f7JCYwfsjI4qFNk

The free quota (10,000 units/day) is far more than checking one channel daily needs.

## Step 2 — Get a Grok (xAI) API key

1. Go to https://console.x.ai/
2. Sign in and create an API key from the dashboard
3. Copy the key somewhere safe
4. Key: xai-zT8DPP6JxADUD4ndnTmR7EOybN31LZAFcGijhpH4fGrR406UoTS1u1ZtMDHrm7eXJGXk1SQQEiijCXd3

## Step 3 — Create the GitHub repo

1. Go to https://github.com/new
2. Repository name: `signal-digest` (or anything you like) → make it **Public** (required for free GitHub Pages) → **Create repository**
3. On your computer or in this chat, download the project files I generated (the zip)
4. On the new repo's page, click **uploading an existing file**, drag in every file/folder from the zip (keep the folder structure), and commit

## Step 4 — Add your API keys as repo secrets

1. In your repo, go to **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**, name it `YOUTUBE_API_KEY`, paste your key from Step 1, **Add secret**
3. Repeat for `GROK_API_KEY` with your key from Step 2

These stay encrypted — never exposed in the dashboard or logs.

## Step 5 — Turn on GitHub Pages

1. **Settings** → **Pages**
2. Under "Build and deployment", Source: **Deploy from a branch**
3. Branch: `main`, folder: `/docs` → **Save**
4. GitHub gives you a URL like `https://yourusername.github.io/signal-digest/` — that's your dashboard, bookmark it

## Step 6 — Turn on the daily scan

The workflow in `.github/workflows/daily.yml` is already scheduled to run every day at 07:00 UTC.
To also run it right now instead of waiting:

1. In your repo, click the **Actions** tab
2. If prompted, click **I understand my workflows, go ahead and enable them**
3. Click **Daily Digest** in the left sidebar → **Run workflow** → **Run workflow**
4. Wait ~2-5 minutes, refresh your Pages URL from Step 5

That's it — from now on it runs itself daily and the dashboard updates automatically.

---

## How the pipeline decides what's "worth watching"

For each new video, `src/analyze.py` sends the transcript plus descriptions of sampled
frames to Grok and asks for:

- **Verdict** — watch / skim / skip, with a one-line reason
- **Novelty score** — how much of this is genuinely new vs. restating known material
- **Insight cards** — claim → evidence → why it matters (not prose summary)
- **Entities** — tools, repos, papers, models mentioned, deduped
- **Timestamped highlights** — jump-to points if it IS worth watching

See `src/analyze.py` — the prompt is the actual "secret sauce" and is easy to tune to your taste
once you see a few days of output. If it's too generous or too harsh with verdicts, edit the
prompt and it improves from the next run onward.

## Costs

- YouTube Data API: free tier covers this easily
- Grok API: a handful of cents per video (transcript + a few frames), so a few dollars a month
  even if the channel posts daily
- GitHub Actions + Pages: free for public repos
