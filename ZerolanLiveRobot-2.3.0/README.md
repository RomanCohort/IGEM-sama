# IGEM-sama

> IGEM-FBH 团队的 AI 虚拟主播 | Bilibili 直播互动 | 知识库驱动的合成生物学宣传者

![Python 3.10+](https://img.shields.io/badge/Python-3.10~3.11-blue) ![License](https://img.shields.io/badge/License-MIT-orange) ![AI VTuber](https://img.shields.io/badge/AI%20VTuber-blue) ![Bilibili](https://img.shields.io/badge/Bilibili-fb7299) ![RAG](https://img.shields.io/badge/RAG-Knowledge%20Base-green) ![Emotion](https://img.shields.io/badge/Emotion-Persistent-yellow)

IGEM-sama 是一个基于 [ZerolanLiveRobot](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot) 框架构建的 AI VTuber 系统，能够像 Neurosama 一样在 Bilibili 上自主直播，与观众实时互动，并通过 RAG 知识库回答关于团队项目的专业问题。

---

## 目录

- [功能概览](#功能概览)
- [系统架构](#系统架构)
- [快速开始](#快速开始)
- [配置说明](#配置说明)
- [子系统详解](#子系统详解)
  - [知识库 (RAG)](#知识库-rag)
  - [情感系统](#情感系统)
  - [长期记忆](#长期记忆)
  - [自主行为](#自主行为)
  - [互动工具](#互动工具)
  - [Live2D 表情映射](#live2d-表情映射)
  - [OBS 叠层控制](#obs-叠层控制)
  - [数据看板](#数据看板)
  - [操作员控制面板](#操作员控制面板)
  - [弹幕防刷 & 容错降级](#弹幕防刷--容错降级)
  - [高并发架构](#高并发架构)
- [部署方式](#部署方式)
- [项目结构](#项目结构)
- [依赖说明](#依赖说明)
- [常见问题](#常见问题)
- [致谢](#致谢)

---

## 功能概览

### 核心能力

| 能力 | 描述 |
|------|------|
| Bilibili 直播互动 | 实时监听弹幕、礼物、SuperChat，自动回复 |
| RAG 知识库 | 基于向量数据库检索队伍文档，专业回答项目问题 |
| 持久化情感系统 | 9种情绪状态追踪，平滑过渡，跨会话持久化 |
| Live2D 表情驱动 | 情绪实时映射到 Live2D 面部参数，表情随对话变化 |
| 长期记忆 | 跨会话记住重要事件、老观众档案、兴趣偏好 |
| 自主行为 | 定时主动发言、科普知识、介绍项目，像真人主播 |
| 互动工具 | 知识问答、抽奖、投票、倒计时，增强观众参与感 |
| TTS 语音合成 | 支持 GPT-SoVITS，可训练特色声线 |
| ASR 语音识别 | 支持语音输入，观众可以"跟 IGEM-sama 说话" |
| OCR + 图像理解 | 看屏幕内容，理解画面并回应 |
| OBS 集成 | 场景切换、叠层文字、问答/投票结果可视化 |
| 数据看板 | Web 实时监控：弹幕频率、情绪趋势、热门话题 |
| 操作员控制面板 | 全功能 Web 控制台，实时操控一切 |
| 容错降级 | 任意服务宕机不崩溃，自动降级到基础功能 |

### 对标 Neurosama 完成度

| Neurosama 特性 | IGEM-sama | 状态 |
|----------------|-----------|------|
| Live2D + 口型同步 | 内置 Live2D 渲染 + 自动口型 | 已有 |
| 弹幕实时互动 | Bilibili / YouTube / Twitch | 已有 |
| 情感驱动表情 | 9种情绪 → Live2D 参数映射 | **新增** |
| 主动说话 | 自主行为系统（闲聊/科普/推介） | **新增** |
| 长期记忆 | 跨会话记忆 + 观众档案 | **新增** |
| RAG 知识库 | Milvus 向量库 + 文档导入 | **新增**（Neurosama 无） |
| 互动游戏 | 问答/抽奖/投票/倒计时 | **新增** |
| 语音交互 | ASR → LLM → TTS 闭环 | 已有 |
| 唱歌 | — | 未实现 |
| 玩游戏 | 仅 Minecraft | 部分 |

---

## 系统架构

```
┌─────────────────────────────────────────────────────────┐
│                    IGEM-sama 整体架构                      │
├──────────────┬──────────────────────────┬───────────────┤
│   输入层      │       核心决策层          │    输出层      │
├──────────────┼──────────────────────────┼───────────────┤
│ B站弹幕      │                          │ TTS 语音输出   │
│ ASR 语音     │    LLM Agent             │ Live2D 表情    │
│ OCR 图像     │  ┌─────────────────┐     │ OBS 叠层       │
│ 键盘快捷键    │  │  上下文注入管线   │     │ B站弹幕回复    │
│              │  │                 │     │               │
│              │  │ [知识库检索]     │     │               │
│              │  │ [长期记忆]       │     │               │
│              │  │ [当前情绪]       │     │               │
│              │  │ [观众档案]       │     │               │
│              │  └────────┬────────┘     │               │
│              │           ↓              │               │
│              │  ┌─────────────────┐     │               │
│              │  │  LLM (DeepSeek) │     │               │
│              │  │  + Tool Agent   │     │               │
│              │  └────────┬────────┘     │               │
│              │           ↓              │               │
│              │  ┌─────────────────┐     │               │
│              │  │ 情感分析 → 表情  │     │               │
│              │  │ 记忆评分 → 存储  │     │               │
│              │  │ 内容过滤 → 审核  │     │               │
│              │  └─────────────────┘     │               │
├──────────────┴──────────────────────────┴───────────────┤
│                    支撑服务层                              │
├──────────┬──────────┬──────────┬──────────┬─────────────┤
│ Milvus   │ zerolan  │ OBS      │ 数据看板  │ 控制面板     │
│ 向量数据库│ -core    │ Studio   │ :8080    │ :9090       │
│          │ 模型服务  │          │          │             │
└──────────┴──────────┴──────────┴──────────┴─────────────┘
```

### 弹幕处理数据流

```
B站弹幕 → on_danmaku()
  ├── 防刷检查 (RateLimiter)
  ├── 情感关键词检测 (EmotionTracker)
  ├── 观众档案更新 (LongTermMemory)
  └── emit_llm_prediction()
        ├── [知识库检索] kb_pipeline.build_context()
        ├── [长期记忆]   long_term_memory.build_memory_context()
        ├── [当前情绪]   emotion_tracker.get_emotion_prompt_hint()
        ├── LLM推理     llm.predict()
        ├── 情感更新     emotion_tracker.update_from_sentiment()
        ├── 记忆存储     long_term_memory.add_memory()
        ├── Live2D表情   expression_driver.apply_emotion()
        └── TTS语音      tts.predict() → 扬声器播放

每秒定时器 (SecondEvent)
  ├── 情感衰减 (drift to neutral)
  ├── 表情同步 (emotion → Live2D)
  ├── 记忆衰减 (cleanup old memories)
  ├── 数据快照 (analytics.save_snapshot)
  └── 自主行为 (idle chat / science facts)
```

---

## 快速开始

### 前置条件

- Python 3.10+
- 至少一个 LLM 后端（推荐 DeepSeek API，最便宜）
- Bilibili 直播间及账号凭证

### 1. 安装依赖

```bash
cd ZerolanLiveRobot-2.3.0
pip install -r requirements.txt
pip install flask flask-cors   # 控制面板和数据看板
```

### 2. 配置

```bash
# 复制配置模板
cp config.igem-sama.yaml config.yaml

# 编辑 config.yaml，填写以下必填项：
# - B站 room_id, SESSDATA, bili_jct, buvid3
# - LLM API 地址和密钥
# - TTS 服务地址（可选）
```

获取B站凭证：浏览器登录B站 → F12 开发者工具 → Application → Cookies → 找到 SESSDATA、bili_jct、buvid3

### 3. 放入队伍文档

```bash
# 将 Markdown/文本/JSON 文档放入知识库目录
cp 你的项目文档/*.md knowledge_base/docs/

# 然后运行导入命令（需要 Milvus 服务运行中）
python -m knowledge_base.ingest --dir knowledge_base/docs
```

详细文档格式和分类建议见 [知识库文档目录](knowledge_base/docs/README.md)。

### 4. 启动

```bash
# Windows
start_igem_sama.bat

# Linux/Mac
chmod +x start_igem_sama.sh
./start_igem_sama.sh

# 或直接
python main.py
```

### 5. 访问控制面板

浏览器打开 `http://localhost:9090`

### 6. 桌宠模式（可选）

不想直播，只想让 IGEM-sama 在桌面上陪你？使用桌宠模式，只启动 Live2D 模型，无需任何后端服务：

```bash
# 默认启动（600px 窗口，右下角）
python desktop_pet.py

# 自定义大小
python desktop_pet.py --size 500

# 指定模型
python desktop_pet.py --model ./resources/static/models/live2d/hiyori_pro_mic.model3.json
```

**桌宠交互**：
- 拖拽移动：左键拖动窗口
- 点击反应：左键点击 → 开心表情 + 动作
- 右键菜单：手动切换情绪（开心/生气/难过/害羞/好奇/得意）
- 自动变化：每 15-30 秒随机切换表情和动作
- 退出：右键 → 退出

### 7. 模拟直播间（Demo 模式，无需真实服务）

无需 B站凭证、Milvus、TTS 服务，一键启动模拟直播间体验全部功能：

```bash
# 基础启动（MockLLM + Live2D + TTS 语音）
python demo.py

# 接入 DeepSeek 真实 AI 回复
python demo.py --api-key YOUR_DEEPSEEK_KEY

# 自动模拟观众弹幕
python demo.py --api-key YOUR_DEEPSEEK_KEY --auto-viewers

# 不启动 Live2D（纯 Web 界面）
python demo.py --no-live2d

# 关闭 TTS 语音输出
python demo.py --no-tts

# 显示 Live2D 桌面窗口（默认隐藏，仅在浏览器中显示）
python demo.py --show-window

# 自定义端口
python demo.py --port 8080
```

浏览器自动打开 `http://localhost:7070`，进入仿 B站直播间界面。

**Demo 模式功能**：

| 功能 | 描述 |
|------|------|
| Live2D 角色 | MJPEG 流嵌入浏览器，表情随弹幕变化 |
| 弹幕互动 | 输入弹幕 → AI 回复 + 语音 + 口型同步 |
| Edge TTS 语音 | 免费 TTS（`zh-CN-XiaoyiNeural`），自动朗读回复 |
| Live2D 口型同步 | 语音播放时驱动嘴型参数 |
| 情绪系统 | 9 种情绪，关键词触发 + 手动切换 |
| 送礼物 | 辣条/小电视/B坷垃/喵娘/礼物盒，触发感谢 + 动画 |
| SuperChat | 醒目留言，金色卡片叠层 + 重点回复 |
| 观众进出场 | 模拟"xxx 进入直播间"通知 |
| 模拟观众 | 自动发送弹幕，模拟真实直播氛围 |
| 自主行为 | 角色定时主动发言 |

---

## 配置说明

配置文件 `config.yaml` 基于 `config.igem-sama.yaml` 模板，主要配置项：

### LLM 后端选择

```yaml
pipeline:
  llm:
    # 方案1: 云端API（推荐新手）
    model_id: "deepseek-chat"
    predict_url: "https://api.deepseek.com/v1/chat/completions"

    # 方案2: 本地模型（需要GPU）
    # model_id: "deepseek-ai/DeepSeek-R1-Distill-Llama-8B"
    # predict_url: "http://127.0.0.1:11002/llm/predict"
```

### Bilibili 直播

```yaml
service:
  live_stream:
    bilibili:
      enable: true
      room_id: 你的直播间ID          # 必填
      credential:
        sessdata: "你的SESSDATA"      # 必填
        bili_jct: "你的bili_jct"      # 必填
        buvid3: "你的buvid3"          # 必填
```

### 知识库

```yaml
pipeline:
  kb:
    enable: true
    collection_name: "igem_kb"       # Milvus 集合名
    top_k: 3                         # 每次检索返回的文档块数
    max_chunk_chars: 500             # 文档分块最大字符数
    chunk_overlap: 50                # 分块重叠字符数
    docs_dir: "knowledge_base/docs"  # 文档目录
    auto_ingest_on_start: false      # 启动时自动导入
```

### 角色人设

```yaml
character:
  bot_name: "IGEM-sama"
  chat:
    system_prompt: >
      你现在是"IGEM-sama"，IGEM-FBH队伍的AI形象大使...
    injected_history:              # 预设对话，塑造角色风格
      - "你是谁？"
      - "我是IGEM-sama！IGEM-FBH队伍的AI大使！"
    max_history: 20                # 对话历史最大轮数
```

---

## 子系统详解

### 知识库 (RAG)

`knowledge_base/` — 基于 Milvus 向量数据库的 RAG 检索增强生成系统。

**文档导入**（知识库接口）：

```bash
# 批量导入目录下所有 .md/.txt/.json 文件
python -m knowledge_base.ingest --dir knowledge_base/docs --category project

# 导入单个文件
python -m knowledge_base.ingest --file wiki/safety.md --category safety

# 重建知识库（清除旧数据后重新导入）
python -m knowledge_base.ingest --dir knowledge_base/docs --reset

# 自定义分块参数
python -m knowledge_base.ingest --dir knowledge_base/docs --max-chars 300 --overlap 30
```

**分类标签**：

| 分类 | 用途 |
|------|------|
| `project` | 项目概述与背景 |
| `parts` | 生物元件 (BioBrick) |
| `wetlab` | 湿实验方案与结果 |
| `drylab` | 干实验建模与仿真 |
| `safety` | 安全规范与伦理 |
| `human_practices` | 人文实践 |
| `collaboration` | 合作与交流 |
| `general` | 其他 |

**工作原理**：每条弹幕发出前，自动在 Milvus 中检索相关文档片段，注入为 LLM 上下文。观众问"你们的项目是做什么的"，IGEM-sama 会从知识库中找到准确的团队项目描述来回答。

### 情感系统

`emotion/` — 持久化情感追踪 + Live2D 表情映射。

**9种情绪状态**：

| 情绪 | 触发关键词 | Live2D 效果 |
|------|-----------|-------------|
| happy | 开心、厉害、棒、哈哈 | 眯眼笑 + 嘴角上扬 |
| excited | 激动、超牛、震撼 | 睁大眼 + 扬眉 + 前倾 |
| calm | — | 平静微张眼 |
| curious | 为什么、怎么回事 | 抬眉 + 眼球上移 + 歪头 |
| sad | 难过、可惜、遗憾 | 垂眼 + 皱眉 + 嘴角下垂 |
| angry | 生气、烦、讨厌 | 压眉 + 紧嘴 |
| shy | 害羞、不好意思 | 低头 + 目光下移 |
| proud | 我们队、IGEM-FBH | 自信抬眉 + 微笑 + 抬头 |
| neutral | （默认/衰减后） | 中性表情 |

**特性**：
- EMA 平滑过渡，不会突然切换情绪
- 时间衰减：每秒向 neutral 漂移，空闲时恢复平静
- 跨会话持久化：情感状态保存到 `data/emotion_state.json`
- 情绪提示注入 LLM：`[当前情绪]你现在很开心，语气轻快。` 影响回复风格

### 长期记忆

`memory/` — 跨会话记忆持久化 + 观众档案。

**记忆类型**：
- **事件记忆**：重要对话自动存储（长度 > 20 字 + 未被过滤）
- **观众档案**：UID、用户名、来访次数、备注、兴趣标签
- **事实记忆**：手动添加的团队信息

**记忆检索**：综合评分 = 关键词匹配 + 时间新近度 + 访问频率 + 重要性权重

**记忆衰减**：基于重要性的指数衰减，7 天半衰期。访问次数越多衰减越慢。

**观众识别**：老观众发弹幕时自动注入上下文——"这是老观众xxx，第5次来直播间"。

### 自主行为

`autonomous/` — 让 IGEM-sama 像真人主播一样主动说话。

| 行为类型 | 触发间隔 | 描述 |
|---------|---------|------|
| 闲聊 | 90-180秒 | 主动聊点轻松话题，活跃气氛 |
| 科普 | 180-360秒 | 分享合成生物学小知识 |
| 项目推介 | 240-480秒 | 介绍 IGEM-FBH 团队项目 |
| 寂寞反应 | 120-200秒 | 长时间无弹幕时呼唤观众 |

**智能机制**：
- 用户互动后 15 秒内不主动发言（避免抢话）
- 需要 60 秒以上沉默才触发"寂寞反应"
- 每次只触发一个行为（不会连续自言自语）
- 可通过控制面板一键开关

### 互动工具

`agent/tool/interactive.py` — LangChain 工具，LLM 可自主调用。

| 工具名 | 功能 | OBS 联动 |
|--------|------|---------|
| IGEM知识问答 | 出生物学/iGEM/合成生物学题 | 题目显示在叠层 |
| 观众抽奖 | 设关键词，观众弹幕参与 | 抽奖信息显示在叠层 |
| 观众投票 | A/B/C 选项投票 | 投票结果 + 进度条显示 |
| 倒计时 | 活动倒计时 | 倒计时数字显示 |

**题库**：内置 6+ 道生物学题、4 道 iGEM 竞赛题、3 道合成生物学题，可自行扩展。

### Live2D 表情映射

`emotion/expression_map.py` — 情绪到 Live2D 参数与动作的桥梁。

当前使用 **Hiyori Pro (肥牛)** Live2D 模型，支持两种表情驱动方式：

**参数驱动**：映射 9 种情绪到 Live2D Cubism 标准参数（眼开合、微笑、眉高、嘴型、脸颊泛红、体角等），以强度为权重平滑应用。每秒通过 SecondEvent 同步一次。

**动作驱动**：情绪变化时自动触发对应的 motion3.json 动画（如开心时挥手、惊讶时身体后仰），增加表现力。

| 情绪 | 触发动作 | 参数效果 |
|------|---------|---------|
| happy | m02/m05/m06/m08 (随机) | 眯眼笑+微笑+脸颊泛红 |
| excited | m07 | 睁大眼+扬眉+张嘴 |
| sad | m10 | 垂眼+皱眉+嘴角下垂 |
| angry | m09 | 压眉+紧嘴+皱眉变形 |
| shy | m04 | 低头+目光下移+脸颊泛红 |
| curious | m03 | 抬眉+眼珠上移+歪头 |
| proud | m05/m08 | 自信微笑+抬眉 |
| neutral | m01 | 中性表情 |

如需适配其他 Live2D 模型，编辑 `EXPRESSION_MAP` 和 `MOTION_MAP` 字典中的参数值。

### OBS 叠层控制

`services/obs/overlay.py` — 高级 OBS WebSocket 控制。

**在 OBS 中需要预创建的文字源**：

| 源名 | 用途 |
|------|------|
| `AssistantText` | AI 回复字幕 |
| `UserText` | 用户输入字幕 |
| `OverlayText` | 通用叠层文字 |
| `QuizOverlay` | 问答题目叠层 |
| `VoteOverlay` | 投票结果叠层 |
| `CountdownOverlay` | 倒计时叠层 |
| `LotteryOverlay` | 抽奖信息叠层 |
| `HighlightOverlay` | 高亮消息叠层 |

**场景切换**：预创建 `idle`、`talk`、`quiz`、`game` 等场景，通过控制面板一键切换。

### 数据看板

`analytics/` — 实时直播数据 Web 看板。

访问地址：`http://localhost:8080`

| 指标 | 描述 |
|------|------|
| 弹幕总数 | 当前会话累计弹幕数 |
| 弹幕频率 | 条/分钟（30分钟滚动窗口） |
| 独立观众 | 去重 UID 计数 |
| 情绪分布 | 彩色条形图 |
| 热门话题 | 关键词云 |
| 互动/主动 | 用户互动 vs 自主发言次数 |

API 端点：
- `GET /api/analytics` — 当前快照
- `GET /api/history` — 历史趋势

### 操作员控制面板

`panel/` — 全功能 Web 控制台。

访问地址：`http://localhost:9090`

| 模块 | 功能 |
|------|------|
| 仪表盘 | 实时数据、情绪状态、服务状态 |
| 快捷操作 | 一键：打招呼/出题/科普/推介/抽奖/投票/倒计时 |
| 知识库管理 | 搜索/导入/重建知识库 |
| 记忆管理 | 查看/添加/删除长期记忆 |
| 观众档案 | 所有已知观众列表和备注 |
| OBS控制 | 场景切换、叠层文字显示/清除 |
| 手动发言 | AI 生成回复 或 直接文字转语音 |

**左侧开关**：自主行为 ON/OFF、情感分析 ON/OFF

**右侧日志**：所有操作实时记录

完整 API 端点列表：

```
GET  /api/status              # 完整系统状态
POST /api/toggle/autonomous   # 开关自主行为
POST /api/toggle/sentiment    # 开关情感分析
POST /api/action/speak        # 发送提示给LLM
POST /api/action/emotion      # 手动设定情绪
POST /api/action/trigger_autonomous  # 触发自主行为
POST /api/kb/ingest           # 导入知识库
POST /api/kb/search           # 搜索知识库
GET  /api/memory/list         # 记忆列表
POST /api/memory/add          # 添加记忆
DELETE /api/memory/delete/:id # 删除记忆
GET  /api/viewers             # 观众列表
POST /api/viewers/:uid/note   # 添加观众备注
POST /api/obs/scene           # 切换OBS场景
POST /api/obs/overlay         # 控制叠层
POST /api/chat/send           # 直接发言（绕过LLM）
```

### 弹幕防刷 & 容错降级

**防刷** (`common/rate_limiter.py`)：
- 单用户限制：10秒内最多3条弹幕
- 全局限制：1秒内最多处理2条弹幕
- 超限自动跳过，不计入对话
- **线程安全**：内置 `threading.Lock`，多线程并发调用安全

**容错降级** (bot.py)：
- LLM 宕机 → 熔断器快速失败，自动回复"我好像有点走神了"，不崩溃
- TTS 宕机 → 熔断器快速失败，仅显示字幕不播放语音，不崩溃
- Milvus 宕机 → 跳过 RAG，用纯 LLM 回答，不崩溃
- 知识库禁用 → 正常聊天，仅无法检索专业内容

**熔断器** (`common/concurrent/circuit_breaker.py`)：
- 三态模式：CLOSED（健康）→ OPEN（快速失败）→ HALF_OPEN（试探恢复）
- 配置：连续 5 次失败后打开，30 秒后尝试恢复
- 防止级联故障：服务异常时不无限重试，快速返回降级响应

---

## 高并发架构

针对 Bilibili 直播高并发场景（1000+ 观众、弹幕洪峰），系统实施了四层防护：

### 1. 线程安全修复

| 模块 | 问题 | 解决方案 |
|------|------|---------|
| `event/event_emitter.py` | 遍历监听器时删除元素导致跳过 | 收集待删除项，遍历后批量移除 |
| `common/rate_limiter.py` | `deque` 多线程不安全 | 添加 `threading.Lock` |
| `memory/long_term.py` | 并发 JSON 读写损坏 | 添加 `threading.RLock` + 原子写入 |
| `emotion/tracker.py` | 并发状态更新冲突 | 添加 `threading.Lock` + 原子写入 |
| `analytics/collector.py` | 并发 `record_*` 数据丢失 | 添加 `threading.Lock` |

### 2. 有界队列

```python
# event/event_emitter.py
SyncTaskExecutor(max_workers=8, max_queue_size=100)   # 同步任务队列
AsyncTaskExecutor(max_queue_size=100)                  # 异步任务队列

# bot.py
subtitles_queue = Queue(maxsize=20)  # 字幕队列
```

**背压机制**：队列满时丢弃任务并记录日志，避免 OOM。

### 3. HTTP 超时

所有外部服务调用（LLM/TTS/ASR/Milvus）添加 `timeout=30` 秒，防止线程无限阻塞。

### 4. 熔断器

```
CLOSED (健康) ──失败≥5次──→ OPEN (拒绝快速失败)
    ↑                           │
    │                        等待30秒
    │                           ↓
    └────探测成功──── HALF_OPEN (试探)
```

### 数据流（高并发优化后）

```
B站弹幕 → on_danmaku()
  ├── 防刷检查 (RateLimiter, 线程安全)
  ├── 情感关键词检测 (EmotionTracker, 线程安全)
  ├── 观众档案更新 (LongTermMemory, 线程安全)
  └── emit_llm_prediction()
        ├── [知识库检索] kb_pipeline.build_context()
        ├── [长期记忆]   long_term_memory.build_memory_context()
        ├── [当前情绪]   emotion_tracker.get_emotion_prompt_hint()
        ├── 熔断器检查   circuit_breaker.allow()
        ├── LLM推理     llm.predict() (30s超时 + 熔断器保护)
        ├── 情感更新     emotion_tracker.update_from_sentiment()
        ├── 记忆存储     long_term_memory.add_memory()
        ├── Live2D表情   expression_driver.apply_emotion()
        └── TTS语音      tts.predict() (熔断器保护)
```

---

## 部署方式

### 方式一：本地直接运行

```bash
cp config.igem-sama.yaml config.yaml
# 编辑 config.yaml ...
pip install -r requirements.txt
pip install flask flask-cors
python -m knowledge_base.ingest --dir knowledge_base/docs
python main.py
```

### 方式二：一键脚本

```bash
# Windows
start_igem_sama.bat

# Linux/Mac
./start_igem_sama.sh
```

脚本会自动：检查 Python → 复制配置 → 安装依赖 → 导入知识库 → 启动 bot

### 方式三：Docker

```bash
# 1. 准备配置
cp config.igem-sama.yaml config.yaml
# 编辑 config.yaml ...

# 2. 启动所有服务（bot + Milvus + 看板）
docker-compose up -d

# 3. 导入知识库
docker exec igem-sama python -m knowledge_base.ingest --dir knowledge_base/docs

# 4. 访问
# 控制面板: http://localhost:9090
# 数据看板: http://localhost:8080
```

### 需要启动的外部服务

| 服务 | 端口 | 用途 | 是否必须 |
|------|------|------|---------|
| LLM (DeepSeek API) | 443 | 语言模型推理 | **必须** |
| Milvus | 11010 | 向量数据库 (RAG) | 推荐 |
| TTS (GPT-SoVITS) | 11005 | 语音合成 | 推荐 |
| OBS Studio + WebSocket | 4455 | 画面控制 | 可选 |
| ASR | 11001 | 语音识别 | 可选 |

---

## 项目结构

```
ZerolanLiveRobot-2.3.0/
├── main.py                          # 入口
├── bot.py                           # 主机器人逻辑（核心修改）
├── config.igem-sama.yaml            # 生产配置模板
├── Dockerfile                       # Docker 镜像
├── docker-compose.yaml              # Docker 编排
├── start_igem_sama.sh               # Linux 启动脚本
├── start_igem_sama.bat              # Windows 启动脚本
├── demo.py                          # Demo 模式入口（模拟直播间）
│
├── demo/                            # 模拟直播间 Demo 模式
│   ├── __init__.py
│   ├── core.py                      # Demo 核心（DeepSeek/MockLLM + Edge TTS + 礼物/SC/观众）
│   ├── server.py                    # Flask API（弹幕/礼物/SC/观众端点 + SSE + MJPEG）
│   ├── video_stream.py              # Live2D MJPEG 流 + 口型同步
│   ├── mock_llm.py                  # 关键词匹配 MockLLM + 模拟观众/弹幕数据
│   └── templates/demo.html          # 仿B站直播间前端
│
├── knowledge_base/                  # RAG 知识库系统
│   ├── models.py                    # 数据模型 (Entry, Query, Result)
│   ├── config.py                    # KB 配置类
│   ├── loader.py                    # 文档加载 & 分块 (.md/.txt/.json)
│   ├── kb_pipeline.py               # RAG 管道 (ingest, retrieve, build_context)
│   ├── ingest.py                    # CLI 导入脚本
│   └── docs/                        # 文档存放目录
│
├── emotion/                         # 情感系统
│   ├── tracker.py                   # 情感追踪器 (9种情绪, EMA, 衰减, 持久化)
│   └── expression_map.py            # 情绪 → Live2D 参数映射
│
├── memory/                          # 长期记忆系统
│   └── long_term.py                 # 跨会话记忆 + 观众档案
│
├── autonomous/                      # 自主行为系统
│   └── behavior.py                  # 定时主动发言 (闲聊/科普/推介/寂寞)
│
├── analytics/                       # 数据看板
│   ├── collector.py                 # 数据采集 (弹幕/情绪/关键词/观众)
│   └── dashboard.py                 # Flask Web 看板 (:8080)
│
├── panel/                           # 操作员控制面板
│   ├── server.py                    # Flask REST API (:9090)
│   └── frontend.py                  # 单页 HTML 前端
│
├── agent/tool/                      # LLM 工具
│   ├── igem_knowledge.py            # IGEM 知识库查询工具
│   ├── interactive.py               # 互动工具包 (问答/抽奖/投票/倒计时)
│   ├── web_search.py                # 百度百科搜索
│   ├── lang_changer.py              # 语言切换
│   ├── microphone_tool.py           # 麦克风控制
│   └── go_creator.py                # 3D模型控制
│
├── services/obs/
│   ├── client.py                    # OBS WebSocket 客户端
│   ├── config.py                    # OBS 配置
│   └── overlay.py                   # OBS 叠层控制器
│
├── common/
│   ├── rate_limiter.py              # 弹幕防刷限速器（线程安全）
│   └── concurrent/
│       ├── circuit_breaker.py       # 熔断器（CLOSED/OPEN/HALF_OPEN）
│       ├── killable_thread.py       # 可终止线程
│       └── abs_runnable.py          # 异步运行基类
│
├── character/
│   ├── config.py                    # 角色配置（IGEM-sama 人设）
│   └── filter/strategy.py           # 内容过滤
│
├── framework/
│   ├── context.py                   # 上下文初始化
│   └── base_bot.py                  # 基础机器人
│
├── pipeline/
│   ├── base/config.py               # 管道配置
│   ├── llm/                         # LLM 管道
│   ├── tts/                         # TTS 管道
│   ├── asr/                         # ASR 管道
│   ├── ocr/                         # OCR 管道
│   └── db/milvus/                   # Milvus 管道
│
├── event/                           # 事件系统（有界队列 + 线程安全）
├── manager/                         # 管理器 (配置/提示词/模型)
├── services/                        # 服务 (B站/YouTube/Twitch/QQ)
└── resources/
    └── static/
        └── models/
            └── live2d/              # Live2D 模型 (Hiyori Pro / 肥牛)
                ├── hiyori_pro_mic.model3.json
                ├── hiyori_pro_mic.moc3
                ├── hiyori_pro_mic.physics3.json
                ├── hiyori_pro_mic.pose3.json
                └── motions/        # 动作文件 (12个motion3.json)
```

---

## 依赖说明

### 核心依赖（requirements.txt 已包含）

| 包 | 用途 |
|----|------|
| `pydantic` | 数据模型与验证 |
| `loguru` | 日志 |
| `langchain-core` | LLM Agent 工具调用 |
| `bilibili-api-python` | B站直播弹幕监听 |
| `live2d-py` | Live2D 模型渲染 |
| `PyQt5` | Live2D 窗口 |
| `websockets` | OBS WebSocket 通信 |

### 额外安装（可选）

```bash
# 控制面板 + 数据看板
pip install flask flask-cors

# Demo 模式（模拟直播间 + TTS 语音）
pip install edge-tts pygame

# 本地 LLM 模型（需 GPU）
pip install vllm  # 或通过 Ollama

# Milvus 向量数据库
pip install pymilvus

# ASR 语音识别
pip install funasr torch

# TTS 语音合成
pip install soundfile
```

---

## 常见问题

### Q: 启动报错 "At least LLMPipeline must be enabled"

A: 必须配置 LLM 后端。编辑 `config.yaml`，设置 `pipeline.llm.enable: true` 并填写 API 地址。

### Q: 弹幕收不到

A: 检查B站凭证是否正确。获取方式：浏览器登录B站 → F12 → Application → Cookies。`room_id` 必须是正整数。

### Q: Live2D 窗口不显示

A: 确保已安装 `live2d-py` 和 `PyQt5`，并且 `service.live2d_viewer.enable` 设为 `true`，`model3_json_file` 指向有效的模型文件。

### Q: 知识库搜索无结果

A: 需要先导入文档：`python -m knowledge_base.ingest --dir knowledge_base/docs`。确保 Milvus 服务正在运行。

### Q: TTS 没有声音

A: 需要运行 zerolan-core 的 TTS 服务，或使用其他 TTS 后端。如无 TTS，bot 仍能通过 OBS 字幕显示回复。

### Q: 控制面板打不开

A: 安装 Flask：`pip install flask flask-cors`。控制面板在 bot 启动时自动运行于 `:9090`。

### Q: 如何训练自己的声线

A: 录制 3-10 分钟干净语音（无背景音），使用 [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) 训练，将模型放到 `resources/static/prompts/tts/` 目录。

### Q: 如何更换 Live2D 模型

A: 替换 `resources/static/models/live2d/` 下的模型文件（当前为 Hiyori Pro / 肥牛），然后在 `config.yaml` 中更新 `model3_json_file` 路径。需要微调 `emotion/expression_map.py` 中的 `EXPRESSION_MAP` 和 `MOTION_MAP` 参数映射。

### Q: 如何让 IGEM-sama 介绍我的团队项目

A: 将项目文档放入 `knowledge_base/docs/`，然后运行导入脚本。文档支持 Markdown、纯文本和 JSON 格式。

---

## 致谢

- [ZerolanLiveRobot](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot) — 基础框架
- [live2d-py](https://github.com/Arkueid/live2d-py) — Live2D 渲染
- [bilibili-api-python](https://github.com/Nemo2011/bilibili-api) — B站API
- [LangChain](https://github.com/langchain-ai/langchain) — Agent 工具调用
- [Milvus](https://milvus.io/) — 向量数据库
- [GPT-SoVITS](https://github.com/RVC-Boss/GPT-SoVITS) — 语音合成

---

<p align="center">
  <strong>IGEM-FBH x IGEM-sama</strong><br>
  让合成生物学被更多人看见
</p>
