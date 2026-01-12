# Data Channel Commands

The WebRTC-RTMP bridge supports remote control via WebRTC data channels.

## Available Commands

### Start Recording
```json
{"action": "start"}
```
Starts recording to all configured RTMP URLs.

**Response:**
```json
{"status": "ok", "action": "start", "urls": ["rtmp://server1/live", "rtmp://server2/live"]}
```

### Stop Recording
```json
{"action": "stop"}
```
Stops all active recorders.

**Response:**
```json
{"status": "ok", "action": "stop"}
```

### Add RTMP URL
```json
{"action": "add_url", "url": "rtmp://newserver.com:1935/live/stream"}
```
Adds a new RTMP destination. If already recording, starts streaming to this URL immediately.

**Response:**
```json
{"status": "ok", "action": "add_url", "url": "rtmp://newserver.com:1935/live/stream"}
```

### Remove RTMP URL
```json
{"action": "remove_url", "url": "rtmp://server.com:1935/live/stream"}
```
Removes an RTMP destination and stops its recorder.

**Response:**
```json
{"status": "ok", "action": "remove_url", "url": "rtmp://server.com:1935/live/stream"}
```

### List URLs
```json
{"action": "list_urls"}
```
Get list of all configured RTMP URLs.

**Response:**
```json
{"status": "ok", "urls": ["rtmp://server1/live", "rtmp://server2/live"]}
```

### Get Status
```json
{"action": "status"}
```
Get current bridge status.

**Response:**
```json
{
  "status": "ok",
  "recording": true,
  "urls": ["rtmp://server1/live"],
  "tracks": 2,
  "active_recorders": 1
}
```

## JavaScript Example

```javascript
// In your PeerJS sender
const peer = new Peer();

peer.on('open', (id) => {
  // Connect to the receiver
  const conn = peer.connect('receiver-peer-id');
  
  conn.on('open', () => {
    // Add a new RTMP URL
    conn.send(JSON.stringify({
      action: "add_url",
      url: "rtmp://youtube.com/live/stream-key"
    }));
    
    // Start recording
    conn.send(JSON.stringify({action: "start"}));
    
    // Get status
    conn.send(JSON.stringify({action: "status"}));
  });
  
  conn.on('data', (data) => {
    const response = JSON.parse(data);
    console.log('Response:', response);
  });
  
  // Now add your media stream
  navigator.mediaDevices.getUserMedia({video: true, audio: true})
    .then(stream => {
      const call = peer.call('receiver-peer-id', stream);
    });
});
```

## Multistreaming Example

```javascript
// Stream to multiple platforms simultaneously
conn.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://a.rtmp.youtube.com/live2/YOUR_KEY"
}));

conn.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://live.twitch.tv/app/YOUR_KEY"
}));

conn.send(JSON.stringify({
  action: "add_url",
  url: "rtmp://live-api-s.facebook.com:80/rtmp/YOUR_KEY"
}));

// Start streaming to all platforms
conn.send(JSON.stringify({action: "start"}));
```
