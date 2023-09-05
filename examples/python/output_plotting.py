import time

# Import plotting library
import matplotlib.pyplot as plt

# Import tenma library
from src.tenma_serial.tenma_dc_lib import (
    instantiate_tenma_class_from_device_response,
)

# Set here the device node to connect to
device_node = "/dev/ttyACM0"

# Retrieve a proper tenma handler for your unit (mainly tries to keep values
# within ranges)
tenma = instantiate_tenma_class_from_device_response(device_node)

print(tenma.get_version())

data = []
tstamps = []
while True:
    current = tenma.running_current(1)
    voltage = tenma.running_voltage(1)
    timestamp = time.time()

    data.append(voltage)
    tstamps.append(timestamp)

    plt.clf()
    plt.plot(tstamps, data)
    plt.pause(0.5)
