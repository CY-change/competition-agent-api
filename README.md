# 大学生竞赛信息库 · API + MCP 服务

把 84 条竞赛数据（品牌 + 届次）封装成一个**同时支持 REST API 和 MCP 协议**的查询服务，
供 AgentArt 上的 Agent 通过「API / MCP」方式调用。**无需租服务器，0 成本即可上线。**

## 目录结构

```
competitions_api/
├── server.py            # 服务（FastAPI + FastMCP，单文件）
├── data/competitions.json  # 84条竞赛数据（从赛事数据导入.sql解析生成）
├── requirements.txt
└── README.md
```

## 本地运行

```bash
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8000
```

## 提供的接口

### REST（浏览器直接可测）

| 端点 | 说明 | 示例 |
|---|---|---|
| `GET /` | 服务说明 | `curl http://localhost:8000/` |
| `GET /search?keyword=机器人&level=国家级&skill=编程&status=报名中&limit=10` | 多条件搜索 | `curl "http://localhost:8000/search?keyword=数学建模"` |
| `GET /detail?name=蓝桥杯` | 按全称/简称查完整信息 | `curl "http://localhost:8000/detail?name=蓝桥杯"` |
| `GET /stats` | 统计（按级别/门类/当前报名中数量） | `curl http://localhost:8000/stats` |

### MCP（给 AgentArt 等 Agent 平台用）

- **传输方式**：Streamable HTTP
- **端点 URL**：`http://<你的地址>/mcp`
- **4 个工具**：

| 工具 | 参数 | 用途 |
|---|---|---|
| `search_competitions` | keyword / level / category / skill / registration_status / limit | 按关键词、级别、门类、技能、报名状态搜竞赛 |
| `get_competition_detail` | name_or_alias | 查某场竞赛全量信息（主办方、届次、日期、人数要求、技能标签、官网） |
| `list_levels` | 无 | 列出所有级别及数量 |
| `list_fields` | 无 | 列出可查询字段说明 |

在 AgentArt 的 MCP/工具配置里填 `https://<部署地址>/mcp` 即可，Agent 会自动发现这 4 个工具。

---

## 部署方案（按成本从低到高）

### 方案 A：免费云托管 —— Render（推荐，5 分钟上线）

1. 把 `competitions_api/` 目录推到一个 GitHub 仓库（公开/私有都行）
2. 注册 [render.com](https://render.com)（GitHub 账号直接登录，免费额度足够）
3. New → **Web Service** → 连接该仓库
4. 配置：
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. 部署完成后拿到 `https://xxxx.onrender.com`，AgentArt 里填
   `https://xxxx.onrender.com/mcp`

> 免费版 15 分钟无访问会休眠，首次唤醒约 30 秒，演示/答辩前先访问一次预热即可。

### 方案 B：免费云托管 —— Hugging Face Spaces（无休眠困扰更少）

1. 注册 [huggingface.co](https://huggingface.co) → New Space → SDK 选 **Docker** → Blank 模板
2. 上传本目录所有文件，外加一个 `Dockerfile`：

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
CMD uvicorn server:app --host 0.0.0.0 --port 7860
```

3. 地址形如 `https://<用户名>-<空间名>.hf.space`，MCP 端点即 `https://xxx.hf.space/mcp`

### 方案 C：本机运行 + 内网穿透 —— cpolar 免费版（不写代码最快）

适合：电脑开机期间临时给 AgentArt 用。

1. 本地启动：`uvicorn server:app --host 0.0.0.0 --port 8000`
2. 下载 [cpolar](https://www.cpolar.com)（免费版）→ `cpolar http 8000`
3. 它给你一个公网地址如 `https://xxxx.r6.cpolar.top`，AgentArt 填 `https://xxxx.r6.cpolar.top/mcp`
4. 免费版地址每次重启会变，用之前重新生成一次即可

### 方案 D：直接上传静态 JSON（零服务，Agent 平台当资料喂）

如果 AgentArt 允许给 Agent 传文件/知识库，直接把 `data/competitions.json` 传上去，
在 Agent 的提示词里写明数据字段含义（见 `/` 端点返回的 tools 说明）。
缺点：无精确查询能力，靠模型自己读，数据量小（84条，约100KB）时完全够用。

### 方案 E：租云服务器（最后选项，确实要稳定在线才考虑）

轻量应用服务器（2核2G）约 ¥50-100/年（学生机更便宜）。装好 Python 后：

```bash
pip install -r requirements.txt
nohup uvicorn server:app --host 0.0.0.0 --port 8000 &
```

---

## 数据更新流程

改了 Excel / 数据库后重新生成 JSON：

```bash
python ../build_json.py   # 解析 赛事数据导入.sql -> data/competitions.json
```

或直接从 MySQL 导出（效果相同）：

```sql
SELECT ... INTO OUTFILE ... -- 或用任意导出工具转 JSON
```

## 数据说明

- 84 条竞赛：国家级 77、国际级 4、行业级 2、省部级 1
- 届次名与报名/比赛日期为联网核实结果，缺失字段为 `null`（未硬编）
- `edition_name` 为「默认」表示该赛事届次编号暂未核实到
