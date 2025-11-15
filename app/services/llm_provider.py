"""LLM Provider abstraction - unified interface for Gemini and Mancer."""

import logging
from typing import List, Dict, AsyncGenerator, Optional, Union
from abc import ABC, abstractmethod

from app.models.chat import ChatCompletionResponse, ModelInfo

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def check_connection(self) -> bool:
        """Test API connection."""
        pass
    
    @abstractmethod
    async def list_models(self) -> List[ModelInfo]:
        """List available models."""
        pass
    
    @abstractmethod
    async def chat_completion(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> ChatCompletionResponse:
        """Generate chat completion."""
        pass
    
    @abstractmethod
    async def chat_completion_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> AsyncGenerator[str, None]:
        """Stream chat completion."""
        pass
    
    @abstractmethod
    def get_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics."""
        pass


class UnifiedLLMClient:
    """
    Unified LLM client that delegates to the appropriate provider.
    
    This class provides a single interface for the rest of the application,
    abstracting away whether we're using Gemini or Mancer.
    """
    
    def __init__(self, provider: LLMProvider, provider_name: str):
        """
        Initialize unified client.
        
        Args:
            provider: The actual provider instance (GeminiClient or MancerClient)
            provider_name: Name of the provider for logging
        """
        self.provider = provider
        self.provider_name = provider_name
        logger.info(f"Unified LLM client initialized with provider: {provider_name}")
    
    async def check_connection(self) -> bool:
        """Test connection to the current provider."""
        try:
            return await self.provider.check_connection()
        except Exception as e:
            logger.error(f"Connection check failed for {self.provider_name}: {e}")
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """
        List available models from the current provider.
        
        Returns:
            List of ModelInfo objects
        """
        try:
            return await self.provider.list_models()
        except Exception as e:
            logger.error(f"Failed to list models from {self.provider_name}: {e}")
            return []
    
    async def chat_completion(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        stream: bool = False,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> ChatCompletionResponse:
        """
        Generate chat completion using the current provider.
        
        Args:
            messages: List of message dicts
            model: Model to use (provider-specific)
            stream: Whether to stream (ignored in non-streaming mode)
            temperature: Sampling temperature
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            
        Returns:
            ChatCompletionResponse
        """
        try:
            # For Mancer, we pass the model parameter
            # For Gemini, the model is configured in settings
            if self.provider_name == "mancer":
                return await self.provider.chat_completion(
                    messages=messages,
                    model=model,
                    stream=stream,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                )
            else:
                # Gemini doesn't support model parameter in chat_completion
                return await self.provider.chat_completion(
                    messages=messages,
                    stream=stream,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                )
        except Exception as e:
            logger.error(f"Chat completion failed with {self.provider_name}: {e}")
            raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict],
        model: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion using the current provider.
        
        Args:
            messages: List of message dicts
            model: Model to use (provider-specific)
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            top_p: Nucleus sampling
            
        Yields:
            SSE-formatted chunks
        """
        try:
            if self.provider_name == "mancer":
                async for chunk in self.provider.chat_completion_stream(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                ):
                    yield chunk
            else:
                # Gemini doesn't support model parameter
                async for chunk in self.provider.chat_completion_stream(
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    top_p=top_p
                ):
                    yield chunk
        except Exception as e:
            logger.error(f"Streaming failed with {self.provider_name}: {e}")
            error_chunk = f'data: {{"error": "{str(e)}"}}\n\n'
            yield error_chunk
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get usage statistics from the current provider."""
        return self.provider.get_usage_stats()
    
    async def close(self):
        """Close the provider client if it has a close method."""
        if hasattr(self.provider, 'close'):
            await self.provider.close()
