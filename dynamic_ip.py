import socket
import netifaces as ni
import os 
from dotenv import load_dotenv, set_key 

def get_local_ip():
    """
    Attempts to find the local IP address, preferring a 192.x.x.x address.
    Raises an exception if no valid network interface with an IPv4 address is found.
    """
    interfaces = ni.interfaces()
    preferred_ip = None

    for interface in interfaces:
        try:
            # Get IPv4 addresses for the current interface
            ip_info = ni.ifaddresses(interface).get(ni.AF_INET)
            if ip_info:
                # Iterate through all IPs assigned to the interface
                for ip_details in ip_info:
                    ip = ip_details['addr']
                    
                    # Skip loopback addresses (e.g., 127.0.0.1)
                    if ip.startswith('127.'):
                        continue
                    
                    # Prioritize IP addresses in the 192.x.x.x range (common for local networks)
                    if ip.startswith('192.'):
                        preferred_ip = ip
                        break # Found a preferred IP, exit inner loop
                if preferred_ip:
                    break # Found a preferred IP, exit outer loop
        except KeyError:
            # This interface might not have IPv4 addresses, or it's down
            continue

    # Fallback: if no 192.x.x.x IP found, try to find any non-loopback IP
    if not preferred_ip:
        for interface in interfaces:
            try:
                ip_info = ni.ifaddresses(interface).get(ni.AF_INET)
                if ip_info:
                    for ip_details in ip_info:
                        ip = ip_details['addr']
                        if not ip.startswith('127.'):
                            preferred_ip = ip
                            break # Found any non-loopback IP, exit inner loop
                if preferred_ip:
                    break # Found any non-loopback IP, exit outer loop
            except KeyError:
                continue

    if not preferred_ip:
        raise Exception("Could not find a valid non-loopback network interface with an IPv4 address.")

    return preferred_ip

def update_env_file(env_path, key, value):
    """
    Updates or adds a key-value pair in a specified .env file.
    Creates the file and its parent directories if they don't exist.
    """
    # Ensure the directory for the .env file exists
    os.makedirs(os.path.dirname(env_path), exist_ok=True)
    
    # load_dotenv loads existing variables. set_key adds/updates a variable.
    # set_key also ensures the file is created if it doesn't exist.
    dotenv_path = env_path
    load_dotenv(dotenv_path) # Load existing environment variables
    set_key(dotenv_path, key, value) # Set or update the specific key

    # print(f"✅ {key} set to: {value} in {env_path}")


# --- Determine the local IP address ---
local_ip = get_local_ip()
api_url_value = f"http://{local_ip}:5000"


# --- Update the frontend's .env file (src/testApp/.env) ---
frontend_env_path = os.path.join("src", "testApp", ".env")
update_env_file(frontend_env_path, "API_URL", api_url_value)


# --- Update the backend's .env file (src/backend/.env) ---
backend_env_path = os.path.join("src", "backend", ".env")
update_env_file(backend_env_path, "EXTERNAL_BASE_URL", api_url_value)

print("\nAll .env files updated successfully.")
print("Remember to restart your Flask backend and React Native app to apply changes!\n")
