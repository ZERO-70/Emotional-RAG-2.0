"""OpenRouter API client with async support - OpenAI-compatible interface."""

import logging
import asyncio
import time
import uuid
import httpx
from typing import List, Dict, AsyncGenerator, Optional
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type
)

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


class OpenRouterClient:
    """Async OpenRouter API client with OpenAI-compatible interface."""
    
    def __init__(self):
        """Initialize OpenRouter client with API key and rate limiting."""
        try:
            self.api_key = settings.openrouter_api_key
            self.base_url = settings.openrouter_base_url
            self.default_model = settings.openrouter_default_model
            
            # HTTP client configuration
            self.timeout = httpx.Timeout(60.0, connect=10.0)
            
            # Build headers with optional site tracking
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            # Add optional headers for OpenRouter rankings
            if settings.openrouter_site_url:
                headers["HTTP-Referer"] = settings.openrouter_site_url
            if settings.openrouter_site_name:
                headers["X-Title"] = settings.openrouter_site_name
            
            self.client = httpx.AsyncClient(
                timeout=self.timeout,
                headers=headers
            )
            
            # Rate limiting: max 5 concurrent requests
            self.rate_limiter = asyncio.Semaphore(5)
            
            # Usage tracking
            self.total_input_tokens = 0
            self.total_output_tokens = 0
            
            logger.info(f"OpenRouter client initialized (base_url: {self.base_url})")
        except Exception as e:
            logger.error(f"Failed to initialize OpenRouter client: {e}")
            raise
    
    async def check_connection(self) -> bool:
        """
        Test OpenRouter API connection.
        
        Returns:
            True if connection successful, False otherwise
        """
        try:
            # Try to list models as a connection test
            models = await self.list_models()
            if models:
                logger.info(f"OpenRouter connection check successful ({len(models)} models available)")
                return True
            
            logger.warning("OpenRouter connection check: no models returned")
            return False
        except Exception as e:
            logger.error(f"OpenRouter connection check failed: {e}", exc_info=True)
            return False
    
    async def list_models(self) -> List[ModelInfo]:
        """
        Fetch available models from OpenRouter API.
        
        Returns:
            List of ModelInfo objects
        """
        try:
            url = f"{self.base_url}/models"
            
            response = await self.client.get(url)
            response.raise_for_status()
            
            data = response.json()
            
            models = []
            for model_data in data.get('data', []):
                models.append(ModelInfo(
                    id=model_data['id'],
                    created=model_data.get('created', int(time.time())),
                    owned_by=model_data.get('owned_by', 'openrouter')
                ))
            
            logger.info(f"Retrieved {len(models)} models from OpenRouter")
            return models
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP error fetching models: {e.response.status_code} - {e.response.text}")
            # Return empty list on error
            return []
        except Exception as e:
            logger.error(f"Error fetching models from OpenRouter: {e}")
            return []
    
    @retry(
        retry=retry_if_exception_type((
            httpx.HTTPStatusError,
            httpx.RequestError,
            httpx.TimeoutException
        )),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        reraise=True
    )
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
        OpenAI-compatible chat completion.
        
        Args:
            messages: List of message dicts with 'role' and 'content'
            model: Model to use (if None, uses default)
            stream: Whether to stream response (not used in non-streaming mode)
            temperature: Sampling temperature (0.0 - 2.0)
            max_tokens: Maximum tokens in response
            top_p: Nucleus sampling parameter
            
        Returns:
            ChatCompletionResponse object
        """
        async with self.rate_limiter:
            try:
                url = f"{self.base_url}/chat/completions"
                
                # Use provided model or default
                selected_model = model or self.default_model
                
                payload = {
                    "model": selected_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": min(max_tokens, settings.max_response_tokens),
                    "top_p": top_p,
                    "stream": False
                }
                
                logger.debug(
                    f"Calling OpenRouter API",
                    extra={
                        "model": selected_model,
                        "temperature": temperature,
                        "max_tokens": max_tokens,
                        "message_count": len(messages)
                    }
                )
                
                start_time = time.time()
                
                response = await self.client.post(url, json=payload)
                response.raise_for_status()
                
                latency = time.time() - start_time
                
                data = response.json()
                
                # Extract response content
                assistant_message = data['choices'][0]['message']['content']
                
                # Get usage info
                usage = data.get('usage', {})
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', input_tokens + output_tokens)
                
                # Track usage
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens
                
                logger.info(
                    f"OpenRouter response received",
                    extra={
                        "latency_seconds": round(latency, 2),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "model": selected_model
                    }
                )
                
                # Format as OpenAI-compatible response
                return ChatCompletionResponse(
                    id=data.get('id', f"chatcmpl-{uuid.uuid4().hex[:8]}"),
                    created=data.get('created', int(time.time())),
                    model=selected_model,
                    choices=[
                        ChatCompletionChoice(
                            index=0,
                            message=Message(
                                role="assistant",
                                content=assistant_message
                            ),
                            finish_reason=data['choices'][0].get('finish_reason', 'stop')
                        )
                    ],
                    usage=UsageInfo(
                        prompt_tokens=input_tokens,
                        completion_tokens=output_tokens,
                        total_tokens=total_tokens
                    )
                )
                
            except httpx.HTTPStatusError as e:
                logger.error(f"OpenRouter API HTTP error: {e.response.status_code} - {e.response.text}")
                
                # Handle specific status codes
                if e.response.status_code == 429:
                    logger.warning("OpenRouter rate limit exceeded")
                    raise
                elif e.response.status_code == 401:
                    raise ValueError("Invalid OpenRouter API key")
                elif e.response.status_code == 400:
                    raise ValueError(f"Invalid request: {e.response.text}")
                else:
                    raise
                    
            except httpx.TimeoutException as e:
                logger.error(f"OpenRouter API timeout: {e}")
                raise
            except Exception as e:
                logger.error(f"OpenRouter API error: {e}")
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
        Stream chat completion in SSE format.
        
        Args:
            messages: List of message dicts
            model: Model to use (if None, uses default)
            temperature: Sampling temperature
            max_tokens: Maximum tokens
            top_p: Nucleus sampling
            
        Yields:
            SSE-formatted chunks
        """
        async with self.rate_limiter:
            try:
                url = f"{self.base_url}/chat/completions"
                
                # Use provided model or default
                selected_model = model or self.default_model
                
                payload = {
                    "model": selected_model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": min(max_tokens, settings.max_response_tokens),
                    "top_p": top_p,
                    "stream": True
                }
                
                logger.debug("Starting OpenRouter streaming response")
                
                async with self.client.stream("POST", url, json=payload) as response:
                    response.raise_for_status()
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            # Forward SSE chunk directly
                            yield f"{line}\n\n"
                            
                            # Check for [DONE] message
                            if line.strip() == "data: [DONE]":
                                break
                
                logger.debug("Streaming response completed")
                
            except httpx.HTTPStatusError as e:
                logger.error(f"Streaming HTTP error: {e.response.status_code}")
                error_chunk = f'data: {{"error": "HTTP {e.response.status_code}: {e.response.text}"}}\n\n'
                yield error_chunk
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                error_chunk = f'data: {{"error": "{str(e)}"}}\n\n'
                yield error_chunk
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
        logger.info("OpenRouter client closed")
    
    def get_usage_stats(self) -> Dict[str, int]:
        """Get total API usage statistics."""
        return {
            "total_input_tokens": self.total_input_tokens,
            "total_output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens
        }
