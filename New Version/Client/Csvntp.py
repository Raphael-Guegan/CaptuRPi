import ntplib
from time import ctime, time as t_time
import csv
import os
import time as t

# Function to get the NTP offset
def get_ntp_offset(server):
    try:
        client = ntplib.NTPClient()
        response = client.request(server)
        offset = response.offset
        return offset
    except Exception as e:
        print(f"Error during NTP request: {e}")
        return None

# Function to log data to a CSV file
def log_ntp_offset_to_csv(file_path, server, interval=16):
    # Check if the CSV file already exists
    file_exists = os.path.isfile(file_path)
    
    # Open or create the CSV file
    with open(file_path, mode='a', newline='') as csv_file:
        fieldnames = ['timestamp', 'ntp_offset']
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)

        # Write the header if the file is new
        if not file_exists:
            writer.writeheader()

        try:
            os.system('sudo ntpdate -b 192.168.1.253')
            while True:
                offset = get_ntp_offset(server)
                if offset is not None:
                    writer.writerow({'timestamp': ctime(), 'ntp_offset': offset})
                    print(f"NTP offset recorded: {offset} at {ctime()}")
                else:
                    print(f"Unable to retrieve offset at {ctime()}")
                t.sleep(interval)
        except KeyboardInterrupt:
            print("\nProgram stopped by user request (Ctrl+C).")

# Parameters
ntp_server = "192.168.1.253"  # NTP server to query
output_csv = "ntp_offsets.csv"  # Output CSV file name
log_interval = 16  # Time interval between each request (in seconds)

# Start logging NTP offsets
log_ntp_offset_to_csv(output_csv, ntp_server, log_interval)
