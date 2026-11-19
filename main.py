import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from graphs.gold import gold_workflow
from graphs.silver import silver_workflow


logging.basicConfig(level=logging.INFO)
log = logging.getLogger("gold-bot")

TZ = "Asia/Karachi"
scheduler = AsyncIOScheduler(timezone=TZ)

async def gold_job():
    log.info("Cron: running gold workflow")
    try:
        out = await asyncio.to_thread(
            gold_workflow.invoke,
            {
                "is_voice": False
            },
        )
        log.info("Cron: sent as %s (attempts=%s)", out.get("attempts"))
    except Exception:
        log.exception("Cron: workflow failed")

async def silver_job():
    log.info("Cron: running silver workflow")
    try:
        out = await asyncio.to_thread(
            silver_workflow.invoke,
            {
                "is_voice": False
            },
        )
        log.info("Cron: sent as %s (attempts=%s)", out.get("attempts"))
    except Exception:
        log.exception("Cron: workflow failed")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        gold_job,
        CronTrigger(day_of_week="mon-sat", hour="16", minute=0, timezone=TZ),
        id="gold_job",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.add_job(
        silver_job,
        CronTrigger(day_of_week="mon-sat", hour="16", minute=0, timezone=TZ),
        id="silver_job",
        replace_existing=True,
        misfire_grace_time=300,
        coalesce=True,
    )
    scheduler.start()
    log.info("Scheduler started: 16:00 %s", TZ)
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(lifespan=lifespan)


@app.api_route("/health", methods=["GET", "HEAD"])
def health():
    return {"status": "ok"}