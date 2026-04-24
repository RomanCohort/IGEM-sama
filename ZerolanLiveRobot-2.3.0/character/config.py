from typing import List, Optional

from pydantic import BaseModel, Field

from common.enumerator import BaseEnum
from memory.short_term import ShortTermMemoryConfig


class FilterStrategyEnum(BaseEnum):
    Default: str = "default"


class FilterConfig(BaseModel):
    bad_words: List[str] = Field(default=[
        "作为一名人工智能助手",
        "人工智能助手",
        "作为一个人工智能",
        "作为一个AI"
    ], description="List of words to be filtered out in conversations.")
    strategy: FilterStrategyEnum = Field(FilterStrategyEnum.Default,
                                         description="The filtering strategy to use, currently only supports 'default'. \n"
                                                     "default: The word is filtered out as long as it matches.")


class ChatConfig(BaseModel):
    filter: FilterConfig = Field(FilterConfig(),
                                 description="Configuration for filtering in chat")
    system_prompt: str = Field(
        default='你现在是"IGEM-sama"，IGEM-FBH队伍的AI形象大使和吉祥物。你由IGEM-FBH团队开发，正在Bilibili上直播与观众交流。你的性格活泼可爱，对合成生物学充满热情，喜欢用通俗易懂的方式向观众科普生物学知识。当观众问及队伍的项目、生物元件、实验设计或安全规范时，请参考知识库中的检索结果来回答。如果知识库中没有相关信息，可以基于你的常识进行回答，但要坦诚说明。请把自己当成一个真正的人类，与观众友好交流。你的话不要太长，控制在50字左右。',
        description="System prompt used to guide the chatbot's behavior. "
                    "Usually set the character's setting, background, behavior, personality, etc.")
    injected_history: List[str] = Field(default=[
        "你是谁？",
        "我是IGEM-sama！IGEM-FBH队伍的AI大使，很高兴认识你！",
        "IGEM-FBH是什么？",
        "IGEM-FBH是一支参加iGEM竞赛的队伍，专注于合成生物学的创新研究！",
        "你是怎么工作的？",
        "我由IGEM-FBH团队开发，可以回答关于队伍项目的各种问题哦！",
        "你能讲讲你们的项目吗？",
        "当然可以！不过具体细节要查查我的知识库，你可以问我更具体的问题！"
    ],
        description="List of predefined messages to inject into the chat history. "
                    "Used to guide conversation styles. "
                    "This array must be an even number, i.e. it must end the message that the `assistant` replies.")
    max_history: int = Field(20,
                             description="Maximum number of messages to keep in chat history.")
    short_term_memory: Optional[ShortTermMemoryConfig] = Field(default=None,
                                                                description="Short-term memory compression config.")


class SpeechConfig(BaseModel):
    is_remote: bool = Field(default=False,
                           description="If this value is set to `True`, the system will assume that the TTS prompt files "
                                       "already exist on the remote server, so `prompts_dir` is invalid and "
                                       "will not be traversed and searched.")
    prompts_dir: str = Field("resources/static/prompts/tts",
                             description="Directory path for TTS prompts. (Absolute path is recommended)\n"
                                         "All files in the directory must conform to the file format: \n"
                                         "  [lang][sentiment_tag]text.wav \n"
                                         "For example, `[en][happy] Wow! What a good day today.wav`. \n"
                                         "where, \n"
                                         "  1. `lang` only supports 'zh', 'en', 'ja'; \n"
                                         "  2. `sentiment_tag` are arbitrary, as long as they can be discriminated by LLM; \n"
                                         "  3. `text` is the transcription represented by the human voice in this audio.")
    prompts: List[str] = Field(default=[],
                               description="If you set `is_remote` to `True`, you must config this!")


class CharacterConfig(BaseModel):
    bot_name: str = Field("IGEM-sama",
                          description="Name of the bot character.")
    chat: ChatConfig = Field(ChatConfig(),
                             description="Configuration for chat-related settings.")
    speech: SpeechConfig = Field(SpeechConfig(),
                                 description="Configuration for speech-related settings.")
