"""
Alternative version using POLLING instead of webhooks
Use this if you can't make the Databricks App publicly accessible

This version continuously polls Telegram for new messages instead of
waiting for webhooks. It can run as a Databricks Job or in the App.
"""
import os
import logging
import time
import asyncio
from typing import Optional
import httpx
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.serving import ChatMessage, ChatMessageRole

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Environment variables
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DATABRICKS_SERVING_ENDPOINT = os.getenv("DATABRICKS_SERVING_ENDPOINT")
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "2"))  # seconds

# Initialize Databricks client
w = WorkspaceClient()

# Telegram API base URL
TELEGRAM_API_URL = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}"


class TelegramPoller:
    """Polls Telegram for new messages and processes them"""
    
    def __init__(self):
        self.last_update_id = 0
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def send_to_databricks_endpoint(self, message: str) -> str:
        """
        Send a message to the Databricks serving endpoint and get the response.
        
        Args:
            message: The user message to send
            
        Returns:
            The response from the model
        """
        try:
            logger.info(f"Sending to Databricks endpoint: {message[:100]}")
            
            # Query the serving endpoint using the Databricks SDK
            response = w.serving_endpoints.query(
                name=DATABRICKS_SERVING_ENDPOINT,
                messages=[
                    ChatMessage(
                        role=ChatMessageRole.USER,
                        content=message
                    )
                ]
            )
            
            # Extract the response content
            if response.choices and len(response.choices) > 0:
                result = response.choices[0].message.content
                logger.info(f"Received response: {result[:100]}")
                return result
            else:
                return "I couldn't generate a response. Please try again."
                
        except Exception as e:
            logger.error(f"Error querying Databricks endpoint: {str(e)}")
            return f"Sorry, I encountered an error: {str(e)}"
    
    async def send_telegram_message(self, chat_id: int, text: str) -> dict:
        """
        Send a message back to Telegram.
        
        Args:
            chat_id: The Telegram chat ID
            text: The message text to send
            
        Returns:
            The Telegram API response
        """
        url = f"{TELEGRAM_API_URL}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown"
        }
        
        try:
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Error sending message to Telegram: {str(e)}")
            return {"ok": False, "error": str(e)}
    
    async def send_chat_action(self, chat_id: int, action: str = "typing"):
        """Send chat action (e.g., typing indicator)"""
        url = f"{TELEGRAM_API_URL}/sendChatAction"
        try:
            await self.client.post(url, json={"chat_id": chat_id, "action": action})
        except Exception as e:
            logger.warning(f"Failed to send chat action: {e}")
    
    async def get_updates(self) -> list:
        """
        Get new updates from Telegram using long polling.
        
        Returns:
            List of updates
        """
        url = f"{TELEGRAM_API_URL}/getUpdates"
        params = {
            "offset": self.last_update_id + 1,
            "timeout": 30,  # Long polling timeout
            "allowed_updates": ["message"]
        }
        
        try:
            response = await self.client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            
            if data.get("ok"):
                updates = data.get("result", [])
                if updates:
                    # Update the last_update_id to avoid processing same messages
                    self.last_update_id = max(update["update_id"] for update in updates)
                return updates
            else:
                logger.error(f"Error getting updates: {data}")
                return []
                
        except Exception as e:
            logger.error(f"Error polling Telegram: {str(e)}")
            return []
    
    async def process_update(self, update: dict):
        """
        Process a single Telegram update.
        
        Args:
            update: The update dictionary from Telegram
        """
        try:
            # Extract message information
            if "message" not in update:
                return
            
            message = update["message"]
            
            # Check if the message contains text
            if "text" not in message:
                logger.info("Message doesn't contain text, skipping")
                return
            
            chat_id = message["chat"]["id"]
            user_message = message["text"]
            user_name = message.get("from", {}).get("first_name", "User")
            
            logger.info(f"Processing message from {user_name} (chat {chat_id}): {user_message}")
            
            # Handle commands
            if user_message.startswith("/start"):
                await self.send_telegram_message(
                    chat_id,
                    "👋 Hello! I'm connected to a Databricks AI model. Send me a message and I'll respond!"
                )
                return
            
            if user_message.startswith("/help"):
                await self.send_telegram_message(
                    chat_id,
                    "💬 Just send me any message and I'll process it through the Databricks AI model.\n\n"
                    "Commands:\n"
                    "/start - Welcome message\n"
                    "/help - This help message\n"
                    "/status - Check bot status"
                )
                return
            
            if user_message.startswith("/status"):
                await self.send_telegram_message(
                    chat_id,
                    f"✅ Bot is running\n"
                    f"🔗 Endpoint: {DATABRICKS_SERVING_ENDPOINT}\n"
                    f"🔄 Mode: Polling\n"
                    f"📊 Last update ID: {self.last_update_id}"
                )
                return
            
            # Send typing indicator
            await self.send_chat_action(chat_id, "typing")
            
            # Get response from Databricks endpoint
            bot_response = await self.send_to_databricks_endpoint(user_message)
            
            # Send response back to Telegram
            await self.send_telegram_message(chat_id, bot_response)
            
            logger.info(f"Successfully processed message for chat {chat_id}")
            
        except Exception as e:
            logger.error(f"Error processing update: {str(e)}")
            # Try to send error message to user
            try:
                await self.send_telegram_message(
                    message["chat"]["id"],
                    "Sorry, I encountered an error processing your message. Please try again."
                )
            except:
                pass
    
    async def run(self):
        """Main polling loop"""
        logger.info("=" * 60)
        logger.info("Telegram Bot Poller Started")
        logger.info("=" * 60)
        logger.info(f"Bot Token: {TELEGRAM_BOT_TOKEN[:10]}...")
        logger.info(f"Endpoint: {DATABRICKS_SERVING_ENDPOINT}")
        logger.info(f"Poll Interval: {POLL_INTERVAL}s")
        logger.info("=" * 60)
        
        # Delete webhook if it exists
        try:
            await self.client.get(f"{TELEGRAM_API_URL}/deleteWebhook")
            logger.info("Webhook deleted (if any)")
        except:
            pass
        
        while True:
            try:
                # Get new updates
                updates = await self.get_updates()
                
                if updates:
                    logger.info(f"Received {len(updates)} new updates")
                    
                    # Process each update
                    for update in updates:
                        await self.process_update(update)
                
                # Wait before next poll (only if not using long polling timeout)
                await asyncio.sleep(POLL_INTERVAL)
                
            except KeyboardInterrupt:
                logger.info("Stopping poller...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {str(e)}")
                await asyncio.sleep(5)  # Wait before retrying
        
        await self.client.aclose()
        logger.info("Poller stopped")


async def main():
    """Entry point"""
    poller = TelegramPoller()
    await poller.run()


if __name__ == "__main__":
    asyncio.run(main())

