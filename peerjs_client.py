import asyncio
import json
import logging
import websockets
import uuid
from typing import Optional, Callable

logger = logging.getLogger(__name__)


class PeerJSClient:
    """PeerJS-compatible WebSocket signaling client"""
    
    def __init__(self, 
                 host: str = "0.peerjs.com",
                 port: int = 443,
                 path: str = "/",
                 secure: bool = True,
                 peer_id: Optional[str] = None):
        self.host = host
        self.port = port
        self.path = path
        self.secure = secure
        self.peer_id = peer_id or self._generate_id()
        self.ws = None
        self.on_offer = None
        self.on_answer = None
        self.on_candidate = None
        
    def _generate_id(self) -> str:
        """Generate a random peer ID"""
        return str(uuid.uuid4())
    
    async def connect(self):
        """Connect to PeerJS server"""
        protocol = "wss" if self.secure else "ws"
        # PeerJS cloud server URL format: wss://host:port/peerjs?key=peerjs&id=peer_id&token=random
        token = str(uuid.uuid4())
        url = f"{protocol}://{self.host}:{self.port}{self.path}peerjs?key=peerjs&id={self.peer_id}&token={token}"
        
        logger.info(f"Connecting to PeerJS server: {url}")
        self.ws = await websockets.connect(url)
        logger.info(f"Connected! Your Peer ID: {self.peer_id}")
        
        # Start listening for messages
        asyncio.create_task(self._listen())
        
    async def _listen(self):
        """Listen for incoming messages from PeerJS server"""
        try:
            async for message in self.ws:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError:
                    logger.warning(f"Invalid JSON message: {message}")
        except websockets.exceptions.ConnectionClosed:
            logger.info("WebSocket connection closed")
        except Exception as e:
            logger.error(f"Error in listen loop: {e}", exc_info=True)
    
    async def _handle_message(self, data: dict):
        """Handle incoming PeerJS message"""
        msg_type = data.get("type")
        
        logger.debug(f"Received message: {msg_type}")
        
        if msg_type == "OPEN":
            # Server confirmed connection
            logger.info("PeerJS server connection established")
            
        elif msg_type == "OFFER":
            # Received an offer from remote peer
            payload = data.get("payload", {})
            sdp = payload.get("sdp")
            logger.debug(f"Offer payload: {payload}")
            if sdp and self.on_offer:
                logger.info(f"Received offer from peer: {data.get('src')}")
                await self.on_offer(sdp, data.get('src'))
                
        elif msg_type == "ANSWER":
            # Received an answer from remote peer
            payload = data.get("payload", {})
            sdp = payload.get("sdp")
            if sdp and self.on_answer:
                logger.info(f"Received answer from peer: {data.get('src')}")
                await self.on_answer(sdp, data.get('src'))
                
        elif msg_type == "CANDIDATE":
            # Received ICE candidate
            payload = data.get("payload", {})
            candidate = payload.get("candidate")
            if candidate and self.on_candidate:
                logger.info(f"Received ICE candidate from peer: {data.get('src')}")
                await self.on_candidate(candidate, data.get('src'))
                
        elif msg_type == "LEAVE":
            logger.info(f"Peer left: {data.get('src')}")
            
        elif msg_type == "ERROR":
            logger.error(f"PeerJS error: {data}")
            
        else:
            logger.debug(f"Unhandled message type: {msg_type}")
    
    async def send_answer(self, answer_sdp: dict, dst_peer_id: str):
        """Send answer SDP to remote peer"""
        message = {
            "type": "ANSWER",
            "dst": dst_peer_id,
            "payload": {
                "sdp": answer_sdp,
                "type": "answer"
            }
        }
        await self.ws.send(json.dumps(message))
        logger.info(f"Sent answer to peer: {dst_peer_id}")
    
    async def send_candidate(self, candidate: dict, dst_peer_id: str):
        """Send ICE candidate to remote peer"""
        message = {
            "type": "CANDIDATE",
            "dst": dst_peer_id,
            "payload": {
                "candidate": candidate,
                "type": "candidate"
            }
        }
        await self.ws.send(json.dumps(message))
        logger.debug(f"Sent ICE candidate to peer: {dst_peer_id}")
    
    async def close(self):
        """Close WebSocket connection"""
        if self.ws:
            await self.ws.close()
            logger.info("PeerJS client disconnected")
