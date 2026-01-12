# WebRTC to RTMP Bridge

A Python-based streaming bridge that receives WebRTC streams and forwards them to RTMP endpoints using `aiortc`. Supports PeerJS signaling, data channel control, and multistreaming to multiple RTMP destinations simultaneously.

## Features

- **PeerJS Signaling**: Automatic WebSocket-based signaling via PeerJS server (no manual SDP copy/paste!)
- **Manual Signaling**: CLI-based SDP offer/answer exchange for custom setups
- **Data Channel Control**: Remote control via WebRTC data channels (start/stop, add/remove RTMP URLs)
- **Multistreaming**: Stream to multiple RTMP destinations simultaneously (YouTube, Twitch, Facebook, etc.)
- **Async Recording**: Each RTMP destination runs independently in parallel
- **Auto-shutdown**: Gracefully stops when all media tracks end
- **Docker Support**: Includes NGINX RTMP server for testing

## Quick Start

### PeerJS Mode (Recommended)

```bash
# Install dependencies
pip install -r requirements.txt

# Run with PeerJS signaling
python main.py --peerjs --rtmp-url rtmp://localhost:1935/live/stream
```

You'll get a Peer ID like `a1b2c3d4-e5f6-7890-abcd-ef1234567890`. Share this with your sender, and they can connect automatically - no manual SDP exchange needed!

### Docker Compose

```bash
# Start bridge, NGINX RTMP server, and stunnel for RTMPS
docker-compose up -d
```

The Docker setup includes:
- **Stunnel**: TLS proxy for RTMPS forwarding (Facebook, YouTube on port 443)
- **NGINX RTMP**: Local RTMP server with stats at http://localhost:8080/stat
- **WebRTC Bridge**: Python bridge for receiving WebRTC streams

**RTMPS Support via Stunnel:**

The stack now supports RTMPS! Stream format in your dashboard:

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
- `--peerjs-port`: PeerJS server port (default: 443)

**Example with custom PeerJS server:**
```bash
python main.py --peerjs --peerjs-host your-server.com --peerjs-port 9000 --peer-id my-receiver
```

### 2. Manual Mode (File-based)

```bash
# Save offer to file
python main.py --rtmp-url rtmp://localhost:1935/live/stream --offer-file offer.json
```

### 3. Manual Mode (Pipe)

```bash
# Pipe offer from stdin
cat offer.json | python main.py --rtmp-url rtmp://localhost:1935/live/stream
```

## Data Channel Control

Control the bridge remotely via WebRTC data channels. See [DATA_CHANNEL_API.md](DATA_CHANNEL_API.md) for full API documentation.

**Available Commands:**

```javascript
// Start recording
conn.send(JSON.stringify({action: "start"}));

// Stop recording
conn.send(JSON.stringify({action: "stop"}));

// Add RTMP URL (multistreaming)
conn.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://live.twitch.tv/app/YOUR_KEY"
}));

// Remove RTMP URL
conn.send(JSON.stringify({
  action: "remove_url",
  url: "rtmp://server.com/live/stream"
}));

// Get status
conn.send(JSON.stringify({action: "status"}));

// List URLs
conn.send(JSON.stringify({action: "list_urls"}));
```

## Multistreaming Example

Stream to multiple platforms simultaneously:

```javascript
const peer = new Peer();
const conn = peer.connect('your-peer-id');

conn.on('open', () => {
  // Add multiple destinations
  conn.send(JSON.stringify({
    action: "add_url",
    url: "rtmp://a.rtmp.youtube.com/live2/YOUR_KEY"
  }));
  
  conn.send(JSON.stringify({
    action: "add_url",
    url: "rtmp://live.twitch.tv/app/YOUR_KEY"
  }));
  
  // Start streaming to all
  conn.send(JSON.stringify({action: "start"}));
});
```

## Testing the Stream

View the RTMP stream:

```bash
# Using ffplay
ffplay rtmp://localhost:1935/live/stream

# Using VLC
vlc rtmp://localhost:1935/live/stream
```

Monitor NGINX RTMP stats: http://localhost:8080/stat

## Configuration

### Command Line Options

| Option | Description | Default |
|--------|-------------|---------|
| `--rtmp-url` | Initial RTMP destination URL | `rtmp://localhost/live/stream` |
| `--peerjs` | Enable PeerJS signaling mode | Off |
| `--peer-id` | Custom Peer ID (PeerJS mode) | Random UUID |
| `--peerjs-host` | PeerJS server host | `0.peerjs.com` |
| `--peerjs-port` | PeerJS server port | `443` |
| `--offer-file` | Path to offer JSON file (manual mode) | None |

## Architecture

### PeerJS Mode
```
Browser → PeerJS Server (WebSocket) → Bridge → RTMP Server(s)
         ↓                           ↓
    Media Tracks              Data Channel Control
```

### Manual Mode
```
WebRTC Client → SDP Exchange (File/CLI) → aiortc RTCPeerConnection
                                          ↓
                                    Media Tracks
                                          ↓
                                   MediaRecorder(s) → RTMP Server(s)
```

## Requirements

- Python 3.11+
- aiortc, aiohttp, av (PyAV), websockets
- ffmpeg/libav system libraries
- RTMP server (NGINX included in Docker setup)

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