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

# Function to wait until conditions are met
def wait_for_conditions(max_temp, max_cpu_usage):
    while True:
        temp = get_cpu_temp()
        cpu_usage = get_cpu_usage()

        print(f"Current CPU temperature: {temp}°C, CPU usage: {cpu_usage}%")

        if temp > max_temp or cpu_usage > max_cpu_usage:
            print("Conditions not met, waiting...")
            time.sleep(5)  # Wait 5 seconds before checking again
        else:
            print("Conditions met, starting capture.")
            break

def relative_error(value, reference):
    return abs(value - reference) / reference

def main(resolutions, time_exposure):
    csv_file = "capture_results.csv"

    os.system('sudo cpufreq-set -g performance')
    
    with open(csv_file, mode="w", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["Resolution", "Pixel count", "Average time (s)"])

        for resolution in resolutions:
            width, height = resolution
            pixel_count = width * height
            print(f"Testing resolution {width}x{height}...")

            # Initialize the camera with this resolution
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

                # Check for relative errors and retry the test if any error exceeds 10%
                for i in range(3, len(times)):
                    error = relative_error(times[i], times[2])
                    if error > 0.06:  # If the relative error exceeds 10%
                        print(f"Relative error for capture {i+1} exceeds 10% ({error*100:.2f}%), retrying the test.")
                        break
                    else:
                        test_failed = False

                # If the test fails, restart the test for this resolution
                if test_failed:
                    wait_for_conditions(max_temp=40.0, max_cpu_usage=20.0)
                    continue
        
                # Calculate the average time excluding the first two captures
                avg_time = sum(times[2:]) / len(times[2:])
                print(f"Average time for resolution {width}x{height}: {avg_time} seconds")

                # If the test is successful, log the result and proceed
                with open(csv_file, mode="a", newline="") as file:
                    writer = csv.writer(file)
                    writer.writerow([f"{width}x{height}", pixel_count, avg_time])

                # Release the camera after each resolution test
                picam2.stop()
                picam2.close()

                # Wait for CPU conditions to be met before moving to the next resolution
                wait_for_conditions(max_temp=40.0, max_cpu_usage=20.0)
        
                # Exit the while loop to proceed to the next resolution
                break


if __name__ == '__main__':
    os.nice(-20)
    resolutions = [
        (320, 240),   # 76,800 pixels
        (352, 288),   # 101,376 pixels
        (384, 384),   # 147,456 pixels
        (480, 320),   # 153,600 pixels
        (480, 360),   # 172,800 pixels
        (640, 352),   # 225,280 pixels
        (640, 360),   # 230,400 pixels
        (640, 400),   # 256,000 pixels
        (512, 512),   # 262,144 pixels
        (640, 480),   # 307,200 pixels
        (768, 432),   # 331,776 pixels
        (720, 480),   # 345,600 pixels
        (800, 480),   # 384,000 pixels
        (854, 480),   # 409,920 pixels
        (720, 576),   # 414,720 pixels
        (800, 600),   # 480,000 pixels
        (960, 540),   # 518,400 pixels
        (1024, 576),  # 589,824 pixels
        (1024, 600),  # 614,400 pixels
        (960, 720),   # 691,200 pixels
        (1152, 648),  # 746,496 pixels
        (1024, 768),  # 786,432 pixels
        (1280, 720),  # 921,600 pixels
        (1280, 768),  # 983,040 pixels
        (1152, 864),  # 995,328 pixels
        (1280, 800),  # 1,024,000 pixels
        (1360, 768),  # 1,044,480 pixels
        (1366, 768),  # 1,049,088 pixels
        (1080, 1080), # 1,166,400 pixels
        (1296, 972),  # 1,259,712 pixels
        (1440, 900),  # 1,296,000 pixels
        (1280, 1024), # 1,310,720 pixels
        (1536, 864),  # 1,327,104 pixels
        (1600, 900),  # 1,440,000 pixels
        (1400, 1050), # 1,470,000 pixels
        (1600, 1024), # 1,638,400 pixels
        (1680, 1050), # 1,764,000 pixels
        (1536, 1152), # 1,769,472 pixels
        (1920, 960),  # 1,843,200 pixels
        (1600, 1200), # 1,920,000 pixels
        (1920, 1080), # 2,073,600 pixels
        (2048, 1080), # 2,211,840 pixels
        (1920, 1200), # 2,304,000 pixels
        (2048, 1280), # 2,621,440 pixels
        (2560, 1080), # 2,764,800 pixels
        (2304, 1296), # 2,985,984 pixels
        (2000, 1500), # 3,000,000 pixels
        (2048, 1536), # 3,145,728 pixels
        (2560, 1440), # 3,686,400 pixels
        (2560, 1600), # 4,096,000 pixels
        (2800, 1575), # 4,410,000 pixels
        (2736, 1824), # 4,986,624 pixels
        (2592, 1944), # 5,038,848 pixels
        (2880, 1800), # 5,184,000 pixels
        (3072, 1728), # 5,308,416 pixels
        (3200, 1800), # 5,760,000 pixels
        (3000, 2000), # 6,000,000 pixels
        (3008, 2008), # 6,033,664 pixels
        (3840, 1600), # 6,144,000 pixels
        (3360, 1890), # 6,350,400 pixels
        (3456, 1944), # 6,723,264 pixels
        (3200, 2400), # 7,680,000 pixels
        (3840, 2160), # 8,294,400 pixels
        (4096, 2160), # 8,847,360 pixels
        (3456, 2592), # 8,962,752 pixels
        (3840, 2400), # 9,216,000 pixels
        (4056, 2280), # 9,244,800 pixels
        (4056, 2704), # 10,960,384 pixels
        (4000, 3000), # 12,000,000 pixels
        (4056, 3040)  # 12,319,680 pixels
    ]
    
    time_exposure = 10000  # in microseconds
    main(resolutions, time_exposure)
