# import necessary modules
import threading
import time
import math
from sense_hat import SenseHat
from datetime import datetime
from csv import writer
from pathlib import Path
from queue import Queue

# get the path to the directory where this script is located
base_folder = Path(__file__).parent.resolve()

# set the path to the CSV file where the data will be written
data_file = base_folder / 'data.csv'

# create a SenseHat object to interact with the Sense HAT device
sense = SenseHat()

# set the gain and integration cycles for the Sense HAT's color sensors
sense.colour.gain = 60
sense.colour.integration_cycles = 64

# configure the Sense HAT's IMU to enable the accelerometer, magnetometer, and gyroscope
sense.set_imu_config(True, True, True)

# set the time delay between data readings in seconds
delay = 5

# get the starting time
start_time = datetime.now()

# get the starting yaw angle from the Sense HAT's orientation sensor
starting_yaw = round(sense.get_orientation()['yaw'], 3)

# set the colors for displaying data on the Sense HAT's LED matrix
red = (255, 0, 0)
green = (0, 255, 0)

# set the altitude of the International Space Station (ISS) in meters
iss_altitude = 408_000

# set the radius of the Earth in meters
earth_radius = 6_378_137

# create a queue to store the yaw angle readings from the Sense HAT's orientation sensor
yaw_queue = Queue()

# add the starting yaw angle to the queue
yaw_queue.put(starting_yaw)

# create a queue to store the angular velocity readings calculated from the yaw angle readings
angular_velocity_queue = Queue()

# add an initial angular velocity of zero to the queue
angular_velocity_queue.put(0)

# define a function for displaying the average linear velocity on the Sense HAT's LED matrix
def display_message(queue, stop_event):
    # get the current time using the monotonic clock
    start_time = time.monotonic()
    # run this loop for 30 seconds or until the stop_event is set
    while not stop_event.is_set() and time.monotonic() - start_time < 30:
        # check if the queue contains any angular velocity readings
        if not queue.empty():
            # calculate the average angular velocity from the queue
            avg_angular_velocity = sum(queue.queue) / queue.qsize()
            # calculate the average linear velocity based on the angular velocity and the altitude of the ISS
            avg_linear_velocity = round(avg_angular_velocity * (earth_radius + iss_altitude), 3)
            # create a message string with the average linear velocity
            message = f"{avg_linear_velocity} m/s"
            # display the message on the Sense HAT's LED matrix
            sense.show_message(str(message))
            # remove the first angular velocity reading from the queue
            queue.get()
        # wait for 0.1 seconds before checking the queue again
        time.sleep(0.1)

# define a function for calculating angular velocity
def get_angular_velocity(yaw):
    #Returns the change in yaw angle over `delay` seconds.
    previous_yaw = yaw_queue.queue[-1]
    angular_velocity = (yaw - previous_yaw) / delay
    return angular_velocity

# define a function for writing data to a CSV file
def write_data(queue, stop_event):
    # open the CSV file in write mode with buffering and no line ending
    with open(data_file, 'w', buffering=1, newline='') as f:
        # create a CSV writer object for writing data to the file
        data_writer = writer(f)
        # write the header row for the CSV file
        data_writer.writerow(['datetime', 'yaw', 'angular_velocity', 'linear_velocity'])
       
# keep track of the last time the file was saved
        last_save_time = datetime.now()
        # loop until the stop event is set or 2 hours and 50 mins have elapsed
        while not stop_event.is_set() and (datetime.now() - start_time).seconds < 10_200:
            # flush the file buffer every 10 seconds to ensure that data is written to disk
            time_since_last_save = datetime.now() - last_save_time
            if time_since_last_save.seconds > 10:
                f.flush()
                last_save_time = datetime.now()
            # read the current orientation data from the SenseHat
            orientation = sense.get_orientation()
            current_yaw = round(orientation['yaw'], 3)
            # calculate the angular velocity and linear velocity based on the current and previous yaw angles
            angular_velocity = round(get_angular_velocity(current_yaw), 3)
            linear_velocity = round(angular_velocity * (earth_radius + iss_altitude), 3)
            # add the data to the CSV file and the queue
            time_difference = datetime.now() - last_save_time
            if time_difference.seconds > delay:
                data = [datetime.now(), current_yaw, angular_velocity, linear_velocity]
                data_writer.writerow(data)
                angular_velocity_queue.put(angular_velocity)
                last_save_time = datetime.now()
            yaw_queue.put(current_yaw)

# create an event object to signal when the threads should stop
stop_event = threading.Event()

# create a thread to display the current linear velocity on the SenseHat
display_thread = threading.Thread(target=display_message, args=(angular_velocity_queue, stop_event))
display_thread.start()

# create a thread to write the data to a CSV file
write_thread = threading.Thread(target=write_data, args=(angular_velocity_queue, stop_event))
write_thread.start()

try:
    # Keep checking if the threads are still alive using a while loop
    while display_thread.is_alive() and write_thread.is_alive():
        # Sleep for 0.1 seconds to reduce the amount of CPU usage
        time.sleep(0.1)
except KeyboardInterrupt:
    # If a KeyboardInterrupt exception is raised (e.g. user presses Ctrl-C), print "Interrupted"
    print('Interrupted')
finally:
    # Signal the stop event to stop the threads
    stop_event.set()
    # Wait for the write thread to finish using the join() method
    write_thread.join()
    # Wait for the display thread to finish using the join() method
    display_thread.join()
