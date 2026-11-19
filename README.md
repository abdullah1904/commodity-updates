# Commodity Updates

Commodity Updates is a Python service that collects gold and silver prices from web pages, formats the figures with Groq, and publishes the updates to Slack. When audio generation succeeds, the service also uploads an Urdu voice note.

The service is built with FastAPI, LangGraph, Firecrawl, Groq, Slack SDK, and APScheduler.

## How it works

Each commodity workflow runs these steps:

1. Firecrawl scrapes the configured source URL as Markdown.
2. The workflow keeps the first 12,000 characters of the scraped content.
3. Groq generates a concise Slack message using only the figures in that content.
4. Groq rewrites the message as spoken Pakistani Urdu and generates a WAV voice
   note.
5. The service mentions the configured Slack member, posts the text update, and
   uploads the voice note when audio generation was successful.

The gold workflow reports 24 and 21 carat prices for one tola and one gram. The silver workflow reports the one-tola price. Both workflows include a trend when the scraped source provides change data.

## Scheduled jobs

When the FastAPI application starts, it registers both workflows with an
in-process scheduler:

- **Gold:** Monday through Saturday at 04:00 PM
- **Silver:** Monday through Saturday at 04:00 PM
- **Timezone:** `Asia/Karachi`
- **Misfire grace period:** 5 minutes

Run only one service instance. Each instance registers both jobs, so multiple instances will send duplicate Slack updates. The scheduler does not run on Sunday.

## Requirements

- Python 3.13 or newer
- [uv](https://docs.astral.sh/uv/)
- A [Firecrawl](https://www.firecrawl.dev/) API key
- A [Groq](https://console.groq.com/) API key with access to:
  - `openai/gpt-oss-120b`
  - `canopylabs/orpheus-arabic-saudi`
- A Slack workspace where you can install a bot

## Configuration

Create a `.env` file in the project root. The application loads it when the commodity workflow modules are imported.

```dotenv
FIRECRAWL_API_KEY=your-firecrawl-api-key
GROQ_API_KEY=your-groq-api-key
GOLD_URL=https://example.com/gold-prices
SILVER_URL=https://example.com/silver-prices
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_CHANNEL_ID=your-channel-id
SLACK_USER_ID=your-member-id
```

| Variable | Purpose |
| --- | --- |
| `FIRECRAWL_API_KEY` | Authenticates Firecrawl scraping requests. |
| `GROQ_API_KEY` | Authenticates text and speech requests to Groq. |
| `GOLD_URL` | Source page for gold rates. |
| `SILVER_URL` | Source page for silver rates. |
| `SLACK_BOT_TOKEN` | Slack bot token, normally beginning with `xoxb-`. |
| `SLACK_CHANNEL_ID` | Channel where both updates are posted. |
| `SLACK_USER_ID` | Slack member ID mentioned above each update. |

The source pages should expose the relevant rates and any trend information in
text or Markdown. The workflows do not independently validate market data and
do not calculate missing values.

## Slack app setup

Create an app at <https://api.slack.com/apps>, then:

1. Add the bot token scopes `chat:write` and `files:write` under **OAuth &
   Permissions**.
2. Install the app in the workspace and copy its bot token.
3. Invite the app to the destination channel with `/invite @YourApp`.
4. Copy the channel ID from the channel details.
5. Copy the member ID of the person who should be mentioned.

Keep all tokens in `.env` or your hosting provider's secret environment
variables. Never commit them.

## Local development

Install the locked dependencies:

```bash
uv sync
```

Start the API and scheduler:

```bash
uv run uvicorn main:app --reload
```

Check the health endpoint:

```bash
curl http://127.0.0.1:8000/health
```

The response is:

```json
{"status":"ok"}
```

To run either workflow immediately instead of waiting for the scheduler:

```bash
uv run python graphs/gold.py
uv run python graphs/silver.py
```

These commands call Firecrawl, Groq, and Slack. Use a test channel and test
URLs because a successful run posts a real message and may consume provider
quotas.

## Deployment

The application can run as a long-lived web service on a platform such as
[Render](https://render.com/).

| Setting | Value |
| --- | --- |
| Runtime | Python 3 |
| Build command | `pip install uv && uv sync --frozen` |
| Start command | `uv run uvicorn main:app --host 0.0.0.0 --port $PORT` |
| Health check path | `/health` |

Configure every variable from the table above in the service's environment. Use the platform-provided `PORT` value and keep one instance running continuously; sleeping or restarting around 04:00 PM can delay or skip a job.

## Project structure

```text
main.py            FastAPI app, health endpoint, and scheduler
utils.py           Slack Markdown and speech-text formatting helpers
graphs/gold.py     Gold scraping, generation, and Slack delivery workflow
graphs/silver.py   Silver scraping, generation, and Slack delivery workflow
pyproject.toml     Project metadata and dependencies
uv.lock            Locked dependency versions
```

## Troubleshooting

- **`invalid_auth` or `not_in_channel`:** verify `SLACK_BOT_TOKEN`, invite the
  bot to the channel, and confirm `SLACK_CHANNEL_ID`.
- **The mention is missing:** use a Slack member ID in `SLACK_USER_ID`, not a
  username or display name.
- **The text update is posted but no voice note appears:** inspect the
  application logs. Groq rate limits and other audio-generation errors cause
  the workflow to continue without the voice upload.
- **The scraped content is empty or incomplete:** verify the relevant source
  URL and that Firecrawl can access the page.
- **Scheduled updates are duplicated:** run only one application instance.
- **No scheduled update is sent:** confirm the service is running, the
  environment variables are present, and the expected time is 04:00 PM in
  `Asia/Karachi`.

## Security

Treat Slack, Firecrawl, and Groq credentials as secrets. If a credential is
exposed, revoke or rotate it immediately and remove it from source control.
