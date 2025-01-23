import os
import zipfile
import time
import paramiko
import socket
import threading

num_cameras = 12

# Starts an SSH client to connect and execute a script on a remote Raspberry Pi
def start_client(ip, username, password, script_path):
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    
    try:
        print(f"Attempting to connect to {ip} as {username}")
        ssh.connect(ip, username=username, password=password)
        print(f"Connected to {ip}, launching script")
        stdin, stdout, stderr = ssh.exec_command(f'nohup sudo python3 {script_path} > /dev/null 2>&1 &')
        print(f"Script launched on {ip}.")
        
        output = stdout.read().decode()
        errors = stderr.read().decode()

        if output:
            print(f"Output: {output}")
        if errors:
            print(f"Errors: {errors}")
    
    except Exception as e:
        print(f"Error connecting to {ip}: {e}")
    
    finally:
        ssh.close()

def start_all_clients_simultaneously():
    threads = []
    for cam_num in range(1, num_cameras + 1):
        ip = f'192.168.1.{cam_num}'
        username = f'admin{cam_num}'
        password = f'Admin{cam_num}'
        script_path = f'/home/admin{cam_num}/Documents/Client/Stereo_client.py'

        # Start each client in a separate thread
        thread = threading.Thread(target=start_client, args=(ip, username, password, script_path))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All clients have launched their scripts.")

# Extracts a ZIP file into a specified folder
def extract_zip(zip_filename, extract_to):
    with zipfile.ZipFile(zip_filename, 'r') as zipf:
        zipf.extractall(extract_to)
    print(f"ZIP file {zip_filename} extracted into {extract_to}")

# Waits for a "RECORDING_STOPPED" confirmation from a client
def wait_for_confirmation(client_socket):
    buffer = b""
    while True:
        confirmation = client_socket.recv(1024)
        if confirmation:
            buffer += confirmation
            if b'RECORDING_STOPPED' in buffer:
                return b'RECORDING_STOPPED'
        else:
            print("Waiting for a valid confirmation...")

# Main function to initialize settings and handle the single photo capture from each client
def main():
    while True:
        width = int(input("Enter the desired resolution width: "))
        height = int(input("Enter the desired resolution height: "))

        if width > 4056 or height > 3040:
            print("Error: Resolution exceeds the maximum of 4056x3040. Please try again.")
        else:
            break
    exposure_time = int(input("Enter the desired exposure time (in µs): "))
    delay = float(input("Enter the wait delay before capturing (in seconds): "))

    stereo_folder = 'Stereo'
    if not os.path.exists(stereo_folder):
        os.makedirs(stereo_folder)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 5000))
    server_socket.listen(num_cameras)
    print('Waiting for client connections...')

    start_all_clients_simultaneously()

    # Start each client and wait for connections
    client_sockets = []
    for cam_num in range(1, num_cameras + 1):

        client_socket, addr = server_socket.accept()
        print(f'Connected to {addr}')
        client_sockets.append(client_socket)

    # Send camera settings to each client
    settings_message = f'SETTINGS {width} {height} {exposure_time}'.encode('utf-8')
    for client_socket in client_sockets:
        client_socket.sendall(settings_message)

    input("Press 's' to start capturing images: ")

    # Single photo capture
    capture_time = time.time_ns() + int(delay * 1_000_000_000)
    take_photo_command = f'TAKE_PHOTO {capture_time}'.encode('utf-8')

    try:
        # Send photo capture command to each client
        for client_socket in client_sockets:
            client_socket.sendall(take_photo_command)

        # Check capture confirmation from each client
        for client_socket in client_sockets:
            ack = client_socket.recv(1024)
    
            if ack != b'PHOTO_TAKEN':
                print("Error: A client did not confirm photo capture.")
                break
        else:
            print("All clients have taken a photo.")

        # Stop recording and wait for confirmations
        for client_socket in client_sockets:
            client_socket.sendall(b'STOP_RECORD')
            confirmation = wait_for_confirmation(client_socket)
            if confirmation != b'RECORDING_STOPPED':
                print("Error: Stop confirmation not received.")
                break
        else:
            print("All clients have stopped recording.")

            time.sleep(10)

            # Extract ZIP files
            for cam_num in range(1, num_cameras + 1):
                cam_folder = os.path.join(stereo_folder)
                cam_zip = os.path.join(cam_folder, f'images{cam_num}.zip')

                if os.path.exists(cam_zip):
                    extract_zip(cam_zip, cam_folder)
                else:
                    print(f"Error: ZIP file not found for camera {cam_num}: {cam_zip}")

    finally:
        # Close all client connections
        for client_socket in client_sockets:
            client_socket.close()
        print('Connections closed.')

if __name__ == '__main__':
    main()
