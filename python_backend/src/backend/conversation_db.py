"""
ConversationDB - SQLite database for persisting conversation history.
"""

import json
import logging
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ConversationDB:
    """SQLite database manager for conversation history."""

    def __init__(self, db_path: str):
        """Initialize the conversation database.

        Args:
            db_path: Path to the SQLite database file
        """
        self.db_path = str(Path(db_path).resolve())

        # Ensure the directory exists
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

        # Initialize database
        self._init_database()

    def _init_database(self):
        """Initialize the database tables."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Create conversations table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS conversations (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE,
                    title TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT  -- JSON string for storing additional metadata
                )
            """
            )

            # Create messages table
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    conversation_id INTEGER,
                    role TEXT NOT NULL,  -- 'user', 'assistant', 'system', 'tool', 'model'
                    content TEXT NOT NULL,
                    message_type TEXT DEFAULT 'text',  -- 'text', 'image', 'tool_result', etc.
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    metadata TEXT,  -- JSON string for storing additional metadata
                    FOREIGN KEY (conversation_id) REFERENCES conversations (id)
                )
            """
            )

            # Create indexes for better performance
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_session_id
                ON conversations (session_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_conversation_id
                ON messages (conversation_id)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_messages_created_at
                ON messages (created_at)
            """
            )

            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_conversations_updated_at
                ON conversations (updated_at)
            """
            )

            conn.commit()
            logger.info(f"Database initialized at {self.db_path}")

    def create_conversation(
        self,
        session_id: str,
        title: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Create a new conversation.

        Args:
            session_id: Unique session identifier
            title: Optional conversation title
            metadata: Optional metadata dictionary

        Returns:
            conversation_id: The ID of the created conversation
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            metadata_json = json.dumps(metadata) if metadata else None

            cursor.execute(
                """
                INSERT INTO conversations (session_id, title, metadata)
                VALUES (?, ?, ?)
            """,
                (session_id, title, metadata_json),
            )

            conversation_id = cursor.lastrowid
            if conversation_id is None:
                raise RuntimeError("Failed to create conversation - no ID returned")

            conn.commit()

            logger.info(
                f"Created conversation {conversation_id} with session {session_id}"
            )
            return conversation_id

    def add_message(
        self,
        conversation_id: int,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ):
        """Add a message to a conversation.

        Args:
            conversation_id: ID of the conversation
            role: Message role ('user', 'assistant', 'system', 'tool', 'model')
            content: Message content
            message_type: Type of message ('text', 'image', 'tool_result', etc.)
            metadata: Optional metadata dictionary
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            metadata_json = json.dumps(metadata) if metadata else None

            cursor.execute(
                """
                INSERT INTO messages (conversation_id, role, content, message_type, metadata)
                VALUES (?, ?, ?, ?, ?)
            """,
                (conversation_id, role, content, message_type, metadata_json),
            )

            # Update conversation's updated_at timestamp
            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (conversation_id,),
            )

            conn.commit()

            logger.debug(f"Added {role} message to conversation {conversation_id}")

    def get_conversation_messages(self, conversation_id: int) -> List[Dict[str, Any]]:
        """Get all messages for a conversation.

        Args:
            conversation_id: ID of the conversation

        Returns:
            List of message dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row  # Enable column access by name
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, role, content, message_type, created_at, metadata
                FROM messages
                WHERE conversation_id = ?
                ORDER BY created_at ASC
            """,
                (conversation_id,),
            )

            messages = []
            for row in cursor.fetchall():
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                messages.append(
                    {
                        "id": row["id"],
                        "role": row["role"],
                        "content": row["content"],
                        "message_type": row["message_type"],
                        "created_at": row["created_at"],
                        "metadata": metadata,
                    }
                )

            return messages

    def get_conversation_history_formatted(
        self, conversation_id: int, format_type: str = "openai"
    ) -> List[Dict[str, Any]]:
        """Get conversation history in a specific format.

        Args:
            conversation_id: ID of the conversation
            format_type: Format type ('openai', 'gemini', 'raw')

        Returns:
            List of formatted messages
        """
        messages = self.get_conversation_messages(conversation_id)

        if format_type == "openai":
            # Convert to OpenAI format
            formatted_messages = []
            for msg in messages:
                # Map roles to OpenAI format
                role = msg["role"]
                if role == "model":
                    role = "assistant"
                elif role == "tool":
                    role = "assistant"  # Or handle tool messages differently

                formatted_messages.append({"role": role, "content": msg["content"]})
            return formatted_messages

        elif format_type == "gemini":
            # Convert to Gemini format
            formatted_messages = []
            for msg in messages:
                # Gemini uses 'user' and 'model' roles
                role = msg["role"]
                if role == "assistant":
                    role = "model"
                elif role == "system":
                    # System messages might need special handling in Gemini
                    continue

                formatted_messages.append({"role": role, "content": msg["content"]})
            return formatted_messages

        else:  # raw format
            return messages

    def get_recent_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get recent conversations.

        Args:
            limit: Maximum number of conversations to return

        Returns:
            List of conversation dictionaries
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT c.id, c.session_id, c.title, c.created_at, c.updated_at, c.metadata,
                       COUNT(m.id) as message_count
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                GROUP BY c.id
                ORDER BY c.updated_at DESC
                LIMIT ?
            """,
                (limit,),
            )

            conversations = []
            for row in cursor.fetchall():
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                conversations.append(
                    {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "metadata": metadata,
                        "message_count": row["message_count"],
                    }
                )

            return conversations

    def update_conversation_title(self, conversation_id: int, title: str):
        """Update the title of a conversation.

        Args:
            conversation_id: ID of the conversation
            title: New title for the conversation
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                UPDATE conversations
                SET title = ?, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (title, conversation_id),
            )

            conn.commit()

            if cursor.rowcount > 0:
                logger.info(f"Updated title for conversation {conversation_id}")
            else:
                logger.warning(f"No conversation found with ID {conversation_id}")

    def delete_conversation(self, conversation_id: int):
        """Delete a conversation and all its messages.

        Args:
            conversation_id: ID of the conversation to delete
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Delete messages first (due to foreign key constraint)
            cursor.execute(
                """
                DELETE FROM messages WHERE conversation_id = ?
            """,
                (conversation_id,),
            )

            # Delete conversation
            cursor.execute(
                """
                DELETE FROM conversations WHERE id = ?
            """,
                (conversation_id,),
            )

            conn.commit()

            logger.info(f"Deleted conversation {conversation_id}")

    def clear_conversation(self, conversation_id: int):
        """Clear all messages from a conversation but keep the conversation record.

        Args:
            conversation_id: ID of the conversation to clear
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM messages WHERE conversation_id = ?
            """,
                (conversation_id,),
            )

            # Update conversation's updated_at timestamp
            cursor.execute(
                """
                UPDATE conversations
                SET updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """,
                (conversation_id,),
            )

            conn.commit()

            logger.info(f"Cleared messages from conversation {conversation_id}")

    def get_conversation_by_session_id(
        self, session_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get conversation by session ID.

        Args:
            session_id: Session ID to search for

        Returns:
            Conversation dictionary or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            cursor.execute(
                """
                SELECT id, session_id, title, created_at, updated_at, metadata
                FROM conversations
                WHERE session_id = ?
            """,
                (session_id,),
            )

            row = cursor.fetchone()
            if row:
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                return {
                    "id": row["id"],
                    "session_id": row["session_id"],
                    "title": row["title"],
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "metadata": metadata,
                }

            return None

    def search_conversations(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search conversations by title or message content.

        Args:
            query: Search query
            limit: Maximum number of results to return

        Returns:
            List of matching conversations
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            search_pattern = f"%{query}%"

            cursor.execute(
                """
                SELECT DISTINCT c.id, c.session_id, c.title, c.created_at, c.updated_at, c.metadata
                FROM conversations c
                LEFT JOIN messages m ON c.id = m.conversation_id
                WHERE c.title LIKE ? OR m.content LIKE ?
                ORDER BY c.updated_at DESC
                LIMIT ?
            """,
                (search_pattern, search_pattern, limit),
            )

            conversations = []
            for row in cursor.fetchall():
                metadata = json.loads(row["metadata"]) if row["metadata"] else {}
                conversations.append(
                    {
                        "id": row["id"],
                        "session_id": row["session_id"],
                        "title": row["title"],
                        "created_at": row["created_at"],
                        "updated_at": row["updated_at"],
                        "metadata": metadata,
                    }
                )

            return conversations

    def get_conversation_stats(self) -> Dict[str, Any]:
        """Get database statistics.

        Returns:
            Dictionary with conversation and message counts
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Get conversation count
            cursor.execute("SELECT COUNT(*) FROM conversations")
            conversation_count = cursor.fetchone()[0]

            # Get message count
            cursor.execute("SELECT COUNT(*) FROM messages")
            message_count = cursor.fetchone()[0]

            # Get oldest and newest conversation dates
            cursor.execute(
                """
                SELECT MIN(created_at), MAX(created_at)
                FROM conversations
            """
            )
            date_range = cursor.fetchone()

            return {
                "conversation_count": conversation_count,
                "message_count": message_count,
                "oldest_conversation": date_range[0],
                "newest_conversation": date_range[1],
            }

    def close(self):
        """Close the database connection (if needed for cleanup)."""
        # SQLite connections are closed automatically when using context managers
        # This method is here for compatibility with the existing code
        logger.info("ConversationDB close() called - connections auto-managed")

    def optimize_database(self):
        """Optimize the database by running VACUUM and ANALYZE."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("VACUUM")
            cursor.execute("ANALYZE")
            conn.commit()
            logger.info("Database optimized")
