from radar.config import Config
from radar.main import build_scheduler

CFG = Config(bot_token="t", channel_id="@c", admin_ids=frozenset({1}),
             openai_api_key="sk", openai_model="m", db_path=":memory:",
             scrapers_dir="scrapers", timezone="Europe/Berlin")


def test_scheduler_has_daily_0800_job():
    async def job():
        pass
    sched = build_scheduler(CFG, job)
    jobs = sched.get_jobs()
    assert len(jobs) == 1
    trigger = str(jobs[0].trigger)
    assert "hour='8'" in trigger and "minute='0'" in trigger
