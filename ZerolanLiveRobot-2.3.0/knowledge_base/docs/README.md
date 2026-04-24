# IGEM-sama 知识库文档目录

将你的队伍官方文档放在此目录下，然后运行导入脚本即可将文档导入知识库。导入后，IGEM-sama 在回答观众问题时会自动检索相关内容，基于真实文档生成准确回答。

## 工作原理

```
观众提问 "你们的安全措施有哪些？"
  → Milvus 语义检索到 safety_protocol.md 的相关片段
  → 注入 LLM prompt: "[知识库检索结果] 1. (分类: safety) 我们在实验中遵循..."
  → LLM 基于真实文档内容回答
```

每次观众发弹幕时，系统自动：
1. 用弹幕内容在 Milvus 中语义搜索最相关的 3 个文档片段
2. 把检索结果注入到发给 LLM 的 prompt 中
3. LLM 基于知识库内容生成准确回答

## 支持的文件格式

| 格式 | 扩展名 | 说明 |
|------|--------|------|
| Markdown | `.md` | **推荐**，保留标题/段落结构，分块效果最好 |
| 纯文本 | `.txt` | 按段落分块 |
| JSON | `.json` | 自动提取所有字符串值 |

## 文档编写建议

### Markdown 格式示例

```markdown
# 项目概述

IGEM-FBH 团队聚焦于合成生物学创新，设计新型生物元件来解决实际问题。

## 项目背景

全球每年因抗生素耐药性导致的死亡人数超过XX万……

## 技术路线

我们采用 XXX 方法，构建了 XXX 载体……

## 预期成果

预计完成以下目标：……
```

### 编写原则

- **一个文件一个主题**：按内容分文件，便于分类检索
- **段落清晰**：用空行分隔段落，系统优先在段落边界分块
- **语言自然**：用正常中文书写，不要写关键词堆砌
- **内容具体**：越具体的描述，检索效果越好

### 文件命名建议

```
knowledge_base/docs/
├── project_overview.md        # 项目概述与背景
├── parts_bio_brick_A.md       # BioBrick 零件设计
├── parts_bio_brick_B.md       # 更多零件
├── wetlab_protocol.md         # 湿实验方案与结果
├── wetlab_results.md          # 实验结果数据
├── drylab_model.md            # 干实验建模与仿真
├── safety_protocol.md         # 安全规范与伦理
├── human_practices.md         # 人类实践调研
├── collaboration.md           # 合作与交流
└── team_introduction.md       # 队伍介绍
```

## 导入命令

### 前提：Milvus 服务必须正在运行

知识库依赖 Milvus 向量数据库，导入前需确保服务已启动：

```bash
# Docker 方式启动 Milvus
docker-compose up -d milvus
```

### 导入文档

```bash
# 导入此目录下所有文档（默认分类: general）
python -m knowledge_base.ingest --dir knowledge_base/docs

# 导入并指定分类
python -m knowledge_base.ingest --dir knowledge_base/docs --category project

# 导入单个文件并指定分类
python -m knowledge_base.ingest --file knowledge_base/docs/safety_protocol.md --category safety
```

### 更新文档

当你修改了文档内容后，需要重建知识库：

```bash
# 重建知识库（删除旧数据后重新导入）
python -m knowledge_base.ingest --dir knowledge_base/docs --reset
```

### 自定义分块参数

文档会被切分为小段存入向量数据库，分块参数影响检索效果：

```bash
# 默认：每块最大 500 字符，相邻块重叠 50 字符
python -m knowledge_base.ingest --dir knowledge_base/docs

# 文档段落较长时，增大分块
python -m knowledge_base.ingest --dir knowledge_base/docs --max-chars 800 --overlap 80

# 需要更精准的检索，减小分块
python -m knowledge_base.ingest --dir knowledge_base/docs --max-chars 300 --overlap 30
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--max-chars` | 500 | 每个分块最大字符数（系统优先在段落/句子边界切分） |
| `--overlap` | 50 | 相邻分块重叠字符数（保证上下文连贯，避免关键信息被切断） |
| `--category` | general | 文档分类标签，用于检索时过滤 |

## 分类 (Category)

建议使用以下分类标签，检索时可按分类过滤：

| 分类标签 | 用途 | 示例问题 |
|---------|------|---------|
| `project` | 项目概述与背景 | "你们的项目是做什么的？" |
| `parts` | 生物元件 (BioBrick) | "你们的 BioBrick 有什么功能？" |
| `wetlab` | 湿实验方案与结果 | "你们的实验是怎么做的？" |
| `drylab` | 干实验建模与仿真 | "你们的模型验证了吗？" |
| `safety` | 安全规范与伦理 | "安全方面有什么考虑？" |
| `human_practices` | 人文实践 | "你们做了哪些社会调研？" |
| `collaboration` | 合作与交流 | "你们和其他队伍有合作吗？" |
| `team` | 队伍介绍 | "介绍一下你们的队伍" |
| `general` | 其他 | — |

## Demo 模式下使用知识库

Demo 模式（`python demo.py`）目前不连接 Milvus，因此知识库功能不可用。如果需要在 Demo 中使用知识库检索，需要：

1. 启动 Milvus 服务
2. 导入文档
3. 修改 `demo/core.py` 中的 `DemoCore`，接入 `KnowledgeBasePipeline`

## 常见问题

### Q: 导入后搜索无结果？

A: 检查 Milvus 是否正常运行，以及文档是否成功导入（查看日志中的 `Ingested X entries`）。

### Q: 回答不够准确？

A: 尝试以下方法：
- 增大 `--max-chars`，让每块包含更多上下文
- 增大 `top_k`（在 `config.yaml` 中），检索更多相关片段
- 优化文档内容，使其更具体、更有条理

### Q: 支持哪些语言的文档？

A: 中文和英文均可。Milvus 的嵌入模型对中文支持良好。混合语言文档也可以处理。
