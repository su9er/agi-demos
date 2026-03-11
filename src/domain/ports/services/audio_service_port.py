from abc import ABC, abstractmethod
from typing import BinaryIO, AsyncGenerator, Optional, Dict, Any

class ASRServicePort(ABC):
    """Port for Automatic Speech Recognition (Audio to Text) service."""
    
    @abstractmethod
    async def transcribe(
        self, 
        audio_file: BinaryIO, 
        language: str = "zh-CN",
        options: Optional[Dict[str, Any]] = None
    ) -> str:
        """Transcribe audio file to text."""
        pass

    @abstractmethod
    async def transcribe_stream(
        self,
        audio_stream: AsyncGenerator[bytes, None],
        language: str = "zh-CN",
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[str, None]:
        """Transcribe audio stream to text."""
        pass

class TTSServicePort(ABC):
    """Port for Text-to-Speech (Text to Audio) service."""
    
    @abstractmethod
    async def synthesize(
        self,
        text: str,
        voice_type: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> bytes:
        """Synthesize text to audio bytes."""
        pass

    @abstractmethod
    async def synthesize_stream(
        self,
        text: str,
        voice_type: Optional[str] = None,
        options: Optional[Dict[str, Any]] = None
    ) -> AsyncGenerator[bytes, None]:
        """Synthesize text to audio stream."""
        pass
