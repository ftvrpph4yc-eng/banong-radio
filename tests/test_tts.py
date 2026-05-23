from banong_radio.tts import DEFAULT_VOICE, synthesize


def test_default_voice_is_chinese() -> None:
    assert DEFAULT_VOICE == "zh-CN-YunJianNeural"


def test_synthesize_does_not_treat_empty_file_as_cache(monkeypatch, tmp_path) -> None:
    output = tmp_path / "voice.mp3"
    output.write_bytes(b"")
    monkeypatch.setattr("banong_radio.tts.shutil.which", lambda name: None)

    generated, source = synthesize("早上好。", output)

    assert generated is None
    assert source == "unavailable"
    assert not output.exists()
