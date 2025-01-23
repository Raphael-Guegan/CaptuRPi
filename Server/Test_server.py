import os
import socket
import time
import paramiko
from paramiko import SSHClient
from scp import SCPClient
import pandas as pd
import glob
import matplotlib.pyplot as plt
import threading


num_cameras = 12  # Number of client cameras

def plot_all_differences(csv_file, width, height, exposure_time):
    # Read the merged CSV file
    df = pd.read_csv(csv_file)

    # Retrieve columns for capture time differences and relative errors
    time_diff_columns = [col for col in df.columns if 'Capture_Time_Diff' in col]
    error_diff_columns = [col for col in df.columns if 'Relative_Error' in col]

    # Create a plot for capture time differences
    plt.figure(figsize=(15, 10))
    for col in time_diff_columns:
        plt.plot(df['Photo_Index'], df[col], marker='o', linestyle='-', label=col)

    plt.title('Capture Time Differences Between Cameras')
    plt.xlabel('Photo Index')
    plt.ylabel('Difference (s)')
    plt.axhline(0, color='red', linestyle='--')  # Horizontal line at y=0
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'capture_time_differences_{width}x{height}_{exposure_time}.png')
    plt.close()
    print("Capture time differences plot saved: capture_time_differences.png")

    # Create a plot for relative error differences
    plt.figure(figsize=(15, 10))
    for col in error_diff_columns:
        plt.plot(df['Photo_Index'], df[col], marker='o', linestyle='-', label=col)

    plt.title('Relative Errors of all Cameras')
    plt.xlabel('Photo Index')
    plt.ylabel('relative errors %')
    plt.axhline(0, color='red', linestyle='--')  # Horizontal line at y=0
    plt.grid()
    plt.legend()
    plt.tight_layout()
    plt.savefig(f'relative_errors_{width}x{height}_{exposure_time}.png')
    plt.close()
    print("Relative errors plot saved: relative_errors.png")

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

def receive_csv_scp(ip, username, password, cam_num, local_folder):
    # Define paths for SCP transfer
    remote_path = f'/home/admin{cam_num}/Documents/Client/capture_results{cam_num}.csv'
    local_path = os.path.join(local_folder, f'capture_data_cam_{cam_num:02d}.csv')
    
    # SCP to receive CSV file
    ssh = SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(ip, username=username, password=password)
    with SCPClient(ssh.get_transport()) as scp:
        scp.get(remote_path, local_path)
    ssh.close()
    print(f"CSV file for Camera {cam_num} received and saved at {local_path}.")

def generate_unique_pairs():
    pairs = []
    for i in range(1, num_cameras + 1):
        for j in range(i + 1, num_cameras + 1):
            pairs.append((i, j))
    return pairs

def merge_csv_files(folder_path, num_cameras, width, height, exposure_time):
    csv_files = sorted(glob.glob(f"{folder_path}/*.csv"))
    merged_data = {"Photo_Index": []}
    
    for cam_num in range(1, num_cameras + 1):
        merged_data[f'Camera_{cam_num}_Capture_Time'] = []
        merged_data[f'Camera_{cam_num}_Relative_Error'] = []

    for cam_num, file in enumerate(csv_files, start=1):
        df = pd.read_csv(file)
        df.rename(columns={'Photo_Index': 'Photo_Index', 
                           'Capture_Time (s)': 'Capture_Time', 
                           'Relative_Error (%)': 'Relative_Error'}, inplace=True)
        df['Camera_ID'] = int(cam_num)  # Ensure camera ID is an integer

        for index, row in df.iterrows():
            if row['Photo_Index'] not in merged_data["Photo_Index"]:
                merged_data["Photo_Index"].append(row['Photo_Index'])
                for i in range(1, num_cameras + 1):
                    merged_data[f'Camera_{i}_Capture_Time'].append(None)
                    merged_data[f'Camera_{i}_Relative_Error'].append(None)

            photo_index = row['Photo_Index']
            idx = merged_data["Photo_Index"].index(photo_index)
            camera_id = int(row['Camera_ID'])  # Explicit conversion to integer
            merged_data[f'Camera_{camera_id}_Capture_Time'][idx] = row['Capture_Time']
            merged_data[f'Camera_{camera_id}_Relative_Error'][idx] = row['Relative_Error']

    merged_df = pd.DataFrame(merged_data)
    specific_pairs = generate_unique_pairs()
    for cam1, cam2 in specific_pairs:
        capture_time_diff_col = f'Capture_Time_Diff_Cam_{cam1}_Cam_{cam2}'
        merged_df[capture_time_diff_col] = merged_df[f'Camera_{cam1}_Capture_Time'] - merged_df[f'Camera_{cam2}_Capture_Time']

    merged_df.to_csv(f'merged_capture_data_with_differences_{width}x{height}_{exposure_time}.csv', index=False)
    print("CSV files merged successfully. File saved as 'merged_capture_data_with_differences.csv'.")


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

    # Create directory for storing checkerboard images and CSV files
    test_folder = 'Test'
    if not os.path.exists(test_folder):
        os.makedirs(test_folder)

    for cam_num in range(1, num_cameras + 1):
        cam_folder = os.path.join(test_folder, f'Cam_{cam_num:02d}')
        if not os.path.exists(cam_folder):
            os.makedirs(cam_folder)

    # Set up server to listen for connections from clients
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(('0.0.0.0', 5000))
    server_socket.listen(num_cameras)
    print('Waiting for client connections...')

    client_sockets = []
    for cam_num in range(1, num_cameras + 1):
        client_socket, addr = server_socket.accept()
        print(f'Connected to {addr}')
        client_sockets.append(client_socket)

    # Send capture settings to all clients
    settings_message = f'SETTINGS {width} {height} {exposure_time}'.encode('utf-8')
    for client_socket in client_sockets:
        client_socket.sendall(settings_message)

    capturing = True
    count = 1
    input("Press Enter to start capturing images: ")

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
        # Send stop signal to all clients
        for client_socket in client_sockets:
            client_socket.sendall(b'STOP_RECORD')

        # Wait for stop confirmation from all clients
        for client_socket in client_sockets:
            confirmation = wait_for_confirmation(client_socket)
            if confirmation != b'RECORDING_STOPPED':
                print("Error: Did not receive stop confirmation from a client.")
                break
        else:
            print("All clients have stopped recording.")
            
            time.sleep(5)  # Wait for clients to prepare CSV files

            # Receive CSV files from each client
            for cam_num in range(1, num_cameras + 1):
                ip = f'192.168.1.{cam_num}'
                username = f'admin{cam_num}'
                password = f'Admin{cam_num}'
                receive_csv_scp(ip, username, password, cam_num, test_folder)

            # Merge received CSV files
            merge_csv_files(test_folder, num_cameras, width, height, exposure_time)

            time.sleep(5)

            plot_all_differences(f'merged_capture_data_with_differences_{width}x{height}_{exposure_time}.csv', width, height, exposure_time)

        # Close all client connections
        for client_socket in client_sockets:
            client_socket.close()

        server_socket.close()

    print("Server terminated.")

if __name__ == "__main__":
    main()
