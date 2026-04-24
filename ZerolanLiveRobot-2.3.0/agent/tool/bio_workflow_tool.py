"""生信工作流 LangChain 工具"""
from typing import Type

from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from loguru import logger

from features.bio_workflow import BioWorkflowGuide, WORKFLOW_TEMPLATES


class BioWorkflowToolInput(BaseModel):
    command: str = Field(description="生信工作流命令，如 'list', 'fastqc', 'blastn', 'primer3', '建树'")


class BioWorkflowTool(BaseTool):
    """生信工作流引导工具。"""
    name: str = "生信工作流"
    description: str = (
        "启动生物信息学分析工作流。支持：\n"
        "  list - 列出所有可用工作流\n"
        "  fastqc / 测序质量 - 检查测序质量\n"
        "  blast / 比对 - 序列比对\n"
        "  primer / 引物 - 设计引物\n"
        "  建树 / 进化树 - 系统发育树\n"
        "示例: 'list', '帮我检查测序质量', 'blast比对'"
    )
    args_schema: Type[BaseModel] = BioWorkflowToolInput

    def __init__(self):
        super().__init__()
        self._guide = BioWorkflowGuide()

    def set_llm_predict(self, llm_predict):
        """设置LLM预测函数。"""
        self._guide.set_llm_predict(llm_predict)

    def _run(self, command: str) -> str:
        mode, payload = BioWorkflowGuide.parse_flow_command(f"/flow {command}")
        logger.debug("BioWorkflowTool: mode={}, payload={}", mode, payload)

        if mode == "list":
            workflows = self._guide.list_workflows()
            lines = ["可用生信工作流："]
            for wf in workflows:
                triggers = " / ".join(wf["trigger_keywords"][:3])
                lines.append(f"  {wf['display_name']} ({wf['steps_count']}步)")
                lines.append(f"    触发词: {triggers}")
            return "\n".join(lines)

        elif mode == "cancel":
            return "已取消当前工作流（直播模式暂不支持多步工作流，请直接描述需求）"

        elif mode == "start":
            wf_type = payload.get("workflow_type", "")
            if wf_type not in WORKFLOW_TEMPLATES:
                available = ", ".join(WORKFLOW_TEMPLATES.keys())
                return f"未知工作流 '{wf_type}'。可用: {available}"

            template = WORKFLOW_TEMPLATES[wf_type]
            return (
                f"生信工作流：{template['display_name']}\n"
                f"共 {len(template['steps'])} 步。\n"
                f"直播模式下暂不支持多步引导，请直接在对话中描述你的需求，\n"
                f"例如：「帮我用FastQC检查 C:/data/sample.fastq 的质量」\n"
                f"工具提示：{template.get('result_hint', '')}"
            )

        return "未知工作流命令。可用: list, fastqc, blast, primer, 建树"
