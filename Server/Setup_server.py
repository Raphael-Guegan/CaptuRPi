import os
import re
import subprocess

# Function to retrieve the number at the end of the Raspberry Pi name
def get_raspberry_number():
    # Retrieve host name
    hostname = os.popen("hostname").read().strip()

    # Find a number at the end of the host name
    match = re.search(r'(\d+)$', hostname)

    if match:
        raspberry_number = int(match.group(1))
        print(f"Raspberry Pi name: {hostname}, number found: {raspberry_number}")
    else:
        raspberry_number = 253  # Default value if no number is found
        print(f"Raspberry Pi name: {hostname}, no number found, using {raspberry_number} by default.")

    return raspberry_number

# Function to write to the interfaces file for static IP configuration
def set_static_ip(raspberry_number):
    interfaces_file = "/etc/dhcpcd.conf"
    
    # IP address construction based on Raspberry Pi number
    ip_address = f"192.168.1.{raspberry_number}"
    
    # Content to be added to the interfaces file
    content = f"""
interface eth0
static ip_address={ip_address}/24
"""
    try:
        # Backup the existing file
        os.system(f"sudo cp {interfaces_file} {interfaces_file}.bak")

        # Write the new configuration to the interfaces file
        with open(interfaces_file, "a") as file:
            file.write(content)

        print(f"Configuration complete. Static IP set to: {ip_address}")
    except Exception as e:
        print(f"Error during IP configuration: {e}")

# Function to update NTP configuration
def update_ntp_conf():
    ntp_conf_file = '/etc/ntpsec/ntp.conf'
    new_ntp_config = """
server 127.127.1.0
fudge 127.127.1.0 stratum 10
restrict 192.168.1.0 mask 255.255.255.0 nomodify notrap
"""

    try:
        with open(ntp_conf_file, 'r') as file:
            conf_content = file.readlines()

        # Look for the line after which new configurations should be added
        insert_after = 'pool 3.debian.pool.ntp.org iburst\n'

        if insert_after in conf_content:
            index = conf_content.index(insert_after) + 1

            # If the next line is not empty, insert a blank line
            if index < len(conf_content) and conf_content[index].strip() != "":
                conf_content.insert(index, '\n')
                index += 1

            # Insert new NTP configuration
            conf_content.insert(index, new_ntp_config)
        
            # Save the updated NTP configuration file
            with open(ntp_conf_file, 'w') as file:
                file.writelines(conf_content)

            print(f"The file {ntp_conf_file} has been updated.")
        else:
            print(f"The line '{insert_after.strip()}' was not found in {ntp_conf_file}.")

    except Exception as e:
        print(f"Error while updating {ntp_conf_file}: {e}")

# Function to restart the NTPSec service
def restart_ntpsec():
    try:
        subprocess.run(['sudo', 'systemctl', 'restart', 'ntpsec'], check=True)
        print("The NTPSec service has been restarted.")
    except subprocess.CalledProcessError as e:
        print(f"Error while restarting the NTPSec service: {e}")

# Main execution
if __name__ == '__main__':
    raspberry_number = get_raspberry_number()
    set_static_ip(raspberry_number)
    os.system("sudo systemctl restart dhcpcd")
    update_ntp_conf()
    restart_ntpsec()

    print("Reboot the Raspberry Pi to apply changes...")
    os.system("sudo reboot")
