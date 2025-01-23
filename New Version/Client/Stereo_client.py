import psutil
import socket
import os
import zipfile
import time
import re
import paramiko
import subprocess
from scp import SCPClient
from picamera2 import Picamera2

num_cameras = 12

# Initialize the camera with specific width, height, and exposure time settings
def initialize_camera(width, height, exposure_time):
    global picam2
    picam2 = Picamera2()
    camera_config = picam2.create_still_configuration(main={"size": (width, height)}, buffer_count=1)
    picam2.configure(camera_config)
    picam2.set_controls({
        "AnalogueGain": 1,             # Set analog gain
        #"AwbEnable": True,               # Enable auto white balance
        "ColourGains": (1.0, 1.0),       # Set color gains for white balance
        "Brightness": 0.5,               # Set brightness
        "Contrast": 1.0,                 # Set contrast
        "ExposureTime": exposure_time    # Set the exposure time
    })
    picam2.start()

# Captures an image
def capture_image(image_path):
    global picam2
    picam2.capture_file(image_path)

def get_cpu_temp():
    temp_str = os.popen("vcgencmd measure_temp").readline()
    temp = float(temp_str.replace("temp=", "").replace("'C\n", ""))
    return temp

# Get the current CPU usage as a percentage
def get_cpu_usage():
    cpu_usage_str = os.popen("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").readline()
    return float(cpu_usage_str)


def wait_for_conditions(max_temp, max_cpu_usage):
    while True:
        temp = get_cpu_temp()
        cpu_usage = get_cpu_usage()
        if temp > max_temp or cpu_usage > max_cpu_usage:
            time.sleep(5)
        else:
            break

# Create a ZIP archive of the images stored in the RAM folder
def create_zip(folder, zip_filename):
    total_files = sum([len(files) for _, _, files in os.walk(folder)])
    if total_files == 0:
        return
    current_file_count = 0
    with zipfile.ZipFile(zip_filename, 'w', zipfile.ZIP_STORED) as zipf:
        for root, _, files in os.walk(folder):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder)
                zipf.write(file_path, arcname)
                current_file_count += 1

# Send the ZIP archive to the server using SCP (via SSH)
def send_zip_scp(zip_filename, server_ip, username, password, raspberry_number):
    for cam_num in range(1, num_cameras + 1):
        if raspberry_number == cam_num:
            remote_path = f'/home/admin/Documents/Server/Stereo/'
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username=username, password=password)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(zip_filename, remote_path=remote_path)
    finally:
        ssh.close()

# Main function
def main(server_ip, port, username, password):
    raspberry_number = int(re.search(r'\d+$', os.popen("hostname").read().strip()).group(0))
    os.system('sudo systemctl restart ntpsec')
    time.sleep(2)
    os.system('sudo ntpdate -b 192.168.1.253')

    os.system('sudo cpufreq-set -g performance')  # Set CPU to high-performance mode
    MAX_TEMP = 40.0
    MAX_CPU_USAGE = 20.0
    wait_for_conditions(MAX_TEMP, MAX_CPU_USAGE)  # Wait for CPU to cool down

    image_folder = 'Output_Image'
    if not os.path.exists(image_folder):
        os.makedirs(image_folder)

    global client_socket, is_capturing
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, port))
    count = 1
    is_capturing = True

    # Get camera settings
    settings_message = client_socket.recv(1024).decode('utf-8')
    if settings_message.startswith('SETTINGS'):
        _, width, height, exposure_time = settings_message.split()
        initialize_camera(int(width), int(height), int(exposure_time))

    try:
        # Capture a single image
        command = client_socket.recv(1024).decode('utf-8')
        if command.startswith('TAKE_PHOTO'):
            _, capture_time = command.split()
            capture_time = float(capture_time)
            image_path = os.path.join(image_folder, f"image_{raspberry_number}.jpg")

            # Wait until capture time
            while time.time_ns() < capture_time:
                time.sleep(0.000001)
                
            capture_image(image_path)
            client_socket.sendall(b'PHOTO_TAKEN')

        # Stop recording and send ZIP
        stop_command = client_socket.recv(1024).decode('utf-8')
        if stop_command == 'STOP_RECORD':
            client_socket.sendall(b'RECORDING_STOPPED')

            zip_filename = f'images{raspberry_number}.zip'
            create_zip(image_folder, zip_filename)  # Create ZIP of images
            send_zip_scp(zip_filename, server_ip, username, password, raspberry_number)  # Send ZIP to server

    finally:
        client_socket.close()
        os.remove(zip_filename)
        os.remove(image_path)

if __name__ == '__main__':
    os.nice(-20)  # Set high priority for the process
    main('192.168.1.253', 5000, 'admin', 'Admin')
