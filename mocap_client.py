"""
Code for connecting to the mocap desktop via Ethernet and sending commands and reading commands."""

import asyncio
import socket
import pandas as pd
import os
import time
import datetime
import numpy as np
import threading

# port on the host where the mocap device published the data
desktop_ip = '192.168.1.5' #192.168.1.18
PORT = 9091

def send_ping():
    """Sends a ping to the desktop to check if it is reachable."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(1)
        try:
            s.connect((desktop_ip, 24))
            print("Desktop is reachable.")
        except ConnectionRefusedError:
            print("Desktop is not reachable.")
        except socket.timeout:
            print("Desktop is not reachable.")

def ping_host(ip):
    """Pings a host to check if it's reachable. Works on both Windows and Unix/macOS."""
    import platform
    if platform.system().lower() == 'windows':
        response = os.system(f"ping -n 1 {ip} > nul")
    else:
        # Unix/macOS: -c 1 means send 1 packet, -W 1 means 1 second timeout
        response = os.system(f"ping -c 1 -W 1 {ip} > /dev/null 2>&1")
    if response == 0:
        print(f"Host {ip} is reachable.")
    else:
        print(f"Host {ip} is not reachable.")

class MocapClient:

    def __init__(self, ip,port,dt=0.1):
        """Initializes the client."""
        self.dt = dt
        self.ip = ip
        self.port = port
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Set socket receive buffer size to limit buffering (helps prevent backlog)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)  # 64KB buffer
        self.sock.bind((ip,self.port))
        # data buffers
        self.x_buffer = []
        self.y_buffer = []
        self.z_buffer = []
        self.q_x_buffer = []
        self.q_y_buffer = []
        self.q_z_buffer = []
        self.q_w_buffer = []
        self.heading_buffer = []  # Heading (yaw) in radians
        self.vxy__buffer = []
        self.timestamps = []
        self.raw_messages = []
        self.lock = threading.Lock()  # Thread lock for buffer access
        print(f"UDP socket bound to {self.ip}:{self.port}, listening for mocap data...")
    
    def flush_old_packets(self, flush_duration=0.1):
        """
        Flush old buffered packets by reading and discarding them for a short period.
        This prevents processing stale data when the client first starts.
        """
        print(f"Flushing old packets for {flush_duration} seconds...")
        self.sock.settimeout(flush_duration)
        flush_start = time.time()
        flushed_count = 0
        
        while time.time() - flush_start < flush_duration:
            try:
                data, addr = self.sock.recvfrom(1024)
                flushed_count += 1
            except socket.timeout:
                break
            except Exception:
                break
        
        self.sock.settimeout(None)  # Reset to blocking mode
        if flushed_count > 0:
            print(f"Flushed {flushed_count} old packets")
        else:
            print("No old packets to flush")
    
    def listen(self, max_messages=None):
        """
        Listens for mocap data at high frequency. Drains the socket buffer to prevent lag.
        After skipping the first message, collects messages indefinitely (or up to max_messages if specified).
        """
        # Flush old packets before starting to collect data
        self.flush_old_packets(flush_duration=0.2)
        
        # Make socket non-blocking to read all available packets
        self.sock.setblocking(False)
        
        first_message = True
        message_count = 0
        try:
            while True:
                packets_read = 0
                # Read all available packets in the buffer (drain the buffer)
                while True:
                    try:
                        data, addr = self.sock.recvfrom(1024)
                        # Skip the first message (usually a "hello world" or initialization message)
                        if first_message:
                            print(f"Skipping first message: {data.decode()}")
                            first_message = False
                            continue
                        #print(f"Received {data} from {addr}")
                        self.extract_data(data.decode())
                        message_count += 1
                        packets_read += 1
                        if max_messages is not None and message_count >= max_messages:
                            print(f"Collected {message_count} messages. Stopping...")
                            return
                    except (BlockingIOError, socket.error, OSError):
                        # No more packets available (would block), break inner loop
                        break
                
                # Only sleep if no packets were read (to avoid tight loop when no data)
                if packets_read == 0:
                    time.sleep(0.001)  # Small sleep to avoid CPU spinning (1ms)
                # If packets were read, continue immediately to process next batch
                
                if max_messages is not None and message_count % 10 == 0:
                    print(f"Collected {message_count}/{max_messages} messages...")
        except KeyboardInterrupt:
            print("Closing the connection with the mocap device.")
        except Exception as e:
            print(e)
        finally:
            self.sock.close()
    
    def quaternion_to_heading(self, q_x, q_y, q_z, q_w):
        """
        Converts quaternion to heading (yaw angle in radians).
        Formula: heading = atan2(2*(w*z + x*y), 1 - 2*(y^2 + z^2))
        """
        heading = np.arctan2(
            2 * (q_w * q_z + q_x * q_y),
            1 - 2 * (q_y**2 + q_z**2)
        )
        return heading
    
    def get_last_heading(self):
        """Returns the last heading in radians (thread-safe)."""
        with self.lock:
            if len(self.heading_buffer) > 0:
                return self.heading_buffer[-1]
            else:
                return 0.0
    
    def get_last_position(self):
        """Returns the last position (thread-safe)."""
        with self.lock:
            if len(self.x_buffer) > 0 and len(self.y_buffer) > 0:
                return self.x_buffer[-1], self.y_buffer[-1]
            else:
                return 0.0, 0.0
    
    def get_last_velocity(self):
        """Returns the last velocity (thread-safe)."""
        with self.lock:
            if len(self.vxy__buffer) > 0:
                return self.vxy__buffer[-1]
            else:
                return 0.0
    
    def get_last_z(self):
        """Returns the last z position (thread-safe)."""
        with self.lock:
            if len(self.z_buffer) > 0:
                return self.z_buffer[-1]
            else:
                return 0.0
    
    def save_data(self, filename=None):
        """Saves all collected data to a CSV file."""
        if filename is None:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"mocap_data_{timestamp}.csv"
        
        # Create DataFrame with all collected data
        data_dict = {
            'timestamp': self.timestamps,
            'x': self.x_buffer,
            'y': self.y_buffer,
            'z': self.z_buffer,
            'q_x': self.q_x_buffer,
            'q_y': self.q_y_buffer,
            'q_z': self.q_z_buffer,
            'q_w': self.q_w_buffer,
            'heading': self.heading_buffer,  # Heading in radians
            'raw_message': self.raw_messages
        }
        print(data_dict)
        # Add velocity if available
        if len(self.vxy__buffer) > 0:
            # Pad velocity buffer with NaN for first entries (velocity needs at least 2 positions)
            velocity_padded = [None] * (len(self.x_buffer) - len(self.vxy__buffer)) + self.vxy__buffer
            data_dict['velocity'] = velocity_padded
        
        df = pd.DataFrame(data_dict)
        df.to_csv(filename, index=False)
        print(f"Data saved to {filename}")
        print(f"Total records: {len(df)}")
        return filename
    
    def extract_data(self, msg):
        """Extracts the data from the message (thread-safe)."""
        split_msg = msg.split(',')
        # Validate message format before extracting data
        if len(split_msg) < 7:
            print(f"Warning: Received malformed message with only {len(split_msg)} fields. Expected at least 7. Message: {msg}")
            return
        
        try:
            # extract the data
            x = float(split_msg[1])
            y = float(split_msg[2])
            z = float(split_msg[3])
            q_x = float(split_msg[4])
            q_y = float(split_msg[5])
            q_z = float(split_msg[6])
            q_w = float(split_msg[7])
            
            # Convert quaternion to heading in real-time
            heading = self.quaternion_to_heading(q_x, q_y, q_z, q_w)
            
            # Update buffers with thread lock
            with self.lock:
                self.x_buffer.append(x)
                self.y_buffer.append(y)
                self.z_buffer.append(z)
                self.q_x_buffer.append(q_x)
                self.q_y_buffer.append(q_y)
                self.q_z_buffer.append(q_z)
                self.q_w_buffer.append(q_w)
                self.heading_buffer.append(heading)
                self.raw_messages.append(msg)
                self.timestamps.append(datetime.datetime.now())
                
                # Check buffer length and calculate dt while holding the lock
                if len(self.x_buffer) > 2:
                    dt = (self.timestamps[-1] - self.timestamps[-2]).total_seconds()
                    #print(f"dt mocap : {dt}, x : {x}, y : {y}, heading : {heading:.4f} rad")
        except (ValueError, IndexError) as e:
            print(f"Error parsing message: {msg}. Error: {e}")

if __name__ == "__main__":
    ping_host(desktop_ip)  # check it with Win + R -> cmd -> ping, and ipconfig
    server = MocapClient(desktop_ip,PORT)
    server.listen()
