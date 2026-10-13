# -*- coding: utf-8 -*-
"""
竞赛信息查询服务 —— 同时提供 MCP 协议接口和 REST API
MCP 端点: /mcp   （可添加到 AgentArt / Claude / 任何支持 MCP 的平台）
REST 端点: /search /detail /list_levels /list_categories
"""
import json
import os
from contextlib import asynccontextmanager
from datetime import date

from fastapi import FastAPI, HTTPException, Query
from mcp.server.fastmcp import FastMCP

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_PATH = os.path.join(BASE, "data", "competitions.json")

with open(DATA_PATH, encoding="utf-8") as f:
    DATA = json.load(f)
COMPETITIONS = DATA["competitions"]

# streamable_http_path="/": 使挂载后最终端点就是 /mcp（不带二级路径）
mcp = FastMCP("campus-competition-db", streamable_http_path="/")
mcp_app = mcp.streamable_http_app()


@asynccontextmanager
async def lifespan(app):
    # 把 MCP 子应用的 lifespan 纳入主应用，否则 Task group is not initialized
    async with mcp_app.router.lifespan_context(app):
        yield


app = FastAPI(title="大学生竞赛信息库 API", version="1.0", lifespan=lifespan)

FIELDS = [
    "name(赛事全称)", "alias(简称)", "organizer(主办单位)", "level(级别)",
    "category(学科门类)", "description(简介/赛道)", "official_url(官网)",
    "edition_name(届次)", "edition_year(届次年份)",
    "registration_start/end(报名起止)", "competition_start/end(比赛起止)",
    "team_size_min/max(队伍人数)", "required_skills(技能标签)",
]


def _match(c, keyword):
    """关键词匹配：全称/简称/技能/类别等任意字段命中即可"""
    kw = keyword.lower()
    ed = c.get("edition") or {}
    hay = " ".join(filter(None, [
        c.get("name"), c.get("alias"), c.get("organizer"), c.get("level"),
        c.get("category"), c.get("description"),
        ed.get("edition_name"), " ".join(ed.get("required_skills") or []),
    ]))
    return kw in hay.lower()


def _brief(c):
    ed = c.get("edition") or {}
    return {
        "brand_id": c["brand_id"],
        "name": c["name"],
        "alias": c["alias"],
        "level": c["level"],
        "category": c["category"],
        "edition_name": ed.get("edition_name"),
        "registration_end": ed.get("registration_end"),
    }


def _full(c):
    ed = c.get("edition") or {}
    out = {k: c[k] for k in ("brand_id", "name", "alias", "official_url",
                             "organizer", "level", "category", "description")}
    out["edition"] = ed
    return out


def _today():
    return date.today().isoformat()


def _search(keyword=None, level=None, category=None, skill=None,
            status=None, limit=20):
    """核心查询逻辑，REST 和 MCP 共用"""
    res = []
    today = _today()
    for c in COMPETITIONS:
        ed = c.get("edition") or {}
        if keyword and not _match(c, keyword):
            continue
        if level and (c.get("level") or "") != level:
            continue
        if category and kw_in(category, c.get("category") or "") is False:
            continue
        if skill:
            skills = [s.lower() for s in (ed.get("required_skills") or [])]
            if skill.lower() not in skills:
                continue
        if status:
            rs, re_ = ed.get("registration_start"), ed.get("registration_end")
            if status == "报名中" and not (rs and re_ and rs <= today <= re_):
                continue
            if status == "未开始" and not (rs and rs > today):
                continue
            if status == "已结束" and not (re_ and re_ < today):
                continue
        res.append(c)
        if len(res) >= max(1, limit):
            break
    return res


def kw_in(needle, haystack):
    return needle.lower() in haystack.lower()


# ---------------- MCP 工具 ----------------

@mcp.tool()
def search_competitions(keyword: str = "", level: str = "",
                        category: str = "", skill: str = "",
                        registration_status: str = "", limit: int = 10) -> str:
    """搜索大学生竞赛。可按关键词(赛事名/简称/主办方等)、级别、学科门类、技能标签、
    报名状态(报名中/未开始/已结束)筛选。返回赛事列表摘要(JSON字符串)。"""
    rows = _search(keyword or None, level or None, category or None,
                   skill or None, registration_status or None, limit)
    return json.dumps([_brief(c) for c in rows], ensure_ascii=False)


@mcp.tool()
def get_competition_detail(name_or_alias: str) -> str:
    """按赛事全称或简称查询某场竞赛的完整信息：主办方、级别、赛道、届次、
    报名/比赛日期、组队人数要求、技能标签、官网。"""
    kw = name_or_alias.lower()
    for c in COMPETITIONS:
        names = [c.get("name") or "", c.get("alias") or ""]
        if any(kw == n.lower() or kw in n.lower() for n in names if n):
            return json.dumps(_full(c), ensure_ascii=False)
    raise ValueError(f"未找到竞赛: {name_or_alias}")


@mcp.tool()
def list_levels() -> str:
    """列出数据库中所有竞赛级别及各级别的竞赛数量。"""
    from collections import Counter
    cnt = Counter(c.get("level") or "未知" for c in COMPETITIONS)
    return json.dumps(dict(cnt), ensure_ascii=False)


@mcp.tool()
def list_fields() -> str:
    """列出本数据库可查询的全部字段说明。"""
    return json.dumps(FIELDS, ensure_ascii=False)


# 把 MCP 挂载到 FastAPI（streamable-http，最终端点 /mcp）
app.mount("/mcp", mcp_app)


# ---------------- REST API ----------------

@app.get("/")
def root():
    return {
        "service": "大学生竞赛信息库",
        "endpoints": ["/search", "/detail", "/stats", "/mcp (MCP)"],
        "mcp_config": {
            "url": "/mcp", "transport": "streamable-http",
            "tools": ["search_competitions", "get_competition_detail",
                      "list_levels", "list_fields"],
        },
        "total": len(COMPETITIONS),
    }


@app.get("/search")
def search(keyword: str = "", level: str = "", category: str = "",
           skill: str = "", status: str = "",
           limit: int = Query(20, ge=1, le=84)):
    rows = _search(keyword or None, level or None, category or None,
                   skill or None, status or None, limit)
    return {"count": len(rows), "results": [_full(c) for c in rows]}


@app.get("/detail")
def detail(name: str):
    kw = name.lower()
    for c in COMPETITIONS:
        names = [c.get("name") or "", c.get("alias") or ""]
        if any(kw == n.lower() or kw in n.lower() for n in names if n):
            return _full(c)
    raise HTTPException(404, f"未找到竞赛: {name}")


@app.get("/stats")
def stats():
    from collections import Counter
    return {
        "brands": len(COMPETITIONS),
        "by_level": dict(Counter(c.get("level") or "未知" for c in COMPETITIONS)),
        "by_category": dict(Counter(c.get("category") or "未知" for c in COMPETITIONS)),
        "registration_open_now": sum(
            1 for c in COMPETITIONS
            if (c["edition"] or {}).get("registration_start")
            and (c["edition"] or {}).get("registration_end")
            and c["edition"]["registration_start"] <= _today() <= c["edition"]["registration_end"]
        ),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
