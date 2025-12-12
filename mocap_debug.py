"""
Debug script for mocap data collection.
- Press Enter to start listening for mocap data
- Press Enter again to stop listening and save the data
"""

import threading
import time
import socket
from mocap_client import MocapClient, desktop_ip, PORT

class MocapDebugClient(MocapClient):
    """Extended MocapClient with stop capability for debug purposes."""
    
    def __init__(self, ip, port, dt=0.1):
        super().__init__(ip, port, dt)
        self.listening = False
        self.stop_listening = False
        self.listen_thread = None
    
    def listen_non_blocking(self):
        """Listens for mocap data in a non-blocking way that can be stopped."""
        first_message = True
        message_count = 0
        self.listening = True
        self.stop_listening = False
        
        # Make socket non-blocking with timeout
        self.sock.settimeout(0.1)  # 100ms timeout
        
        print("Started listening for mocap data...")
        try:
            while not self.stop_listening:
                try:
                    data, addr = self.sock.recvfrom(1024)
                    # Skip the first message
                    if first_message:
                        print(f"Skipping first message: {data.decode()}")
                        first_message = False
                        continue
                    
                    self.extract_data(data.decode())
                    message_count += 1
                    
                    if message_count % 50 == 0:
                        print(f"Collected {message_count} messages...")
                        
                except socket.timeout:
                    # Timeout is expected when no data arrives, just continue
                    continue
                except Exception as e:
                    print(f"Error receiving data: {e}")
                    break
                    
        except KeyboardInterrupt:
            print("Interrupted by user.")
        finally:
            self.listening = False
            print(f"Stopped listening. Total messages collected: {message_count}")
    
    def start_listening(self):
        """Starts listening in a separate thread."""
        if self.listening:
            print("Already listening!")
            return
        
        self.listen_thread = threading.Thread(target=self.listen_non_blocking, daemon=True)
        self.listen_thread.start()
    
    def stop(self):
        """Stops listening."""
        if not self.listening:
            print("Not currently listening!")
            return
        
        print("Stopping data collection...")
        self.stop_listening = True
        
        # Wait for thread to finish (with timeout)
        if self.listen_thread:
            self.listen_thread.join(timeout=2.0)
        
        # Reset socket timeout for cleanup
        self.sock.settimeout(None)

def main():
    """Main debug function."""
    print("=" * 60)
    print("Mocap Debug Client")
    print("=" * 60)
    print(f"Connecting to {desktop_ip}:{PORT}")
    print()
    print("Instructions:")
    print("  - Press Enter to START listening for mocap data")
    print("  - Press Enter again to STOP listening and save data")
    print("  - Type 'quit' or 'exit' to exit without saving")
    print("=" * 60)
    print()
    
    # Initialize client
    client = MocapDebugClient(desktop_ip, PORT)
    
    try:
        # Wait for first input to start
        input("Press Enter to START listening...")
        client.start_listening()
        
        # Wait for second input to stop
        input("\nPress Enter to STOP listening and save data...")
        client.stop()
        
        # Save the data
        if len(client.x_buffer) > 0:
            print(f"\nCollected {len(client.x_buffer)} data points")
            filename = client.save_data()
            print(f"\n✓ Data saved successfully to: {filename}")
        else:
            print("\n⚠ No data collected!")
        
    except KeyboardInterrupt:
        print("\n\nInterrupted by user. Cleaning up...")
        client.stop()
    except Exception as e:
        print(f"\nError: {e}")
        client.stop()
    finally:
        if client.sock:
            client.sock.close()
        print("\nDebug session ended.")

if __name__ == "__main__":
    main()

