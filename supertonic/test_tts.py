from supertonic import TTS

tts = TTS(auto_download=True)

style = tts.get_voice_style(voice_name="M1")

wav, duration = tts.synthesize(
    text="오 ~빠,  형님, 누나, 삼촌 슈퍼토닉 쓰리 로컬 티티에스 설치 테스트입니다. 정말 잘되는지 성능이 어떠지 확인해보시죠",
    lang="ko",
    voice_style=style,
    total_steps=8,
    speed=1.05,
)

tts.save_audio(wav, "output.wav")

print("생성 완료")
print("파일명: output.wav")