# WebRTC to RTMP Bridge

High-performance Python streaming bridge that receives WebRTC streams and forwards them to RTMP/RTMPS endpoints. Built with `aiortc` and `PyAV` for professional-quality multicast streaming.

## Features

- **PeerJS Signaling**: Automatic WebSocket-based signaling (no manual SDP exchange)
- **Data Channel Control**: Real-time control via WebRTC data channels
- **Multistreaming**: Stream to unlimited RTMP destinations simultaneously
- **HD Video Processing**: High-quality H.264 encoding with AAC audio
- **RTMPS Support**: Secure streaming via stunnel TLS proxy
- **Docker Stack**: Complete NGINX RTMP + stunnel infrastructure
- **Dynamic URL Management**: Add/remove destinations during live streaming
- **Auto-shutdown**: Graceful cleanup when streams end

## Video Quality Settings

- **Video Codec**: H.264 High Profile Level 4.1
- **Video Bitrate**: 6 Mbps (1080p streaming)
- **Preset**: `veryfast` (optimized for live streaming)
- **GOP Size**: 60 frames (2 second keyframe interval)
- **Audio Codec**: AAC @ 256k, 48kHz stereo
- **Container**: FLV (standard for RTMP)

## Quick Start

### Standalone Mode (Direct RTMP)

```bash
# Install dependencies
pip install -r requirements.txt

# Run bridge (no default URL - add via data channel)
python main.py --peerjs
```

**Output:**
```
Connected! Your Peer ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
```

Share this Peer ID with your browser client to connect.

### Docker Compose (RTMPS Support)

```bash
# Start full stack: stunnel + NGINX RTMP + bridge
docker-compose up -d

# Check status
docker-compose ps

# View logs
docker-compose logs -f webrtc-rtmp-bridge
```

## RTMPS Streaming (Facebook, YouTube)

The Docker stack provides RTMPS support via stunnel:

**Facebook Live:**
```
rtmp://nginx-rtmp:1935/facebook/FB-YOUR-STREAM-KEY
```

**YouTube:**
```
rtmp://nginx-rtmp:1935/youtube/YOUR-STREAM-KEY
```

**How it works:**
1. WebRTC bridge sends to NGINX RTMP (port 1935)
2. NGINX forwards to stunnel (internal ports 1936/1937)
3. Stunnel wraps in TLS and forwards to platform RTMPS endpoints (port 443)

For direct RTMP without TLS, use standard URLs:
```
rtmp://live-api-s.facebook.com:80/rtmp/YOUR_KEY
rtmp://a.rtmp.youtube.com/live2/YOUR_KEY
```

### Manual Signaling Mode

```bash
# For custom signaling servers
python main.py --rtmp-url rtmp://localhost:1935/live/stream --offer-file offer.json
```

## Usage Modes

### 1. PeerJS Mode (Automatic Signaling)

```bash
python main.py --peerjs --rtmp-url rtmp://localhost:1935/live/stream
```

**Options:**
- `--peer-id YOUR_ID`: Use custom Peer ID (optional, random by default)
- `--peerjs-host`: PeerJS server host (default: 0.peerjs.com)

**Facebook Live (with RTMPS):**
```
rtmp://nginx-rtmp:1935/facebook/FB-YOUR-STREAM-KEY
```

**YouTube (with RTMPS):**
```
rtmp://nginx-rtmp:1935/youtube/YOUR-STREAM-KEY
```

**Twitch (direct RTMP):**
```
rtmp://live.twitch.tv/app/YOUR-STREAM-KEY
```

### Traffic Flow (RTMPS)
```
Browser → WebRTC Bridge → NGINX RTMP → stunnel → Facebook/YouTube (port 443)
```

## Data Channel API

Control the bridge in real-time via WebRTC data channels:

### Start Recording
```javascript
dataChannel.send(JSON.stringify({ action: "start" }));
// Response: { status: "ok", action: "start", urls: [...] }
```

### Stop Recording
```javascript
dataChannel.send(JSON.stringify({ action: "stop" }));
```

### Add RTMP Destination
```javascript
dataChannel.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://live.twitch.tv/app/YOUR_KEY"
}));
```

### Remove RTMP Destination
```javascript
dataChannel.send(JSON.stringify({
  action: "remove_url",
  url: "rtmp://server.com/live/stream"
}));
```

### Get Status
```javascript
dataChannel.send(JSON.stringify({ action: "status" }));
// Response: { status: "ok", recording: true, urls: [...], tracks: 2 }
```

### List URLs
```javascript
dataChannel.send(JSON.stringify({ action: "list_urls" }));
```

## Multistreaming Example

Stream to multiple platforms simultaneously:

```javascript
// Add destinations
dataChannel.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://a.rtmp.youtube.com/live2/YOUTUBE_KEY"
}));

dataChannel.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://live.twitch.tv/app/TWITCH_KEY"
}));

// Start streaming to all destinations
dataChannel.send(JSON.stringify({ action: "start" }));
```

## Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--peerjs` | Enable PeerJS signaling mode | Off |
| `--peer-id` | Custom Peer ID | Random UUID |
| `--peerjs-host` | PeerJS server host | `0.peerjs.com` |
| `--peerjs-port` | PeerJS server port | `443` |
| `--rtmp-url` | Initial RTMP destination (optional) | None |
| `--offer-file` | Path to offer JSON file (manual mode) | None |

## Docker Services

### stunnel
- **Purpose**: TLS proxy for RTMPS
- **Ports**: 1936 (Facebook), 1937 (YouTube)
- **Config**: `stunnel.conf`

### nginx-rtmp
- **Purpose**: RTMP server and router
- **Ports**: 1935 (RTMP), 8080 (stats)
- **Stats**: http://localhost:8080/stat

### webrtc-rtmp-bridge
- **Purpose**: WebRTC receiver
- **Mode**: PeerJS signaling
- **Depends on**: nginx-rtmp, stunnel

## Testing

### View RTMP Stream
```bash
# Using ffplay
ffplay rtmp://localhost:1935/live/stream

# Using VLC
vlc rtmp://localhost:1935/live/stream
```

### Check Docker Logs
```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f webrtc-rtmp-bridge
```

## Architecture

```
┌─────────────┐
│   Browser   │
│  (Sender)   │
└──────┬──────┘
       │ WebRTC (PeerJS)
       ▼
┌─────────────────────┐
│  Python Bridge      │
│  (aiortc + PyAV)    │
│  • H.264 6Mbps      │
│  • AAC 256k         │
└──────┬──────────────┘
       │ RTMP
       ▼
┌─────────────────────┐      ┌──────────────┐
│   NGINX RTMP        │─────→│   stunnel    │──→ Facebook :443
│   (router)          │      │   (TLS)      │──→ YouTube :443
└─────────────────────┘      └──────────────┘
       │
       └──→ Direct RTMP (Twitch, etc.)
```

## Requirements

- Python 3.11+
- aiortc, PyAV, websockets
- ffmpeg/libav (system libraries)
- Docker & Docker Compose (for RTMPS)

## Troubleshooting

### "Blocked plain RTMP" Error
Facebook requires RTMPS. Use Docker with stunnel or direct port 80:
```
rtmp://live-api-s.facebook.com:80/rtmp/YOUR_KEY
```

### Connection Refused
Ensure NGINX RTMP is running:
```bash
docker-compose ps nginx-rtmp
```

### No Video/Audio Tracks
Check browser console - media stream must include tracks before connecting.

## Development

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run with debug logging
python main.py --peerjs
```

## License

MIT