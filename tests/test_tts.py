from banong_radio.tts import DEFAULT_VOICE


def test_default_voice_is_chinese() -> None:
    assert DEFAULT_VOICE == "zh-CN-YunJianNeural"
