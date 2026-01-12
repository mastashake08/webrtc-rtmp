# WebRTC to RTMP Bridge

A Python-based streaming bridge that receives WebRTC streams and forwards them to RTMP endpoints using `aiortc`.

## Features

- **Receive-only mode**: Accepts WebRTC streams from browsers or clients
- **Text-based signaling**: Simple CLI interface for SDP offer/answer exchange
- **RTMP forwarding**: Automatically records and forwards streams to RTMP servers
- **Docker support**: Includes NGINX RTMP server for complete streaming setup
- **Auto-shutdown**: Gracefully stops when all tracks end

## Quick Start

### Using Docker Compose (Recommended)

```bash
# Start the bridge and NGINX RTMP server
docker-compose up --build

# The service will prompt you to paste the WebRTC offer
```

### Local Installation

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run the bridge
python main.py --rtmp-url rtmp://localhost:1935/live/stream
```

## Usage

1. **Start the receiver**:
   ```bash
   python main.py --rtmp-url rtmp://your-server:1935/live/stream
   ```

2. **Paste the WebRTC offer** (JSON format) from your client and press Enter twice

3. **Copy the answer SDP** displayed in the CLI and send it back to your client

4. **Paste ICE candidates** (one JSON per line, empty line to finish)

5. The stream will automatically forward to your RTMP server

## Testing the Stream

Once running, view the RTMP stream with:

```bash
# Using ffplay
ffplay rtmp://localhost:1935/live/stream

# Using VLC
vlc rtmp://localhost:1935/live/stream
```

Monitor NGINX RTMP stats at: http://localhost:8080/stat

## Configuration

### Command Line Options

- `--rtmp-url`: RTMP destination URL (default: `rtmp://localhost/live/stream`)

### Docker Environment Variables

Edit `docker-compose.yml` to change the RTMP URL:

```yaml
environment:
  - RTMP_URL=rtmp://nginx-rtmp:1935/live/stream
```

## Architecture

```
WebRTC Client → SDP Exchange (CLI) → aiortc RTCPeerConnection
                                      ↓
                                 Media Tracks
                                      ↓
                                MediaRecorder → RTMP Server
```

## Requirements

- Python 3.11+
- ffmpeg/libav system libraries
- RTMP server (included in Docker setup)

## License

MIT