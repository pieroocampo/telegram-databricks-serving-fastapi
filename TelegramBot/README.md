# Telegram Bot - Databricks Integration

This FastAPI application serves as a bridge between a Telegram bot and a Databricks serving endpoint. It receives messages from Telegram users, processes them through a Databricks AI model, and sends the responses back to Telegram.

## Features

- **Polling-based**: Polls the Telegram bot for new messages. Needed because Telegram can't send Auth headers and we don't want to open up the FastAPI to everyone.
- **Databricks Integration**: Queries a Databricks serving endpoint for AI responses
- **FastAPI**: Modern, high-performance Python web framework
- **Databricks App Ready**: Configured for deployment as a Databricks App

## Architecture

```
Telegram User → Telegram API → FastAPI Webhook → Databricks Endpoint → FastAPI → Telegram API → User
```

## Setup

### Prerequisites

1. A Telegram bot token (already configured)
2. A Databricks workspace with a serving endpoint deployed
3. Databricks CLI installed (for deployment)

### Configuration

1. **Update the endpoint name** in `app.yaml`:
   ```yaml
   env:
     - name: DATABRICKS_SERVING_ENDPOINT
       value: "your-endpoint-name"  # Replace with your actual endpoint name
   ```

2. The Telegram bot token is already configured in `app.yaml`

## Local Development

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set environment variables:
   ```bash
   export TELEGRAM_BOT_TOKEN="<Your Telegram Token>"
   export DATABRICKS_SERVING_ENDPOINT="<Your endpoint name>"
   export DATABRICKS_HOST="https://your-workspace.cloud.databricks.com"
   export DATABRICKS_TOKEN="your-token"
   ```

3. Run the app:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000 --reload
   ```

4. Test locally with a tunnel (e.g., ngrok):
   ```bash
   ngrok http 8000
   ```

## Deployment to Databricks

### Using Databricks CLI

1. Install the Databricks CLI:
   ```bash
   pip install databricks-cli
   ```

2. Configure authentication:
   ```bash
   databricks configure
   ```

3. Deploy the app:
   ```bash
   databricks apps create telegram-bot
   databricks apps deploy telegram-bot --source-dir .
   ```

### Using Databricks UI

1. Go to your Databricks workspace
2. Navigate to **Apps** in the sidebar
3. Click **Create App**
4. Choose **Upload files** and upload all files from this directory
5. Click **Deploy**

## How It Works

1. **User sends message**: A user sends a message to your Telegram bot
2. **Databricks app polls for new messages**: Sends a GET request to the bot's `/getUpdates`
3. **Message processing**: The app extracts the message text
4. **Query Databricks**: The message is sent to your Databricks serving endpoint
5. **Get response**: The model's response is received
6. **Send to Telegram**: The response is sent back to the user via Telegram API

## Customization

### Modifying the Model Query

To customize how messages are sent to your Databricks endpoint, edit the `send_to_databricks_endpoint()` function in `main.py`:

```python
async def send_to_databricks_endpoint(message: str) -> str:
    # Customize the query format here
    response = w.serving_endpoints.query(
        name=DATABRICKS_SERVING_ENDPOINT,
        messages=[
            ChatMessage(
                role=ChatMessageRole.USER,
                content=message
            )
        ]
    )
    return response.choices[0].message.content
```

### Adding Commands

To add Telegram bot commands (like `/start` or `/help`):

```python
@app.post("/webhook")
async def telegram_webhook(request: Request):
    data = await request.json()
    message = data.get("message", {})
    text = message.get("text", "")
    
    if text.startswith("/start"):
        # Handle /start command
        await send_telegram_message(chat_id, "Welcome! Send me a message.")
        return {"status": "ok"}
    
    # Process regular messages...
```

## Monitoring

Check the logs in Databricks to monitor your app:
1. Go to **Apps** in Databricks
2. Click on your app
3. View the **Logs** tab

## Troubleshooting

### Databricks endpoint errors
- Verify the endpoint name in `app.yaml`
- Check that the endpoint is deployed and ready
- Ensure your app's service principal has access to the endpoint

### Telegram API errors
- Verify the bot token is correct
- Review Telegram API rate limits

## Security Notes
- The Telegram bot token is stored in `app.yaml`. In production, consider using Databricks secrets
- Databricks Apps are only accessible to authenticated Databricks users by default

## References

- [Telegram Bot API Documentation](https://core.telegram.org/bots/api)
- [Databricks Apps Documentation](https://docs.databricks.com/aws/en/dev-tools/databricks-apps/)
- [Databricks Model Serving](https://docs.databricks.com/aws/en/machine-learning/model-serving/create-manage-serving-endpoints)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

