"""RouterGraph（US-12）：意图路由，把用户输入分发到对应业务图。

D4 先落地意图判定 + 分发骨架；写意图由 WriteGraph 承接，其余意图返回 dispatch 结果，
后续天（D6/D8/D9）逐步接入拆文/审查/扫榜图。
"""

from typing import TypedDict

from app.graphs.ctx import GraphRuntime
from app.llm.contracts import OutputContract
from app.llm.retry import generate_checked
from app.schemas.writing import IntentResult
from app.services.prompt_registry import PromptRegistry

WRITE_INTENTS = {"write_chapter", "create_outline", "daily"}


class RouterState(TypedDict, total=False):
    user_id: int
    project_id: int | None
    user_intent: str
    scenario: str
    action: str
    intent: str
    project_ref: str | None
    dispatch: str | None  # 路由结果


def build_router_graph(runtime: GraphRuntime):
    db = runtime.db
    reg = PromptRegistry()

    async def _project_list(user_id: int | None) -> str:
        if user_id is None:
            return ""
        from sqlalchemy import select

        from app.models import Project

        rows = await db.scalars(select(Project).where(Project.owner_id == user_id).limit(10))
        return "；".join(f"{p.title}（{p.slug}）" for p in rows)

    async def intent_router(state: RouterState) -> RouterState:
        runtime.emit("stage", stage="route")
        if await runtime.factory.available("low"):
            projects = await _project_list(state.get("user_id"))
            prompt = reg.build_prompt({
                "system": reg.render("system/base"),
                "project": "【可用项目】",
                "tracking": "【追踪】意图路由",
                "task": "判断用户意图并给出 project_ref。",
                "tail": f"【用户输入】{state.get('user_intent', '')}\n【可用项目】{projects}",
            })
            result = await generate_checked(
                runtime.factory, "low", prompt, OutputContract(IntentResult), task_type="intent_router"
            )
        else:
            # 确定性兜底：按请求字段推断
            action = state.get("action", "write_chapter")
            intent = "write_chapter" if action in WRITE_INTENTS else "other"
            result = IntentResult(intent=intent, project_ref=state.get("project_ref"))
        dispatch = "write" if result.intent in WRITE_INTENTS else "unhandled"
        runtime.emit("status", progress=f"意图={result.intent} → {dispatch}")
        return {"intent": result.intent, "project_ref": result.project_ref, "dispatch": dispatch}

    async def unhandled(state: RouterState) -> RouterState:
        runtime.emit("stage", stage="unhandled")
        runtime.emit("status", progress=f"意图「{state.get('intent')}」尚未接入，请使用写作/拆文等入口")
        return {"dispatch": "unhandled"}

    from langgraph.graph import END, START, StateGraph

    graph = StateGraph(RouterState)
    graph.add_node("intent_router", intent_router)
    graph.add_node("unhandled", unhandled)
    graph.add_edge(START, "intent_router")
    graph.add_conditional_edges(
        "intent_router",
        lambda s: "write" if s.get("dispatch") == "write" else "unhandled",
        {"write": "unhandled", "unhandled": "unhandled"},  # D4: 写意图也返回路由结果，由 API 层接管
    )
    return graph.compile()
