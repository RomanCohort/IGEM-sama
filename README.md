# IGEM-sama (IGEM-FBH AI VTuber)

> IGEM-FBH 团队的 AI 虚拟主播 | Bilibili 直播互动 | 知识库驱动的合成生物学宣传者

![Python 3.10+](https://img.shields.io/badge/Python-3.10~3.11-blue)
![License](https://img.shields.io/badge/License-MIT-orange)
![AI VTuber](https://img.shields.io/badge/AI%20VTuber-blue)
![Bilibili](https://img.shields.io/badge/Bilibili-fb7299)
![RAG](https://img.shields.io/badge/RAG-Knowledge%20Base-green)
![Emotion](https://img.shields.io/badge/Emotion-Persistent-yellow)

## 项目来源与致谢

本项目基于 [ZerolanLiveRobot](https://github.com/AkagawaTsurunaki/ZerolanLiveRobot) 进行开发，为 IGEM-FBH 团队定制。

**原始项目**：
- ZerolanLiveRobot: https://github.com/AkagawaTsurunaki/ZerolanLiveRobot
- zerolan-core: 多模态 AI 核心 (ASR/TTS/LLM/VLA)
- zerolan-data: 数据处理与 RAG 知识库

**许可证**: MIT License (Copyright AkagawaTsurunaki)

## 定制功能

- IGEM 知识库集成
- 合成生物学内容问答
- 情感记忆系统
- 自主行为驱动
- Bilibili 弹幕互动

## 目录结构

```
IGEM-sama/
├── ZerolanLiveRobot-2.3.0/     # 主程序
│   ├── agent/                   # AI Agent
│   ├── autonomous/              # 自主行为
│   ├── emotion/                 # 情感系统
│   ├── features/                # 功能模块
│   ├── knowledge_base/          # 知识库
│   ├── memory/                  # 记忆系统
│   ├── perception/              # 感知模块
│   ├── pipeline/                # 处理流水线
│   └── ...
├── zerolan-core-1.4/            # 多模态 AI 核心
│   ├── asr/                     # 语音识别
│   ├── tts/                     # 语音合成
│   ├── llm/                     # 大语言模型
│   ├── vla/                     # 视觉语言动作
│   └── ...
└── zerolan-data-1.5.0/          # 数据处理与 RAG
    └── ...
```

## 运行

```bash
# Linux/macOS
./start_igem_sama.sh

# Windows
start_igem_sama.bat

# Docker
docker-compose up
```

## 依赖

详见各子模块的 requirements.txt 和 pyproject.toml

## 许可证

本项目继承 MIT License，详见 LICENSE 文件。
