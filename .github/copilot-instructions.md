# WebRTC to RTMP Bridge Project

## Project Overview
This is a Python-based streaming bridge that receives WebRTC streams and forwards them to RTMP endpoints using the `aiortc` library.

## Architecture

### Core Components
- **main.py**: Entry point for the streaming bridge application (currently empty - to be implemented)
- Uses `aiortc` for WebRTC protocol handling
- Streams are received via WebRTC and transcoded/forwarded to RTMP destinations

### Key Dependencies
- **aiortc**: Python WebRTC implementation for receiving streams
- Requires system dependencies for media processing (likely ffmpeg/libav)

## Development Environment

### Setup
```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install aiortc
```

### Python Environment
- Uses virtual environment (`.venv/`)
- Python 3.x required (aiortc compatibility)
- No requirements.txt yet - dependencies managed via direct pip install

## Implementation Guidance

### When implementing main.py:
1. **WebRTC Server Setup**: Create an aiortc `RTCPeerConnection` to accept incoming streams
2. **Media Track Handling**: Subscribe to incoming video/audio tracks from WebRTC connection
3. **RTMP Forwarding**: Use ffmpeg subprocess or aiortc's media recorder to forward to RTMP
4. **Signaling**: Implement WebSocket or HTTP server for WebRTC SDP exchange

### Typical Flow
```
WebRTC Client → aiortc RTCPeerConnection → Media Tracks → FFmpeg/RTMP Output → RTMP Server
```

### Common Patterns for aiortc Projects
- Async/await throughout (aiortc is asyncio-based)
- Use `MediaStreamTrack` for custom processing pipelines
- Handle ICE candidates and SDP offer/answer exchanges
- Manage connection lifecycle (open, close, error states)

## Configuration (To Be Added)
Consider implementing:
- RTMP destination URL configuration
- WebRTC signaling server port/endpoint
- Media encoding parameters (bitrate, resolution, codec)
- STUN/TURN server configuration for NAT traversal

## Testing & Debugging
- Test WebRTC connections with browser clients (Chrome/Firefox)
- Monitor ffmpeg output for encoding issues
- Check RTMP server reception (use VLC or ffplay to verify stream)
- Enable aiortc debug logging: `logging.basicConfig(level=logging.DEBUG)`
