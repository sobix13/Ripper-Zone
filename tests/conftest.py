import pytest
from ripper_zone.storage import Database


@pytest.fixture
def clock():
    class Clock:
        now=1794484800
        def __call__(self):return self.now
    return Clock()


@pytest.fixture
async def db(tmp_path,clock):
    d=Database(tmp_path/'zone.sqlite3',clock);await d.open()
    cfg,rev=await d.config(1)
    cfg.update(active=True,panel_channel=11,tasks_channel=12,leaderboard_channel=13,raffle_channel=14,log_channel=15)
    await d.save_config(1,cfg,rev,2)
    return d


@pytest.fixture
def spec(clock):
    return dict(title='Community prize',prize='One collector car',price=10,max_tickets=10,winners=2,minimum=2,ends=clock.now+3600)


async def open_raffle(db,spec):
    rid=await db.create_raffle(1,2,spec)
    await db.begin_publish(1,rid,2,14);await db.bind_raffle(1,rid,100+rid)
    return rid
