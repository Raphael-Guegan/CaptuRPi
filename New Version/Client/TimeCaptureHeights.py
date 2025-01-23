import os
import time
import csv
from picamera2 import Picamera2


# Initialize camera with specified resolution and exposure_time
def initialize_camera(width, height, exposure_time):
    global picam2
    picam2 = Picamera2()
    camera_config = picam2.create_still_configuration(main={"size": (width, height)}, buffer_count=1)
    picam2.configure(camera_config)
    picam2.set_controls({
        "AnalogueGain": 1.0,             # Set analog gain
        "ColourGains": (1.0, 1.0),       # Set color gains for white balance
        "Brightness": 0.5,               # Set brightness
        "Contrast": 1.0,                 # Set contrast
        "ExposureTime": exposure_time
    })
    picam2.start()
    return picam2

# Function to capture an image without reinitializing the camera
def capture_image(picam2,image_path):
    picam2.capture_file(image_path)

# Function to get the CPU temperature
def get_cpu_temp():
    temp_str = os.popen("vcgencmd measure_temp").readline()
    temp = float(temp_str.replace("temp=", "").replace("'C\n", ""))
    return temp

# Function to get the CPU usage
def get_cpu_usage():
    cpu_usage_str = os.popen("top -bn1 | grep 'Cpu(s)' | awk '{print $2 + $4}'").readline()
    return float(cpu_usage_str)

# Function to wait until the conditions are met
def wait_for_conditions(max_temp, max_cpu_usage):
    while True:
        temp = get_cpu_temp()
        cpu_usage = get_cpu_usage()

        print(f"Current CPU temperature: {temp}°C, CPU usage: {cpu_usage}%")

        if temp > max_temp or cpu_usage > max_cpu_usage:
            print("Conditions not met, waiting...")
            time.sleep(5)  # Wait for 5 seconds before checking again
        else:
            print("Conditions met, starting capture.")
            break

def relative_error(value, reference):
    return abs(value - reference) / reference

def main(width, heights, time_exposure):
    csv_file = "capture_results.csv"

    os.system('sudo cpufreq-set -g performance')
    
    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Height", "Pixel count", "Average time (s)"])

        for height in heights:
            pixel_count = width * height
            print(f"Testing height {height}...")

            # Initialize the camera with this fixed width and current height
            picam2 = initialize_camera(width, height, time_exposure)

            test_failed = True

            while test_failed:  # Loop to repeat the test if necessary
                times = []

                for i in range(7):
                    image_path = f"image_{width}x{height}_{i+1}.jpg"
                    start_time = time.time()
                    capture_image(picam2, image_path)
                    end_time = time.time()
                    times.append(end_time - start_time)

                for i in range(7):
                    image_path = f"image_{width}x{height}_{i+1}.jpg"
                    if os.path.exists(image_path):
                        os.remove(image_path) 

                # Check relative errors and redo the test if an error exceeds 10%
                for i in range(3, len(times)):
                    error = relative_error(times[i], times[2])
                    if error > 0.06:  # If relative error exceeds 10%
                        print(f"Relative error for capture {i+1} exceeds 10% ({error*100:.2f}%), retesting.")
                        break
                    else:
                        test_failed = False

                # If the test fails, repeat the test for this height
                if test_failed:
                    wait_for_conditions(max_temp=40.0, max_cpu_usage=20.0)
                    continue
        
                # Calculate the average time, excluding the first two
                avg_time = sum(times[2:]) / len(times[2:])
                print(f"Average time for height {height}: {avg_time} seconds")

                # If the test is successful, record the result and continue
                with open(csv_file, mode="a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow([f"{width}x{height}", pixel_count, avg_time])

                # Stop the camera after each height test
                picam2.stop()
                picam2.close()

                # Wait for CPU conditions to be met before moving to the next height
                wait_for_conditions(max_temp=40.0, max_cpu_usage=20.0)
        
                # Exit the while loop to move to the next height
                break


if __name__ == '__main__':
    os.nice(-20)
    
    # List of heights to test, with a fixed width
    heights = list(range(240, 3040, (3040 - 240) // 69))
    width = 4056  # Fixed width
    time_exposure = 10000  # in microseconds
    main(width, heights, time_exposure)
