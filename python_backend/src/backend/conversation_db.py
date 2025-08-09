# conversation_db.py
import sqlite3
import json
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ConversationDB:
    """Simple SQLite database for storing conversation history."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()
    
    def _init_db(self):
        """Initialize the database with required tables."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    title TEXT,
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            conn.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',
                    metadata TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id) ON DELETE CASCADE
                )
            """)
            
            conn.commit()
    
    def create_conversation(self, session_id: str, title: str = None, metadata: Dict = None) -> int:
        """Create a new conversation and return its ID."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO conversations (session_id, title, metadata)
                VALUES (?, ?, ?)
            """, (session_id, title, json.dumps(metadata or {})))
            return cursor.lastrowid
    
    def add_message(self, conversation_id: int, role: str, content: str, 
                   message_type: str = "text", metadata: Dict = None):
        """Add a message to a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT INTO messages (conversation_id, role, content, message_type, metadata)
                VALUES (?, ?, ?, ?, ?)
            """, (conversation_id, role, content, message_type, json.dumps(metadata or {})))
            
            # Update conversation timestamp
            conn.execute("""
                UPDATE conversations SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (conversation_id,))
            
            conn.commit()
    
    def get_conversation_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT role, content, message_type, metadata, created_at
                FROM messages 
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """, (conversation_id,))
            
            messages = []
            for row in cursor.fetchall():
                message = dict(row)
                if message['metadata']:
                    message['metadata'] = json.loads(message['metadata'])
                messages.append(message)
            
            return messages
    
    def get_conversation_history_formatted(self, conversation_id: int, format_type: str = "openai") -> List[Dict[str, Any]]:
        """Get conversation history in specific format."""
        messages = self.get_conversation_messages(conversation_id)
        
        if format_type == "openai":
            formatted = []
            for msg in messages:
                # Map roles to OpenAI format
                role = msg['role']
                if role == 'model':
                    role = 'assistant'
                elif role == 'tool':
                    continue  # Skip tool messages for now
                    
                formatted.append({
                    'role': role,
                    'content': msg['content']
                })
            return formatted
        
        return messages
    
    def clear_conversation(self, conversation_id: int):
        """Clear all messages from a conversation."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.commit()
    
    def delete_conversation(self, conversation_id: int):
        """Delete a conversation and all its messages."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))
            conn.commit()
    
    def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT id, session_id, title, metadata, created_at, updated_at
                FROM conversations 
                ORDER BY updated_at DESC
                LIMIT ?
            """, (limit,))
            
            conversations = []
            for row in cursor.fetchall():
                conv = dict(row)
                if conv['metadata']:
                    conv['metadata'] = json.loads(conv['metadata'])
                conversations.append(conv)
            
            return conversations
    
    def update_conversation_title(self, conversation_id: int, title: str):
        """Update conversation title."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                UPDATE conversations SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, (title, conversation_id))
            conn.commit()
    
    def close(self):
        """Close database connection."""
        # SQLite connections are closed automatically when context manager exits
        pass