import psutil
import socket
import os
import zipfile
import time
import re
import paramiko
import subprocess
from scp import SCPClient
from picamera2 import Picamera2, controls

num_cameras = 12
RAM_THRESHOLD = 90.0  # RAM usage threshold (percentage) for stopping the capture
TMPFS_THRESHOLD = 90.0  # Define tmpfs usage limit

# Wait for the server to confirm that the image extraction is complete
def wait_for_extraction_complete():
    while True:
        confirmation = client_socket.recv(1024)
        if confirmation == b'EXTRACTION_COMPLETE':
            break
        else:
            time.sleep(1)

# Check the current RAM usage and return the percentage used
def check_ram_usage():
    ram_info = psutil.virtual_memory()
    return ram_info.percent

def check_tmpfs_space(folder):
    usage = psutil.disk_usage(folder)
    return usage.percent

# Mount a folder in RAM for faster read/write access (tmpfs)
def mount_tmpfs(folder, size="2G"):
    if not os.path.exists(folder):
        os.makedirs(folder)
    if not os.path.ismount(folder):
        subprocess.run(["sudo", "mount", "-t", "tmpfs", "-o", f"size={size}", "tmpfs", folder])

# Unmount the folder from RAM after use
def unmount_tmpfs(folder):
    if os.path.ismount(folder):
        subprocess.run(["sudo", "umount", folder])

# Get the Raspberry Pi number from its hostname (used to differentiate devices)
def get_raspberry_number():
    hostname = os.popen("hostname").read().strip()
    match = re.search(r'(\d+)$', hostname)
    if match:
        raspberry_number = int(match.group(1))
    else:
        raspberry_number = 253  # Default number if none is found
    return raspberry_number

ram_folder = '/mnt/ram_images'
image_format = 'jpg'
image_prefix = 'img'

client_socket = None
picam2 = None

# Initialize the camera with specific width, height, and exposure time settings
def initialize_camera(width, height, exposure_time):
    global picam2
    picam2 = Picamera2()
    camera_config = picam2.create_still_configuration(main={"size": (width, height)}, buffer_count=1)
    picam2.configure(camera_config)
    picam2.set_controls({
        "AnalogueGain": 2.0,             # Set analog gain
        "AwbEnable": True,               # Enable auto white balance
        "ColourGains": (1.0, 1.0),       # Set color gains for white balance
        "Brightness": 0.5,               # Set brightness
        "Contrast": 1.0,                 # Set contrast
        "ExposureTime": exposure_time    # Set the exposure time
    })
    picam2.start()

# Capture an image and save it to the specified path
def capture_image(image_path):
    global picam2
    picam2.capture_file(image_path)

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

# Clean up the ZIP file after it has been sent
def cleanup_files(zip_filename):
    if os.path.exists(zip_filename):
        os.remove(zip_filename)

# Get the current CPU temperature
def get_cpu_temp():
    temp_str = os.popen("vcgencmd measure_temp").readline()
    temp = float(temp_str.replace("temp=", "").replace("'C\n", ""))
    return temp

# Get the current CPU usage as a percentage
def get_cpu_usage():
    cpu_usage_str = os.popen("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").readline()
    return float(cpu_usage_str)

# Wait for CPU temperature and usage to drop below specified thresholds
def wait_for_conditions(max_temp, max_cpu_usage):
    while True:
        temp = get_cpu_temp()
        cpu_usage = get_cpu_usage()
        if temp > max_temp or cpu_usage > max_cpu_usage:
            time.sleep(5)
        else:
            break

# Main function to control the photo capture and synchronization process
def main(server_ip, port):
    raspberry_number = get_raspberry_number()
    mount_tmpfs(ram_folder, "2G")
    os.system('sudo systemctl restart ntpsec')  # Restart NTP to synchronize time
    time.sleep(2)
    os.system('sudo ntpdate -b 192.168.1.253')  # Sync time with NTP server

    os.system('sudo cpufreq-set -g performance')  # Set CPU to high-performance mode
    MAX_TEMP = 40.0
    MAX_CPU_USAGE = 20.0
    wait_for_conditions(MAX_TEMP, MAX_CPU_USAGE)  # Wait for CPU to cool down

    global client_socket, is_capturing
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, port))
    count = 1
    is_capturing = True

    capture_times = []
    photo_anomalies = []

    settings_message = client_socket.recv(1024).decode('utf-8')
    if settings_message.startswith('SETTINGS'):
        _, width, height, exposure_time = settings_message.split()
        width = int(width)
        height = int(height)
        exposure_time = int(exposure_time)
        initialize_camera(width, height, exposure_time)

    try:
        while is_capturing:
            command = client_socket.recv(1024).decode('utf-8')
            ram_usage = check_ram_usage()  # Check RAM usage before each capture
            tmpfs_usage = check_tmpfs_space(ram_folder)

            if ram_usage > RAM_THRESHOLD or tmpfs_usage > TMPFS_THRESHOLD:
                client_socket.sendall(b'RAM_LOW')
                command = client_socket.recv(1024).decode('utf-8')
                if command == 'STOP_RECORD':
                    is_capturing = False
                    client_socket.sendall(b'RECORDING_STOPPED')
                break

            if command.startswith('TAKE_PHOTO'):
                _, capture_time = command.split()
                capture_time = float(capture_time)
                image_path = os.path.join(ram_folder, f"{image_prefix}{count}.{image_format}")
                while time.time_ns() < capture_time:
                    time.sleep(0.000001)
                start_time = time.time()
                capture_image(image_path)
                end_time = time.time()
                capture_delay = end_time - start_time

                if count == 3:
                    ref_delay = capture_delay

                if count > 3:
                    capture_times.append(capture_delay)
                    relative_diff = abs(capture_delay - ref_delay) / ref_delay
                    if relative_diff > 0.06:
                        photo_anomalies.append(count)
                client_socket.sendall(b'PHOTO_TAKEN')
                count += 1

            elif command == 'STOP_RECORD':
                is_capturing = False
                client_socket.sendall(b'RECORDING_STOPPED')
                break

        zip_filename = f'/home/admin{raspberry_number}/Documents/Client/images.zip'
        create_zip(ram_folder, zip_filename)  # Create ZIP of images
        time.sleep(5)
        client_socket.sendall(b'READY')

        time.sleep(1)
        if photo_anomalies:
            anomalies_str = f"ANOMALIES {raspberry_number} " + ",".join(map(str, photo_anomalies))
            client_socket.sendall(anomalies_str.encode('utf-8'))
        else:
            no_anomalies_str = f"NO_ANOMALIES {raspberry_number}"
            client_socket.sendall(no_anomalies_str.encode('utf-8'))
        wait_for_extraction_complete()

    finally:
        cleanup_files(zip_filename)  # Clean up the ZIP file
        unmount_tmpfs(ram_folder)  # Unmount the RAM folder
        client_socket.close()

if __name__ == '__main__':
    os.nice(-20)  # Set high priority for the process
    SERVER_IP = '192.168.1.253'
    PORT = 5000
    main(SERVER_IP, PORT)
