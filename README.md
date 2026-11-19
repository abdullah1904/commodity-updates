# Commodity Updates

Commodity Updates is a Python service that scrapes gold and silver prices, turns the
source content into a concise update with Groq, and publishes the result to Slack.
Gold updates can also include a short Urdu voice note when audio generation succeeds.

The FastAPI application exposes a health endpoint for hosting platforms and starts an
APScheduler job on application startup. The scheduled gold job runs Monday through
Saturday at **16:00 Asia/Karachi**.

## What it does

1. Firecrawl retrieves the configured gold or silver price page.
2. Groq generates a Slack-formatted update using only the scraped figures.
3. The Slack bot posts the update and mentions the configured user.
4. Groq optionally creates an Urdu voice note and uploads it to the same channel.

The current scheduler in `main.py` runs the gold workflow. The silver workflow is
available in `graphs/silver.py` but is not scheduled by default.

## Requirements

- Python 3.13 or newer
- A [Firecrawl](https://www.firecrawl.dev/) API key
- A [Groq](https://console.groq.com/) API key with access to the configured text and
  audio models
- A Slack workspace where you can install a Slack app
- [uv](https://docs.astral.sh/uv/) for the recommended local setup, or another Python
  environment manager

## Slack app setup

Create a Slack app at <https://api.slack.com/apps>:

1. Select **Create New App** and choose **From scratch**.
2. Under **OAuth & Permissions**, add these **Bot Token Scopes**:
   - `chat:write` — post commodity updates.
   - `files:write` — upload the optional voice note.
3. Install or reinstall the app in your workspace and copy the **Bot User OAuth
   Token**. It normally starts with `xoxb-`.
4. Invite the app to the destination channel with `/invite @YourApp`.
5. Copy the channel ID. In Slack, open the channel and choose **View channel
   details**; the channel ID is shown at the bottom.
6. Copy the Slack user ID of the person who should be mentioned. Open that user's
   profile, choose **More**, then **Copy member ID**.

Do not commit the bot token or any other secret. Store them in `.env` locally and in
Render's environment variables in production.

## Configuration

Copy the example file and fill in every value:

```bash
cp .env.example .env
```

| Variable | Description |
| --- | --- |
| `FIRECRAWL_API_KEY` | Firecrawl API key used to scrape the price pages. |
| `GROQ_API_KEY` | Groq API key used for text and optional voice generation. |
| `GOLD_URL` | URL containing the gold prices to scrape. |
| `SILVER_URL` | URL containing the silver price to scrape. |
| `SLACK_BOT_TOKEN` | Slack bot token, usually beginning with `xoxb-`. |
| `SLACK_CHANNEL_ID` | ID of the channel where updates are posted. |
| `SLACK_USER_ID` | Slack member ID to mention in each update. |

The source page should expose the relevant prices in text or Markdown. The generated
message is intentionally limited to figures found in the scraped content; it is not a
market-data validation service.

## Run locally

Install dependencies from the lockfile:

```bash
uv sync
```

Start the API:

```bash
uv run uvicorn main:app --reload
```

Check that the application is running:

```bash
curl http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

The scheduler runs when the application starts. To test a workflow immediately, run
its module directly after configuring `.env`:

```bash
uv run python graphs/gold.py
uv run python graphs/silver.py
```

These commands call external APIs and can create a real Slack message and incur
provider usage. Use a test channel and test source URLs first.

## Deploy on Render

Create a **Web Service** on [Render](https://render.com/):

1. Push this repository to GitHub or another Git provider.
2. In Render, choose **New → Web Service** and select the repository.
3. Use these settings:

   | Setting | Value |
   | --- | --- |
   | Runtime | Python 3 |
   | Build command | `pip install uv && uv sync --frozen` |
   | Start command | `uv run uvicorn main:app --host 0.0.0.0 --port $PORT` |
   | Health check path | `/health` |

4. Add all variables from the configuration table under **Environment**. Do not
   upload `.env` to the repository.
5. Choose a plan that keeps the service running continuously. A sleeping service can
   miss the scheduled 16:00 job.
6. Deploy and wait for the health check to pass.
7. Open the Render service URL and confirm `/health` returns `{"status":"ok"}`.

Render's `PORT` variable must be used in the start command. Binding to
`127.0.0.1` or hard-coding port `8000` will prevent Render from routing traffic to
the service.

### Render scheduling considerations

The scheduler is in-process. Run exactly one always-on Render instance to avoid
duplicate Slack messages. If you scale the service horizontally, every instance will
register the same cron job.

The job uses the `Asia/Karachi` timezone and has a five-minute misfire grace period.
Render restarts, deploys, sleeping services, or outages around 16:00 can therefore
cause an update to be delayed or skipped.

## Project layout

```text
main.py            FastAPI app, health endpoint, and scheduler
utils.py           Slack and speech text formatting helpers
graphs/gold.py     Gold scraping, generation, and Slack delivery workflow
graphs/silver.py   Silver scraping, generation, and Slack delivery workflow
.env.example       Required environment variable template
pyproject.toml     Project metadata and dependencies
uv.lock            Locked dependency versions
```

## Pre-deployment check

The checked-in `main.py` imports `workflow` from a top-level `graph` module, while
the visible workflow implementation is `gold_workflow` in `graphs/gold.py`. Before
deploying, make sure that import points to the workflow you intend to schedule (or
provide the `graph.py` module expected by `main.py`). Also ensure that any helper
imports used by the selected workflow exist in `utils.py`.

A quick import check is:

```bash
uv run python -c "import main; print(main.app)"
```

If this command fails, fix the import error before creating the Render service.

## Troubleshooting

- **`invalid_auth` or `not_in_channel`**: verify `SLACK_BOT_TOKEN`, invite the bot
  to the channel, and confirm `SLACK_CHANNEL_ID`.
- **No mention appears**: verify `SLACK_USER_ID` is a member ID, not a username or
  display name.
- **Firecrawl returns empty content**: check `GOLD_URL` or `SILVER_URL`, the page's
  accessibility, and Firecrawl usage limits.
- **Voice upload is missing**: the text update can still succeed when Groq audio
  generation is rate-limited or fails; inspect the Render logs for the voice error.
- **No scheduled message**: confirm the service is running continuously, only one
  instance is deployed, and the expected time is 16:00 in Pakistan Standard Time.

## Security

Treat Slack, Firecrawl, and Groq keys as secrets. Rotate them immediately if they
are exposed, and use Render's secret environment variables instead of putting them
in source control or README examples.
