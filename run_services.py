import subprocess
import sys
from time import sleep

def run_services():
    commands = [
        ["docker", "run", "--name", "my-redis", "-p", "6379:6379", "-d", "redis"],
    ]
    
    processes = []
    try:
        for command in commands:
            process = subprocess.Popen(command)
            processes.append(process)
            sleep(2)  # Give each service time to start
        
        # Wait for any process to finish
        for process in processes:
            process.wait()
            
    except KeyboardInterrupt:
        print("\nStopping all services...")
        for process in processes:
            process.terminate()
        sys.exit(0)

if __name__ == "__main__":
    run_services() 