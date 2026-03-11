# Volcengine (Doubao) Provider Support

MemStack provides comprehensive support for Volcengine (火山引擎/豆包 Doubao) services, including LLM, Vision, Audio, and Real-time Voice Chat.

## LLM Configuration

Volcengine models are accessed via **Deployment Endpoint IDs** (`ep-xxx`).

### Environment Variables
- `VOLC_AK`: Access Key
- `VOLC_SK`: Secret Key
- `VOLC_APP_ID`: Application ID for Voice services

### Supported Models
| Model Category | Registry ID | Context Window |
|----------------|-------------|----------------|
| **Chat** | `doubao-1.5-pro` | 128k/256k |
| | `doubao-1.5-lite` | 128k/256k |
| **Vision** | `doubao-vision` | 128k |
| **Embedding** | `doubao-embedding-large` | 2560 dim |
| **Reranker** | `doubao-reranker-large` | - |

## Audio Services

MemStack implements specialized adapters for Volcengine Audio APIs which deviate from OpenAI standards.

### ASR (Speech-to-Text)
- **Adapter**: `VolcengineASRAdapter`
- **Pattern**: Submit/Query asynchronous task pattern.
- **Config**: `VOLC_ASR_CLUSTER` (default: `volcano_asr`)

### TTS (Text-to-Speech)
- **Adapter**: `VolcengineTTSAdapter`
- **Pattern**: Doubao Speech Synthesis 2.0 (HTTP Chunked/SSE).
- **Config**: `VOLC_TTS_RESOURCE_ID` (default: `volc.speech.dialog`)

## Real-time Voice Chat (RTC)

For low-latency multimodal voice interactions, MemStack uses the Volcengine RTC-based protocol (`rtc-aigc`).

- **Protocol**: Custom RTC signaling (not standard WebSocket).
- **Adapter**: `VolcengineRTCChatAdapter`
- **Capabilities**: Integrated ASR + LLM + TTS with sub-second latency.

## Usage in DI Container

```python
# Accessing via DIContainer
asr_service = container.asr_service()
tts_service = container.tts_service()
rtc_adapter = container.rtc_chat_adapter()
```
