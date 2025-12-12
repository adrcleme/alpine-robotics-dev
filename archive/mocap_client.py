"""
Code for connecting to the mocap desktop via Ethernet and sending commands and reading commands."""

import asyncio
import socket
import pandas as pd
import os
import time
import datetime

# port on the host where the mocap device published the data
desktop_ip = '192.168.1.18' #192.168.1.13
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
        self.sock.bind((ip,self.port))
        # data buffers
        self.x_buffer = []
        self.y_buffer = []
        self.z_buffer = []
        self.r_buffer = []
        self.p_buffer = []
        self.q_buffer = []
        self.vxy__buffer = []
        self.timestamps = []
        self.raw_messages = []
        self.lock = asyncio.Lock()
        print(f"UDP socket bound to {self.ip}:{self.port}, listening for mocap data...")
    
    def listen(self, max_messages=None):
        """Listens for mocap data. After skipping the first message, collects messages indefinitely (or up to max_messages if specified)."""
        first_message = True
        message_count = 0
        try:
            while True:
                data, addr = self.sock.recvfrom(1024)
                # Skip the first message (usually a "hello world" or initialization message)
                if first_message:
                    print(f"Skipping first message: {data.decode()}")
                    first_message = False
                    continue
                #print(f"Received {data} from {addr}")
                self.extract_data(data.decode())
                message_count += 1
                if max_messages is not None and message_count >= max_messages:
                    print(f"Collected {message_count} messages. Stopping...")
                    break
                if max_messages is not None and message_count % 10 == 0:
                    print(f"Collected {message_count}/{max_messages} messages...")
                time.sleep(self.dt)
        except KeyboardInterrupt:
            print("Closing the connection with the mocap device.")
        except Exception as e:
            print(e)
        finally:
            self.sock.close()
    
    def get_last_velocity(self):
        """Returns the last velocity."""
        if len(self.vxy__buffer) > 0:
            # makes sure there is no access to the buffer while reading , with a lock
            #with self.lock:
            v = self.vxy__buffer[-1]
            return v
        else:
            return 0.0
    
    def get_last_position(self):
        """Returns the last position."""
        return self.x_buffer[-1], self.y_buffer[-1]
    
    def get_last_heading(self):
        """Returns the last heading/yaw in radians."""
        if len(self.q_buffer) > 0:
            return self.q_buffer[-1]
        else:
            return 0.0
    
    def get_last_z(self):
        """Returns the last z position."""
        if len(self.z_buffer) > 0:
            return self.z_buffer[-1]
        else:
            return 0.0
    
    def get_last_roll(self):
        """Returns the last roll in radians."""
        if len(self.r_buffer) > 0:
            return self.r_buffer[-1]
        else:
            return 0.0
    
    def get_last_pitch(self):
        """Returns the last pitch in radians."""
        if len(self.p_buffer) > 0:
            return self.p_buffer[-1]
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
            'roll': self.r_buffer,
            'pitch': self.p_buffer,
            'yaw': self.q_buffer,
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
        """Extracts the data from the message."""
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
            r = float(split_msg[4])
            p = float(split_msg[5])
            q = float(split_msg[6])
            self.x_buffer.append(x)
            self.y_buffer.append(y)
            self.z_buffer.append(z)
            self.r_buffer.append(r)
            self.p_buffer.append(p)
            self.q_buffer.append(q)
            self.raw_messages.append(msg)
            self.timestamps.append(datetime.datetime.now())
            if len(self.x_buffer) > 2:
                dt = (self.timestamps[-1] - self.timestamps[-2]).total_seconds()
                #print(f"dt mocap : {dt}, x : {x}, y : {y} ")
        except (ValueError, IndexError) as e:
            print(f"Error parsing message: {msg}. Error: {e}")

if __name__ == "__main__":
    ping_host(desktop_ip)  # check it with Win + R -> cmd -> ping, and ipconfig
    server = MocapClient(desktop_ip,PORT)
    server.listen()
