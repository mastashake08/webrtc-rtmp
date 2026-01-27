import asyncio
import logging
import json
import sys
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaRecorder
import argparse
from peerjs_client import PeerJSClient

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)


class WebRTCReceiver:
    def __init__(self, rtmp_url=None, peerjs_client=None, get_remote_peer_id=None):
        self.pc = RTCPeerConnection()
        self.rtmp_urls = [rtmp_url] if rtmp_url else []
        self.recorders = {}  # {rtmp_url: MediaRecorder}
        self.tracks = []
        self.recording_started = False
        self.datachannel = None
        self.peerjs_client = peerjs_client
        self.get_remote_peer_id = get_remote_peer_id
        
    async def setup(self):
        """Setup peer connection event handlers"""
        
        @self.pc.on("datachannel")
        async def on_datachannel(channel):
            logger.info(f"Data channel opened: {channel.label}")
            self.datachannel = channel
            
            @channel.on("message")
            async def on_message(message):
                await self.handle_command(message)
        
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"✓ Receiving {track.kind} track (total tracks: {len(self.tracks) + 1})")
            self.tracks.append(track)
            
            # Notify frontend about track
            self.send_response({
                "status": "ok",
                "message": f"Receiving {track.kind} track",
                "tracks": len(self.tracks)
            })
            
            # If recording is already started, add track to active recorders
            if self.recording_started:
                for rtmp_url, recorder in self.recorders.items():
                    if recorder:
                        recorder.addTrack(track)
                        logger.info(f"Added {track.kind} track to {rtmp_url}")
            
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track {track.kind} ended")
                if track in self.tracks:
                    self.tracks.remove(track)
                
                # Stop recording when all tracks have ended
                if len(self.tracks) == 0:
                    logger.info("All tracks ended, stopping all recorders")
                    await self.stop_recording()
                
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                await self.pc.close()
        
        @self.pc.on("icecandidate")
        async def on_icecandidate(candidate):
            # Send ICE candidates to remote peer via PeerJS
            if candidate and self.peerjs_client and self.get_remote_peer_id:
                remote_id = self.get_remote_peer_id()
                if remote_id:
                    await self.peerjs_client.send_candidate({
                        "candidate": candidate.candidate,
                        "sdpMid": candidate.sdpMid,
                        "sdpMLineIndex": candidate.sdpMLineIndex
                    }, remote_id)
    
    async def handle_command(self, message):
        """Handle data channel commands"""
        try:
            cmd = json.loads(message)
            action = cmd.get("action")
            
            logger.info(f"Received command: {action}")
            
            if action == "start":
                await self.start_recording()
                self.send_response({"status": "ok", "action": "start", "urls": self.rtmp_urls})
                
            elif action == "stop":
                await self.stop_recording()
                self.send_response({"status": "ok", "action": "stop"})
                
            elif action == "add_url":
                url = cmd.get("url")
                if url:
                    url = url.strip()  # Remove leading/trailing whitespace
                    await self.add_rtmp_url(url)
                    self.send_response({"status": "ok", "action": "add_url", "url": url})
                else:
                    self.send_response({"status": "error", "message": "URL required"})
                    
            elif action == "remove_url":
                url = cmd.get("url")
                if url:
                    url = url.strip()  # Remove leading/trailing whitespace
                    await self.remove_rtmp_url(url)
                    self.send_response({"status": "ok", "action": "remove_url", "url": url})
                else:
                    self.send_response({"status": "error", "message": "URL required"})
                    
            elif action == "list_urls":
                self.send_response({"status": "ok", "urls": self.rtmp_urls})
                
            elif action == "status":
                self.send_response({
                    "status": "ok",
                    "recording": self.recording_started,
                    "urls": self.rtmp_urls,
                    "tracks": len(self.tracks),
                    "active_recorders": len(self.recorders)
                })
            else:
                self.send_response({"status": "error", "message": f"Unknown action: {action}"})
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON command: {message}")
            self.send_response({"status": "error", "message": "Invalid JSON"})
        except Exception as e:
            logger.error(f"Error handling command: {e}", exc_info=True)
            self.send_response({"status": "error", "message": str(e)})
    
    def send_response(self, response):
        """Send response back through data channel"""
        if self.datachannel and self.datachannel.readyState == "open":
            self.datachannel.send(json.dumps(response))
            logger.debug(f"Sent response: {response}")
    
    async def add_rtmp_url(self, url):
        """Add a new RTMP URL for multistreaming"""
        url = url.strip()  # Ensure no whitespace
        if url not in self.rtmp_urls:
            self.rtmp_urls.append(url)
            logger.info(f"Added RTMP URL: {url}")
            
            # If already recording, start recorder for this URL
            if self.recording_started and self.tracks:
                await self._start_recorder(url)
    
    async def remove_rtmp_url(self, url):
        """Remove an RTMP URL"""
        if url in self.rtmp_urls:
            self.rtmp_urls.remove(url)
            
            # Stop and remove recorder for this URL
            if url in self.recorders:
                recorder = self.recorders[url]
                if recorder:
                    try:
                        await recorder.stop()
                        logger.info(f"Stopped recorder for {url}")
                    except Exception as e:
                        logger.warning(f"Error stopping recorder for {url}: {e}")
                del self.recorders[url]
    
    async def _start_recorder(self, url):
        """Start a single recorder for a URL"""
        try:
            logger.info(f"Attempting to connect to: {url}")
            logger.info(f"Available tracks: {len(self.tracks)}")
            
            # Log track details to see actual resolutions
            for track in self.tracks:
                logger.info(f"  - Track: {track.kind} (id: {track.id})")
                if track.kind == 'video':
                    # Try to get video frame to determine actual resolution
                    try:
                        frame = await track.recv()
                        logger.info(f"    Video frame size: {frame.width}x{frame.height}")
                    except Exception as e:
                        logger.warning(f"    Could not read video frame: {e}")
            
            # Validate URL format
            if not url.startswith('rtmp://'):
                raise ValueError(f"Invalid RTMP URL format: {url}")
            
            # MediaRecorder will transcode WebRTC (VP8/Opus) to RTMP (H.264/AAC)
            logger.info(f"Creating MediaRecorder with FLV format...")
            options = {
                'video_bitrate': '12000k',  # Video quality (12 Mbps for 4K)
                'audio_bitrate': '192k',    # Audio quality (192 kbps)
            }
            recorder = MediaRecorder(url, format='flv', options=options)
            logger.info(f"MediaRecorder created successfully")
            
            # Add all existing tracks
            for track in self.tracks:
                logger.info(f"Adding {track.kind} track to recorder...")
                recorder.addTrack(track)
                logger.info(f"✓ Added {track.kind} track to recorder for {url}")
            
            if not self.tracks:
                logger.warning(f"⚠️  No tracks available to record for {url}")
                self.send_response({"status": "error", "message": "No media tracks available"})
                return
            
            logger.info(f"Starting recorder...")
            await recorder.start()
            logger.info(f"Recorder started successfully")
            self.recorders[url] = recorder
            logger.info(f"✓ Started recording to {url}")
            self.send_response({"status": "ok", "message": f"Recording started to {url}"})
            
        except FileNotFoundError as e:
            error_msg = f"Cannot connect to RTMP server at {url}. Make sure the server is running and accessible."
            logger.error(f"✗ {error_msg}: {e}")
            self.send_response({"status": "error", "message": error_msg})
        except Exception as e:
            logger.error(f"✗ Failed to start recorder for {url}: {e}", exc_info=True)
            self.send_response({"status": "error", "message": f"Failed to start {url}: {str(e)}"})
    
    async def start_recording(self):
        """Start recording to all RTMP URLs"""
        if not self.rtmp_urls:
            logger.warning("No RTMP URLs configured")
            return
            
        if self.recording_started:
            logger.info("Recording already started")
            return
        
        logger.info(f"Starting recording to {len(self.rtmp_urls)} destination(s)")
        
        # Start all recorders in parallel
        tasks = [self._start_recorder(url) for url in self.rtmp_urls]
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.recording_started = True
        logger.info(f"Recording started to {len(self.recorders)} destination(s)")
    
    async def stop_recording(self):
        """Stop all recorders"""
        if not self.recording_started:
            logger.info("Recording not started")
            return
        
        logger.info(f"Stopping {len(self.recorders)} recorder(s)")
        
        # Stop all recorders in parallel
        tasks = []
        for url, recorder in list(self.recorders.items()):
            if recorder:
                tasks.append(self._stop_recorder_safe(url, recorder))
        
        await asyncio.gather(*tasks, return_exceptions=True)
        
        self.recorders.clear()
        self.recording_started = False
        logger.info("All recorders stopped")
    
    async def _stop_recorder_safe(self, url, recorder):
        """Safely stop a recorder with error handling"""
        try:
            await recorder.stop()
            logger.info(f"✓ Stopped recorder for {url}")
        except Exception as e:
            logger.warning(f"✗ Error stopping recorder for {url}: {e}")
                
    async def receive_offer(self, offer_sdp):
        """Process incoming offer and create answer"""
        await self.setup()
        
        # Set remote description from offer
        offer = RTCSessionDescription(sdp=offer_sdp["sdp"], type=offer_sdp["type"])
        
        # Check if this is a media offer
        if "m=audio" not in offer.sdp and "m=video" not in offer.sdp:
            logger.warning("⚠️  Received datachannel-only offer (no media tracks)")
            logger.warning("⚠️  This bridge requires audio/video media streams")
            logger.warning("⚠️  Make sure your sender is sharing getUserMedia() tracks, not just datachannel")
            # Still process it to be polite, but no media will flow
        
        # Set remote description - aiortc will automatically create matching transceivers
        await self.pc.setRemoteDescription(offer)
        
        # Create data channel for commands
        self.datachannel = self.pc.createDataChannel("commands")
        logger.info(f"Created data channel: {self.datachannel.label}")
        
        # Set up data channel handlers
        @self.datachannel.on("open")
        async def on_open():
            logger.info("Data channel opened!")
        
        @self.datachannel.on("message")
        async def on_message(message):
            await self.handle_command(message)
        
        @self.datachannel.on("close")
        async def on_close():
            logger.info("Data channel closed")
        
        # Create answer
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        return {
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp
        }
        
    async def add_ice_candidate(self, candidate_data):
        """Add ICE candidate"""
        if candidate_data:
            from aiortc.sdp import candidate_from_sdp
            
            try:
                # Parse the candidate string into an RTCIceCandidate
                candidate_str = candidate_data.get("candidate", "")
                sdp_mid = candidate_data.get("sdpMid")
                sdp_mline_index = candidate_data.get("sdpMLineIndex")
                
                if candidate_str:
                    # Remove "candidate:" prefix if present
                    if candidate_str.startswith("candidate:"):
                        candidate_str = candidate_str[10:]
                    
                    # Parse using aiortc's SDP parser
                    candidate = candidate_from_sdp(candidate_str)
                    candidate.sdpMid = sdp_mid
                    candidate.sdpMLineIndex = sdp_mline_index
                    
                    await self.pc.addIceCandidate(candidate)
                    logger.debug(f"Added ICE candidate: {candidate.type}")
            except Exception as e:
                # ICE candidates are best-effort, connection may work without all of them
                logger.debug(f"Skipping ICE candidate: {e}")
            
    async def close(self):
        """Close connections"""
        await self.stop_recording()
        await self.pc.close()
        logger.info("Peer connection closed")


async def main_peerjs(rtmp_url, peer_id=None, peerjs_host="0.peerjs.com", peerjs_port=443):
    """Run in PeerJS mode - connect to PeerJS server and wait for connections"""
    receiver = None
    peerjs = PeerJSClient(
        host=peerjs_host,
        port=peerjs_port,
        peer_id=peer_id,
        secure=True
    )
    
    remote_peer_id = None
    
    # Handle incoming offers
    async def handle_offer(payload, src_peer_id):
        nonlocal remote_peer_id, receiver
        remote_peer_id = src_peer_id
        
        logger.info(f"Processing offer from peer: {src_peer_id}")
        logger.debug(f"Offer payload type: {type(payload)}, keys: {payload.keys() if isinstance(payload, dict) else 'N/A'}")
        
        # Ensure payload is in the correct format
        if not isinstance(payload, dict):
            logger.error(f"Invalid payload format: {payload}")
            return
        
        # Extract SDP and connectionId from payload
        sdp = payload.get('sdp')
        connection_id = payload.get('connectionId')
        
        if not sdp:
            logger.error(f"No SDP in payload: {payload}")
            return
        
        logger.debug(f"Connection ID: {connection_id}")
        
        # Close previous receiver if it exists
        if receiver is not None:
            logger.info("Closing previous peer connection")
            await receiver.close()
        
        # Create new receiver for this offer
        receiver = WebRTCReceiver(
            rtmp_url=rtmp_url,
            peerjs_client=peerjs,
            get_remote_peer_id=lambda: remote_peer_id
        )
            
        # Process offer and create answer
        answer_sdp = await receiver.receive_offer(sdp)
        
        # Send answer with connectionId preserved for PeerJS routing
        await peerjs.send_answer(answer_sdp, src_peer_id, connection_id)
        logger.info("Answer sent successfully")
        
    # Handle incoming ICE candidates
    async def handle_candidate(candidate, src_peer_id):
        if receiver is not None:
            await receiver.add_ice_candidate(candidate)
        else:
            logger.warning("Received ICE candidate but no receiver exists yet")
    
    # Set up handlers
    peerjs.on_offer = handle_offer
    peerjs.on_candidate = handle_candidate
    
    try:
        await peerjs.connect()
        print(f"\n✓ Connected to PeerJS server")
        print(f"✓ Your Peer ID: {peerjs.peer_id}")
        print(f"\nShare this Peer ID with the sender to start streaming!\n")
        print("Waiting for connections... (Press Ctrl+C to stop)\n")
        
        # Keep running until interrupted
        while True:
            await asyncio.sleep(1)
            # Exit if receiver exists and stream ended
            if receiver is not None:
                if receiver.pc.connectionState == "closed":
                    break
                if len(receiver.tracks) == 0 and receiver.recording_started is False and len(receiver.recorders) > 0:
                    logger.info("Stream ended")
                    break
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await peerjs.close()
        if receiver is not None:
            await receiver.close()


async def main(rtmp_url, offer_file):
    receiver = WebRTCReceiver(rtmp_url)
    
    print("\n=== WebRTC to RTMP Bridge (Receiver Mode) ===")
    print(f"RTMP Output: {rtmp_url}\n")
    
    try:
        # Read offer from file, stdin pipe, or interactive input
        if offer_file:
            print(f"Reading offer from: {offer_file}")
            with open(offer_file, 'r') as f:
                offer_json = json.load(f)
        elif not sys.stdin.isatty():
            # Stdin is piped (e.g., cat offer.json | python main.py)
            print("Reading offer from stdin pipe...")
            offer_text = sys.stdin.read()
            offer_json = json.loads(offer_text.strip())
        else:
            # Interactive input
            print("Paste the WebRTC offer SDP (JSON format) on a single line and press Enter:")
            loop = asyncio.get_event_loop()
            offer_text = await loop.run_in_executor(None, sys.stdin.readline)
            offer_json = json.loads(offer_text.strip())
        
        logger.info("Received offer")
        
        # Process offer and get answer
        answer = await receiver.receive_offer(offer_json)
        
        print("\n=== Answer SDP (copy this back to the client) ===")
        print(json.dumps(answer, indent=2))
        print("=" * 50)
        
        print("\nPaste ICE candidates (JSON, one per line, empty line to finish):\n")
        
        # Read ICE candidates
        loop = asyncio.get_event_loop()
        while True:
            try:
                line = await loop.run_in_executor(None, sys.stdin.readline)
                line = line.strip()
                if line == "":
                    break
                candidate = json.loads(line)
                await receiver.add_ice_candidate(candidate)
                logger.info("Added ICE candidate")
            except json.JSONDecodeError:
                logger.warning("Invalid ICE candidate JSON")
            except Exception:
                break
        
        print("\nWaiting for stream... (Press Ctrl+C to stop)")
        
        # Keep running until connection closes or user interrupts
        try:
            while receiver.pc.connectionState != "closed":
                await asyncio.sleep(1)
                # Exit if all tracks ended and recorder stopped
                if len(receiver.tracks) == 0 and receiver.recording_started is False and receiver.recorder is not None:
                    logger.info("Stream ended, exiting")
                    break
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            
    except json.JSONDecodeError as e:
        logger.error(f"Invalid JSON: {e}")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await receiver.close()
        logger.info("Closed connection")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC to RTMP Bridge")
    parser.add_argument(
        "--rtmp-url",
        default=None,
        help="RTMP output URL (optional, can be added via data channel commands)"
    )
    parser.add_argument(
        "--peerjs",
        action="store_true",
        help="Use PeerJS signaling mode (automatic WebSocket signaling)"
    )
    parser.add_argument(
        "--peer-id",
        help="Custom Peer ID (PeerJS mode only, random if not specified)"
    )
    parser.add_argument(
        "--peerjs-host",
        default="0.peerjs.com",
        help="PeerJS server host (default: 0.peerjs.com)"
    )
    parser.add_argument(
        "--peerjs-port",
        type=int,
        default=443,
        help="PeerJS server port (default: 443)"
    )
    parser.add_argument(
        "--offer-file",
        help="Path to JSON file containing the WebRTC offer (manual mode only)"
    )
    args = parser.parse_args()
    
    if args.peerjs:
        asyncio.run(main_peerjs(
            args.rtmp_url,
            peer_id=args.peer_id,
            peerjs_host=args.peerjs_host,
            peerjs_port=args.peerjs_port
        ))
    else:
        asyncio.run(main(args.rtmp_url, args.offer_file))