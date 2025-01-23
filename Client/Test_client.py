import psutil
import socket
import os
import zipfile
import time
import re
import paramiko
import subprocess
from picamera2 import Picamera2, controls
import csv
from scp import SCPClient

# Save capture times and relative errors to a CSV file for analysis
def save_results_to_csv(filename, capture_times, relative_errors):
    with open(filename, mode='w', newline='') as file:
        writer = csv.writer(file)
        writer.writerow(["Photo_Index", "Capture_Time (s)", "Relative_Error (%)"])
        for index, (time, error) in enumerate(zip(capture_times, relative_errors), start=4):
            writer.writerow([index, time, error * 100])

num_cameras = 12
RAM_THRESHOLD = 90.0  # Define RAM usage limit
TMPFS_THRESHOLD = 90.0  # Define tmpfs usage limit

# Check current RAM usage as a percentage
def check_ram_usage():
    ram_info = psutil.virtual_memory()
    return ram_info.percent

# Check space usage of the tmpfs folder as a percentage
def check_tmpfs_space(folder):
    usage = psutil.disk_usage(folder)
    return usage.percent

# Mount a temporary filesystem (RAM-based) for storing images
def mount_tmpfs(folder, size="2G"):
    if not os.path.exists(folder):
        os.makedirs(folder)
    if not os.path.ismount(folder):
        subprocess.run(["sudo", "mount", "-t", "tmpfs", "-o", f"size={size}", "tmpfs", folder])

# Unmount the temporary filesystem
def unmount_tmpfs(folder):
    if os.path.ismount(folder):
        subprocess.run(["sudo", "umount", folder])

# Extract the Raspberry Pi's unique number from the hostname
def get_raspberry_number():
    hostname = os.popen("hostname").read().strip()
    match = re.search(r'(\d+)$', hostname)
    if match:
        raspberry_number = int(match.group(1))
    else:
        raspberry_number = 253
    return raspberry_number

ram_folder = '/mnt/ram_images'
image_format = 'jpg'
image_prefix = 'img'

client_socket = None
picam2 = None

# Initialize camera with specified resolution and exposure_time
def initialize_camera(width, height, exposure_time):
    global picam2
    picam2 = Picamera2()
    camera_config = picam2.create_still_configuration(main={"size": (width, height)}, buffer_count=1)
    picam2.configure(camera_config)
    picam2.set_controls({
        "AnalogueGain": 1.0,             # Set analog gain
        "ColourGains": (1.0, 1.0),       # Set color gains for white balance
        "Brightness": 0.5,               # Set brightness
        "Contrast": 1.0,                 # Set contrast
        "ExposureTime": exposure_time
    })
    picam2.start()

# Capture an image and save it to the specified path
def capture_image(image_path):
    global picam2
    picam2.capture_file(image_path)

# Get the current CPU temperature
def get_cpu_temp():
    temp_str = os.popen("vcgencmd measure_temp").readline()
    temp = float(temp_str.replace("temp=", "").replace("'C\n", ""))
    return temp

# Get the current CPU usage percentage
def get_cpu_usage():
    cpu_usage_str = os.popen("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").readline()
    return float(cpu_usage_str)

# Wait until CPU temperature and usage are within specified limits
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
            remote_path = f'/home/admin/Documents/Server/Test/Cam_{cam_num:02d}/'
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(server_ip, username=username, password=password)
        with SCPClient(ssh.get_transport()) as scp:
            scp.put(zip_filename, remote_path=remote_path)
    finally:
        ssh.close()

# Main function to connect to server and handle camera operation
def main(server_ip, port, username, password):
    raspberry_number = get_raspberry_number()
    mount_tmpfs(ram_folder, "2G")
    os.system('sudo systemctl restart ntpsec')
    time.sleep(2)
    os.system('sudo ntpdate -b 192.168.1.253')
    os.system('sudo cpufreq-set -g performance')
    MAX_TEMP = 40.0
    MAX_CPU_USAGE = 20.0
    wait_for_conditions(MAX_TEMP, MAX_CPU_USAGE)

    global client_socket, is_capturing
    client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client_socket.connect((server_ip, port))
    count = 1
    is_capturing = True
    capture_times = []
    relative_errors = []

    # Receive initial camera settings from server
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
            ram_usage = check_ram_usage()
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
                print(capture_delay)

                if count == 3:
                    ref_delay = capture_delay

                if count > 3:
                    capture_times.append(capture_delay)
                    relative_diff = abs(capture_delay - ref_delay) / ref_delay
                    relative_errors.append(relative_diff)

                client_socket.sendall(b'PHOTO_TAKEN')
                count += 1

            elif command == 'STOP_RECORD':
                is_capturing = False
                client_socket.sendall(b'RECORDING_STOPPED')
                break

    finally:
        # Save captured data to CSV and clean up
        csv_filename = f"capture_results{raspberry_number}.csv"
        save_results_to_csv(csv_filename, capture_times, relative_errors)

        #zip_filename = f'/home/admin{raspberry_number}/Documents/Client/images.zip'
        #create_zip(ram_folder, zip_filename)  # Create ZIP of images
        #send_zip_scp(zip_filename, server_ip, username, password, raspberry_number)  # Send ZIP to server
        unmount_tmpfs(ram_folder)
        client_socket.close()

# Entry point of the program
if __name__ == '__main__':
    os.nice(-20)
    SERVER_IP = '192.168.1.253'
    PORT = 5000
    USERNAME = 'admin'
    PASSWORD = 'Admin'
    main(SERVER_IP, PORT, USERNAME, PASSWORD)
