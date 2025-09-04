"""Fixed conversation management for Umbra bot."""
import logging
from typing import List, Dict, Any, Optional
from .database import DatabaseManager


class ConversationManager:
    """Manages conversation history and context for users."""
    
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager
        self.logger = logging.getLogger(__name__)
        self._conversation_context: Dict[int, List[Dict[str, Any]]] = {}
    
    def add_message(self, user_id: int, message: str, response: str, 
                  module: Optional[str] = None) -> None:
        """Add a message-response pair to the conversation."""
        # Store in database
        self.db.add_conversation(user_id, message, response, module)
        
        # Update in-memory context
        if user_id not in self._conversation_context:
            self._conversation_context[user_id] = []
        
        self._conversation_context[user_id].append({
            "message": message,
            "response": response,
            "module": module,
            "timestamp": None  # Will be set by database
        })
        
        # Keep only last 20 messages in memory
        if len(self._conversation_context[user_id]) > 20:
            self._conversation_context[user_id] = self._conversation_context[user_id][-20:]
    
    def get_conversation_context(self, user_id: int, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversation context for a user."""
        # Try in-memory cache first
        if user_id in self._conversation_context:
            context = self._conversation_context[user_id][-limit:]
            if context:
                return context
        
        # Fall back to database
        history = self.db.get_conversation_history(user_id, limit)
        
        # Update in-memory cache
        if history and user_id not in self._conversation_context:
            self._conversation_context[user_id] = history
        
        return history or []
    
    def get_recent_messages(self, user_id: int, limit: int = 5) -> List[Dict[str, Any]]:
        """Get recent messages for a user (alias for get_conversation_context)."""
        return self.get_conversation_context(user_id, limit)
    
    def get_conversation_summary(self, user_id: int, max_length: int = 500) -> str:
        """Get a summary of recent conversation for AI context."""
        context = self.get_conversation_context(user_id, limit=5)
        
        if not context:
            return "No recent conversation history."
        
        summary_parts = []
        for entry in context:
            summary_parts.append(f"User: {entry['message']}")
            summary_parts.append(f"Bot: {entry['response']}")
        
        summary = "\n".join(summary_parts)
        
        # Truncate if too long
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary
    
    def clear_context(self, user_id: int) -> None:
        """Clear in-memory conversation context for a user."""
        if user_id in self._conversation_context:
            del self._conversation_context[user_id]
        
        self.logger.info(f"Cleared conversation context for user {user_id}")
    
    def get_active_users(self) -> List[int]:
        """Get list of users with active conversations."""
        return list(self._conversation_context.keys())
