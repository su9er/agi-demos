import os
import json
import asyncio
import httpx
from src.configuration.config import get_settings
from src.infrastructure.adapters.secondary.external.volcengine.audio_adapters import VolcengineASRAdapter, VolcengineTTSAdapter
from src.infrastructure.adapters.secondary.external.volcengine.rtc_chat_adapter import VolcengineRTCChatAdapter

async def test_llm_connection():
    settings = get_settings()
    if not settings.volc_ak:
        print("Skipping LLM test: VOLC_AK not set")
        return

    # Use a dummy ep-xxx for testing structure
    endpoint_id = os.getenv("VOLC_CHAT_ENDPOINT_ID", "ep-20240101000000-xxxxx")
    url = "https://ark.cn-beijing.volces.com/api/v3/chat/completions"
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {settings.volc_ak}" # Ark often uses AK as API Key for simple calls
    }
    
    payload = {
        "model": endpoint_id,
        "messages": [{"role": "user", "content": "Hello"}],
        "max_tokens": 10
    }
    
    print(f"Testing LLM connection to endpoint {endpoint_id}...")
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload, headers=headers, timeout=10)
            print(f"LLM Status: {response.status_code}")
            print(f"LLM Response: {response.text[:200]}...")
    except Exception as e:
        print(f"LLM Error: {e}")

async def test_audio_adapters():
    settings = get_settings()
    if not settings.volc_ak:
        print("Skipping Audio test: VOLC_AK not set")
        return

    asr = VolcengineASRAdapter(settings.volc_ak, settings.volc_sk, settings.volc_app_id)
    tts = VolcengineTTSAdapter(settings.volc_ak, settings.volc_sk, settings.volc_app_id)
    
    print("Testing TTS synthesis (mocked implementation check)...")
    audio = await tts.synthesize("你好，我是豆包。")
    print(f"TTS result length: {len(audio)} bytes")
    
    print("Testing ASR transcription (mocked implementation check)...")
    text = await asr.transcribe(None)
    print(f"ASR result: {text}")

async def test_rtc_adapter():
    settings = get_settings()
    if not settings.volc_ak:
        print("Skipping RTC test: VOLC_AK not set")
        return

    rtc = VolcengineRTCChatAdapter(settings.volc_ak, settings.volc_sk, settings.volc_app_id)
    print("RTC Adapter initialized successfully.")
    # We won't actually call start_session as it needs real app_id/room_id and is stateful

async def main():
    await test_llm_connection()
    await test_audio_adapters()
    await test_rtc_adapter()

if __name__ == "__main__":
    asyncio.run(main())
