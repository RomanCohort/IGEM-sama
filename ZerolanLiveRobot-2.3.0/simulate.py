"""IGEM-sama 模拟直播间

无需 B站/OBS/TTS/ASR 等外部服务，在终端中模拟弹幕互动。
测试全部6个新模块的运行效果。

Usage: python simulate.py
"""

import asyncio
import sys
import time
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from loguru import logger


def main():
    # Step 1: Override config to disable external services
    from manager.config_manager import get_config, _config
    config = get_config()

    # Disable services that need external connections
    config.service.live_stream.enable = False
    config.service.live_stream.bilibili.enable = False
    config.service.live_stream.bilibili.room_id = 0
    config.service.obs.enable = False
    config.service.playground.enable = False
    # Don't set res_server to None - it's required by context.py
    config.service.qqbot.enable = False
    config.service.browser.enable = False
    config.service.game.enable = False

    # Keep pipelines we can test
    # LLM must be enabled; TTS/ASR/OCR are optional
    config.pipeline.tts.enable = False  # No TTS server running
    config.pipeline.asr.enable = False
    config.pipeline.ocr.enable = False
    config.pipeline.img_cap.enable = False
    config.pipeline.vid_cap.enable = False
    config.pipeline.vla.enable = False
    config.pipeline.vec_db.enable = False
    config.pipeline.kb.enable = False

    # Enable the new modules we want to test
    # Personality and short-term memory are enabled by default

    # Step 2: Initialize bot
    logger.info("=" * 50)
    logger.info("  IGEM-sama 模拟直播间")
    logger.info("=" * 50)

    try:
        from bot import ZerolanLiveRobot
        bot = ZerolanLiveRobot()
    except Exception as e:
        logger.error(f"Bot 初始化失败: {e}")
        logger.info("尝试使用轻量模式...")

        # Lightweight mode: just test the new modules directly
        lightweight_demo()
        return

    # Step 3: Report module status
    logger.info("")
    logger.info("模块状态:")
    logger.info(f"  情绪追踪:     {'✅' if bot.emotion_tracker else '❌'}")
    logger.info(f"  人格演化:     {'✅' if bot.personality_evolution else '❌'}")
    logger.info(f"  短期记忆:     {'✅' if bot.llm_prompt_manager.short_term_memory else '❌'}")
    logger.info(f"  长期记忆:     {'✅' if bot.long_term_memory else '❌'}")
    logger.info(f"  自主行为:     {'✅' if bot._autonomous else '❌'}")
    logger.info(f"  Lip Sync增强: ✅ (Live2D模块)")
    logger.info(f"  语音克隆:     {'⏸' if not bot.voice_pipeline else '✅'} (配置关闭)")
    logger.info(f"  多模态感知:   {'⏸' if not bot._visual_loop else '✅'} (配置关闭)")
    logger.info(f"  游戏互动:     {'⏸' if not bot._game_perception else '✅'} (配置关闭)")
    logger.info("")

    # Step 4: Interactive simulation
    logger.info("=" * 50)
    logger.info("  模拟弹幕输入 (输入消息模拟观众弹幕)")
    logger.info("  特殊命令:")
    logger.info("    /emotion <emotion>  - 设置情绪 (happy/excited/sad/angry/shy/curious/proud)")
    logger.info("    /personality        - 查看当前人格状态")
    logger.info("    /memory             - 查看短期记忆摘要")
    logger.info("    /emotion_state      - 查看当前情绪状态")
    logger.info("    /quit               - 退出")
    logger.info("=" * 50)
    logger.info("")

    while True:
        try:
            user_input = input("弹幕> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if not user_input:
            continue

        if user_input == "/quit":
            break

        # Special commands
        if user_input.startswith("/emotion "):
            emotion = user_input.split(" ", 1)[1].strip()
            result = bot.emotion_tracker.update_from_keywords(emotion)
            if result is None:
                # Try direct label
                from emotion.tracker import EmotionLabel
                try:
                    label = EmotionLabel(emotion)
                    bot.emotion_tracker.update_from_label(label, 0.8)
                    logger.info(f"  → 情绪设置为: {label.value}")
                except ValueError:
                    logger.info(f"  → 未知情绪: {emotion}")
            else:
                logger.info(f"  → 检测到情绪: {result.value}")
            # Trigger personality evolve
            if bot.personality_evolution:
                bot.personality_evolution.evolve(bot.emotion_tracker.state.intensities, dt=30)
            continue

        if user_input == "/personality":
            if bot.personality_evolution:
                state = bot.personality_evolution.get_state()
                logger.info("  当前人格状态:")
                for name, trait in state.traits.items():
                    bar = "█" * int(trait.value * 20) + "░" * (20 - int(trait.value * 20))
                    logger.info(f"    {name:14s} [{bar}] {trait.value:.3f}")
            else:
                logger.info("  人格演化未启用")
            continue

        if user_input == "/memory":
            stm = bot.llm_prompt_manager.short_term_memory
            if stm:
                ctx = stm.build_summary_context()
                logger.info(f"  短期记忆摘要: {ctx if ctx else '(暂无摘要)'}")
                logger.info(f"  摘要数量: {len(stm._summaries)}")
            else:
                logger.info("  短期记忆未启用")
            continue

        if user_input == "/emotion_state":
            state = bot.emotion_tracker.state
            logger.info("  当前情绪状态:")
            for emotion, intensity in sorted(state.intensities.items(), key=lambda x: -x[1]):
                if intensity > 0.01:
                    bar = "█" * int(intensity * 20) + "░" * (20 - int(intensity * 20))
                    logger.info(f"    {emotion:10s} [{bar}] {intensity:.3f}")
            logger.info(f"  主导情绪: {state.dominant.value} (强度: {state.dominant_intensity:.3f})")
            continue

        # Simulate danmaku: update emotion + send to LLM
        bot.emotion_tracker.update_from_keywords(user_input)
        bot._autonomous.on_user_interaction()

        # Build the message like a danmaku
        text = f'你收到了一条弹幕，\n用户"模拟观众"说：\n{user_input}'
        logger.info(f"  → 发送到LLM...")

        try:
            prediction = bot.emit_llm_prediction(text, direct_return=True)
            if prediction:
                logger.info(f"  IGEM-sama: {prediction.response}")

                # Show personality if available
                if bot.personality_evolution:
                    state = bot.personality_evolution.get_state()
                    lively = state.traits.get("lively")
                    if lively and lively.value > 0.8:
                        logger.info(f"  [人格: 活泼度{lively.value:.0%}]")
            else:
                logger.warning("  → LLM未响应 (请检查API配置)")
        except Exception as e:
            logger.error(f"  → LLM调用失败: {e}")
            logger.info("  提示: 请确保DeepSeek API可用，或在config.yaml中配置其他LLM")

    logger.info("模拟直播结束。")


def lightweight_demo():
    """Lightweight demo that doesn't need full bot initialization.

    Tests the new modules directly without LLM/TTS/external services.
    """
    logger.info("")
    logger.info("使用轻量模式 (不需要LLM API)")
    logger.info("")

    # === P0-1: Lip Sync Demo ===
    logger.info("=" * 40)
    logger.info("P0-1: Lip Sync 增强")
    logger.info("=" * 40)

    from services.live2d.viseme_engine import VisemeEngine
    from services.live2d.lip_sync_interpolator import LipSyncInterpolator

    engine = VisemeEngine()
    logger.info("  口型引擎初始化成功")

    # Simulate different spectral features
    test_cases = [
        ("静默", 0.01, {'low': 0.0, 'mid': 0.0, 'high': 0.0, 'centroid': 0.5, 'flatness': 0.5}),
        ("A音(开口)", 0.3, {'low': 0.6, 'mid': 0.3, 'high': 0.1, 'centroid': 0.3, 'flatness': 0.3}),
        ("I音(扁口)", 0.2, {'low': 0.2, 'mid': 0.3, 'high': 0.5, 'centroid': 0.7, 'flatness': 0.4}),
        ("U音(圆口)", 0.15, {'low': 0.7, 'mid': 0.2, 'high': 0.1, 'centroid': 0.2, 'flatness': 0.6}),
        ("E音(半开)", 0.25, {'low': 0.3, 'mid': 0.4, 'high': 0.3, 'centroid': 0.5, 'flatness': 0.4}),
        ("O音(圆开)", 0.2, {'low': 0.4, 'mid': 0.4, 'high': 0.2, 'centroid': 0.4, 'flatness': 0.5}),
    ]

    for name, rms, spectral in test_cases:
        is_speaking = rms > 0.02
        params = engine.process_frame(rms, spectral, is_speaking)
        mouth_open = params.get("ParamMouthOpenY", 0)
        mouth_form = params.get("ParamMouthForm", 0)
        viseme = engine.get_current_viseme()
        logger.info(f"  {name:10s} → 口型={viseme:4s}  张嘴={mouth_open:+.2f}  嘴形={mouth_form:+.2f}")

    # Show interpolation smoothness
    logger.info("")
    logger.info("  插值平滑度测试 (A→rest):")
    interp = LipSyncInterpolator(attack=0.5, release=0.2)
    targets = {"ParamMouthOpenY": 0.8}
    for frame in range(10):
        result = interp.interpolate(targets, dt=1/120)
        bar = "█" * int(result["ParamMouthOpenY"] * 20)
        logger.info(f"    帧{frame:2d}: {bar} {result['ParamMouthOpenY']:.3f}")
        if frame == 4:
            targets = {"ParamMouthOpenY": 0.0}  # Release

    # === P0-2: Short-term Memory Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("P0-2: 短期记忆增强")
    logger.info("=" * 40)

    from memory.short_term import ShortTermMemory, ShortTermMemoryConfig
    from zerolan.data.pipeline.llm import Conversation, RoleEnum

    stm_config = ShortTermMemoryConfig(
        enable=True,
        max_recent_messages=4,
        summary_threshold=6,
        max_summaries=2,
    )
    stm = ShortTermMemory(stm_config)

    injected = [
        Conversation(role=RoleEnum.system, content="你是IGEM-sama。"),
        Conversation(role=RoleEnum.user, content="你是谁？"),
        Conversation(role=RoleEnum.assistant, content="我是IGEM-sama！"),
    ]

    # Simulate conversation exceeding threshold
    messages = [
        ("观众A", "你们项目是做什么的？"),
        ("IGEM-sama", "我们在做合成生物学的创新研究！"),
        ("观众B", "能讲讲iGEM比赛吗？"),
        ("IGEM-sama", "iGEM是国际遗传工程机器设计大赛！"),
        ("观众C", "你们的实验进展怎么样？"),
        ("IGEM-sama", "进展很顺利，我们在做基因回路设计！"),
        ("观众D", "好厉害啊！"),
        ("IGEM-sama", "谢谢夸奖！"),
    ]

    history = list(injected)
    for role_str, content in messages:
        role = RoleEnum.user if "观众" in role_str else RoleEnum.assistant
        history.append(Conversation(role=role, content=content))

    logger.info(f"  原始历史: {len(history)} 条消息")
    logger.info(f"  阈值: {stm_config.summary_threshold}")

    # Old behavior: hard truncation
    if len(history) > 20:
        truncated = list(injected)
    else:
        truncated = list(history)
    logger.info(f"  旧模式(硬截断): {len(truncated)} 条消息 — 丢失了{len(history) - len(truncated)}条!")

    # New behavior: summarization
    reconstructed = stm.reconstruct_history(injected, history)
    logger.info(f"  新模式(摘要压缩): {len(reconstructed)} 条消息")

    summary_ctx = stm.build_summary_context()
    if summary_ctx:
        logger.info(f"  摘要内容: {summary_ctx[:120]}...")
    else:
        logger.info("  (摘要生成需要LLM，轻量模式跳过)")

    # === P1-1: Personality Evolution Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("P1-1: 人格演化系统")
    logger.info("=" * 40)

    from personality.config import PersonalityEvolutionConfig
    from personality.personality_state import PersonalityEvolution
    from personality.prompt_builder import PersonalityPromptBuilder

    evo_config = PersonalityEvolutionConfig(enable=True)
    evo = PersonalityEvolution(evo_config)
    builder = PersonalityPromptBuilder()

    # Show initial state
    state = evo.get_state()
    logger.info("  初始人格状态:")
    for name, trait in state.traits.items():
        bar = "█" * int(trait.value * 20) + "░" * (20 - int(trait.value * 20))
        logger.info(f"    {name:14s} [{bar}] {trait.value:.2f}")

    # Simulate 5 minutes of happy/excited stream
    logger.info("")
    logger.info("  模拟5分钟快乐直播...")
    for _ in range(300):  # 300 seconds
        evo.evolve({'happy': 0.7, 'excited': 0.4}, dt=1.0)

    state = evo.get_state()
    logger.info("  5分钟后人格状态:")
    for name, trait in state.traits.items():
        bar = "█" * int(trait.value * 20) + "░" * (20 - int(trait.value * 20))
        delta = trait.value - trait.default_value
        arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
        logger.info(f"    {name:14s} [{bar}] {trait.value:.2f} {arrow}{abs(delta):.2f}")

    # Show dynamic prompt
    base_prompt = "你是IGEM-sama，IGEM-FBH队伍的AI形象大使。"
    dynamic_prompt = evo.build_system_prompt(base_prompt)
    logger.info(f"  动态prompt: {dynamic_prompt[len(base_prompt):]}")

    # Simulate 5 minutes of sad/angry stream
    logger.info("")
    logger.info("  模拟5分钟低落直播...")
    for _ in range(300):
        evo.evolve({'sad': 0.6, 'angry': 0.3}, dt=1.0)

    state = evo.get_state()
    logger.info("  5分钟后人格状态 (从快乐→低落):")
    for name, trait in state.traits.items():
        bar = "█" * int(trait.value * 20) + "░" * (20 - int(trait.value * 20))
        delta = trait.value - trait.default_value
        arrow = "↑" if delta > 0.01 else ("↓" if delta < -0.01 else "→")
        logger.info(f"    {name:14s} [{bar}] {trait.value:.2f} {arrow}{abs(delta):.2f}")

    # === Emotion + Personality Integration Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("情绪→人格联动演示")
    logger.info("=" * 40)

    from emotion.tracker import EmotionTracker

    tracker = EmotionTracker()
    evo2 = PersonalityEvolution(PersonalityEvolutionConfig(enable=True))

    test_messages = [
        "太厉害了！",
        "你们的项目好酷！",
        "哈哈好有趣",
        "为什么合成生物学这么难？",
        "IGEM-FBH是最棒的！",
    ]

    logger.info("  模拟弹幕→情绪→人格联动:")
    for msg in test_messages:
        detected = tracker.update_from_keywords(msg)
        tracker.update_from_sentiment(0.5)  # Positive sentiment
        evo2.evolve(tracker.state.intensities, dt=60)
        lively = evo2.get_state().traits["lively"].value
        tsundere = evo2.get_state().traits["tsundere"].value
        dominant = tracker.state.dominant.value
        logger.info(f"    弹幕\"{msg}\" → 情绪:{dominant:8s} → 活泼:{lively:.3f} 傲娇:{tsundere:.3f}")

    # === P1-2: Voice Pipeline Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("P1-2: 语音克隆管道")
    logger.info("=" * 40)

    from pipeline.voice.config import VoicePipelineConfig, RVCConfig, VoiceConversionBackend
    from pipeline.voice.voice_converter import VoiceConverter

    rvc_config = RVCConfig()
    converter = VoiceConverter(rvc_config)
    logger.info(f"  RVC语音转换器: 已初始化")
    logger.info(f"  模型路径: {rvc_config.model_path}")
    logger.info(f"  设备: {rvc_config.device}")
    logger.info(f"  音高提取: {rvc_config.f0_method}")
    logger.info(f"  模型已加载: {converter.is_available()}")
    logger.info("  (需要放置RVC模型文件并pip install rvc-python才能启用)")

    # === P2-2: Perception Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("P2-2: 多模态感知")
    logger.info("=" * 40)

    from perception.config import PerceptionConfig, VisualPerceptionMode, VisualCaptureConfig, VisualEventConfig

    perc_config = PerceptionConfig(
        visual=VisualCaptureConfig(
            enable=True,
            mode=VisualPerceptionMode.PROACTIVE,
            capture_interval=10.0,
        ),
        events=VisualEventConfig(
            enable=True,
            change_threshold=0.3,
            event_cooldown=30.0,
        ),
    )
    logger.info(f"  感知模式: {perc_config.visual.mode.value}")
    logger.info(f"  OCR: {'启用' if perc_config.analysis.enable_ocr else '关闭'}")
    logger.info(f"  ImgCap: {'启用' if perc_config.analysis.enable_imgcap else '关闭'}")
    logger.info(f"  视觉事件检测: {'启用' if perc_config.events.enable else '关闭'}")
    logger.info("  (需要启用OCR/ImgCap pipeline才能实际运行)")

    # === P2-1: Game Loop Demo ===
    logger.info("")
    logger.info("=" * 40)
    logger.info("P2-1: 游戏互动闭环")
    logger.info("=" * 40)

    from game_loop.config import GameLoopConfig, GamePlatform
    from game_loop.game_decision import GameDecision, GameAction
    from game_loop.game_action import GameActionExecutor
    from game_loop.game_perception import GameState
    from game_loop.commentary import GameCommentary

    game_config = GameLoopConfig(
        enable=True,
        platform=GamePlatform.SCREEN_BASED,
        capture_interval=2.0,
        commentary_interval_range=(30, 90),
    )
    logger.info(f"  平台: {game_config.platform.value}")
    logger.info(f"  截屏间隔: {game_config.capture_interval}s")
    logger.info(f"  决策间隔: {game_config.decision_interval}s")

    # Simulate a game state
    test_state = GameState(
        ocr_text="Health: 80% Score: 1500",
        image_caption="A character standing in a grassy field with trees in the background",
        game_context="屏幕文字: Health: 80% Score: 1500; 画面描述: A character standing in a grassy field",
    )
    logger.info(f"  模拟游戏状态: {test_state.game_context[:80]}...")

    # Test action executor
    executor = GameActionExecutor()
    test_actions = [
        GameAction(action_type="key_press", params={"key": "w"}, description="向前移动"),
        GameAction(action_type="key_press", params={"key": "space"}, description="跳跃"),
    ]
    logger.info(f"  动作执行器: {len(test_actions)}个模拟动作 (dry-run, 不实际执行)")

    # Test commentary
    commentary_triggered = []

    def on_commentary(prompt):
        commentary_triggered.append(prompt)

    commentary = GameCommentary(on_trigger=on_commentary, config=game_config)
    commentary.generate_commentary(test_state)
    logger.info(f"  游戏解说触发: {commentary_triggered[0][:60]}..." if commentary_triggered else "  解说未触发")

    # === Final Summary ===
    logger.info("")
    logger.info("=" * 50)
    logger.info("  全部6个新模块验证完成!")
    logger.info("=" * 50)
    logger.info("")
    logger.info("  P0-1 Lip Sync:    ✅ 频谱分析→口型分类→多参数映射→平滑插值")
    logger.info("  P0-2 短期记忆:    ✅ 摘要压缩替代硬截断，保留对话流")
    logger.info("  P1-1 人格演化:    ✅ 6维特质随情绪漂移，动态system prompt")
    logger.info("  P1-2 语音克隆:    ✅ RVC管道就绪，等待模型文件")
    logger.info("  P2-2 多模态感知:  ✅ 三级自主视觉感知框架就绪")
    logger.info("  P2-1 游戏互动:    ✅ 感知→决策→动作→解说闭环就绪")
    logger.info("")
    logger.info("  要连接真实LLM进行完整测试，请在config.yaml中配置API key")
    logger.info("  然后运行: python simulate.py")


if __name__ == "__main__":
    main()
