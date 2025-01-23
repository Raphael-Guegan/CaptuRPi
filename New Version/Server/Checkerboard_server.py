import os
import zipfile
import time
import paramiko
import socket
import threading
from paramiko import SSHClient
from scp import SCPClient

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
        script_path = f'/home/admin{cam_num}/Documents/Client/Checkerboard_client.py'

        # Start each client in a separate thread
        thread = threading.Thread(target=start_client, args=(ip, username, password, script_path))
        threads.append(thread)
        thread.start()

    # Wait for all threads to complete
    for thread in threads:
        thread.join()

    print("All clients have launched their scripts.")

# Sends a notification to a client that extraction is complete
def notify_extraction_complete(client_socket):
    client_socket.sendall(b'EXTRACTION_COMPLETE')
    print("Extraction complete notification sent to client.")

# Waits for a "RECORDING_STOPPED" confirmation message from a client
def wait_for_confirmation(client_socket):
    buffer = b""
    while True:
        confirmation = client_socket.recv(1024)
        if confirmation:
            buffer += confirmation
            if b'RECORDING_STOPPED' in buffer:
                return b'RECORDING_STOPPED'
        else:
            print("Waiting for valid confirmation...")

# Waits for a "READY" confirmation message from a client
def wait_ready(client_socket):
    buffer = b""
    while True:
        confirmation = client_socket.recv(1024)
        if confirmation:
            buffer += confirmation
            if b'READY' in buffer:
                return b'READY'
        else:
            print("Waiting for valid confirmation...")

# Receives a list of anomaly data from a client
def receive_anomalies(client_socket):
    # Reçoit le message d'un client
    message = client_socket.recv(1024).decode('utf-8')
    message_parts = message.split()

    # Vérifie le type de message (ANOMALIES ou NO_ANOMALIES) et le numéro de la caméra
    if message_parts[0] == "ANOMALIES":
        cam_num = int(message_parts[1])  # Extrait le numéro de la caméra
        anomalies = list(map(int, message_parts[2].split(',')))  # Extrait la liste des anomalies
        return cam_num, anomalies
    elif message_parts[0] == "NO_ANOMALIES":
        cam_num = int(message_parts[1])  # Extrait le numéro de la caméra
        return cam_num, None

def receive_scp(ip, username, password, cam_num, local_folder):
    # Define paths for SCP transfer
    remote_path = f'/home/admin{cam_num}/Documents/Client/images.zip'
    local_path = os.path.join(local_folder, f'Cam_{cam_num:02d}')
    
    # SCP to receive CSV file
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password)
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(remote_path, local_path)
    ssh.close()
    print(f"CSV file for Camera {cam_num} received and saved at {local_path}.")


# Main function to initialize settings and handle image capture from multiple clients
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

    checkerboard_folder = 'Checkerboard'
    if not os.path.exists(checkerboard_folder):
        os.makedirs(checkerboard_folder)

    for cam_num in range(1, num_cameras + 1):
        cam_folder = os.path.join(checkerboard_folder, f'Cam_{cam_num:02d}')
        if not os.path.exists(cam_folder):
            os.makedirs(cam_folder)

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 5000))
    server_socket.listen(num_cameras)
    print('Waiting for client connections...')

    start_all_clients_simultaneously()

    # Start each client and wait for connections
    client_sockets = []
    for _ in range(num_cameras):  # Itère pour chaque caméra attendue
        client_socket, addr = server_socket.accept()
        print(f'Connected to {addr}')
    
        # Extraire le dernier chiffre de l'adresse IP comme numéro de caméra
        ip = addr[0]  # addr est un tuple (IP, port)
        cam_num = int(ip.split('.')[-1])  # Dernière partie de l'adresse IP
    
        # Ajouter le socket et le numéro de caméra à la liste
        client_sockets.append((client_socket, cam_num))

    # Trier les sockets par numéro de caméra
    client_sockets.sort(key=lambda x: x[1])

    # Extraire uniquement les sockets triés
    client_sockets = [sock for sock, _ in client_sockets]

    # Send camera settings to each client
    settings_message = f'SETTINGS {width} {height} {exposure_time}'.encode('utf-8')
    for client_socket in client_sockets:
        client_socket.sendall(settings_message)

    capturing = True
    count = 1

    input("Enter 's' to start capturing images: ")

    try:
        print("Starting capture...")
        while capturing:
            # Calculate capture time with delay
            capture_time = time.time_ns() + int(delay * 1_000_000_000)
            take_photo_command = f'TAKE_PHOTO {capture_time}'.encode('utf-8')

            # Send capture command to all clients
            for client_socket in client_sockets:
                client_socket.sendall(take_photo_command)

            # Check for photo acknowledgments from each client
            for client_socket in client_sockets:
                ack = client_socket.recv(1024)
    
                if ack == b'RAM_LOW':
                    print("Error: A client has low RAM. Stop the capture.")
                    capturing = False
                    break
    
                elif ack != b'PHOTO_TAKEN':
                    print("Error: A client did not confirm photo capture. Stopping capture.")
                    capturing = False
                    break
            else:
                count += 1

    except KeyboardInterrupt:
        print("Stopping capture...")
        capturing = False

    finally:    
        # Signal clients to stop recording
        for client_socket in client_sockets:
            client_socket.sendall(b'STOP_RECORD')

        # Wait for stop confirmation from each client
        for client_socket in client_sockets:
            confirmation = wait_for_confirmation(client_socket)
            if confirmation != b'RECORDING_STOPPED':
                print("Error: Did not receive stop confirmation from a client.")
                break
        else:
            print("All clients have stopped recording.")
            time.sleep(5)

            # Wait for clients to be ready to send files
            for client_socket in client_sockets:
                ready = wait_ready(client_socket)
                if ready != b'READY':
                    print("Error: A client is not ready to send the zip file.")
                    break
            else:

                # Extract and process each camera's zip file
                for cam_num in range(1, num_cameras + 1):
                    time.sleep(1)
                    anomalies = receive_anomalies(client_sockets[cam_num - 1])
                    if anomalies:
                        print(f"Camera {cam_num} encountered anomalies in the following photos: {anomalies}")
                    else:
                        print(f"No anomalies reported for Camera {cam_num}.")

                print("ZIP files is ready to be send.")
                for cam_num in range(1, num_cameras + 1):
                    ip = f'192.168.1.{cam_num}'
                    username = f'admin{cam_num}'
                    password = f'Admin{cam_num}'
                    receive_scp(ip, username, password, cam_num, checkerboard_folder)
                    notify_extraction_complete(client_sockets[cam_num - 1])

        # Close all client sockets
        for client_socket in client_sockets:
            client_socket.close()
        print('Connections closed.')

if __name__ == '__main__':
    main()
