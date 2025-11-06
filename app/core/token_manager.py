"""Token counting and context building with budget management."""

import logging
from typing import List, Dict, Optional, Tuple
import tiktoken

from app.core.config import settings
from app.models.memory import ContextBuildResult

logger = logging.getLogger(__name__)


class TokenManager:
    """Manages token budgets and builds context within limits."""
    
    def __init__(self):
        """Initialize token counter."""
        try:
            # Use cl100k_base encoding (GPT-4/GPT-3.5-turbo)
            # Works as reasonable approximation for Gemini
            self.encoding = tiktoken.get_encoding("cl100k_base")
            logger.info("Token manager initialized with cl100k_base encoding")
        except Exception as e:
            logger.warning(f"Failed to load tiktoken encoding: {e}. Using fallback.")
            self.encoding = None
    
    def count_tokens(self, text: str) -> int:
        """
        Count tokens in text.
        
        Args:
            text: Input text
            
        Returns:
            Number of tokens
        """
        if self.encoding:
            try:
                return len(self.encoding.encode(text))
            except Exception as e:
                logger.warning(f"Token counting error: {e}. Using fallback.")
        
        # Fallback: rough approximation
        return max(1, len(text) // 4)
    
    def count_message_tokens(self, messages: List[Dict]) -> int:
        """
        Count tokens in message list.
        
        Args:
            messages: List of message dicts
            
        Returns:
            Total token count
        """
        total = 0
        for msg in messages:
            # Count role
            total += 4  # Overhead per message
            total += self.count_tokens(msg.get('role', ''))
            total += self.count_tokens(msg.get('content', ''))
        
        total += 3  # Response priming
        return total
    
    def truncate_to_token_limit(
        self,
        text: str,
        max_tokens: int,
        preserve_start: bool = True
    ) -> str:
        """
        Truncate text to fit within token limit.
        
        Args:
            text: Input text
            max_tokens: Maximum allowed tokens
            preserve_start: If True, keep beginning; else keep end
            
        Returns:
            Truncated text
        """
        current_tokens = self.count_tokens(text)
        
        if current_tokens <= max_tokens:
            return text
        
        # Binary search for correct length
        if preserve_start:
            # Keep beginning
            ratio = max_tokens / current_tokens
            estimated_chars = int(len(text) * ratio * 0.95)  # 5% safety margin
            truncated = text[:estimated_chars]
            
            while self.count_tokens(truncated) > max_tokens:
                truncated = truncated[:int(len(truncated) * 0.9)]
            
            return truncated + "..."
        else:
            # Keep end
            ratio = max_tokens / current_tokens
            estimated_chars = int(len(text) * ratio * 0.95)
            truncated = text[-estimated_chars:]
            
            while self.count_tokens(truncated) > max_tokens:
                truncated = truncated[-int(len(truncated) * 0.9):]
            
            return "..." + truncated
    
    def allocate_token_budget(
        self,
        total_budget: int = None
    ) -> Dict[str, int]:
        """
        Allocate token budget across context components.
        
        Args:
            total_budget: Total tokens available (default from settings)
            
        Returns:
            Dict mapping component to token allocation
        """
        if total_budget is None:
            total_budget = settings.max_context_tokens
        
        return {
            'system': int(total_budget * settings.system_token_percent / 100),
            'rag': int(total_budget * settings.rag_token_percent / 100),
            'history': int(total_budget * settings.history_token_percent / 100),
            'response': int(total_budget * settings.response_token_percent / 100),
        }
    
    def fit_messages_to_budget(
        self,
        messages: List[Dict],
        budget: int,
        keep_recent: int = 10
    ) -> Tuple[List[Dict], bool]:
        """
        Fit messages within token budget, keeping most recent.
        
        Args:
            messages: List of message dicts
            budget: Token budget
            keep_recent: Minimum recent messages to keep
            
        Returns:
            Tuple of (fitted_messages, was_truncated)
        """
        if not messages:
            return [], False
        
        # Always keep at least the most recent messages
        recent_messages = messages[-keep_recent:] if len(messages) > keep_recent else messages
        recent_tokens = self.count_message_tokens(recent_messages)
        
        if recent_tokens <= budget:
            # All recent messages fit
            return recent_messages, len(messages) > len(recent_messages)
        
        # Need to truncate even recent messages
        fitted = []
        current_tokens = 0
        
        # Add from most recent backwards
        for msg in reversed(messages):
            msg_tokens = self.count_message_tokens([msg])
            
            if current_tokens + msg_tokens <= budget:
                fitted.insert(0, msg)
                current_tokens += msg_tokens
            else:
                # Budget exhausted
                break
        
        was_truncated = len(fitted) < len(messages)
        
        logger.debug(
            f"Fitted {len(fitted)}/{len(messages)} messages within {budget} token budget",
            extra={
                "budget": budget,
                "fitted_count": len(fitted),
                "total_count": len(messages),
                "truncated": was_truncated
            }
        )
        
        return fitted, was_truncated
    
    def build_context_summary(
        self,
        system_text: str,
        rag_context: str,
        history_messages: List[Dict],
        current_message: str,
        budget: Dict[str, int] = None
    ) -> ContextBuildResult:
        """
        Build complete context with budget allocation tracking.
        
        This is a monitoring function that doesn't modify content,
        just tracks token usage.
        
        Args:
            system_text: System/persona prompt
            rag_context: Retrieved RAG context
            history_messages: Conversation history
            current_message: Current user message
            budget: Token budget allocation
            
        Returns:
            ContextBuildResult with token tracking
        """
        if budget is None:
            budget = self.allocate_token_budget()
        
        # Count tokens
        system_tokens = self.count_tokens(system_text)
        rag_tokens = self.count_tokens(rag_context)
        history_tokens = self.count_message_tokens(history_messages)
        current_tokens = self.count_tokens(current_message)
        
        total_tokens = system_tokens + rag_tokens + history_tokens + current_tokens
        
        logger.info(
            f"Context built: {total_tokens} total tokens",
            extra={
                "system_tokens": system_tokens,
                "rag_tokens": rag_tokens,
                "history_tokens": history_tokens,
                "current_tokens": current_tokens,
                "total_tokens": total_tokens,
                "budget_system": budget.get('system', 0),
                "budget_rag": budget.get('rag', 0),
                "budget_history": budget.get('history', 0)
            }
        )
        
        # Combine all into message list
        all_messages = []
        
        if system_text:
            all_messages.append({
                "role": "system",
                "content": system_text
            })
        
        if rag_context:
            all_messages.append({
                "role": "system",
                "content": rag_context
            })
        
        all_messages.extend(history_messages)
        
        all_messages.append({
            "role": "user",
            "content": current_message
        })
        
        return ContextBuildResult(
            messages=all_messages,
            total_tokens=total_tokens,
            system_tokens=system_tokens,
            rag_tokens=rag_tokens,
            history_tokens=history_tokens,
            retrieved_chunks=rag_context.count('relevance:') if rag_context else 0,
            summarized=False  # Set by caller if summarization was used
        )
