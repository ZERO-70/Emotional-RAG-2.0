"""OpenRouter API client with async support - OpenAI-compatible interface."""

import logging
import asyncio
import json
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
        top_p: float = 1.0,
        web_search: Optional[bool] = None
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
            web_search: Override the web-search plugin for this call. None = use
                the global setting; False = force off (e.g. memory summarisation
                must never pull live web facts into a character's memory).

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
                    "stream": False,
                    # Ask OpenRouter to return token accounting (incl. cached tokens
                    # and cache_discount) so prompt-cache hits are observable in logs.
                    "usage": {"include": True}
                }
                # Let the model research live info via OpenRouter's web plugin.
                use_web = settings.openrouter_web_search if web_search is None else web_search
                if use_web:
                    payload["plugins"] = [{"id": "web"}]

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
                assistant_message = data["choices"][0]["message"]["content"]
                finish_reason = data["choices"][0].get("finish_reason", "unknown")
                
                # Get usage info
                usage = data.get('usage', {})
                input_tokens = usage.get('prompt_tokens', 0)
                output_tokens = usage.get('completion_tokens', 0)
                total_tokens = usage.get('total_tokens', input_tokens + output_tokens)

                # Prompt-cache accounting (Anthropic via OpenRouter).
                # cached_tokens = portion of the prompt served from cache (read).
                prompt_details = usage.get('prompt_tokens_details') or {}
                cached_tokens = prompt_details.get('cached_tokens', 0)
                cache_discount = usage.get('cache_discount')

                # Track usage
                self.total_input_tokens += input_tokens
                self.total_output_tokens += output_tokens

                logger.info(
                    f"OpenRouter response received",
                    extra={
                        "latency_seconds": round(latency, 2),
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "cached_tokens": cached_tokens,
                        "cache_discount": cache_discount,
                        "model": selected_model,
                        "finish_reason": finish_reason
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

    async def _agentic_raw_call(
        self,
        messages: List[Dict],
        tools: Optional[List[Dict]],
        model: Optional[str],
        temperature: float,
        max_tokens: int,
        top_p: float,
    ) -> Dict:
        """One OpenRouter call returning the raw assistant message dict (which
        may include tool_calls) plus usage. Used by the agentic tool loop."""
        async with self.rate_limiter:
            url = f"{self.base_url}/chat/completions"
            selected_model = model or self.default_model
            payload = {
                "model": selected_model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": min(max_tokens, settings.max_response_tokens),
                "top_p": top_p,
                "stream": False,
                "usage": {"include": True},
            }
            # Let the model research live info via OpenRouter's web plugin. This
            # is the path production uses when Notion tools are enabled, so the
            # web-search flag must be honored here too (not just chat_completion).
            if settings.openrouter_web_search:
                payload["plugins"] = [{"id": "web"}]
            if tools:
                payload["tools"] = tools
                payload["tool_choice"] = "auto"
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            choice = data["choices"][0]
            usage = data.get("usage", {}) or {}
            self.total_input_tokens += usage.get("prompt_tokens", 0)
            self.total_output_tokens += usage.get("completion_tokens", 0)
            # Observe prompt-cache effectiveness in the tool path (tools sit in the
            # cached prefix behind the card breakpoint).
            cached = (usage.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
            logger.info(
                "Agentic LLM call",
                extra={
                    "with_tools": bool(tools),
                    "input_tokens": usage.get("prompt_tokens", 0),
                    "cached_tokens": cached,
                    "output_tokens": usage.get("completion_tokens", 0),
                    "finish_reason": choice.get("finish_reason", "stop"),
                },
            )
            return {
                "message": choice.get("message", {}) or {},
                "finish_reason": choice.get("finish_reason", "stop"),
                "usage": usage,
            }

    def _final_response(self, model, content: str, usage: dict) -> ChatCompletionResponse:
        return ChatCompletionResponse(
            id=f"chatcmpl-{uuid.uuid4().hex[:8]}",
            created=int(time.time()),
            model=model or self.default_model,
            choices=[ChatCompletionChoice(
                index=0,
                message=Message(role="assistant", content=content),
                finish_reason="stop",
            )],
            usage=UsageInfo(
                prompt_tokens=usage.get("prompt_tokens", 0),
                completion_tokens=usage.get("completion_tokens", 0),
                total_tokens=usage.get("total_tokens", 0),
            ),
        )

    async def chat_completion_agentic(
        self,
        messages: List[Dict],
        tools: List[Dict],
        tool_executor,
        model: Optional[str] = None,
        temperature: float = 0.9,
        max_tokens: int = 800,
        top_p: float = 1.0,
        max_iters: int = 5,
        expand_tools: Optional[Dict[str, List[Dict]]] = None,
    ) -> ChatCompletionResponse:
        """Tool-calling loop: let the model call `tools` (run via the async
        `tool_executor(name, args) -> str`) until it returns a final answer.
        Returns a normal ChatCompletionResponse so SillyTavern is unchanged.
        If the loop hits max_iters, force one final tool-free answer.

        `expand_tools` maps a lightweight "gateway" tool name -> the fuller tool
        list to switch to once the model calls it. This lets us offer a tiny
        unlock tool by default and only pay for heavy tool schemas on the rare
        turns the model actually asks for them (lazy/layered loading)."""
        convo = list(messages)
        active_tools = tools
        last_usage: dict = {}
        for round_idx in range(max_iters):
            raw = await self._agentic_raw_call(
                convo, tools=active_tools, model=model,
                temperature=temperature, max_tokens=max_tokens, top_p=top_p,
            )
            msg = raw["message"]
            last_usage = raw["usage"] or last_usage
            tool_calls = msg.get("tool_calls") or []
            if not tool_calls:
                return self._final_response(model, msg.get("content") or "", last_usage)
            # Assistant turn requesting tools, then the tool results.
            convo.append({
                "role": "assistant",
                "content": msg.get("content") or "",
                "tool_calls": tool_calls,
            })
            for tc in tool_calls:
                fn = tc.get("function") or {}
                name = fn.get("name", "")
                try:
                    args = json.loads(fn.get("arguments") or "{}")
                except (json.JSONDecodeError, TypeError):
                    args = {}
                try:
                    result = await tool_executor(name, args)
                except Exception as e:
                    result = f"Tool '{name}' raised: {e}"
                convo.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": str(result)[:8000],
                })
                # Lazy expansion: once the model calls the gateway tool, swap in
                # the fuller tool set so subsequent rounds can actually use it.
                if expand_tools and name in expand_tools:
                    active_tools = expand_tools[name]
            logger.info("Notion tool round executed",
                        extra={"round": round_idx + 1, "calls": len(tool_calls)})
        # Exhausted iterations — force a final, tool-free answer. Nudge explicitly
        # so the model stops emitting tool calls and actually replies in character:
        # without this, a conversation that ends on tool results can come back as an
        # empty turn (the model tries to call yet another tool that isn't offered).
        convo.append({
            "role": "user",
            "content": "[Stop searching now and reply to me directly, in character, "
                       "using whatever you've already found.]",
        })
        raw = await self._agentic_raw_call(
            convo, tools=None, model=model,
            temperature=temperature, max_tokens=max_tokens, top_p=top_p,
        )
        return self._final_response(model, raw["message"].get("content") or "", raw["usage"] or last_usage)

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
                # Let the model research live info via OpenRouter's web plugin.
                if settings.openrouter_web_search:
                    payload["plugins"] = [{"id": "web"}]
                
                logger.debug("Starting OpenRouter streaming response")
                
                async with self.client.stream("POST", url, json=payload) as response:
                    # Read response body first so it's available if raise_for_status() throws
                    if response.status_code != 200:
                        await response.aread()
                        if response.status_code == 429:
                            logger.warning("OpenRouter streaming rate limit exceeded (429)")
                            yield 'data: {"error": "Rate limit exceeded. Please wait a moment and try again.", "code": 429}\n\n'
                            return
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
                # response body is already read above, safe to access .text
                status = e.response.status_code
                try:
                    body = e.response.text
                except Exception:
                    body = "(unreadable)"
                logger.error(f"Streaming HTTP error: {status} - {body}")
                yield f'data: {{"error": "HTTP {status} from OpenRouter"}}\n\n'
            except Exception as e:
                logger.error(f"Streaming error: {e}")
                yield f'data: {{"error": "{str(e)}"}}\n\n'
    
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
