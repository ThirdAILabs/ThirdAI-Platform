import asyncio
import json
from threading import Thread

from database import schema
from database.session import get_session

from .websocket_connection_manager import WebsocketConnectionManager

manager = WebsocketConnectionManager()


def notify_model_change(target, event_type):
    def run_async():
        async def notify_clients():
            # Send a message to all connected WebSocket clients
            session = next(get_session())
            data = session.query(schema.Model).get(target.id)

            model = {"name": data.name, "event": event_type}
            json_data = json.dumps(model)

            # logger.info(f"Notifying the frontend about the model {model['name']}")

            await manager.broadcast(json_data)
            session.close()

        asyncio.run(notify_clients())

    # Run the asynchronous task in a separate thread
    thread = Thread(target=run_async)
    thread.start()
