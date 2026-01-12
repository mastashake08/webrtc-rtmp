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
    def __init__(self, rtmp_url):
        self.pc = RTCPeerConnection()
        self.rtmp_url = rtmp_url
        self.recorder = None
        self.tracks = []
        self.recording_started = False
        
    async def setup(self):
        """Setup peer connection event handlers"""
        
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"Receiving {track.kind} track")
            self.tracks.append(track)
            
            if self.recorder is None:
                # Initialize recorder with RTMP output (use flv format for RTMP)
                self.recorder = MediaRecorder(self.rtmp_url, format='flv')
                
            # Add track to recorder
            self.recorder.addTrack(track)
            
            # Start recorder only once when we have tracks
            if not self.recording_started:
                await self.recorder.start()
                self.recording_started = True
                logger.info("Started recording to RTMP")
            
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track {track.kind} ended")
                if track in self.tracks:
                    self.tracks.remove(track)
                
                # Stop recording when all tracks have ended
                if len(self.tracks) == 0 and self.recorder:
                    logger.info("All tracks ended, stopping recorder")
                    await self.recorder.stop()
          #Add receive-only transceivers for audio and video
        self.pc.addTransceiver("audio", direction="recvonly")
        self.pc.addTransceiver("video", direction="recvonly")
        
        #           self.recording_started = False
                
        @self.pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                await self.pc.close()
                
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
        
        await self.pc.setRemoteDescription(offer)
        
        # Create answer (transceivers already defined by the offer)
        answer = await self.pc.createAnswer()
        await self.pc.setLocalDescription(answer)
        
        return {
            "type": self.pc.localDescription.type,
            "sdp": self.pc.localDescription.sdp
        }
        
    async def add_ice_candidate(self, candidate_data):
        """Add ICE candidate"""
        if candidate_data:
            from aiortc import RTCIceCandidate
            candidate = RTCIceCandidate(
                candidate=candidate_data.get("candidate"),
                sdpMid=candidate_data.get("sdpMid"),
                sdpMLineIndex=candidate_data.get("sdpMLineIndex")
            )
            await self.pc.addIceCandidate(candidate)
            
    async def close(self):
        """Close connections"""
        if self.recorder and self.recording_started:
            try:
                await self.recorder.stop()
                logger.info("Recorder stopped")
            except Exception as e:
                logger.warning(f"Error stopping recorder: {e}")
        await self.pc.close()
        logger.info("Peer connection closed")


async def main_peerjs(rtmp_url, peer_id=None, peerjs_host="0.peerjs.com", peerjs_port=443):
    """Run in PeerJS mode - connect to PeerJS server and wait for connections"""
    receiver = WebRTCReceiver(rtmp_url)
    peerjs = PeerJSClient(
        host=peerjs_host,
        port=peerjs_port,
        peer_id=peer_id,
        secure=True
    )
    
    remote_peer_id = None
    
    # Handle incoming offers
    async def handle_offer(sdp, src_peer_id):
        nonlocal remote_peer_id
        remote_peer_id = src_peer_id
        
        logger.info(f"Processing offer from peer: {src_peer_id}")
        logger.debug(f"Offer type: {type(sdp)}, keys: {sdp.keys() if isinstance(sdp, dict) else 'N/A'}")
        
        # Ensure sdp is in the correct format
        if not isinstance(sdp, dict):
            logger.error(f"Invalid SDP format: {sdp}")
            return
            
        # Process offer and create answer
        answer = await receiver.receive_offer(sdp)
        await peerjs.send_answer(answer, src_peer_id)
        logger.info("Answer sent successfully")
        
    # Handle incoming ICE candidates
    async def handle_candidate(candidate, src_peer_id):
        await receiver.add_ice_candidate(candidate)
    
    # Set up handlers
    peerjs.on_offer = handle_offer
    peerjs.on_candidate = handle_candidate
    
    # Also send our ICE candidates to remote peer
    @receiver.pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate and remote_peer_id:
            await peerjs.send_candidate({
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex
            }, remote_peer_id)
    
    try:
        await peerjs.connect()
        print(f"\n✓ Connected to PeerJS server")
        print(f"✓ Your Peer ID: {peerjs.peer_id}")
        print(f"\nShare this Peer ID with the sender to start streaming!\n")
        print("Waiting for connections... (Press Ctrl+C to stop)\n")
        
        # Keep running until interrupted
        while receiver.pc.connectionState != "closed":
            await asyncio.sleep(1)
            # Exit if all tracks ended
            if len(receiver.tracks) == 0 and receiver.recording_started is False and receiver.recorder is not None:
                logger.info("Stream ended")
                break
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
    finally:
        await peerjs.close()
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
        default="rtmp://localhost/live/stream",
        help="RTMP output URL (default: rtmp://localhost/live/stream)"
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