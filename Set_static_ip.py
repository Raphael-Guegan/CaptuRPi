import os
import re

# Function to retrieve the number at the end of the Raspberry Pi's name
def get_raspberry_number():
    # Get the hostname
    hostname = os.popen("hostname").read().strip()

    # Search for a number at the end of the hostname
    match = re.search(r'(\d+)$', hostname)

    if match:
        raspberry_number = int(match.group(1))
        print(f"Raspberry Pi name: {hostname}, number found: {raspberry_number}")
    else:
        raspberry_number = 253  # Default value if no number is found
        print(f"Raspberry Pi name: {hostname}, no number found, using default {raspberry_number}.")

    return raspberry_number

# Function to write to the interfaces file
def set_static_ip(raspberry_number):
    interfaces_file = "/etc/dhcpcd.conf"
    
    # Build the IP address based on the Raspberry Pi's number
    ip_address = f"192.168.1.{raspberry_number}"
    
    # Content to add to the interfaces file
    content = f"""
interface eth0
static ip_address={ip_address}/24
"""
    try:
        # Backup the existing file
        os.system(f"sudo cp {interfaces_file} {interfaces_file}.bak")

        # Write to the interfaces file
        with open(interfaces_file, "a") as file:
            file.write(content)

        print(f"Configuration completed. Static IP set: {ip_address}")
    except Exception as e:
        print(f"Error during configuration: {e}")

# Get the Raspberry Pi's number
raspberry_number = get_raspberry_number()

# Call the function to configure the IP
set_static_ip(raspberry_number)

# Reboot the Raspberry Pi to apply changes
os.system("sudo systemctl restart dhcpcd")
print("Rebooting Raspberry Pi to apply changes...")
os.system("sudo reboot")
