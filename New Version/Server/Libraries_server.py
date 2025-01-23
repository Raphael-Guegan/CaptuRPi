import subprocess

def run_command(command):
    try:
        # Exécute la commande
        subprocess.run(command, shell=True, check=True)
        print(f"Commande exécutée avec succès: {command}")
    except subprocess.CalledProcessError as e:
        print(f"Erreur lors de l'exécution de la commande: {command}\nErreur: {e}")

def main():
    # Commandes à exécuter
    commands = [
        "sudo apt update",
        "sudo apt upgrade -y",
        "sudo apt install ntp -y",
        "sudo apt install python3-scp -y",
        "sudo apt install python3-pandas -y",
        "sudo apt install python3-paramiko -y",
        "sudo apt install dhcpcd5 -y"
    ]

    for command in commands:
        run_command(command)

if __name__ == "__main__":
    main()
