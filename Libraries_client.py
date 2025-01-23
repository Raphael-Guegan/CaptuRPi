import subprocess

def run_command(command):
    try:
        subprocess.run(command, shell=True, check=True)
        print(f"Order successfully executed: {command}")
    except subprocess.CalledProcessError as e:
        print(f"Error during command execution: {command}\nError: {e}")

def main():
    commands = [
        "sudo apt update",
        "sudo apt upgrade -y",
        "sudo apt install python3-paramiko -y",
        "sudo apt install python3-scp -y",
        "sudo apt install ntp -y",
        "sudo apt install ntpdate -y",
        "sudo apt install python3-pandas -y",
        "sudo apt install python3-ntplib -y",
        "sudo apt-get install cpufrequtils -y",
        "sudo apt install dhcpcd5 -y"
    ]

    for command in commands:
        run_command(command)

if __name__ == "__main__":
    main()
