import asyncio
import logging
import json
import sys
from aiortc import RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaRecorder
import argparse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebRTCReceiver:
    def __init__(self, rtmp_url):
        self.pc = RTCPeerConnection()
        self.rtmp_url = rtmp_url
        self.recorder = None
        
    async def setup(self):
        """Setup peer connection event handlers"""
        
        @self.pc.on("track")
        async def on_track(track):
            logger.info(f"Receiving {track.kind} track")
            
            if self.recorder is None:
                # Initialize recorder with RTMP output
                self.recorder = MediaRecorder(self.rtmp_url)
                
            # Add track to recorder
            self.recorder.addTrack(track)
            await self.recorder.start()
            
            @track.on("ended")
            async def on_ended():
                logger.info(f"Track {track.kind} ended")
                
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
        await self.pc.setRemoteDescription(offer)
        
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
            from aiortc import RTCIceCandidate
            candidate = RTCIceCandidate(
                candidate=candidate_data.get("candidate"),
                sdpMid=candidate_data.get("sdpMid"),
                sdpMLineIndex=candidate_data.get("sdpMLineIndex")
            )
            await self.pc.addIceCandidate(candidate)
            
    async def close(self):
        """Close connections"""
        if self.recorder:
            await self.recorder.stop()
        await self.pc.close()


async def main(rtmp_url):
    receiver = WebRTCReceiver(rtmp_url)
    
    print("\n=== WebRTC to RTMP Bridge (Receiver Mode) ===")
    print(f"RTMP Output: {rtmp_url}")
    print("\n1. Paste the WebRTC offer SDP (JSON format) and press Enter twice:\n")
    
    # Read multi-line offer
    offer_lines = []
    while True:
        line = sys.stdin.readline()
        if line.strip() == "":
            break
        offer_lines.append(line)
    
    try:
        offer_json = json.loads("".join(offer_lines))
        logger.info("Received offer")
        
        # Process offer and get answer
        answer = await receiver.receive_offer(offer_json)
        
        print("\n=== Answer SDP (send this to the client) ===")
        print(json.dumps(answer, indent=2))
        print("=" * 50)
        
        print("\n2. Paste ICE candidates (JSON format, one per line, empty line to finish):\n")
        
        # Read ICE candidates
        while True:
            line = sys.stdin.readline().strip()
            if line == "":
                break
            try:
                candidate = json.loads(line)
                await receiver.add_ice_candidate(candidate)
                logger.info("Added ICE candidate")
            except json.JSONDecodeError:
                logger.warning("Invalid ICE candidate JSON")
        
        print("\nWaiting for stream... (Press Ctrl+C to stop)")
        
        # Keep running
        try:
            await asyncio.sleep(3600)  # Run for 1 hour max
        except KeyboardInterrupt:
            pass
            
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
    args = parser.parse_args()
    
    asyncio.run(main(args.rtmp_url))
