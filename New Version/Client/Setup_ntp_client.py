import os
import subprocess
import time

# Server details for 'sim'
server_ip = '192.168.1.253'
server_user = 'admin'
server_password = 'Admin'

# Path to the NTP configuration file
ntp_config_file = '/etc/ntpsec/ntp.conf'

# The pool entries to comment out
pools_to_comment = [
    'pool 0.debian.pool.ntp.org iburst',
    'pool 1.debian.pool.ntp.org iburst',
    'pool 2.debian.pool.ntp.org iburst',
    'pool 3.debian.pool.ntp.org iburst'
]

# The new local NTP server entry
new_ntp_server = 'server 192.168.1.253 iburst minpoll 0 maxpoll 0'

def restart_ntp_on_server():
    try:
        # Use SSH to remotely restart the NTP service on the server
        subprocess.run([
            'ssh', f'{server_user}@{server_ip}', 'sudo systemctl restart ntpsec'
        ], check=True)
        print("NTP service restarted on the server successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart NTP service on the server: {e}")

def modify_ntp_config():
    try:
        # Read the content of the configuration file
        with open(ntp_config_file, 'r') as file:
            lines = file.readlines()

        # Flag to know if we inserted the new server
        server_inserted = False

        # Write back with modifications
        with open(ntp_config_file, 'w') as file:
            for index, line in enumerate(lines):
                # Comment out the default Debian pool entries
                if any(pool in line for pool in pools_to_comment):
                    file.write('# ' + line)
                else:
                    file.write(line)

                # Check if we're at the 'pool 3' line and insert the new server just after it
                if 'pool 3.debian.pool.ntp.org iburst' in line:
                    if index + 1 < len(lines) and lines[index + 1].strip() == '':
                        # The next line is already empty, so we insert the server
                        file.write(new_ntp_server + '\n')
                    else:
                        # Add an empty line and insert the server
                        file.write('\n' + new_ntp_server + '\n')
                    server_inserted = True

            # If the server was not inserted (e.g., if the pool 3 line was missing), append it at the end
            if not server_inserted:
                file.write(new_ntp_server + '\n')

        print(f"Successfully modified {ntp_config_file}")

    except Exception as e:
        print(f"An error occurred: {e}")

def restart_ntp_service():
    try:
        # Restart the NTP service
        subprocess.run(['sudo', 'systemctl', 'restart', 'ntpsec'], check=True)
        print("NTP service restarted successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to restart NTP service: {e}")

def sync_ntp_time():
    try:
        # Sync time with the local NTP server
        subprocess.run(['sudo', 'ntpdate', '192.168.1.253'], check=True)
        print("Time synchronized successfully with 192.168.1.253.")
    except subprocess.CalledProcessError as e:
        print(f"Failed to synchronize time: {e}")

if __name__ == '__main__':
    restart_ntp_on_server()
    time.sleep(5)
    modify_ntp_config()
    time.sleep(5)
    restart_ntp_service()
    time.sleep(5)
    sync_ntp_time()
