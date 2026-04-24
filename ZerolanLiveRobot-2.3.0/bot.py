import asyncio
import os
from concurrent.futures.thread import ThreadPoolExecutor
from pathlib import Path
from queue import Queue
from typing import List

from loguru import logger
from zerolan.data.data.prompt import TTSPrompt
from zerolan.data.pipeline.asr import ASRStreamQuery
from zerolan.data.pipeline.img_cap import ImgCapQuery
from zerolan.data.pipeline.llm import LLMQuery, LLMPrediction
from zerolan.data.pipeline.milvus import MilvusInsert, InsertRow, MilvusQuery
from zerolan.data.pipeline.ocr import OCRQuery
from zerolan.data.pipeline.tts import TTSQuery
from zerolan.data.pipeline.vla import ShowUiQuery

from agent.api import sentiment_analyse, translate, summary_history, find_file, model_scale, sentiment_score, \
    memory_score
from emotion.tracker import EmotionTracker
from emotion.expression_map import Live2DExpressionDriver
from analytics.collector import StreamAnalytics
from common.rate_limiter import RateLimiter
from memory.long_term import LongTermMemory
from autonomous.behavior import AutonomousBehavior
from personality.personality_state import PersonalityEvolution
from pipeline.voice.voice_pipeline import VoicePipeline
from perception.visual_loop import VisualLoop
from perception.perception_context import PerceptionContext
from perception.event_handler import VisualEventHandler
from game_loop.game_perception import GamePerception
from game_loop.game_decision import GameDecision
from game_loop.game_action import GameActionExecutor
from game_loop.commentary import GameCommentary
from common.concurrent.abs_runnable import stop_all_runnable
from common.concurrent.killable_thread import KillableThread, kill_all_threads
from common.concurrent.circuit_breaker import CircuitBreaker
from common.enumerator import Language
from common.io.api import save_audio
from common.io.file_type import AudioFileType
from common.utils import audio_util, math_util
from common.utils.img_util import is_image_uniform
from common.utils.str_util import split_by_punc, is_blank
from event.event_data import DeviceMicrophoneVADEvent, DeviceKeyboardPressEvent, DeviceScreenCapturedEvent, \
    PipelineOutputLLMEvent, \
    PipelineImgCapEvent, \
    QQMessageEvent, DeviceMicrophoneSwitchEvent, PipelineOutputTTSEvent, PipelineASREvent, \
    PipelineOCREvent, SecondEvent, ConfigFileModifiedEvent, LiveStreamDanmakuEvent, DeviceSpeakerPlayEvent
from event.event_emitter import emitter
from event.registry import EventKeyRegistry
from framework.base_bot import BaseBot
from manager.config_manager import get_config
from pipeline.ocr.ocr_sync import avg_confidence, stringify

_config = get_config()


class ZerolanLiveRobot(BaseBot):
    def __init__(self):
        super().__init__()
        self.cur_lang = Language.ZH
        self.tts_prompt_manager.set_lang(self.cur_lang)
        self._timer_flag = True
        self.tts_thread_pool = ThreadPoolExecutor(max_workers=1)
        self.enable_exp_memory = _config.system.enable_intelligent_memory
        self.enable_sentiment_analysis = _config.system.enable_sentiment_analysis
        self.enable_split_by_punc = _config.system.enable_clause_split
        self.emotion_tracker = EmotionTracker()
        self._expression_driver = Live2DExpressionDriver()
        self.stream_analytics = StreamAnalytics()
        # Connect expression driver to Live2D viewer if available
        if self.live2d_viewer is not None:
            self._expression_driver.set_viewer(self.live2d_viewer)
        self.long_term_memory = LongTermMemory()
        self._autonomous = AutonomousBehavior(on_trigger=self.emit_llm_prediction)
        # Personality evolution (initialized from config if available)
        self.personality_evolution = None
        try:
            personality_cfg = getattr(_config, 'personality', None)
            if personality_cfg and hasattr(personality_cfg, 'evolution') and personality_cfg.evolution.enable:
                self.personality_evolution = PersonalityEvolution(personality_cfg.evolution)
                logger.info("Personality evolution enabled.")
        except Exception as e:
            logger.debug(f"Personality evolution not configured: {e}")
        # Voice pipeline (TTS + optional RVC conversion)
        self.voice_pipeline = None
        try:
            voice_cfg = getattr(_config.pipeline, 'voice', None)
            if voice_cfg and voice_cfg.enable:
                self.voice_pipeline = VoicePipeline(self.tts, voice_cfg)
                logger.info("Voice pipeline (TTS + RVC) enabled.")
        except Exception as e:
            logger.debug(f"Voice pipeline not configured: {e}")
        # Multimodal perception (visual awareness)
        self._visual_loop = None
        self._perception_context = None
        self._visual_event_handler = None
        try:
            perc_cfg = getattr(_config, 'perception', None)
            if perc_cfg and perc_cfg.visual.enable:
                self._visual_loop = VisualLoop(self.screen, self.ocr, self.img_cap, perc_cfg)
                self._perception_context = PerceptionContext(self._visual_loop, perc_cfg)
                self._visual_event_handler = VisualEventHandler(
                    on_trigger=self.emit_llm_prediction,
                    emotion_tracker=self.emotion_tracker,
                    visual_loop=self._visual_loop,
                    config=perc_cfg,
                )
                logger.info("Multimodal perception enabled.")
        except Exception as e:
            logger.debug(f"Perception not configured: {e}")
        # Game interaction loop
        self._game_perception = None
        self._game_decision = None
        self._game_action_executor = None
        self._game_commentary = None
        try:
            game_cfg = getattr(_config, 'game_loop', None)
            if game_cfg and game_cfg.enable:
                self._game_perception = GamePerception(
                    self.screen, self.ocr, self.img_cap, game_cfg
                )
                self._game_decision = GameDecision(
                    self.llm, self.game_agent, game_cfg
                )
                self._game_action_executor = GameActionExecutor(self.game_agent)
                self._game_commentary = GameCommentary(
                    on_trigger=self.emit_llm_prediction,
                    config=game_cfg,
                )
                logger.info("Game interaction loop enabled.")
        except Exception as e:
            logger.debug(f"Game loop not configured: {e}")
        self.stream_analytics = StreamAnalytics()
        self._rate_limiter = RateLimiter(per_user_limit=3, per_user_window=10, global_limit=2)
        self.subtitles_queue = Queue(maxsize=20)
        # Circuit breakers for external services
        self._llm_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0, name="llm")
        self._tts_breaker = CircuitBreaker(failure_threshold=5, recovery_timeout=30.0, name="tts")
        self.init()
        logger.info("🤖 Zerolan Live Robot: Initialized services successfully.")

    async def start(self):
        logger.info("🤖 Zerolan Live Robot: Running...")
        async with asyncio.TaskGroup() as tg:
            tg.create_task(emitter.start())
            if self.model_manager is not None:
                self.model_manager.scan()

            threads = []
            if _config.system.default_enable_microphone:
                vad_thread = KillableThread(target=self.mic.start, daemon=True, name="VADThread")
                threads.append(vad_thread)

            if self.keyboard is not None:
                keyboard_thread = KillableThread(target=self.keyboard.start, daemon=True, name="KeyboardThread")
                threads.append(keyboard_thread)

            speaker_thread = KillableThread(target=self.speaker.start, daemon=True, name="SpeakerThread")
            threads.append(speaker_thread)

            if self.playground:
                playground_thread = KillableThread(target=self.playground.start, daemon=True, name="PlaygroundThread")
                threads.append(playground_thread)

            if self.res_server:
                res_server_thread = KillableThread(target=self.res_server.start, daemon=True, name="ResServerThread")
                threads.append(res_server_thread)

            if self.obs is not None:
                obs_client_thread = KillableThread(target=self.obs.start, daemon=True, name="ObsClientThread")
                threads.append(obs_client_thread)

            if self.live2d_viewer is not None:
                live2d_viewer_thread = KillableThread(target=self.live2d_viewer.start, daemon=True,
                                                      name="Live2DViewerThread")
                threads.append(live2d_viewer_thread)

            if self.game_agent:
                game_agent_thread = KillableThread(target=self.game_agent.start, daemon=True, name="GameAgentThread")
                threads.append(game_agent_thread)

            for thread in threads:
                thread.start()

            # tg.create_task(emitter.start())
            if self.bilibili:
                def start_bili():
                    asyncio.run(self.bilibili.start())

                bili_thread = KillableThread(target=start_bili, daemon=True, name="BilibiliThread")
                bili_thread.start()
            if self.youtube:
                tg.create_task(self.youtube.start())
            if self.twitch:
                tg.create_task(self.twitch.start())
            if self.config_page:
                tg.create_task(self.config_page.start())

            # Start operator control panel
            try:
                from panel.server import set_bot, start_panel
                set_bot(self)
                panel_thread = KillableThread(target=start_panel, kwargs={"host": "0.0.0.0", "port": 9090},
                                              daemon=True, name="ControlPanelThread")
                panel_thread.start()
                logger.info("Control panel: http://0.0.0.0:9090")
            except Exception as e:
                logger.warning(f"Control panel failed to start: {e}")
            elapsed = 0
            while self._timer_flag:
                await asyncio.sleep(1)
                emitter.emit(SecondEvent(elapsed=elapsed))
                elapsed += 1

        for thread in threads:
            thread.join()

    async def stop(self):
        self.tts_thread_pool.shutdown()
        emitter.stop()
        kill_all_threads()
        await stop_all_runnable()
        logger.info("Good Bye!")

    def init(self):
        @emitter.on(EventKeyRegistry.Playground.CONNECTED)
        def on_playground_connected(_):
            self.mic.pause()
            logger.info("Because ZerolanPlayground client connected, close the local microphone.")
            if self.playground:
                self.playground.load_live2d_model(
                    bot_id=self.bot_id,
                    bot_display_name=self.bot_name,
                    model_dir=self.live2d_model
                )
            logger.info(f"Live 2D model loaded: {self.live2d_model}")

        @emitter.on(EventKeyRegistry.Playground.DISCONNECTED)
        def on_playground_disconnected(_):
            # self.vad.resume()
            # logger.info("Because ZerolanPlayground client disconnected, open the local microphone.")
            pass

        @emitter.on(EventKeyRegistry.Device.KEYBOARD_HOTKEY_PRESS)
        def hotkey_handler(event: DeviceKeyboardPressEvent):
            logger.info(f'Hotkey toggle: {event.hotkey}')
            # 判断 hotkey 内容
            try:
                if event.hotkey == _config.system.microphone_hotkey:
                    if _config.system.default_enable_microphone:
                        # 麦克风对象锁
                        with self.keyboard.microphone_state_lock:
                            if self.mic.is_set_talk_enabled_event():
                                logger.debug(f'Hotkey toggled: MIC OFF')

                                # 关麦
                                self.mic.unset_talk_enabled_event()

                                # 强制 emit 已经收集的片段
                                self.mic.force_commit(is_emit=True)

                                # TODO: 播放停止提示音
                                pass
                            else:
                                logger.debug(f'Hotkey toggled: MIC ON')

                                # 仅清空可能遗留的音频
                                self.mic.force_commit(is_emit=False)

                                # TODO: 播放开始提示音，block=True
                                pass

                                # 开麦
                                self.mic.set_talk_enabled_event()
                    else:
                        logger.info(f'Microphone is disabled at config.yaml')
                elif False:
                    # example
                    pass
            except Exception as e:
                logger.exception(e)

        @emitter.on(EventKeyRegistry.Device.MICROPHONE_SWITCH)
        def on_open_microphone(event: DeviceMicrophoneSwitchEvent):
            if self.mic.is_recording:
                if event.switch:
                    logger.warning("The microphone has already resumed.")
                    return
                self.mic.pause()
            else:
                if not event.switch:
                    logger.warning("The microphone has already paused.")
                    return
                self.mic.resume()

        @emitter.on(EventKeyRegistry.Device.MICROPHONE_VAD)
        def on_service_vad_speech_chunk(event: DeviceMicrophoneVADEvent):
            logger.debug("`SpeechEvent` received.")
            speech, channels, sample_rate = event.speech, event.channels, event.sample_rate
            query = ASRStreamQuery(is_final=True, audio_data=speech, channels=channels, sample_rate=sample_rate,
                                   media_type=event.audio_type.value)

            for prediction in self.asr.stream_predict(query):
                logger.info(f"ASR: {prediction.transcript}")
                if is_blank(prediction.transcript):
                    continue
                emitter.emit(PipelineASREvent(prediction=prediction))
                logger.debug("ASREvent emitted.")

        @emitter.on(EventKeyRegistry.Pipeline.ASR)
        def asr_handler(event: PipelineASREvent):
            logger.debug("`ASREvent` received.")
            self._autonomous.on_user_interaction()
            prediction = event.prediction
            if self.playground:
                self.playground.add_history(role="user", text=prediction.transcript, username=self.master_name)
            if "打开浏览器" in prediction.transcript:
                if self.browser is not None:
                    self.browser.open("https://www.bing.com")
            elif "关闭浏览器" in prediction.transcript:
                if self.browser is not None:
                    self.browser.close()
            elif "网页搜索" in prediction.transcript:
                if self.browser is not None:
                    self.browser.move_to_search_box()
                    text = prediction.transcript[4:]
                    self.browser.send_keys_and_enter(text)
            elif "游戏" in prediction.transcript:
                self.game_agent.exec_instruction(prediction.transcript)
            elif "看见" in prediction.transcript:
                img, img_save_path = self.screen.safe_capture(k=0.99)
                if not self.check_img(img):
                    return
                emitter.emit(DeviceScreenCapturedEvent(img_path=img_save_path, is_camera=False))
            elif "点击" in prediction.transcript:
                # If there is no display, then can not use this feature
                if os.environ.get('DISPLAY', None) is None:
                    return
                img, img_save_path = self.screen.safe_capture(k=0.99)
                if not self.check_img(img):
                    return

                query = ShowUiQuery(query=prediction.transcript, env="web", img_path=img_save_path)
                prediction = self.showui.predict(query)
                logger.debug("ShowUI: " + prediction.model_dump_json())
                action = prediction.actions[0]
                if action.action == "CLICK":
                    import pyautogui
                    logger.info("Click action triggered.")
                    x, y = action.position[0] * img.width, action.position[1] * img.height
                    pyautogui.moveTo(x, y)
                    pyautogui.click()
            elif "记得" in prediction.transcript:
                query = MilvusQuery(collection_name="history_collection", limit=2, output_fields=['history', 'text'],
                                    query=prediction.transcript)
                result = self.vec_db.search(query)
                memory = result.result[0][0]
                memory = memory.entity["text"]
                logger.debug(f"Memory found: {memory}")
                self.emit_llm_prediction(f"{memory}\n\n请根据上文回答：{prediction.transcript} \n")
            elif "加载模型" in prediction.transcript:
                file_id = find_file(self.model_manager.get_files(), prediction.transcript)
                file_info = self.model_manager.get_file_by_id(file_id)
                if self.playground:
                    self.playground.load_3d_model(file_info)
            elif "调整模型" in prediction.transcript:
                if self.playground:
                    info = self.playground.get_gameobjects_info()
                    if not info:
                        logger.warning("No gameobjects info")
                        return
                    so = model_scale(info, prediction.transcript)
                    self.playground.modify_game_object_scale(so)
            else:
                if self.playground:
                    assert self.custom_agent is not None
                    tool_called = self.custom_agent.run(prediction.transcript)
                    if tool_called:
                        logger.debug("Tool called.")
                self.emit_llm_prediction(prediction.transcript)
            if self.playground:
                if self.playground.is_connected:
                    self.playground.show_user_input_text(prediction.transcript)
            if self.obs:
                self.obs.subtitle(prediction.transcript, which="user")

        @emitter.on(EventKeyRegistry.LiveStream.DANMAKU)
        def on_danmaku(event: LiveStreamDanmakuEvent):
            # Anti-spam rate limiting
            if not self._rate_limiter.allow(uid=event.danmaku.uid):
                logger.debug(f"Rate limited: {event.danmaku.username}")
                return
            # Emotion: detect from danmaku keywords
            self.emotion_tracker.update_from_keywords(event.danmaku.content)
            # Long-term memory: track returning viewers
            viewer_ctx = self.long_term_memory.build_viewer_context(
                uid=event.danmaku.uid,
                username=event.danmaku.username,
                platform=event.danmaku.platform,
            )
            # Analytics: record danmaku
            self.stream_analytics.record_danmaku(
                event.danmaku.content, uid=event.danmaku.uid, username=event.danmaku.username
            )
            text = f'你收到了一条弹幕，{viewer_ctx}\n用户"{event.danmaku.username}"说：\n{event.danmaku.content}'
            # Notify autonomous system of user interaction
            self._autonomous.on_user_interaction()
            self.emit_llm_prediction(text)

        # @emitter.on(EventKeyRegistry.System.SECOND)
        # async def on_second_danmaku_check(event: SecondEvent):
        #     # Try select danmaku every 5 seconds.
        #     if event.elapsed % 5 == 0:
        #         danmaku = await self.bilibili.select_max_long_one()
        #         if danmaku:
        #             logger.info(f"Selected danmaku: [{danmaku.username}] {danmaku.content}")
        #             text = f'你收到了一条弹幕，用户"{danmaku.username}"说：\n{danmaku.content}'
        #             self.emit_llm_prediction(text)

        @emitter.on(EventKeyRegistry.Device.SCREEN_CAPTURED)
        def on_device_screen_captured(event: DeviceScreenCapturedEvent):
            img_path = event.img_path
            if isinstance(event.img_path, Path):
                img_path = str(event.img_path)

            ocr_prediction = self.ocr.predict(OCRQuery(img_path=img_path))
            # TODO: 0.6 is a hyperparameter that indicates the average confidence of the text contained in the image.
            if avg_confidence(ocr_prediction) > 0.6:
                logger.info("OCR: " + stringify(ocr_prediction.region_results))
                emitter.emit(PipelineOCREvent(prediction=ocr_prediction))
            else:
                img_cap_prediction = self.img_cap.predict(ImgCapQuery(prompt="There", img_path=img_path))
                src_lang = Language.value_of(img_cap_prediction.lang)
                caption = translate(src_lang, self.cur_lang, img_cap_prediction.caption)
                img_cap_prediction.caption = caption
                logger.info("ImgCap: " + caption)
                emitter.emit(PipelineImgCapEvent(prediction=img_cap_prediction))

        def predict_image_modal(images: List[Path]):
            results = []
            for image in images:
                if image.exists():
                    ocr_prediction = self.ocr.predict(OCRQuery(img_path=str(image)))
                    ocr_text = stringify(ocr_prediction.region_results)
                    img_cap_prediction = self.img_cap.predict(ImgCapQuery(prompt="There", img_path=str(image)))
                    img_cap_text = img_cap_prediction.caption
                    results.append({
                        "ocr": ocr_text,
                        "sentiment": img_cap_text
                    })
            return results

        @emitter.on(EventKeyRegistry.QQBot.QQ_MESSAGE)
        def on_qq_message(event: QQMessageEvent):
            if "语音" in event.message:
                prediction = self.emit_llm_prediction(event.message, direct_return=True)
                if prediction is None:
                    logger.warning("No response from LLM remote service and will not send QQ message.")
                    return
                tts_prompt = self.tts_prompt_manager.default_tts_prompt
                query = TTSQuery(
                    text=prediction.response,
                    text_language="auto",
                    refer_wav_path=tts_prompt.audio_path,
                    prompt_text=tts_prompt.prompt_text,
                    prompt_language=tts_prompt.lang,
                    audio_type="wav"
                )
                prediction = self.tts.predict(query=query)
                file_path = save_audio(prediction.wave_data, prefix="tts")
                self.qq.send_speech(event.group_id, str(file_path))
            elif event.images is not None and len(event.images) > 0:
                result = predict_image_modal(event.images)
                query_text = "你看见群友给你发了张图片，内容是：" + str(result)
                logger.info(f"OCR + ImgCap: {result}")
                prediction = self.emit_llm_prediction(query_text, direct_return=True)
                if prediction is None:
                    logger.warning("No response from LLM remote service and will not send QQ message.")
                    return
                self.qq.send_plain_message(group_id=event.group_id, receiver_id=event.sender_id,
                                           text=prediction.response)
            else:
                prediction = self.emit_llm_prediction(event.message, direct_return=True)
                if prediction is None:
                    logger.warning("No response from LLM remote service and will not send QQ message.")
                    return
                self.qq.send_plain_message(group_id=event.group_id, receiver_id=event.sender_id,
                                           text=prediction.response)

        @emitter.on(EventKeyRegistry.Pipeline.OCR)
        def on_pipeline_ocr(event: PipelineOCREvent):
            prediction = event.prediction
            text = "你看见了" + stringify(prediction.region_results) + "\n请总结一下"
            self.emit_llm_prediction(text)

        @emitter.on(EventKeyRegistry.Pipeline.IMG_CAP)
        def on_pipeline_img_cap(event: PipelineImgCapEvent):
            prediction = event.prediction
            text = "你看见了" + prediction.caption
            self.emit_llm_prediction(text)

        @emitter.on(EventKeyRegistry.Pipeline.LLM)
        def llm_query_handler(event: PipelineOutputLLMEvent):
            prediction = event.prediction
            text = prediction.response
            logger.info("LLM: " + text)

            # Update emotion from LLM response
            self.emotion_tracker.update_from_keywords(text)

            if self.enable_sentiment_analysis:
                sentiment = sentiment_analyse(sentiments=self.tts_prompt_manager.sentiments, text=text)
                tts_prompt = self.tts_prompt_manager.get_tts_prompt(sentiment)
                # Also update emotion tracker from sentiment analysis result
                try:
                    score = sentiment_score(text)
                    self.emotion_tracker.update_from_sentiment(score)
                except Exception:
                    pass
            else:
                tts_prompt = self.tts_prompt_manager.default_tts_prompt
            if self.playground:
                self.playground.add_history(role="assistant", text=text, username=self.bot_name)

            if self.enable_split_by_punc:
                transcripts = split_by_punc(text, self.cur_lang)
                # Note that transcripts may be [] because we can not apply split in some cases.
                if len(transcripts) > 0:
                    for idx, transcript in enumerate(transcripts):
                        self._tts_without_block(tts_prompt, transcript)
            else:
                self._tts_without_block(tts_prompt, text)

        @emitter.on(EventKeyRegistry.System.CONFIG_FILE_MODIFIED)
        def on_config_modified(_: ConfigFileModifiedEvent):
            config = get_config()

        @emitter.on(EventKeyRegistry.System.SECOND)
        def on_second(event: SecondEvent):
            # Decay emotion over time (drifts back to neutral when idle)
            self.emotion_tracker.decay(dt=1.0)
            # Personality evolution: drift based on current emotions
            if self.personality_evolution:
                try:
                    self.personality_evolution.evolve(self.emotion_tracker.state.intensities, dt=1.0)
                except Exception:
                    pass
            # Sync emotion → Live2D expression every second
            try:
                dominant = self.emotion_tracker.state.dominant.value
                intensity = self.emotion_tracker.state.dominant_intensity
                self._expression_driver.apply_emotion(dominant, intensity)
                # Trigger motion on emotion change (not every tick)
                prev_emotion = self._expression_driver._current_emotion
                if dominant != prev_emotion and intensity > 0.3:
                    self._expression_driver.trigger_motion(dominant)
                # Show mic accessory once Live2D canvas is ready
                if event.elapsed == 5 and self.live2d_viewer is not None:
                    self._expression_driver.show_mic(True)
                # Analytics: record emotion
                self.stream_analytics.record_emotion(dominant, intensity)
            except Exception:
                pass
            # Periodic memory decay (every 60 seconds)
            if event.elapsed % 60 == 0:
                self.long_term_memory.apply_decay()
            # Save analytics snapshot every 10 seconds
            if event.elapsed % 10 == 0:
                try:
                    self.stream_analytics.save_snapshot()
                except Exception:
                    pass
            # Autonomous behavior (see autonomous module)
            if hasattr(self, '_autonomous'):
                self._autonomous.on_tick(event.elapsed)
            # Multimodal perception: periodic visual capture
            if self._visual_loop:
                self._visual_loop.on_tick(event.elapsed)
            if self._visual_event_handler:
                self._visual_event_handler.check_and_react(event.elapsed)
            # Game interaction loop
            if self._game_perception and self._game_perception.should_capture(event.elapsed):
                try:
                    game_state = self._game_perception.capture()
                    if game_state and self._game_decision:
                        actions = self._game_decision.decide(game_state)
                        if actions and self._game_action_executor:
                            self._game_action_executor.execute(actions)
                    if game_state and self._game_commentary:
                        if self._game_commentary.should_comment(game_state, event.elapsed):
                            self._game_commentary.generate_commentary(game_state)
                except Exception:
                    pass

        @emitter.on(EventKeyRegistry.Device.SPEAKER_PLAY)
        def on_speaker_play(event: DeviceSpeakerPlayEvent):
            if self.obs is not None:
                assert event.audio_path.exists()
                sample_rate, num_channels, duration = audio_util.get_audio_info(event.audio_path)
                text = self.subtitles_queue.get()
                self.obs.subtitle(text, which="assistant", duration=math_util.clamp(0, 5, duration - 1))

    def _tts_without_block(self, tts_prompt: TTSPrompt, text: str):
        def wrapper():
            try:
                query = TTSQuery(
                    text=text,
                    text_language="auto",
                    refer_wav_path=tts_prompt.audio_path,
                    prompt_text=tts_prompt.prompt_text,
                    prompt_language=tts_prompt.lang,
                    audio_type="wav"
                )
                # Circuit breaker: skip TTS if service is down
                if not self._tts_breaker.allow():
                    logger.warning(f"TTS circuit breaker OPEN, skipping: {text[:30]}")
                    return
                prediction = (self.voice_pipeline or self.tts).predict(query=query)
                self._tts_breaker.record_success()
                logger.info(f"TTS: {query.text}")

                self.play_tts(PipelineOutputTTSEvent(prediction=prediction, transcript=text))
            except Exception as e:
                self._tts_breaker.record_failure()
                logger.error(f"TTS service unavailable: {e}")
                # TTS failed, still show subtitle if OBS is available
                if self.obs is not None:
                    try:
                        self.obs.subtitle(text, which="assistant")
                    except Exception:
                        pass

        # To sync audio playing and subtitle
        self.tts_thread_pool.submit(wrapper)

    def exp_memory(self, text: str, is_filtered: bool, response: str, len_history: int):

        l_max = get_config().character.chat.max_history
        try:
            s = sentiment_score(text)
        except Exception as e:
            logger.exception(e)
            s = 1

        if not is_filtered:
            b = 0
        else:
            b = self.filter.match(response)

        try:
            r = memory_score(response)
        except Exception as e:
            logger.exception(e)
            r = 1
        t_memory = 0.3 * (l_max - len_history) / l_max + 0.2 * s + 0.2 * b + 0.1 * r
        return t_memory > 0.5

    def emit_llm_prediction(self, text, direct_return: bool = False) -> None | LLMPrediction:
        logger.debug("`emit_llm_prediction` called")

        # RAG: Inject knowledge base context before sending to LLM
        if self.kb_pipeline is not None:
            try:
                kb_context = self.kb_pipeline.build_context(text)
                if kb_context:
                    text = f"{kb_context}\n\n[用户消息]\n{text}"
                    logger.debug("RAG context injected into LLM query.")
            except Exception as e:
                logger.warning(f"RAG context injection failed: {e}")

        # Long-term memory: Inject relevant memories
        try:
            memory_ctx = self.long_term_memory.build_memory_context(text)
            if memory_ctx:
                text = f"{memory_ctx}\n{text}"
        except Exception as e:
            logger.warning(f"Memory context injection failed: {e}")

        # Emotion: Inject current emotion hint into LLM query
        emotion_hint = self.emotion_tracker.get_emotion_prompt_hint()
        if emotion_hint:
            text = f"[当前情绪]{emotion_hint}\n{text}"

        # Visual perception: inject visual context if available
        if self._perception_context:
            try:
                visual_ctx = self._perception_context.build_context()
                if visual_ctx:
                    text = f"{visual_ctx}\n{text}"
            except Exception:
                pass

        # Personality: dynamically adjust system prompt based on evolved traits
        if self.personality_evolution:
            try:
                base_prompt = self.llm_prompt_manager.system_prompt
                dynamic_prompt = self.personality_evolution.build_system_prompt(base_prompt)
                self.llm_prompt_manager.update_system_prompt(dynamic_prompt)
            except Exception:
                pass

        query = LLMQuery(text=text, history=self.llm_prompt_manager.current_history)

        # Circuit breaker: skip LLM call if service is known to be down
        if not self._llm_breaker.allow():
            logger.warning(f"LLM circuit breaker OPEN, returning fallback for: {text[:40]}")
            if not direct_return:
                from zerolan.data.pipeline.llm import LLMPrediction
                fallback = "嗯...我的大脑正在休息中，稍等一下~"
                emitter.emit(PipelineOutputLLMEvent(
                    prediction=LLMPrediction(response=fallback, history=[])
                ))
            return None

        try:
            prediction = self.llm.predict(query)
            self._llm_breaker.record_success()
        except Exception as e:
            self._llm_breaker.record_failure()
            logger.error(f"LLM service unavailable: {e}")
            # Graceful degradation: emit a fallback response
            if not direct_return:
                from zerolan.data.pipeline.llm import LLMPrediction
                fallback = "嗯...我好像有点走神了，再说一次好吗？"
                emitter.emit(PipelineOutputLLMEvent(
                    prediction=LLMPrediction(response=fallback, history=[])
                ))
            return None

        # Filter applied here
        is_filtered = self.filter.filter(prediction.response)

        if is_filtered:
            logger.warning(f"LLM (Filtered): {prediction.response}")
            return None

        # Remove \n start
        if prediction.response[0] == '\n':
            prediction.response = prediction.response[1:]

        logger.info(f"Length of current history: {len(self.llm_prompt_manager.current_history)}")

        if self.enable_exp_memory:
            if self.exp_memory(text, is_filtered, prediction.response, len(prediction.response)):
                self.llm_prompt_manager.reset_history(prediction.history)
        else:
            # If experiment memory disabled, history should be updated for each chat commit.
            self.llm_prompt_manager.reset_history(prediction.history)

        # Long-term memory: save important exchanges
        try:
            if not is_filtered and len(prediction.response) > 20:
                self.long_term_memory.add_memory(
                    content=f"观众问: {text[:80]} | 回答: {prediction.response[:80]}",
                    category="event",
                    importance=min(len(prediction.response) / 200, 0.8),
                    tags=text.split()[:5],
                )
        except Exception:
            pass

        if not direct_return:
            emitter.emit(PipelineOutputLLMEvent(prediction=prediction))
            logger.debug("LLMEvent emitted.")

        # Sync emotion to Live2D expression
        try:
            dominant = self.emotion_tracker.state.dominant.value
            intensity = self.emotion_tracker.state.dominant_intensity
            self._expression_driver.apply_emotion(dominant, intensity)
        except Exception:
            pass

        return prediction

    def change_lang(self, lang: Language):
        self.cur_lang = lang.name()
        self.tts_prompt_manager.set_lang(self.cur_lang)

    def check_img(self, img) -> bool:
        if is_image_uniform(img):
            logger.warning("Are you sure you capture the screen properly? The screen is black!")
            self.emit_llm_prediction("你忽然什么都看不见了！请向你的开发者求助！")
            return False
        return True

    def save_memory(self):
        start = len(self.llm_prompt_manager.injected_history)
        history = self.llm_prompt_manager.current_history[start:]
        ai_msg = summary_history(history)
        row = InsertRow(id=1, text=ai_msg.content, subject="history")
        insert = MilvusInsert(collection_name="history_collection", texts=[row])
        try:
            insert_res = self.vec_db.insert(insert)
            if insert_res.insert_count == 1:
                logger.info(f"Add a history memory: {row.text}")
            else:
                logger.warning(f"Failed to add a history memory.")
        except Exception as e:
            logger.warning("Milvus pipeline failed!")

    def play_tts(self, event: PipelineOutputTTSEvent):
        prediction = event.prediction
        text = event.transcript
        self.subtitles_queue.put(text)
        audio_path = save_audio(wave_data=prediction.wave_data, format=AudioFileType(prediction.audio_type),
                                prefix='tts')
        if self.live2d_viewer:
            self.live2d_viewer.sync_lip(audio_path)
        if self.playground:
            if self.playground.is_connected:
                self.playground.play_speech(bot_id=self.bot_id, audio_path=audio_path,
                                            transcript=text, bot_name=self.bot_name)
                logger.debug("Remote speaker enqueue speech data")
        else:
            # `playsound(audio_path, block=True)` will block the thread, use `enqueue_sound(audio_path)` instead
            self.speaker.enqueue_sound(audio_path)
            logger.debug("Local speaker enqueue speech data")
