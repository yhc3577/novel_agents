"""端到端演示脚本（D12：US-32）——跑通写作 → 审查 → 去味 → 接受 → 扫榜 → 用量 全流程。

用法：
    python -m scripts.demo_flow                        # 连本机 http://127.0.0.1:8000/api
    python -m scripts.demo_flow --base http://localhost:8080/api   # 走 docker-compose 前端反代
    python -m scripts.demo_flow --keep                  # 跑完不删演示项目

依赖：pip install httpx（已包含在 [project.optional-dependencies] demo 组：pip install -e ".[demo]"）

前置：后端已启动（uvicorn / docker compose up），数据库已建表。
说明：
    - 每次运行注册一个全新演示账号（时间戳后缀），避免用户名冲突与数据串扰；
      登录后创建新项目，写作走 demo 模式（无 API key 时确定性 stub 内容）。
    - 写作任务用 SSE 实时订阅 Agent 活动（stage/tool/token/status），直观展示流式输出；
      其余任务（审查/去味/扫榜）用轮询 /tasks/{id} 收尾。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time

import httpx

# 所有路径都走 /api 前缀（后端 api_prefix="/api"）；health 不经 API 前缀
BASE = "http://127.0.0.1:8000/api"
HEADERS = {"Accept": "application/json"}

# ---- 终端彩色输出 ----

CYAN = "\033[36m"; GREEN = "\033[32m"; YELLOW = "\033[33m"; RED = "\033[31m"; DIM = "\033[2m"; RESET = "\033[0m"


def banner(title: str) -> None:
    print(f"\n{CYAN}=== {title} ==={RESET}")


def ok(msg: str) -> None:
    print(f"  {GREEN}✔{RESET} {msg}")


def info(msg: str) -> None:
    print(f"  {DIM}{msg}{RESET}")


def warn(msg: str) -> None:
    print(f"  {YELLOW}!{RESET} {msg}")


def fail(msg: str) -> None:
    print(f"  {RED}✘{RESET} {msg}")


def step(msg: str) -> None:
    print(f"\n  {YELLOW}▸{RESET} {msg}")


class DemoError(RuntimeError):
    pass


async def _ensure_ok(resp: httpx.Response, what: str) -> dict:
    if resp.is_error:
        detail = resp.text[:400]
        raise DemoError(f"{what} 失败 HTTP {resp.status_code}: {detail}")
    try:
        return resp.json()
    except json.JSONDecodeError:
        raise DemoError(f"{what} 响应非 JSON: {resp.text[:200]}")


async def _wait_task(client: httpx.AsyncClient, token: str, task_id: int, timeout: float = 180.0) -> dict:
    """轮询任务直到 success/failed/cancelled。"""
    auth = {"Authorization": f"Bearer {token}"}
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        r = await client.get(f"{BASE}/tasks/{task_id}", headers={**HEADERS, **auth})
        data = await _ensure_ok(r, "查询任务")
        status = data.get("status")
        if status in ("success", "failed", "cancelled"):
            if status != "success":
                raise DemoError(f"任务 {task_id}({data.get('type')}) 结束态为 {status}: {data.get('error')}")
            return data
        await asyncio.sleep(0.5)
    raise DemoError(f"任务 {task_id} 等待超时（>{timeout}s）")


async def _stream_sse(client: httpx.AsyncClient, token: str, task_id: int) -> None:
    """订阅 SSE 事件流直到 done，实时打印 stage/tool/token 活动。"""
    auth = {"Authorization": f"Bearer {token}"}
    headers = {**HEADERS, **auth, "Accept": "text/event-stream"}
    async with client.stream("GET", f"{BASE}/tasks/{task_id}/events", headers=headers) as resp:
        if resp.is_error:
            warn(f"SSE 订阅失败 HTTP {resp.status_code}（改用轮询）")
            return
        async for line in resp.aiter_lines():
            if not line.startswith("data: "):
                continue
            try:
                ev = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            etype = ev.get("type")
            if etype == "stage":
                print(f"      {CYAN}[stage]{RESET} {ev.get('stage')}")
            elif etype == "tool":
                out = ev.get("output")
                print(f"      {YELLOW}[tool]{RESET} {ev.get('tool')} · {ev.get('status')}"
                      + (f" · {ev.get('duration_ms')}ms" if ev.get("duration_ms") else ""))
                if out:
                    info(f"          {out[:160]}")
            elif etype == "token":
                # 只在流式阶段提示，不逐 token 刷屏
                pass
            elif etype == "status":
                print(f"      {GREEN}[status]{RESET} {ev.get('progress') or ev.get('status')}")
            elif etype == "checkpoint":
                print(f"      {CYAN}[checkpoint]{RESET} {ev.get('label', '')}")
            elif etype == "error":
                warn(f"事件流报错: {ev.get('error')}")
            elif etype == "done":
                ok(f"SSE 收到 done({ev.get('status')})，任务结束")
                return
    warn("SSE 流提前断开")


async def main() -> None:
    global BASE
    parser = argparse.ArgumentParser(description="novel_agents 全流程演示")
    parser.add_argument("--base", default=BASE)
    parser.add_argument("--keep", action="store_true", help="跑完不删除演示项目")
    parser.add_argument("--scenario", default="现代都市程序员穿越修仙界，靠代码思维炼丹炼器", help="写作场景（无 API key 时影响 stub 大纲）")
    args = parser.parse_args()
    BASE = args.base.rstrip("/")

    async with httpx.AsyncClient(timeout=httpx.Timeout(60.0, connect=10.0)) as client:
        # ---------- 1. 注册 / 登录 ----------
        banner("1/7 注册演示账号")
        suffix = str(int(time.time()))[-6:]
        username = f"demo_{suffix}"
        password = "demo-password"
        r = await client.post(f"{BASE}/auth/register", headers=HEADERS,
                              json={"username": username, "password": password, "display_name": "演示账号"})
        if r.status_code == 409:
            # 极端情况撞名：直接登录
            r = await client.post(f"{BASE}/auth/login", headers=HEADERS,
                                  json={"username": username, "password": password})
        tokens = await _ensure_ok(r, "注册/登录")
        token = tokens["access_token"]
        auth = {"Authorization": f"Bearer {token}"}
        ok(f"账号 {username} 就绪")

        # ---------- 2. 创建项目 ----------
        banner("2/7 创建项目")
        project_slug = f"demo-{suffix}"
        r = await client.post(f"{BASE}/projects", headers={**HEADERS, **auth},
                              json={"slug": project_slug, "title": f"演示项目·{suffix}", "genre": "玄幻", "platform": "起点"})
        project = await _ensure_ok(r, "创建项目")
        pid = project["id"]
        ok(f"项目 {project['title']} (id={pid})")

        # ---------- 3. 写作（SSE 流式） ----------
        banner("3/7 写作章节（SSE 实时订阅）")
        r = await client.post(f"{BASE}/projects/{pid}/chapters/next", headers={**HEADERS, **auth},
                              json={"action": "write_next", "scenario": args.scenario})
        task = await _ensure_ok(r, "发起写作任务")
        tid = task["id"]
        ok(f"写作任务 #{tid} 已启动")
        await _stream_sse(client, token, tid)
        await _wait_task(client, token, tid)

        r = await client.get(f"{BASE}/projects/{pid}/chapters", headers={**HEADERS, **auth})
        chapters = await _ensure_ok(r, "读取章节列表")
        ch1 = next((c for c in chapters if c["chapter_no"] == 1), None)
        if ch1 is None:
            raise DemoError("第 1 章未落库")
        ok(f"第 1 章《{ch1['title']}》已提交（{ch1['wordcount']} 字, rev {ch1['revision']}）")

        # ---------- 4. 审查 ----------
        banner("4/7 审查章节")
        r = await client.post(f"{BASE}/projects/{pid}/chapters/1/review", headers={**HEADERS, **auth},
                              json={"mode": "full"})
        task = await _ensure_ok(r, "发起审查")
        await _wait_task(client, token, task["id"])
        r = await client.get(f"{BASE}/projects/{pid}/chapters/1/reviews", headers={**HEADERS, **auth})
        reviews = await _ensure_ok(r, "读取审查结果")
        if not reviews:
            raise DemoError("审查未产生结果")
        top = reviews[0]
        ok(f"审查 {top.get('mode')} · 得分 {top.get('score')} · 结论 {top.get('verdict')}")
        for f in (top.get("findings") or [])[:3]:
            info(f"  · {f}" if isinstance(f, str) else f"  · {f}")
        info(f"汇总: {(top.get('summary') or '')[:120]}")

        # ---------- 5. 去味 + 接受 ----------
        banner("5/7 去味并接受改写")
        r = await client.post(f"{BASE}/projects/{pid}/chapters/1/deslop", headers={**HEADERS, **auth})
        task = await _ensure_ok(r, "发起去味")
        await _wait_task(client, token, task["id"])
        r = await client.get(f"{BASE}/projects/{pid}/chapters/1/deslop", headers={**HEADERS, **auth})
        dsl = await _ensure_ok(r, "读取去味结果")
        if not dsl.get("ready"):
            raise DemoError("去味结果未就绪")
        ok(f"去味定级 {dsl.get('grade')} · 得分 {dsl.get('score')} · "
           f"{dsl.get('original_wordcount')}→{dsl.get('new_wordcount')} 字（Δ{dsl.get('delta_wordcount', 0):+}）")
        info(f"改写片段: {(dsl.get('rewritten') or '')[:100]}…")
        r = await client.post(f"{BASE}/projects/{pid}/chapters/1/deslop/accept", headers={**HEADERS, **auth})
        await _ensure_ok(r, "接受去味")
        r = await client.get(f"{BASE}/projects/{pid}/chapters", headers={**HEADERS, **auth})
        ch1b = next(c for c in await _ensure_ok(r, "读取章节") if c["chapter_no"] == 1)
        ok(f"改写已写回，第 1 章 rev {ch1b['revision']}（原 {ch1['revision']}）")

        # ---------- 6. 扫榜 ----------
        banner("6/7 扫榜选题")
        r = await client.post(f"{BASE}/scan/runs", headers={**HEADERS, **auth}, json={})
        task = await _ensure_ok(r, "发起扫榜")
        await _wait_task(client, token, task["id"])
        r = await client.get(f"{BASE}/scan/latest", headers={**HEADERS, **auth})
        scan = await _ensure_ok(r, "读取扫榜结果")
        platforms = scan.get("platforms", [])
        if not platforms:
            raise DemoError("扫榜未产生平台快照")
        for p in platforms:
            report = p.get("report") or ""
            topic = "—"
            if isinstance(report, str):
                for line in report.splitlines():
                    if "推荐选题" in line and "：" in line:
                        topic = line.split("：", 1)[-1].strip()
                        break
            elif isinstance(report, dict):  # 兼容对象型 report
                topic = report.get("topic", "—")
            info(f"{p['platform']} · {len(p.get('cleaned', []))} 本有效 · 推荐选题: {topic}")
        ok("两平台快照已就绪")

        # ---------- 7. 用量 ----------
        banner("7/7 用量统计")
        r = await client.get(f"{BASE}/usage?days=30", headers={**HEADERS, **auth})
        usage = await _ensure_ok(r, "读取用量")
        totals = usage.get("totals", {})
        calls = totals.get("calls", 0)
        ok(f"本次演示产生 {calls} 次调用 · "
           f"{totals.get('prompt_tokens', 0)}/{(totals.get('completion_tokens', 0))} token（缓存命中 {totals.get('cached_tokens', 0)}）· "
           f"成本 ¥{totals.get('cost', '0')}")
        if calls == 0:
            info("（demo 模式未配置 API key，全流程走确定性 stub，故无真实 LLM 用量；")
            info("  配置 providers 密钥后，同样流程会按实际 token/成本计入用量页）")
        daily = usage.get("daily", [])
        if daily:
            top_day = daily[-1]
            info(f"最新一天 {top_day.get('date')}: {top_day.get('calls')} 次调用")

        # ---------- 收尾 ----------
        banner("演示完成")
        print(f"\n  {GREEN}全流程跑通 ✔{RESET}")
        print(f"  账号   {username} / {password}")
        print(f"  项目   {project['title']} (id={pid})")
        if not args.keep:
            step("清理演示项目（--keep 可保留）")
            r = await client.delete(f"{BASE}/projects/{pid}", headers={**HEADERS, **auth})
            if r.is_error:
                warn(f"删除项目失败 HTTP {r.status_code}: {r.text[:120]}")
            else:
                ok("演示项目已删除")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except DemoError as e:
        fail(str(e))
        sys.exit(1)
    except httpx.HTTPError as e:
        fail(f"网络错误: {e}")
        sys.exit(1)
