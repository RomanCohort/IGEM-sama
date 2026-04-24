# IGEM-sama 🤖🎙️

> IGEM-FBH 团队的 AI 虚拟主播，基于 ZerolanLiveRobot 深度定制，支持 Bilibili 直播互动、知识库问答与合成生物学领域智能助手。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux-blue?logo=windows)
[![Bilibili](https://img.shields.io/badge/Live-Bilibili-FF69B4?logo=bilibili)](https://live.bilibili.com)
[![IGEM](https://img.shields.io/badge/IGEM-SynBio-00C853)](https://igem.org)

## 🌟 项目特色

### 🎙️ Bilibili VTuber 实时互动
- **VTuber 直播模式** — 在 Bilibili 直播间实时与观众互动
- **多模型 API 支持** — 兼容 DeepSeek / GPT / Claude 等主流大模型后端
- **自动语音合成** — 本地 TTS，无需云端 API

### 🧠 知识增强系统
- **RAG 知识库** — 基于 zerolan-data 1.5.0 的检索增强生成，支持 IGEM 专业知识注入
- **合成生物学问答** — 内置 IGEM 竞赛、生物实验、基因回路设计等领域的专项问答能力
- **会议追踪** — 自动记录组会要点，生成会议纪要

### 📋 任务管理与协作
- **任务看板** — IGEM 项目任务管理，支持进度追踪与提醒
- **工作流助手** — 生信工作流辅助（引物设计 / 质粒构建 / 转化步骤咨询）
- **上下文记忆** — 长期记忆系统，多轮对话中保持上下文一致

### 🎭 情感与个性化
- **情感记忆系统** — 根据对话内容动态更新角色情感状态
- **多角色支持** — 可配置不同人设与性格
- **个性化互动** — 观众好感度系统，差异化直播体验

## 📁 项目结构

```
IGEM-sama/
├── ZerolanLiveRobot-2.3.0/       # 上游 ZerolanLiveRobot 核心
├── zerolan-core-1.4/               # 多模态 AI 核心引擎
├── zerolan-data-1.5.0/             # RAG 数据管道与知识库
├── config.igem-sama.yaml           # IGEM 团队定制配置
└── pyproject.toml                 # Python 依赖
```

### 核心模块

| 模块 | 功能 |
|------|------|
| `zerolan-core` | 多模型 API 调用、对话管理、TTS 引擎 |
| `zerolan-data` | RAG 检索、知识库构建、文档向量化 |
| `ZerolanLiveRobot` | Bilibili 直播连接、弹幕解析、互动逻辑 |

## 🚀 快速开始

### 前置依赖

- Python 3.10+
- ffmpeg（音频处理）
- 至少一个大模型 API（DeepSeek / OpenAI / 等）

### 安装

```bash
git clone https://github.com/RomanCohort/IGEM-sama.git
cd IGEM-sama
pip install -r requirements.txt
```

### 配置

编辑 `config.igem-sama.yaml`，填入：

```yaml
api:
  model: "deepseek-chat"          # 选择模型
  base_url: "https://api.deepseek.com"
  api_key: "YOUR_API_KEY"          # 你的 API Key

bilibili:
  live_room_id: 你的直播间号       # Bilibili 直播间号
  cookie: "你的 Cookie"             # 登录 Bilibili 获取

vtuber:
  enabled: true
  voice_rate: 1.0
```

### 运行

```bash
python vtuber_main.py
```

## 🎯 适用场景

| 场景 | 说明 |
|------|------|
| 🧬 IGEM 竞赛辅助 | 合成生物学知识问答、实验方案咨询 |
| 🎙️ B站直播互动 | 自动化弹幕回复、直播助手 |
| 📝 会议记录 | 组会内容自动整理与任务追踪 |
| 🤖 团队知识库 | 构建团队专属的知识问答机器人 |

## 🛠️ 技术栈

| 层级 | 技术 |
|------|------|
| 大模型 | DeepSeek / GPT / Claude 等（API） |
| TTS | pyttsx3 / edge-tts（本地） |
| 直播平台 | Bilibili WebSocket API |
| 知识检索 | LangChain + 向量数据库（RAG） |
| 框架上游 | [ZerolanLiveRobot](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot) |

## 🙏 致谢

本项目基于以下开源项目二次开发：

- **ZerolanLiveRobot** — [AkagawaTsurunaki/ZerolanLiveRobot](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot)
- **fake-neuro** — [zyl9737/fake-neuro](https://github.com/zyl9737/fake-neuro)

## 📝 License

MIT License &copy; 2024 [RomanCohort](https://github.com/RomanCohort)

---

*如需体验直播效果，请在 [Bilibili](https://live.bilibili.com) 关注 IGEM-FBH 团队直播间！*
