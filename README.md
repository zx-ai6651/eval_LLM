# 🤖 Agent Eval Platform

> 基于多智能体的联网搜索型 Agent 配置测试与优化平台 — 系统化测试、评分、对比、自动优化你的 Agent 的 Prompt、模型与参数组合。

[![Python](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115-009688.svg)](https://fastapi.tiangolo.com/)
[![Vue](https://img.shields.io/badge/Vue-3.5-4FC08D.svg)](https://vuejs.org/)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)

---

## 📖 目录

- [项目概述](#-项目概述)
- [为什么需要这个平台](#-为什么需要这个平台)
- [核心功能](#-核心功能)
- [系统架构](#-系统架构)
- [技术栈](#-技术栈)
- [项目结构](#-项目结构)
- [快速开始](#-快速开始)
- [配置说明](#-配置说明)
- [API 参考](#-api-参考)
- [多智能体系统](#-多智能体系统)
- [评估体系](#-评估体系)
- [路线图](#-路线图)
- [参与贡献](#-参与贡献)

---

## 🎯 项目概述

**Agent Eval Platform** 是一个工程化的联网搜索型 AI Agent 配置测试与优化平台。你不再需要凭感觉猜测哪个 Prompt、哪个模型、哪组参数更好——而是通过可视化界面，**系统化地测试、评分、对比和自动优化**你的 Agent 配置。

### 核心问题

在开发联网搜索型 Agent 时，同一个任务，使用不同的 Prompt、模型和参数，结果可能天差地别。LLM 在联网搜索任务中经常出现以下问题：

| 问题类型 | 典型表现 |
|---|---|
| **时间错置** | 把旧信息改写成"最新消息" |
| **预测当事实** | 把报告中的预测内容当成已发生事件 |
| **编造事实** | 在没有可靠来源的情况下拼凑结论 |
| **来源不匹配** | 引用的来源无法支撑关键结论 |
| **虚假完整** | 输出看似全面，但真实有效信息很少 |
| **成本浪费** | 高价模型并没有带来明显的质量提升 |

**本平台将 Agent 调试从"凭感觉试 Prompt"转变为数据驱动、可复现的工程化流程。**

### 你能测试什么？

- ✅ 同一任务下多个 Prompt 版本的质量对比
- ✅ 同一 Prompt 下不同 LLM 模型的表现对比
- ✅ 参数敏感度测试（temperature、搜索次数、结构化输出等）
- ✅ 全组合测试：**Prompt × 模型 × 参数**
- ✅ 不同配置组合的成本与质量权衡

---

## ✨ 核心功能

### 第一阶段 —— 测试闭环（已完成）

| 功能 | 说明 |
|---|---|
| **任务创建** | 定义联网搜索型测试任务，设置背景与关注点 |
| **Prompt 管理** | 添加、编辑、版本管理、对比多个 Prompt 模板 |
| **模型配置** | 选择 DeepSeek、阿里百炼（Qwen）等候选模型 |
| **参数调优** | 配置 temperature、top_p、搜索次数、结构化输出等 |
| **组合生成** | 自动生成 `Prompt × 模型 × 参数` 测试矩阵 |
| **批次执行** | 运行所有组合，捕获原始输出、来源和成本 |
| **启发式评分** | 多维度评估，权重可配置 |
| **报告生成** | Markdown 对比报告，含排名与推荐 |
| **可视化面板** | Vue 3 全功能 Web 界面 |

### 第二阶段 —— 优化闭环（开发中）

| 功能 | 说明 |
|---|---|
| **自动 Prompt 优化** | 诊断失败原因 → 自动生成改进版 Prompt |
| **一键重测** | 将优化后的配置与原始配置同批对比 |
| **优化前后对比** | 并列展示质量与成本的变化 |
| **优化方案规划** | 多智能体诊断 → 行动计划 → 配置生成 |

### 核心特色

1. **真实性优先** — 表达质量再好也不能抵消事实错误
2. **严重问题规则** — 幻觉、伪造来源、时间错置自动触发分数上限
3. **成本追踪** — 每组组合的 token 用量 × 价格表 = 真实成本
4. **来源验证** — 来源 URL 归一化提取 + 引用与结论匹配检查
5. **演示模式** — 无 API Key 也能验证完整流程（结果明确标注为模拟数据）

---

## 🏗️ 系统架构

### 整体架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                      🖥️  前端展示层（Vue 3 + TypeScript + Vite）               │
│                                                                             │
│   用户浏览器 (http://localhost:5173)                                          │
│     │                                                                       │
│     ├── Vue Router（路由管理）                                                │
│     ├── Pinia（状态管理）                                                     │
│     ├── 6 个页面组件                                                          │
│     │   Dashboard · 任务列表 · 任务创建 · 任务详情 · 流水线 · 模型库            │
│     ├── 通用组件：SectionPanel · StatusBadge                                 │
│     └── Axios HTTP 客户端（38 个类型化 API 函数）                              │
│                                                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  HTTP REST 调用
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    ⚙️  后端应用层（FastAPI + Python 3.12）                     │
│                                                                             │
│   FastAPI 服务器 (http://localhost:8000)                                      │
│     │                                                                       │
│     ├── REST API 路由层（8 个模块）                                           │
│     │   /api/tasks · /api/batches · /api/pipeline · /api/reports            │
│     │   /api/optimization · /api/model-library · /api/configs · /api/health │
│     │                                                                       │
│     ├── 业务服务层（14 个模块）                                                │
│     │   ├── 核心服务：execution · evaluator · reporting · pipeline           │
│     │   ├── 优化服务：prompt_optimization · optimization_planner              │
│     │   ├── 规则引擎：evaluation_rules · recommendation                      │
│     │   └── 工具服务：search_planning · source_normalization · output_contracts│
│     │                                                                       │
│     └── 数据访问层                                                            │
│         ├── Pydantic v2 校验（50+ DTO 模型）                                  │
│         └── SQLAlchemy ORM（14 张数据表映射）                                  │
│                                                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  编排调用
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                    🧠  多智能体系统（LangGraph 编排）                           │
│                                                                             │
│   ┌───────────────────────────────────────────────────────────────────┐    │
│   │                    7 个专用智能体                                    │    │
│   │                                                                   │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │    │
│   │  │ 流水线规划    │  │ 任务执行      │  │ 评估 Agent   │            │    │
│   │  │ Agent         │  │ Agent         │  │              │            │    │
│   │  │              │  │              │  │              │            │    │
│   │  │ 自然语言 →    │  │ 调用 LLM +   │  │ 6 维度打分   │            │    │
│   │  │ 测试方案      │  │ 搜索工具      │  │ + 评分理由   │            │    │
│   │  │              │  │              │  │              │            │    │
│   │  │ 模型:Qwen-Max│  │ 模型:Qwen-Plus│  │ 模型:Qwen-Plus│           │    │
│   │  └──────────────┘  └──────────────┘  └──────────────┘            │    │
│   │                                                                   │    │
│   │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐            │    │
│   │  │ 问题发现      │  │ Prompt 优化  │  │ 优化方案      │            │    │
│   │  │ Agent         │  │ Agent         │  │ Agent         │            │    │
│   │  │              │  │              │  │              │            │    │
│   │  │ 幻觉/时间     │  │ 诊断 → 生成  │  │ 汇总结果 →   │            │    │
│   │  │ 错置检测      │  │ 改进版 Prompt │  │ 行动计划      │            │    │
│   │  │              │  │              │  │              │            │    │
│   │  │ 模型:Qwen-Plus│  │ 模型:Qwen-Plus│  │ 模型:Qwen-Max│            │    │
│   │  └──────────────┘  └──────────────┘  └──────────────┘            │    │
│   │                                                                   │    │
│   │  ┌──────────────────────────────────────────────────────────┐    │    │
│   │  │                    报告生成 Agent                          │    │    │
│   │  │            Markdown 对比报告 + 排名 + 推荐                  │    │    │
│   │  │                    模型: Qwen-Plus                          │    │    │
│   │  └──────────────────────────────────────────────────────────┘    │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                    │                                        │
│   ┌────────────────────────────────▼───────────────────────────────────┐    │
│   │                     🔧 工具层（脚本化，非 LLM）                       │    │
│   │                                                                   │    │
│   │  ┌─────────────────────────┐  ┌─────────────────────────┐         │    │
│   │  │ ModelClient              │  │ SearchClient             │         │    │
│   │  │ LLM API 调用客户端        │  │ 搜索 API 调用客户端       │         │    │
│   │  │ OpenAI 兼容 + 重试        │  │ Tavily / Serper           │         │    │
│   │  │ + 成本记录               │  │ 外部搜索                  │         │    │
│   │  └─────────────────────────┘  └─────────────────────────┘         │    │
│   └───────────────────────────────────────────────────────────────────┘    │
│                                                                             │
└──────────────────────────────────┬──────────────────────────────────────────┘
                                   │  API 调用
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          🌐  外部服务                                        │
│                                                                             │
│   ┌─────────────────────────┐  ┌─────────────────────────────────┐         │
│   │ LLM 平台 API             │  │ 搜索引擎 API                     │         │
│   │                         │  │                                 │         │
│   │ DeepSeek                │  │ 百炼内置搜索（默认）               │         │
│   │ 阿里百炼 (Qwen)          │  │ Tavily（可选）                    │         │
│   │ OpenAI 兼容接口          │  │ Serper（可选）                    │         │
│   └─────────────────────────┘  └─────────────────────────────────┘         │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────────────┐
│                       💾  数据与部署                                         │
│                                                                             │
│   ┌──────────────────┐  ┌──────────────────────────────────────┐           │
│   │ 数据库            │  │ Docker Compose 部署                   │           │
│   │                  │  │                                      │           │
│   │ MySQL 8.4（生产）│  │  MySQL :3306                         │           │
│   │ SQLite（开发）    │  │  Backend :8000                       │           │
│   │ 14 张数据表       │  │  Frontend :5173                      │           │
│   └──────────────────┘  └──────────────────────────────────────┘           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 核心数据流

```
用户创建任务
      │
      ├──→ 添加 Prompt（多个版本）
      ├──→ 添加模型配置（多个候选模型）
      └──→ 添加参数配置（多组参数组合）
                  │
                  ▼
         自动生成测试组合矩阵
         Prompt × 模型 × 参数
                  │
                  ▼
┌─────────────────────────────────────────────────────┐
│                   批次异步执行                        │
│                                                     │
│   ① 构建搜索计划                                     │
│        │                                            │
│        ▼                                            │
│   ② 执行联网搜索（百炼内置 / Tavily / Serper）        │
│        │                                            │
│        ▼                                            │
│   ③ 调用 LLM 生成结果（含结构化输出约束）              │
│        │                                            │
│        ▼                                            │
│   ④ 提取并归一化来源 URL                              │
│        │                                            │
│        ▼                                            │
│   ⑤ 评估 Agent 打分（6 个维度）                       │
│        │                                            │
│        ▼                                            │
│   ⑥ 应用严重问题规则（幻觉/时间错置自动扣分封顶）       │
│        │                                            │
│        ▼                                            │
│   ⑦ 保存 TestResult + EvaluationResult              │
│        │                                            │
│        ▼                                            │
│   ⑧ 排名所有组合 → 标记推荐组合                        │
│        │                                            │
│        ▼                                            │
│   ⑨ 生成 Markdown 对比报告                           │
│                                                     │
└─────────────────────────────────────────────────────┘
                  │
                  ▼
         用户查看报告 + 排名
                  │
                  ├──→ 选择推荐配置，投入使用
                  │
                  └──→ [一键优化]
                        │
                        ▼
                 自动诊断问题 → 生成新版 Prompt/参数
                        │
                        ▼
                 创建新一轮测试批次
                        │
                        ▼
                 优化前后对比报告 → 继续迭代
```

### 数据库实体关系

```
TestTask（测试任务）
  │
  ├── 1:N ──→ Prompt（Prompt 模板）
  ├── 1:N ──→ ModelConfig（模型配置）
  ├── 1:N ──→ ParameterConfig（参数配置）
  ├── 1:N ──→ EvaluationTarget（评测目标 + 权重）
  │
  └── 1:N ──→ TestBatch（测试批次）
                │
                ├── 1:N ──→ TestCombination（测试组合）
                │             │
                │             ├── N:1 ──→ Prompt
                │             ├── N:1 ──→ ModelConfig
                │             ├── N:1 ──→ ParameterConfig
                │             │
                │             ├── 1:1 ──→ TestResult（执行结果）
                │             │            raw_output · sources_json
                │             │            search_logs_json · cost
                │             │
                │             └── 1:1 ──→ EvaluationResult（评分结果）
                │                          total_score · truthfulness_score
                │                          completeness_score · source_quality_score
                │                          stability_score · structure_score
                │                          cost_efficiency_score · risk_level
                │
                ├── 1:N ──→ Report（对比报告）
                │
                └── 1:1 ──→ OptimizationPlan（优化方案）
                              │
                              └──→ 指向新的 TestBatch（优化后重测）

ModelProfile（模型库，独立维护）
  │ provider · name · display_name
  │ input_price · output_price
  │ characteristics_json（特点标签）
  │ avg_total_score · total_test_count（自动聚合统计）
```

---

## 🛠️ 技术栈

| 层级 | 技术 | 用途 |
|---|---|---|
| **前端** | Vue 3、TypeScript、Vite | 响应式单页应用 |
| | Vue Router、Pinia | 路由与状态管理 |
| | Axios | HTTP API 调用 |
| **后端** | FastAPI 0.115 | 异步 REST API，自动生成 OpenAPI 文档 |
| | Pydantic v2 | 请求/响应校验与序列化 |
| | SQLAlchemy 2.0 | ORM 数据库映射 |
| | LangGraph 0.2 | 多智能体工作流编排 |
| **数据库** | MySQL 8.4（生产）/ SQLite（开发） | 持久化存储 |
| **模型平台** | DeepSeek、阿里百炼 (Qwen) | OpenAI 兼容 Chat Completions |
| **搜索引擎** | 百炼内置搜索、Tavily、Serper | 联网搜索后端 |
| **部署** | Docker Compose | 一键全栈部署 |

---

## 📁 项目结构

```
eval_LLM/
├── backend/                        # FastAPI 后端
│   ├── app/
│   │   ├── agents/                 # 智能体 Prompt 模板
│   │   │   ├── graph.py                    # LangGraph 工作流编排
│   │   │   ├── evaluation_prompts.py       # 评估 Agent Prompt
│   │   │   ├── pipeline_prompts.py         # 流水线规划 Agent Prompt
│   │   │   ├── prompt_optimization_prompts.py  # Prompt 优化 Agent Prompt
│   │   │   └── optimization_planner_prompts.py # 优化方案 Agent Prompt
│   │   ├── api/                    # REST API 层
│   │   │   ├── router.py                   # 路由汇总
│   │   │   └── routes/                     # 各路由模块
│   │   │       ├── tasks.py                # 任务 CRUD
│   │   │       ├── batches.py              # 批次管理
│   │   │       ├── pipeline.py             # 智能流水线
│   │   │       ├── reports.py              # 报告生成
│   │   │       ├── model_library.py        # 模型库管理
│   │   │       ├── optimization.py         # 一键优化
│   │   │       ├── configs.py              # Prompt/模型/参数配置
│   │   │       └── health.py               # 健康检查
│   │   ├── core/                   # 核心配置
│   │   │   ├── config.py                   # 应用设置（环境变量）
│   │   │   ├── model_adapters.py           # 多平台 LLM 适配器
│   │   │   └── pricing.py                  # 成本计算引擎
│   │   ├── db/                     # 数据库
│   │   │   └── session.py                  # SQLAlchemy 会话与初始化
│   │   ├── models/                 # ORM 实体
│   │   │   └── entities.py                 # 14 张数据表模型定义
│   │   ├── schemas/                # Pydantic DTO
│   │   │   └── dto.py                      # 50+ 请求/响应模型
│   │   ├── services/               # 业务逻辑
│   │   │   ├── crud.py                     # 通用 CRUD 操作
│   │   │   ├── execution.py                # 批次执行编排器
│   │   │   ├── evaluator.py                # 多维度评分
│   │   │   ├── evaluation_rules.py         # 严重问题规则引擎
│   │   │   ├── reporting.py                # Markdown 报告生成
│   │   │   ├── pipeline.py                 # 智能规划与自动生成
│   │   │   ├── recommendation.py           # 最佳配置排名算法
│   │   │   ├── prompt_optimization.py      # Prompt 自动优化
│   │   │   ├── optimization_planner.py     # 优化动作规划器
│   │   │   ├── model_library.py            # 模型库管理
│   │   │   ├── search_planning.py          # 搜索策略规划
│   │   │   ├── source_normalization.py     # 来源 URL 提取与归一化
│   │   │   ├── output_contracts.py         # 结构化输出协议
│   │   │   └── defaults.py                 # 默认评测配置
│   │   ├── tools/                  # 外部服务客户端
│   │   │   ├── model_client.py             # 统一 LLM API 客户端
│   │   │   └── search_client.py            # 统一搜索 API 客户端
│   │   └── main.py                 # FastAPI 应用入口
│   ├── scripts/
│   │   └── migrate_models_to_db.py         # 数据库迁移脚本
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                       # Vue 3 前端
│   ├── src/
│   │   ├── api/                    # API 客户端层
│   │   │   ├── client.ts                   # Axios 实例配置
│   │   │   └── platform.ts                 # 38 个类型化 API 函数
│   │   ├── components/             # 通用组件
│   │   │   ├── SectionPanel.vue             # 可折叠区域容器
│   │   │   └── StatusBadge.vue             # 状态标签
│   │   ├── layouts/
│   │   │   └── AppLayout.vue               # 主布局（含侧边导航）
│   │   ├── router/
│   │   │   └── index.ts                    # Vue Router 路由配置
│   │   ├── types/
│   │   │   └── index.ts                    # TypeScript 类型定义
│   │   ├── utils/
│   │   │   └── format.ts                   # 格式化工具函数
│   │   ├── views/                  # 页面组件
│   │   │   ├── DashboardView.vue           # 首页仪表盘
│   │   │   ├── TasksView.vue               # 任务列表
│   │   │   ├── TaskCreateView.vue          # 任务创建向导
│   │   │   ├── TaskDetailView.vue          # 任务详情与配置管理
│   │   │   ├── TaskPipelineView.vue        # 智能流水线生成
│   │   │   └── ModelLibraryView.vue        # 模型库管理
│   │   ├── App.vue                 # 根组件
│   │   ├── main.ts                 # Vue 应用入口
│   │   ├── styles.css              # 全局样式
│   │   └── env.d.ts                # 环境类型声明
│   ├── package.json
│   └── Dockerfile
├── config/                         # 集中配置文件
│   ├── model_adapters.json         # LLM 平台与 Agent 模型分配
│   └── pricing.json                # 模型与工具定价表
├── classifier/                     # 实验性：文本分类评估工具
├── docker-compose.yml              # Docker 全栈部署
├── requirements.txt                # 根依赖（指向 backend/）
├── .gitignore
├── .editorconfig
├── AGENTS.md                       # 编程助手指引
├── LICENSE
└── README.md
```

---

## 🚀 快速开始

### 环境要求

- **Python** 3.12+
- **Node.js** 18+
- **MySQL** 8.4（可选，本地开发默认使用 SQLite）

### 本地开发

#### 1. 克隆项目并启动后端

```bash
git clone <your-repo-url>
cd eval_LLM

# 后端
cd backend
cp .env.example .env          # 编辑 .env 填入 API Key
python -m venv .venv
.venv\Scripts\activate         # Windows
# source .venv/bin/activate    # macOS / Linux
pip install -r requirements.txt
uvicorn app.main:app --reload
```

后端运行在 **http://localhost:8000**
- 交互式 API 文档：http://localhost:8000/docs
- 健康检查：http://localhost:8000/api/health

#### 2. 启动前端

```bash
cd frontend
cp .env.example .env
npm install
npm run dev
```

前端运行在 **http://localhost:5173**

#### 3. 配置 API Key

编辑 `backend/.env`：

```env
# LLM 平台 API Key
DEEPSEEK_API_KEY=你的-DeepSeek-Key
BAILIAN_API_KEY=你的-百炼-Key

# 数据库（本地开发默认 SQLite）
DATABASE_URL=sqlite:///./agent_eval.db

# 可选：外部搜索引擎
# SEARCH_PROVIDER=tavily
# TAVILY_API_KEY=你的-Tavily-Key
```

每个 Agent 的模型分配在 `config/model_adapters.json` 中配置，可以为执行、评估、优化等不同 Agent 指定不同的平台和模型。

### Docker Compose 一键部署

```bash
cp backend\.env.example backend\.env   # 编辑 .env 填入 API Key
docker compose up --build
```

一键启动 MySQL 8.4 + FastAPI 后端 + Vue 前端。

---

## ⚙️ 配置说明

### 模型适配器（`config/model_adapters.json`）

定义可用的 LLM 平台及每个 Agent 的模型分配：

```json
{
  "providers": {
    "deepseek": {
      "label": "DeepSeek",
      "api_style": "openai_compatible",
      "base_url": "https://api.deepseek.com",
      "default_model": "deepseek-v4-flash"
    },
    "bailian": {
      "label": "阿里百炼",
      "builtin_search": { "enabled": true }
    }
  },
  "agents": {
    "task_executor": { "provider": "bailian", "model": "qwen3.7-plus" },
    "evaluator":     { "provider": "bailian", "model": "qwen3.7-plus" },
    "reporter":      { "provider": "bailian", "model": "qwen3.7-plus" }
  }
}
```

**支持的搜索模式：**
- `bailian_builtin`（默认）— 百炼 Chat Completions 内置联网搜索
- `tavily` / `serper` — 外部搜索 API（需配置对应的 API Key）

### 定价配置（`config/pricing.json`）

按模型和工具配置价格，用于成本统计：

```json
{
  "currency": "CNY",
  "providers": {
    "bailian": {
      "models": {
        "qwen3.7-plus": {
          "input_per_million_tokens": 1,
          "output_per_million_tokens": 4
        }
      },
      "tools": {
        "web_search_per_1000_calls": 4
      }
    }
  }
}
```

### 评测权重

默认评分权重（每个任务可单独调整）：

| 维度 | 权重 | 说明 |
|---|---|---|
| **真实性** | 50 | 事实准确性，是否存在幻觉 |
| **完整性** | 20 | 是否覆盖了所有必要信息 |
| **来源质量** | 10 | 引用来源的可靠性与相关性 |
| **稳定性** | 10 | 多次运行结果的一致性 |
| **结构与表达** | 5 | 输出组织的清晰度与可读性 |
| **成本效率** | 5 | 成本与质量的比值 |

> **真实性是不可妥协的第一原则。** 报告写得再好，也不能抵消事实错误。

---

## 📡 API 参考

后端启动后，完整的交互式 API 文档在 http://localhost:8000/docs。

### 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| `GET` | `/api/health` | 健康检查 |
| `POST` | `/api/tasks` | 创建测试任务 |
| `GET` | `/api/tasks` | 获取任务列表 |
| `GET` | `/api/tasks/{id}` | 获取任务详情 |
| `POST` | `/api/tasks/{id}/prompts` | 添加 Prompt |
| `POST` | `/api/tasks/{id}/model-configs` | 添加模型配置 |
| `POST` | `/api/tasks/{id}/parameter-configs` | 添加参数配置 |
| `POST` | `/api/tasks/{id}/batches` | 创建并运行测试批次 |
| `GET` | `/api/batches/{id}` | 获取批次状态与结果 |
| `GET` | `/api/reports/{id}` | 获取评估报告 |
| `POST` | `/api/pipeline/draft` | 从需求描述生成测试方案 |
| `POST` | `/api/pipeline/commit` | 将生成的方案提交为正式任务 |
| `POST` | `/api/optimization/plan` | 生成优化方案 |
| `POST` | `/api/optimization/execute/{plan_id}` | 执行优化 |
| `GET` | `/api/model-library/models` | 获取模型库列表 |
| `GET` | `/api/model-library/models/{id}/stats` | 获取模型性能统计 |

---

## 🧠 多智能体系统

平台使用 **LangGraph** 编排 7 个专用 LLM Agent 协作完成测试全流程：

| Agent | 角色 | 核心职责 |
|---|---|---|
| **流水线规划 Agent** | 任务解析与规划 | 理解用户自然语言需求 → 生成包含 Prompt、模型、参数的测试方案 |
| **任务执行 Agent** | 测试执行 | 调用 LLM + 搜索工具，捕获输出、来源、token 用量和成本 |
| **评估 Agent** | 质量评分 | 6 维度打分，输出分项得分和详细评分理由 |
| **问题发现 Agent** | 问题诊断 | 识别幻觉、时间错置、来源不匹配、信息遗漏等问题 |
| **Prompt 优化 Agent** | 配置改进 | 诊断失败模式 → 生成改进版 Prompt |
| **优化方案 Agent** | 行动规划 | 汇总评估结果 → 生成结构化的优化行动计划 |
| **报告生成 Agent** | 报告输出 | 汇总所有结果 → 生成带排名的 Markdown 对比报告 |

### 设计原则：Agent + 工具 混合架构

- **LLM Agent** 负责语义理解和判断：质量评估、失败归因、优化方案设计
- **脚本化工具** 负责确定性计算：成本计算、参数组合生成、来源 URL 提取、格式校验

这种混合设计兼顾了 LLM 的语义理解能力和工程自动化的可靠性。

---

## 📊 评估体系

### 评分流水线

```
原始 LLM 输出
      │
      ▼
来源归一化（提取并校验 URL）
      │
      ▼
多维度评分（6 个维度 × 可配置权重）
      │
      ▼
严重问题规则检查（幻觉/时间错置/伪造来源 自动扣分封顶）
      │
      ▼
问题诊断（具体问题定位）
      │
      ▼
最终得分 + 风险等级 + 推荐标记
```

### 严重问题规则

以下问题会触发自动分数上限，不因其他维度表现好而豁免：

| 问题 | 处理 |
|---|---|
| **出现明显幻觉**（≥1 处） | 至少扣 40 分 |
| **伪造来源** 或 **来源无法支撑关键结论** | 总分封顶 40 分 |
| **时间错置**（把旧信息写成最新事件） | 总分封顶 60 分 |
| **预测内容当成已发生事实** | 总分封顶 60 分 |
| **关键结论缺少来源支撑** | 总分封顶 70 分 |

---

## 🗺️ 路线图

| 阶段 | 重点 | 状态 |
|---|---|---|
| **第一阶段** | 核心测试闭环：创建任务 → 执行 → 评估 → 报告 | ✅ 已完成 |
| **第二阶段** | Prompt 优化闭环：诊断 → 优化 → 重测 → 对比 | 🔄 开发中 |
| **第三阶段** | 高级组合测试：全矩阵排名与综合分析 | 📋 计划中 |
| **第四阶段** | 工程化增强：异步任务（Celery）、Redis 缓存、增强持久化 | 📋 计划中 |
| **第五阶段** | 任务类型扩展：文档分析、代码调试、写作辅助等 Agent 类型 | 📋 计划中 |

---

## 🤝 参与贡献

欢迎贡献代码！参与步骤：

1. **Fork** 本仓库
2. **创建分支**：`git checkout -b feature/你的功能`
3. **编写代码**，遵循项目代码风格
4. **本地测试**，确保功能正常
5. **提交** 并附上清晰的 commit message
6. **Push** 并发起 **Pull Request**

### 代码风格

- **后端**：遵循 PEP 8，使用类型标注，业务逻辑放在 `services/` 中，不在路由处理函数中写复杂逻辑
- **前端**：TypeScript 严格模式，使用 Vue 3 Composition API，API 调用统一放在 `api/` 层
- **配置**：配置文件集中在 `config/` 目录，不在源码中硬编码

### 开发提示

- 没有 MySQL 时，保持 `backend/.env` 中 `DATABASE_URL=sqlite:///./agent_eval.db` 即可使用 SQLite
- 不配置 API Key 时平台会自动进入**演示模式**（结果明确标注为模拟数据）
- Conda 用户：项目使用名为 `eval` 的 conda 环境

---

## 📄 许可证

本项目基于 MIT 许可证开源 — 详见 [LICENSE](LICENSE) 文件。

---

## 🙏 致谢

- **LangGraph** — 多智能体工作流编排框架
- **FastAPI** — 高性能 Python Web 框架
- **Vue.js** — 渐进式 JavaScript 框架
- **DeepSeek** & **阿里百炼 (Qwen)** — LLM API 平台
- **Tavily** & **Serper** — 联网搜索 API

---

*为 Agent 工程社区而建。让 Agent 调试从凭感觉变成靠数据。*
