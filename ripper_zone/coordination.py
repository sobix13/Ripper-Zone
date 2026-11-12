"""Protocol 2 registry. Never change other bots' roles, channels or bindings."""
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from pathlib import Path
from . import suite_protocol as protocol

SCHEMA = """CREATE TABLE IF NOT EXISTS resources(guild INTEGER NOT NULL,key TEXT NOT NULL,object_id INTEGER NOT NULL,
kind TEXT NOT NULL,owner TEXT NOT NULL,baseline TEXT NOT NULL,desired TEXT NOT NULL,state TEXT NOT NULL,PRIMARY KEY(guild,key));"""


class Registry:
    def __init__(self,path,owner):
        self.path=str(path);self.owner=owner

    async def run(self,fn):
        def run():
            c=sqlite3.connect(self.path,timeout=15);c.row_factory=sqlite3.Row
            try:
                c.execute("BEGIN IMMEDIATE");out=fn(c);c.commit();return out
            except BaseException:c.rollback();raise
            finally:c.close();protocol.shared_permissions(self.path)
        return await asyncio.to_thread(run)

    async def open(self):
        Path(self.path).parent.mkdir(parents=True,exist_ok=True)
        def init(c):
            c.execute(SCHEMA);protocol.initialize(c)
        await self.run(init)

    @asynccontextmanager
    async def lease(self,guild):
        token=await self.run(lambda c:protocol.claim(c,guild))
        try:yield token
        finally:await self.run(lambda c:protocol.release(c,guild,'server-setup',token))

    async def check_role(self,guild,role):
        def check(c):
            row=c.execute("SELECT * FROM resources WHERE guild=? AND object_id=?",(guild,role)).fetchone()
            if row and (row['owner']!=self.owner or row['state']!='active' or not row['key'].startswith('zone:role:')):
                raise ValueError("This role belongs to another bot or requires review.")
        await self.run(check)

    async def record(self,guild,obj,kind,key):
        async with self.lease(guild) as token:
            def put(c):
                protocol.ensure(c,guild,'server-setup',token)
                old=c.execute("SELECT * FROM resources WHERE guild=? AND object_id=?",(guild,obj)).fetchone()
                full=f"zone:{kind}:{key}"
                if old and (old['owner']!=self.owner or old['key']!=full or old['state']!='active'):
                    raise ValueError("A foreign resource binding was preserved.")
                other=c.execute("SELECT object_id FROM resources WHERE guild=? AND key=?",(guild,full)).fetchone()
                if other and other[0]!=obj:raise ValueError("This resource key is already bound. Review the existing message/role first.")
                c.execute("INSERT OR IGNORE INTO resources VALUES(?,?,?,?,?,'{}','{}','active')",(guild,full,obj,kind,self.owner))
            await self.run(put)
