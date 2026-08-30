"""演示数据种子（D4 起验收工具链）：demo 用户 + 一本书（卷/细纲/设定），幂等。

用法：.venv/bin/python scripts/seed_demo.py
登录：demo / demo-password
"""

import asyncio

from sqlalchemy import select

from app.core.security import hash_password
from app.db.engine import SessionLocal
from app.models import OutlineChapter, Project, Setting, User, Volume


async def ensure_demo(db) -> None:
    user = await db.scalar(select(User).where(User.username == "demo"))
    if user is None:
        user = User(username="demo", password_hash=hash_password("demo-password"), display_name="演示作者")
        db.add(user)
        await db.flush()
    project = await db.scalar(select(Project).where(Project.owner_id == user.id, Project.slug == "xianlu"))
    if project is None:
        project = Project(owner_id=user.id, slug="xianlu", title="仙路初开", genre="玄幻", platform="起点", status="active")
        db.add(project)
        await db.flush()
        vol = Volume(project_id=project.id, no=1, title="第一卷·风起")
        db.add(vol)
        await db.flush()
        beats_map = {
            1: ("苏醒", "主角陈玄自异变中苏醒，获得神秘玉佩金手指，遭遇首个冲突", 2000),
            2: ("试炼", "陈玄初步运用玉佩应对挑战，结识关键伙伴，埋下宿敌线索", 2000),
            3: ("初露锋芒", "陈玄当众展露实力引来注意，卷尾冲突爆发", 2200),
            4: ("破局", "陈玄化解危机，赢得宗门长老赏识", 2000),
            5: ("暗流", "宗门内斗浮现，玉佩异动指向旧日秘辛", 2200),
            6: ("夺宝", "秘境开启，多方势力争夺，陈玄浑水摸鱼", 2400),
            7: ("结怨", "宿敌正式登场，陈玄与之结下死仇", 2000),
            8: ("闭关", "陈玄闭关修炼，玉佩传授新功法", 2000),
            9: ("出山", "出关即遇袭，陈玄反杀立威", 2200),
            10: ("启程", "陈玄决定远行历练，第一卷终", 2000),
        }
        for no, (title, summary, target) in beats_map.items():
            db.add(
                OutlineChapter(
                    volume_id=vol.id,
                    chapter_no=no,
                    title=title,
                    beats={"summary": summary, "target_wordcount": target, "beats": [summary]},
                )
            )
        for kind, title, content in [
            ("style", "文风", "节奏明快，对话简练，环境描写克制，多用动作推动剧情。"),
            ("emotion_module", "情绪", "开篇聚焦紧迫感，中段松弛对比，结尾留钩子。"),
            ("rhythm", "节奏", "每章一个冲突，三幕结构：入场-推进-钩子。"),
            ("setting", "世界观", "修仙世界，灵气复苏纪元，宗门林立，秘境为机缘主战场。"),
        ]:
            db.add(Setting(project_id=project.id, kind=kind, title=title, content=content))
    await db.commit()
    print(f"✅ demo 数据就绪：user={user.username} / project={project.slug}（{project.title}）")


async def main() -> None:
    async with SessionLocal() as db:
        await ensure_demo(db)


if __name__ == "__main__":
    asyncio.run(main())
