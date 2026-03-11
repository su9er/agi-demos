# Final Multimodal Agent Pipeline Blueprint (Volcengine)

This document outlines the architecture for a manual, multimodal agent that integrates RTC, ASR, LLM, and TTS.

## 1. Core Architecture (The Loop)

### High-Level Data Flow:
```text
[RTC Participant (User)] 
      |
      | (PCM 48k/Mono via RTC SDK)
      v
[RTC Sidecar (C++)] --(Unix Socket)--> [Python Agent (Controller)]
                                             |
                                             |-- (PCM 16k/Mono) --> [ASR V3 WebSocket]
                                             |                          |
                                             | <--- (Text Segments) ----|
                                             |
                                             |-- (Maas/LLM Request) --> [DeepSeek/Skylark LLM]
                                             |                          |
                                             | <--- (Streamed Text) ----|
                                             |
                                             |-- (Text Chunks) -------> [TTS V3 WebSocket]
                                             |                          |
                                             | <--- (PCM Chunks) -------|
                                             |
[RTC Participant (Agent)] <--(PCM/RTC)-- [RTC Sidecar] <--(Unix Socket)--|
```

## 2. Component Design

### A. The Controller (Python)
- **Role**: Orchestrates the sub-tasks.
- **ASR Segmenting**: Accumulates ASR text. Once a silence/endpoint is detected (via ASR V3 `is_final`), it triggers the LLM.
- **Interrupt Handling**: If new user audio is detected (VAD/ASR) while the agent is speaking, the Controller must signal the TTS WebSocket to "Stop" and clear the RTC publication buffer.

### B. The Speech Engine (V3 Protocol)
- Uses **WebSocket-based bidirectional streams** for both ASR and TTS.
- **Latency Optimization**: Start sending TTS text to the engine as soon as the first sentence from the LLM is available.

### C. The RTC Bridge (C++ Sidecar)
- Handles the native Volcengine Linux SDK.
- **Subscription**: Subscribes to the specific User's audio stream.
- **Publication**: Publishes the Agent's audio as an external audio source.

## 3. Deployment Topology
- **Container**: Use a single Docker container with:
    - `rtc_sidecar`: Compiled binary for RTC.
    - `agent_main.py`: Python process for speech logic.
- **Infrastructure**: Shared volumes or Unix sockets for zero-copy audio transfer between processes.

## 4. Key Performance Indicators (Target)
- **Turn-around Latency (E2E)**: < 1.5 seconds from user silence to agent speech start.
- **Audio Quality**: 24kHz (TTS) / 16kHz (ASR) minimum.

