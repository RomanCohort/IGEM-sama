# IGEM-sama (IGEM-FBH AI VTuber)

> IGEM-FBH 团队的 AI 虚拟主播 | Bilibili 直播互动 | 知识库驱动的合成生物学宣传者

![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![License](https://img.shields.io/badge/License-MIT-orange)
![AI VTuber](https://img.shields.io/badge/AI%20VTuber-blue)
![Bilibili](https://img.shields.io/badge/Bilibili-fb7299)
![RAG](https://img.shields.io/badge/RAG-Knowledge%20Base-green)
![Emotion](https://img.shields.io/badge/Emotion-Persistent-yellow)

## 项目来源与致谢

本项目主体来自 [fake-neuro](https://github.com/zyl9737/fake-neuro)（基于 ZerolanLiveRobot 二次开发），为 IGEM-FBH 团队进一步定制。

**原始项目**：
- fake-neuro: https://github.com/zyl9737/fake-neuro
- ZerolanLiveRobot: https://github.com/AkagawaTsurunaki/ZerolanLiveRobot
- zerolan-core: 多模态 AI 核心 (ASR/TTS/LLM/VLA)
- zerolan-data: 数据处理与 RAG 知识库

**许可证**: MIT License (Copyright AkagawaTsurunaki)

## 主要功能

- **IGEM 知识库**：合成生物学相关问答与文档检索
- **情感记忆系统**：长期记忆与情感追踪
- **Bilibili 互动**：弹幕接收与智能回复
- **多模态 AI**：语音识别(ASR)、语音合成(TTS)、视觉语言动作(VLA)
- **RAG 检索增强**：基于向量数据库的知识库问答
- **自主行为**：AI 驱动的自发动作与互动

## 目录结构

```
IGEM-sama/
├── ZerolanLiveRobot-2.3.0/     # 主程序
│   ├── agent/                  # AI Agent 与工具集
│   ├── autonomous/             # 自主行为系统
│   ├── emotion/                # 情感追踪
│   ├── features/               # 功能模块 (会议追踪/任务看板等)
│   ├── knowledge_base/         # 知识库与 RAG
│   ├── memory/                 # 短/长期记忆
│   ├── perception/             # 感知处理
│   ├── pipeline/               # AI 处理流水线 (ASR/TTS/LLM等)
│   ├── services/               # 服务层 (Live2D/Bilibili/OBS等)
│   └── requirements.txt        # Python 依赖
├── zerolan-core-1.4/           # 多模态 AI 核心
│   ├── asr/                    # 语音识别 (Whisper/Paraformer)
│   ├── tts/                    # 语音合成 (GPT-SoVITS)
│   ├── llm/                    # 大语言模型 (ChatGLM/DeepSeek/Qwen等)
│   ├── vla/                    # 视觉语言动作 (ShowUI)
│   ├── ocr/                    # 光学字符识别
│   ├── img_cap/                # 图像描述
│   └── vid_cap/                # 视频理解
└── zerolan-data-1.5.0/         # 数据处理与 RAG
    ├── pipeline/                # 数据处理流水线
    └── src/                     # 核心数据结构
```

## 环境要求

- Python 3.10+
- FFmpeg
- Milvus 向量数据库 (可选，用于 RAG)

## 安装

```bash
# 克隆仓库
git clone https://github.com/RomanCohort/IGEM-sama.git
cd IGEM-sama

# 安装主程序依赖
cd ZerolanLiveRobot-2.3.0
pip install -r requirements.txt

# 配置 API Key (编辑 config.yaml 或 config.igem-sama.yaml)
```

## 运行

```bash
# Linux/macOS
./start_igem_sama.sh

# Windows
start_igem_sama.bat

# Docker (需要先配置)
docker-compose up
```

## 配置

编辑 `ZerolanLiveRobot-2.3.0/config.igem-sama.yaml`：

```yaml
llm:
  api_key: "your-api-key"
  model: "deepseek-chat"

bilibili:
  room_id: 你的直播间号

knowledge_base:
  enabled: true
  milvus_uri: "http://localhost:19530"
```

## 子模块

| 模块 | 说明 | 依赖 |
|------|------|------|
| zerolan-core | 多模态 AI 核心框架 | torch, transformers |
| zerolan-data | RAG 数据管道 | langchain, milvus-haystack |

## 许可证

本项目继承 MIT License。
- ZerolanLiveRobot: MIT (Copyright AkagawaTsurunaki)
- zerolan-core: MIT
- zerolan-data: MIT

详见各子模块 LICENSE 文件。

## Related Projects

| Project | Description |
|---------|-------------|
| [paper-search-tool](https://github.com/RomanCohort/paper-search-tool) | AI 论文搜索与整理工具 |
| [ai-desktop-pet](https://github.com/RomanCohort/ai-desktop-pet) | AI 桌面宠物 |
| [web-crawler-v2](https://github.com/RomanCohort/web-crawler-v2) | 网站爬取器 |
| [berlin-tank-commander](https://github.com/RomanCohort/berlin-tank-commander) | 柏林车长文字冒险 |
| [bioease](https://github.com/RomanCohort/bioease) | 生物信息学分析 |
| [IGEM-sama](https://github.com/RomanCohort/IGEM-sama) | IGEM AI 虚拟主播 |
| [ppt-agent](https://github.com/RomanCohort/ppt-agent) | PPT 草稿生成器 |
