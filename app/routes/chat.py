"""Chat completion endpoints - OpenAI-compatible API."""

import logging
import asyncio
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from typing import Optional

from app.models.chat import (
    ChatCompletionRequest,
    ChatCompletionResponse,
    ModelListResponse,
    ModelInfo
)
from app.core.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/v1/chat/completions", response_model=ChatCompletionResponse)
async def chat_completions(request: ChatCompletionRequest):
    """
    OpenAI-compatible chat completion endpoint.
    
    Flow:
    1. Extract chat_id from request.user (SillyTavern sends this)
    2. Detect emotion from user message
    3. Retrieve semantic context via RAG
    4. Build context with token budget
    5. Call Gemini API
    6. Store messages with metadata
    7. Trigger summarization if needed
    
    Args:
        request: ChatCompletionRequest with messages
        
    Returns:
        ChatCompletionResponse or StreamingResponse
    """
    from app.main import (
        llm_client,
        gemini_client,
        memory_manager,
        emotion_tracker,
        token_manager,
        rag_engine
    )
    
    try:
        # Extract chat ID (SillyTavern sends in 'user' field)
        chat_id = request.user or "default"
        
        logger.info(
            f"Chat completion request",
            extra={
                "chat_id": chat_id,
                "message_count": len(request.messages),
                "stream": request.stream,
                "temperature": request.temperature,
                "user_field": request.user  # Log the actual user field
            }
        )
        
        # DEBUG: Log all message roles to understand conversation structure
        message_roles = [f"{msg.role}:{len(msg.content)}" for msg in request.messages]
        logger.debug(f"Message structure: {message_roles}")
        
        # Debug: Log the actual messages for troubleshooting
        if len(request.messages) == 0:
            logger.warning("Empty messages array received from SillyTavern")
            logger.debug(f"Full request: model={request.model}, user={request.user}, stream={request.stream}")
        
        # Extract user message (last message should be from user)
        user_message = None
        for msg in reversed(request.messages):
            if msg.role == "user":
                user_message = msg.content
                break
        
        if not user_message:
            logger.error(f"No user message found in {len(request.messages)} messages")
            
            # If this is a streaming request with no messages, SillyTavern might be testing
            # Return a simple response instead of erroring
            if request.stream and len(request.messages) == 0:
                logger.warning("Empty streaming request detected - SillyTavern might be testing connection")
                
                async def empty_stream():
                    yield 'data: {"choices":[{"delta":{"content":""},"index":0,"finish_reason":"stop"}]}\n\n'
                    yield "data: [DONE]\n\n"
                
                return StreamingResponse(
                    empty_stream(),
                    media_type="text/event-stream"
                )
            
            logger.debug(f"Messages: {request.messages}")
            raise HTTPException(
                status_code=400, 
                detail=f"No user message found. Received {len(request.messages)} messages."
            )
        
        # Step 1: Detect emotion from user message
        emotional_state = emotion_tracker.detect_emotion(user_message)
        
        logger.debug(
            f"Emotion detected: {emotional_state.emotion}",
            extra={
                "emotion": emotional_state.emotion,
                "confidence": emotional_state.confidence,
                "importance": emotional_state.importance_score
            }
        )
        
        # Step 2: Check if persona exists, if not extract from system messages
        persona = await memory_manager.get_persona(chat_id)
        if not persona:
            # Extract persona from system messages
            for msg in request.messages:
                if msg.role == "system":
                    await memory_manager.store_persona(
                        chat_id=chat_id,
                        persona_text=msg.content,
                        generate_embeddings=True
                    )
                    persona = msg.content
                    break
        
        # Step 3: Retrieve semantic context via RAG
        rag_context = await memory_manager.retrieve_semantic_context(
            chat_id=chat_id,
            query=user_message,
            query_emotion=emotional_state.emotion,
            top_k=settings.rag_top_k,
            max_tokens=settings.rag_token_budget
        )

        # Step 3b: Retrieve from knowledge_base collection (client's ingested docs/chats)
        kb_context = ""
        try:
            import app.main as _main_module
            _ki = _main_module.knowledge_ingester
            _reranker = _main_module.reranker
            if _ki is not None:
                query_embedding = rag_engine.encode(user_message)
                # Fetch more candidates when reranker will refine them
                kb_fetch_k = 15 if _reranker is not None else 5
                kb_results = await _ki.search(query_embedding, top_k=kb_fetch_k)
                if kb_results:
                    # Stage 2: Rerank KB results for true relevance (if enabled)
                    if _reranker is not None:
                        try:
                            rerank_input = [(r[0], r[1], r[2], r[3]) for r in kb_results]
                            kb_results = _reranker.rerank(user_message, rerank_input, top_k=5)
                            # Reranker returns (id, doc, meta, score) — higher score = more relevant
                            # Convert score back to distance-like value for threshold (score > 0 = relevant)
                            kb_results = [(r[0], r[1], r[2], 1.0 - min(max(r[3] / 10.0 + 0.5, 0), 1)) for r in kb_results]
                            logger.info("Reranker applied to KB results",
                                        extra={"chat_id": chat_id, "results": len(kb_results)})
                        except Exception as rr_err:
                            logger.warning(f"KB reranker failed, using cosine order: {rr_err}")
                            kb_results.sort(key=lambda x: x[3])  # fallback: sort by distance
                    else:
                        # No reranker: sort best-first by cosine distance
                        kb_results.sort(key=lambda x: x[3])

                    kb_parts = []
                    for _, doc, meta, dist in kb_results:
                        if dist < 0.70:  # Only genuinely relevant KB chunks
                            source = meta.get("title", meta.get("filename", "unknown"))
                            kb_parts.append(f"[{source}]\n{doc}")
                            logger.info(
                                "KB result",
                                extra={
                                    "chat_id": chat_id,
                                    "title": source,
                                    "distance": round(dist, 4),
                                    "preview": doc[:120].replace("\n", " ")
                                }
                            )
                    kb_context = "\n\n---\n\n".join(kb_parts)
                    if kb_context:
                        logger.info(
                            "KB block injected into prompt",
                            extra={"chat_id": chat_id, "kb_chars": len(kb_context), "results": len(kb_parts)}
                        )
                    else:
                        logger.info("KB search: no results met relevance threshold",
                                    extra={"chat_id": chat_id, "candidates": len(kb_results),
                                           "min_dist": round(min(d for _, _, _, d in kb_results), 4) if kb_results else 1.0})
            else:
                logger.debug("knowledge_ingester is None — KB search skipped")
        except Exception as kb_err:
            logger.warning(f"Knowledge base search failed: {kb_err}", exc_info=True)

        # DEBUG: Log RAG retrieval results
        logger.debug(
            f"RAG context retrieved: {len(rag_context) if rag_context else 0} chars, KB context: {len(kb_context)} chars",
            extra={
                "chat_id": chat_id,
                "rag_context_length": len(rag_context) if rag_context else 0,
                "kb_context_length": len(kb_context),
            }
        )
        
        # Step 4: Get conversation history
        # IMPORTANT: Use SillyTavern's provided context (request.messages)
        # instead of database history to respect their conversation management
        # We'll supplement with RAG for long-term memory retrieval
        
        # Extract history from request (excluding system messages and current user message)
        history_messages = []
        for msg in request.messages:
            # Skip system messages (we'll add our own) and the current user message
            if msg.role in ["user", "assistant"]:
                # Don't include the very last user message (it's the current one)
                if not (msg.role == "user" and msg.content == user_message):
                    history_messages.append({
                        "role": msg.role,
                        "content": msg.content
                    })
        
        # DEBUG: Log what history we're using
        logger.debug(
            f"Using conversation history from request",
            extra={
                "chat_id": chat_id,
                "history_message_count": len(history_messages),
                "using_st_context": True  # We're using SillyTavern's context
            }
        )
        
        # Step 5: Build context with token budget
        budget = token_manager.allocate_token_budget()
        
        # Build system prompt
        system_parts = []
        
        if persona:
            # Truncate persona to budget
            persona_truncated = token_manager.truncate_to_token_limit(
                persona,
                max_tokens=budget['system'],
                preserve_start=True
            )
            system_parts.append(persona_truncated)
        
        # Add emotional context
        emotional_context = emotion_tracker.get_emotional_context_prompt(
            current_emotion=emotional_state.emotion,
            current_confidence=emotional_state.confidence
        )
        if emotional_context:
            system_parts.append(emotional_context)
        
        system_prompt = "\n\n".join(system_parts)
        
        # Fit history to budget
        fitted_history, was_truncated = token_manager.fit_messages_to_budget(
            history_messages,
            budget=budget['history'],
            keep_recent=10
        )
        
        # Build final context
        context_messages = []
        
        if system_prompt:
            context_messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Always inject RAG block so the LLM is aware retrieval ran (even on cold start)
        rag_block = rag_context if rag_context else "[No relevant memories retrieved yet — this is the start of a new conversation]"
        context_messages.append({
            "role": "system",
            "content": f"## Retrieved Memory Context\n{rag_block}"
        })

        # Inject knowledge base context if available
        if kb_context:
            context_messages.append({
                "role": "system",
                "content": f"## Knowledge Base Context\n(From client's ingested documents and past conversations)\n\n{kb_context}"
            })
        
        # Add conversation history
        context_messages.extend(fitted_history)
        
        # Add current user message
        context_messages.append({
            "role": "user",
            "content": user_message
        })
        
        # Log context build
        context_result = token_manager.build_context_summary(
            system_text=system_prompt,
            rag_context=rag_context,
            history_messages=fitted_history,
            current_message=user_message,
            budget=budget
        )
        
        logger.info(
            f"Context built: {context_result.total_tokens} tokens",
            extra={
                "total_tokens": context_result.total_tokens,
                "system_tokens": context_result.token_breakdown.get('system', 0),
                "rag_tokens": context_result.token_breakdown.get('rag', 0),
                "history_tokens": context_result.token_breakdown.get('history', 0),
                "truncated": was_truncated,
                "history_count": len(fitted_history),
                "has_rag_context": bool(rag_context)
            }
        )
        
        # DEBUG: Log the full context structure being sent
        logger.debug(
            "Context structure:",
            extra={
                "chat_id": chat_id,
                "context_messages": [
                    {
                        "role": msg["role"],
                        "content_length": len(msg["content"]),
                        "preview": msg["content"][:100]
                    }
                    for msg in context_messages
                ]
            }
        )
        
        # Step 6: Call LLM API (Gemini or Mancer)
        if request.stream:
            # Streaming response — accumulate text to store embeddings after stream ends
            accumulated_chunks = []

            async def generate_stream():
                try:
                    async for chunk in llm_client.chat_completion_stream(
                        messages=context_messages,
                        model=request.model,
                        temperature=request.temperature or 0.9,
                        max_tokens=request.max_tokens or 800,
                        top_p=request.top_p or 1.0
                    ):
                        # Extract text content from SSE chunk for accumulation
                        if chunk and chunk.startswith("data: ") and chunk.strip() != "data: [DONE]":
                            try:
                                import json
                                payload = json.loads(chunk[6:].strip())
                                delta = payload.get("choices", [{}])[0].get("delta", {}).get("content", "")
                                if delta:
                                    accumulated_chunks.append(delta)
                            except Exception:
                                pass
                        yield chunk
                except Exception as e:
                    logger.error(f"Streaming error: {e}")
                    yield f'data: {{"error": "{str(e)}"}}\n\n'

            async def stream_and_store():
                """Wrap generator: yield chunks, then store embeddings when done."""
                async for chunk in generate_stream():
                    yield chunk
                # After stream completes, store messages with embeddings
                try:
                    assistant_text = "".join(accumulated_chunks)
                    if assistant_text:
                        _store_embed = settings.store_chat_embeddings
                        # Only embed messages with meaningful content (avoids 'Hi' noise in RAG)
                        _embed_user = _store_embed and len(user_message.strip()) >= 15
                        _embed_asst = _store_embed and len(assistant_text.strip()) >= 15
                        await memory_manager.store_message(
                            chat_id=chat_id,
                            role="user",
                            content=user_message,
                            emotion=emotional_state.emotion,
                            importance=emotional_state.importance_score,
                            generate_embedding=_embed_user
                        )
                        await memory_manager.store_message(
                            chat_id=chat_id,
                            role="assistant",
                            content=assistant_text,
                            emotion=None,
                            importance=0.5,
                            generate_embedding=_embed_asst
                        )
                        logger.info(
                            f"Stored streaming messages",
                            extra={"chat_id": chat_id, "embeddings": _store_embed,
                                   "user_embedded": _embed_user, "asst_embedded": _embed_asst,
                                   "assistant_length": len(assistant_text)}
                        )
                except Exception as store_err:
                    logger.error(f"Failed to store streaming embeddings: {store_err}")

            return StreamingResponse(
                stream_and_store(),
                media_type="text/event-stream"
            )
        
        else:
            # Non-streaming response
            response = await llm_client.chat_completion(
                messages=context_messages,
                model=request.model,  # Pass model for Mancer
                temperature=request.temperature or 0.9,
                max_tokens=request.max_tokens or 800,
                top_p=request.top_p or 1.0
            )
            
            assistant_message = response.choices[0].message.content
            
            # Step 7: Store messages (embeddings only if enabled in .env)
            _store_embed = settings.store_chat_embeddings
            # Only embed messages with meaningful content (avoids 'Hi' noise in RAG)
            _embed_user = _store_embed and len(user_message.strip()) >= 15
            _embed_asst = _store_embed and len(assistant_message.strip()) >= 15
            await memory_manager.store_message(
                chat_id=chat_id,
                role="user",
                content=user_message,
                emotion=emotional_state.emotion,
                importance=emotional_state.importance_score,
                generate_embedding=_embed_user
            )

            await memory_manager.store_message(
                chat_id=chat_id,
                role="assistant",
                content=assistant_message,
                emotion=None,
                importance=0.5,
                generate_embedding=_embed_asst
            )
            
            # Step 8: Check if summarization needed
            if await memory_manager.should_summarize(chat_id):
                # Run summarization in background
                asyncio.create_task(
                    memory_manager.create_summary(chat_id, llm_client)
                )
                logger.info(f"Triggered background summarization for chat: {chat_id}")
            
            logger.info(
                f"Chat completion successful",
                extra={
                    "chat_id": chat_id,
                    "input_tokens": response.usage.prompt_tokens,
                    "output_tokens": response.usage.completion_tokens,
                    "total_tokens": response.usage.total_tokens
                }
            )
            
            return response
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Chat completion error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/v1/models", response_model=ModelListResponse)
async def list_models():
    """
    List available models.
    
    Returns OpenAI-compatible model list for SillyTavern.
    Dynamically fetches models from the active provider (Gemini or Mancer).
    """
    from app.main import llm_client
    
    try:
        # Fetch models from the active provider
        models = await llm_client.list_models()
        
        logger.info(f"Returning {len(models)} models from provider")
        
        return ModelListResponse(data=models)
        
    except Exception as e:
        logger.error(f"Error listing models: {e}", exc_info=True)
        
        # Fallback: return at least one model to prevent errors
        import time
        return ModelListResponse(
            data=[
                ModelInfo(
                    id=settings.gemini_model if settings.llm_provider == "gemini" else settings.mancer_default_model,
                    created=int(time.time()),
                    owned_by=settings.llm_provider
                )
            ]
        )


@router.post("/api/backends/chat-completions/generate")
async def sillytavern_chat_completions(request: ChatCompletionRequest):
    """
    SillyTavern-specific chat completion endpoint.
    
    This is an alias for /v1/chat/completions to support SillyTavern's
    custom backend format.
    
    Just forwards to the main chat_completions endpoint.
    """
    logger.info("SillyTavern endpoint called, forwarding to chat_completions")
    return await chat_completions(request)


@router.post("/api/settings/save")
async def sillytavern_settings_save():
    """
    SillyTavern settings save endpoint.
    
    SillyTavern tries to save settings to the backend.
    We just acknowledge it without actually storing anything.
    """
    return {"success": True, "message": "Settings saved (no-op)"}


@router.post("/api/chats/get")
async def sillytavern_chats_get():
    """Get chat history - return empty for now."""
    return []


@router.post("/api/chats/save")
async def sillytavern_chats_save():
    """Save chat - acknowledge without storing."""
    return {"success": True}


@router.post("/api/avatars/get")
async def sillytavern_avatars_get():
    """Get avatar - return empty."""
    return ""


@router.post("/api/ping")
async def sillytavern_ping():
    """Ping endpoint for SillyTavern health check."""
    return {"result": "pong"}


@router.post("/api/stats/get")
async def sillytavern_stats_get():
    """Get server stats."""
    return {
        "status": "ok",
        "version": "1.0.0"
    }


@router.post("/api/stats/update")
async def sillytavern_stats_update():
    """Update stats - acknowledge."""
    return {"success": True}


@router.post("/api/secrets/write")
async def sillytavern_secrets_write():
    """Write secrets - acknowledge."""
    return {"success": True}


@router.post("/api/backends/chat-completions/status")
async def sillytavern_status():
    """Backend status."""
    return {"status": "ok"}


@router.post("/api/tokenizers/openai/count")
async def sillytavern_token_count(request: dict = None):
    """Token counting endpoint."""
    from app.main import token_manager
    
    # Handle empty or missing request
    if not request:
        return {"token_count": 0}
    
    text = request.get("text", "") if isinstance(request, dict) else ""
    
    # If text is empty, return 0
    if not text:
        return {"token_count": 0}
    
    count = token_manager.count_tokens(str(text))
    return {"token_count": count}


@router.post("/api/quick-replies/save")
async def sillytavern_quick_replies_save():
    """Save quick replies - acknowledge."""
    return {"success": True}


@router.get("/scripts/extensions/expressions/list-item.html")
async def sillytavern_expressions_list_item():
    """Return empty HTML for expression list items."""
    return ""


@router.get("/api/sprites/get")
async def sillytavern_sprites_get():
    """Get sprites - return empty."""
    return ""

