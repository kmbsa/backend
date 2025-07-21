import socket
import netifaces as ni

def get_local_ip():
    # Get all network interfaces
    interfaces = ni.interfaces()

    # We will first try to pick an IP from the 192.x.x.x range
    preferred_ip = None

    for interface in interfaces:
        try:
            # Get the IPv4 address associated with this interface
            ip = ni.ifaddresses(interface)[ni.AF_INET][0]['addr']
            
            # Skip loopback addresses
            if ip.startswith('127.'):
                continue
            
            # Check if it's in the 192.x.x.x range (preferred)
            if ip.startswith('192.'):
                preferred_ip = ip
                break

            # If no 192.x.x.x IP found, pick any non-loopback address
            if not preferred_ip:
                preferred_ip = ip

        except KeyError:
            continue

    if not preferred_ip:
        raise Exception("Could not find a valid network interface")

    return preferred_ip

def update_env_file(ip):
    # Update the .env file with the correct API URL
    with open("./testApp/.env", "r") as file:
        lines = file.readlines()

    # Check if API_URL already exists in the .env file
    found = False
    for i, line in enumerate(lines):
        if line.startswith("API_URL="):
            lines[i] = f"API_URL=http://{ip}:5000\n"
            found = True
            break

    # If API_URL doesn't exist, add it
    if not found:
        lines.append(f"API_URL=http://{ip}:5000\n")

    # Write back to .env
    with open("./testApp/.env", "w") as file:
        file.writelines(lines)

    print(f"✅ API_URL set to: http://{ip}:5000")

# Fetch the correct IP and update the .env file
local_ip = get_local_ip()
update_env_file(local_ip)
