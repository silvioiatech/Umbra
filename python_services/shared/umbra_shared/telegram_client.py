"""Telegram client for Umbra services."""

import httpx
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel
from .logger import UmbraLogger
from .retry import RetryUtils, retry_async


class TelegramUser(BaseModel):
    """Telegram user information."""
    id: int
    is_bot: bool
    first_name: str
    last_name: Optional[str] = None
    username: Optional[str] = None
    language_code: Optional[str] = None


class TelegramChat(BaseModel):
    """Telegram chat information."""
    id: int
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    username: Optional[str] = None
    type: str


class TelegramDocument(BaseModel):
    """Telegram document information."""
    file_name: Optional[str] = None
    mime_type: Optional[str] = None
    file_id: str
    file_unique_id: str
    file_size: Optional[int] = None


class TelegramPhoto(BaseModel):
    """Telegram photo information."""
    file_id: str
    file_unique_id: str
    width: int
    height: int
    file_size: Optional[int] = None


class TelegramMessage(BaseModel):
    """Telegram message structure."""
    message_id: int
    from_user: Optional[TelegramUser] = None  # 'from' is a reserved keyword
    chat: TelegramChat
    date: int
    text: Optional[str] = None
    document: Optional[TelegramDocument] = None
    photo: Optional[List[TelegramPhoto]] = None
    caption: Optional[str] = None
    
    class Config:
        fields = {'from_user': 'from'}


class TelegramUpdate(BaseModel):
    """Telegram update structure."""
    update_id: int
    message: Optional[TelegramMessage] = None


class SendMessageOptions(BaseModel):
    """Options for sending Telegram messages."""
    chat_id: Union[str, int]
    text: str
    parse_mode: Optional[str] = None
    reply_markup: Optional[Dict[str, Any]] = None
    disable_web_page_preview: Optional[bool] = None


class SendDocumentOptions(BaseModel):
    """Options for sending Telegram documents."""
    chat_id: Union[str, int]
    document: str  # URL or file_id
    caption: Optional[str] = None
    parse_mode: Optional[str] = None


class TelegramClient:
    """Client for Telegram Bot API."""
    
    def __init__(self, bot_token: str, webhook_url: Optional[str] = None):
        self.bot_token = bot_token
        self.webhook_url = webhook_url
        self.base_url = f"https://api.telegram.org/bot{bot_token}"
        self.logger = UmbraLogger("TelegramClient")
        self.retry_utils = RetryUtils()
        
        self.client = httpx.AsyncClient(
            timeout=30.0
        )
    
    @retry_async()
    async def send_message(
        self,
        chat_id: Union[str, int],
        text: str,
        parse_mode: Optional[str] = None,
        reply_markup: Optional[Dict[str, Any]] = None,
        disable_web_page_preview: Optional[bool] = None
    ) -> Dict[str, Any]:
        """Send a text message."""
        try:
            payload = {
                "chat_id": chat_id,
                "text": text,
            }
            
            if parse_mode:
                payload["parse_mode"] = parse_mode
            if reply_markup:
                payload["reply_markup"] = reply_markup
            if disable_web_page_preview is not None:
                payload["disable_web_page_preview"] = disable_web_page_preview
            
            self.logger.debug("Sending message", chat_id=chat_id, text_length=len(text))
            
            response = await self.client.post(
                f"{self.base_url}/sendMessage",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            
            self.logger.info("Message sent successfully", chat_id=chat_id)
            return result["result"]
            
        except Exception as e:
            self.logger.error("Failed to send message", chat_id=chat_id, error=str(e))
            raise
    
    @retry_async()
    async def send_document(
        self,
        chat_id: Union[str, int],
        document: str,
        caption: Optional[str] = None,
        parse_mode: Optional[str] = None
    ) -> Dict[str, Any]:
        """Send a document."""
        try:
            payload = {
                "chat_id": chat_id,
                "document": document,
            }
            
            if caption:
                payload["caption"] = caption
            if parse_mode:
                payload["parse_mode"] = parse_mode
            
            self.logger.debug("Sending document", chat_id=chat_id)
            
            response = await self.client.post(
                f"{self.base_url}/sendDocument",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            
            self.logger.info("Document sent successfully", chat_id=chat_id)
            return result["result"]
            
        except Exception as e:
            self.logger.error("Failed to send document", chat_id=chat_id, error=str(e))
            raise
    
    @retry_async()
    async def get_file(self, file_id: str) -> Dict[str, Any]:
        """Get file information."""
        try:
            response = await self.client.get(
                f"{self.base_url}/getFile",
                params={"file_id": file_id}
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            
            return result["result"]
            
        except Exception as e:
            self.logger.error("Failed to get file", file_id=file_id, error=str(e))
            raise
    
    async def download_file(self, file_path: str) -> bytes:
        """Download file from Telegram servers."""
        try:
            file_url = f"https://api.telegram.org/file/bot{self.bot_token}/{file_path}"
            
            response = await self.client.get(file_url)
            response.raise_for_status()
            
            return response.content
            
        except Exception as e:
            self.logger.error("Failed to download file", file_path=file_path, error=str(e))
            raise
    
    async def set_webhook(
        self,
        url: str,
        secret_token: Optional[str] = None,
        allowed_updates: Optional[List[str]] = None
    ) -> bool:
        """Set webhook for receiving updates."""
        try:
            payload = {"url": url}
            
            if secret_token:
                payload["secret_token"] = secret_token
            if allowed_updates:
                payload["allowed_updates"] = allowed_updates
            
            response = await self.client.post(
                f"{self.base_url}/setWebhook",
                json=payload
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            
            self.logger.info("Webhook set successfully", url=url)
            return True
            
        except Exception as e:
            self.logger.error("Failed to set webhook", url=url, error=str(e))
            raise
    
    async def delete_webhook(self, drop_pending_updates: bool = False) -> bool:
        """Delete webhook."""
        try:
            response = await self.client.post(
                f"{self.base_url}/deleteWebhook",
                json={"drop_pending_updates": drop_pending_updates}
            )
            response.raise_for_status()
            
            result = response.json()
            if not result.get("ok"):
                raise Exception(f"Telegram API error: {result}")
            
            self.logger.info("Webhook deleted successfully")
            return True
            
        except Exception as e:
            self.logger.error("Failed to delete webhook", error=str(e))
            raise
    
    def parse_update(self, update_data: Dict[str, Any]) -> TelegramUpdate:
        """Parse incoming update data."""
        return TelegramUpdate(**update_data)
    
    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
    
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()