"""Google Gemini API client with async support and retry logic."""

import logging
import asyncio
import time
import uuid
from typing import List, Dict, AsyncGenerator, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)
from google import genai
from google.genai import types
from google.api_core import exceptions as google_exceptions

from app.core.config import settings
from app.models.chat import (
    ChatCompletionResponse,
    ChatCompletionChoice,
    ChatCompletionChunk,
    Message,
    UsageInfo,
    ModelInfo
)

logger = logging.getLogger(__name__)


class GeminiClient:
    """Async Gemini API client with OpenAI-compatible interface using new google-genai SDK."""
    
    def __init__(self):
        """Initialize Gemini client with API key and rate limiting."""
        try:
            # Initialize the new genai client
            self.client = genai.Client(api_key=settings.gemini_api_key)
            self.model_name = settings.gemini_model
            
            # Rate limiting: max 5 concurrent requests
            self.rate_limiter = asyncio.Semaphore(5)
            
            # Usage tracking
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            
            logger.info(f"Gemini client initialized (model: {self.model_name})")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini client: {e}")
            raise
    
    async def check_connection(self) -> bool:
        """
        Test Gemini API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Simple test request using the new SDK
            response = await asyncio.to_thread(
                self.client.models.generate_content,
                model=self.model_name,
                contents="Hi"
            )
            
            # With the new SDK, accessing .text is straightforward
            if response.text:
                logger.info("Gemini connection check successful")
                return True
            
            logger.warning("Gemini response has no text content")
            return False
        except Exception as e:
            logger.error(f"Gemini connection check failed: {e}", exc_info=True)
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """
        List available Gemini models.
        
        For Gemini, we return the configured model.
        In the future, this could query the Gemini API for available models.
        
        Returns:
            List of ModelInfo objects
        """
        return [
            ModelInfo(
                id=self.model_name,
                created=int(time.time()),
                owned_by="google"
            )
        ]
    
    @retry(
        retry=retry_if_exception_type((
            google_exceptions.ResourceExhausted,
            google_exceptions.ServiceUnavailable,
            google_exceptions.DeadlineExceeded
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
    async def chat_completion(
        self,
        messages: List[Dict],
        stream: bool = False,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> ChatCompletionResponse:
        """
        OpenAI-compatible chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            stream: Whether to stream response (not used in non-streaming mode)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            
        Returns:
            ChatCompletionResponse object
        """
        async with self.rate_limiter:
            try:
                # Convert messages to Gemini format
                contents = self._convert_messages_to_contents(messages)
                
                # Configure generation
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=min(max_tokens, settings.max_response_tokens),
                    top_p=top_p,
                )
                
                logger.debug(
                    f"Calling Gemini API",
                    extra={
                        "model": self.model_name,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                    }
                )
                
                start_time = time.time()
                
                # Call Gemini API using new SDK (sync call wrapped in thread)
                response = await asyncio.to_thread(
                    self.client.models.generate_content,
                    model=self.model_name,
                    contents=contents,
                    config=config
                )
                
                latency = time.time() - start_time
                
                # Extract response text
                response_text = response.text if response.text else ""
                
                # Get usage metadata if available
                input_tokens = 0
                output_tokens = 0
                if hasattr(response, 'usage_metadata'):
                    usage = response.usage_metadata
                    input_tokens = getattr(usage, 'prompt_token_count', 0)
                    output_tokens = getattr(usage, 'candidates_token_count', 0)
                
                # Fallback to estimation if no usage data
                if input_tokens == 0:
                    input_tokens = self._estimate_tokens(contents)
                if output_tokens == 0:
                    output_tokens = self._estimate_tokens(response_text)
                
                # Track usage
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                
                logger.info(
                    f"Gemini response received",
                    extra={
                        "latency_seconds": round(latency, 2),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "response_length": len(response_text)
                    }
                )
                
                # Format as OpenAI-compatible response
                return self._format_response(
                    response_text,
                    input_tokens,
                    output_tokens
                )
                
            except google_exceptions.InvalidArgument as e:
                logger.error(f"Invalid Gemini API argument: {e}")
                raise ValueError(f"Invalid request: {e}")
            except google_exceptions.ResourceExhausted as e:
                logger.warning(f"Gemini rate limit exceeded: {e}")
                raise
            except Exception as e:
                logger.error(f"Gemini API error: {e}")
                raise
    
    async def chat_completion_stream(
        self,
        messages: List[Dict],
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat completion in SSE format.
        
        Args:
            messages: List of message dicts
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            top_p: Nucleus sampling
            
        Yields:
            SSE-formatted chunks
        """
        async with self.rate_limiter:
            try:
                contents = self._convert_messages_to_contents(messages)
                
                config = types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=min(max_tokens, settings.max_response_tokens),
                    top_p=top_p,
                )
                
                logger.debug("Starting Gemini streaming response")
                
                response_id = f"chatcmpl-{uuid.uuid4().hex[:8]}"
                created_timestamp = int(time.time())
                
                # Stream response using new SDK
                # Note: The new SDK's streaming might be sync, so we wrap it
                stream = await asyncio.to_thread(
                    self.client.models.generate_content_stream,
                    model=self.model_name,
                    contents=contents,
                    config=config
                )
                
                # Iterate through stream chunks
                for chunk in stream:
                    if chunk.text:
                        # Format as SSE
                        sse_chunk = self._format_sse_chunk(
                            chunk.text,
                            response_id,
                            created_timestamp
                        )
                        yield sse_chunk
                
                # Send final [DONE] message
                yield "data: [DONE]\n\n"
                
                logger.debug("Streaming response completed")
                
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                # Send error in SSE format
                error_chunk = f'data: {{"error": "{str(e)}"}}\n\n'
                yield error_chunk
    
    def _convert_messages_to_contents(self, messages: List[Dict]) -> str:
        """
        Convert OpenAI message format to Gemini contents.
        
        For now, we'll use simple string concatenation.
        The new SDK also supports more structured content.
        
        Args:
            messages: List of message dicts
            
        Returns:
            Formatted content string
        """
        prompt_parts = []
        
        for msg in messages:
            role = msg.get('role', 'user')
            content = msg.get('content', '')
            
            if role == 'system':
                # System messages become instructions
                prompt_parts.append(f"INSTRUCTIONS:\n{content}\n")
            elif role == 'user':
                prompt_parts.append(f"USER: {content}\n")
            elif role == 'assistant':
                prompt_parts.append(f"ASSISTANT: {content}\n")
        
        # Add final assistant prompt
        prompt_parts.append("ASSISTANT:")
        
        return "\n".join(prompt_parts)
    
    def _format_response(
        self,
        response_text: str,
        input_tokens: int,
        output_tokens: int
    ) -> ChatCompletionResponse:
        """Format Gemini response as OpenAI ChatCompletionResponse."""
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=self.model_name,
            choices=[
                ChatCompletionChoice(
                    index=0,
                    message=Message(
                        role="assistant",
                        content=response_text
                    ),
                    finish_reason="stop"
                )
            ],
            usage=UsageInfo(
                prompt_tokens=input_tokens,
                completion_tokens=output_tokens,
                total_tokens=input_tokens + output_tokens
            )
        )
    
    def _format_sse_chunk(
        self,
        text: str,
        response_id: str,
        created_timestamp: int
    ) -> str:
        """Format text chunk as Server-Sent Event."""
        chunk = ChatCompletionChunk(
            id=response_id,
            created=created_timestamp,
            model=self.model_name,
            choices=[
                {
                    "index": 0,
                    "delta": {"content": text},
                    "finish_reason": None
                }
            ]
        )
        return f"data: {chunk.model_dump_json()}\n\n"
    
    def _estimate_tokens(self, text: str) -> int:
        """
        Estimate token count (rough approximation).
        
        Args:
            text: Input text
            
        Returns:
            Estimated token count
        """
        # Rough approximation: 1 token ≈ 4 characters for English text
        return max(1, len(str(text)) // 4)
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get total API usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens
        }
