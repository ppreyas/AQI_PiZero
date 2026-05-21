# PiZero Air Quality Meter
Monitor and log air quality with this Pi Zero W powered air quality meter, using PMS7003 and BME688 sensors and publish the results via MQTT to Home Assistant.

# Source: Heavily influenced from the work done by Electro Dan here:  https://electro-dan.co.uk/pc/raspberry-pi-air-quality-meter


# Operating System

Image OS: Raspberry PI OS 32 bit Lite
Customisations to be done to update Language, locale and wifi credentials

# First Steps post initial boot:

1. Update and upgrade packages: 

```
apt update && apt upgrade 
```

2. Install packages:

 ```
 git cmake gcc g++ iotop vim zram-tools
 ```
ZRAM sacrifices some CPU power in order to potentially allow more processes in the RAM available
iotop - Optional if you'd like to save RAM usage with any un-necessary writes
 
3. Update boot config to enable I2C for BME688 and UART for PMS7003. Disable audio as we're only using it for measuring air quality and don't need any audio.

in /boot/firmware/config.txt 

```
dtparam=i2c_arm=on

# Enable audio (loads snd_bcm2835)
dtparam=audio=off

[all]
dtoverlay=miniuart-bt
enable_uart=1
```

`sudo sh -c "echo i2c-dev >> /etc/modules"`

# Influx DB

Since its a 32-bit OS, ensure to use only the correct architecture binary
```
wget https://dl.influxdata.com/influxdb/releases/influxdb_1.8.10_armhf.deb
dpkg -i influxdb_1.8.10_armhf.deb
```

Influx DB logs:

```
systemctl enable influxdb
systemctl start influxdb
systemctl status influxdb
● influxdb.service - InfluxDB is an open-source, distributed, time series database
     Loaded: loaded (/usr/lib/systemd/system/influxdb.service; enabled; preset: enabled)
     Active: active (running) since Sun 2026-05-17 20:53:11 BST; 8s ago
 Invocation: 825a899181ee42bbb64ba7b4f5f77ba6
       Docs: https://docs.influxdata.com/influxdb/
    Process: 19376 ExecStart=/usr/lib/influxdb/scripts/influxd-systemd-start.sh (code=exited, status=0/SUCCESS)
   Main PID: 19377 (influxd)
      Tasks: 8 (limit: 378)
        CPU: 2.821s
     CGroup: /system.slice/influxdb.service
             └─19377 /usr/bin/influxd -config /etc/influxdb/influxdb.conf


```
Run the below command to validate if influxdb is running and to create the aqi database:

```
root@pizeroaqi:/var/log# python3
Python 3.13.5 (main, May  5 2026, 21:05:52) [GCC 14.2.0] on linux
Type "help", "copyright", "credits" or "license" for more information.
>>> from influxdb import InfluxDBClient
client = InfluxDBClient(host='localhost', port=8086)
>>> client = InfluxDBClient(host='localhost', port=8086)
>>> client.create_database('airq')
>>> client.get_list_database()
[{'name': '_internal'}, {'name': 'airq'}]
>>> exit()
```

## Python Requirements
`sudo apt install -y python3-pip python3-influxdb python3-schedule python3-serial python3-smbus2`

# Python Virtual env and activating venv

Do henceforth steps in the venv:

mkdir -p /code
python3 -m venv ./venv
source ./venv/bin/activate

```
(venv) root@pizeroaqi:/code# python3 -m pip install busio bme68x setuptools 
```

Validate installation with the below command:
```
python3 -c "import busio; print('busio OK')"
busio OK
```

# Clone Repositories

```
git clone https://github.com/mcalisterkm/p-sensors
git clone https://github.com/pi3g/bme68x-python-library
```

Put the BSEC zip in the bme68x-python-library directory that is created and unzip it there (unzip bsec_2-0-6-1_generic_release_04302021.zip). The folder BSEC_2.0.6.1_Generic_Release_04302021 should be created inside bme68x-python-library. This isn't available on bosch's website for download but can be accessed via wget from here:

```
wget "https://www.bosch-sensortec.com/media/boschsensortec/downloads/software/bme688_development_software/bsec_software_previous_versions/bsec_2-0-6-1_generic_release_04302021.zip"
```

`cd ~/bme68x-python-library`

The code is passing &id_regs (pointer-to-array) but the function expects uint8_t * (pointer-to-first-element). Since id_regs is already an array, you just drop the & 

`sed -i 's/bme68x_get_regs(BME68X_REG_UNIQUE_ID, \&id_regs/bme68x_get_regs(BME68X_REG_UNIQUE_ID, id_regs/' bme68xmodule.c`

`python3 setup.py install`

## Clone this repo

`git clone https://github.com/electro-dan/PiZero_Air_Quality_Meter.git`

`mv PiZero_Air_Quality_Meter/* ~`

# Debug if the sensors are working ok?
Enable I2C using raspi-config
Do: raspi-config → Interface Options → I2C → Enable → reboot


1. Check if I2C is enabled and the sensor is visible on the bus
Validate if BME688 is working by running the below: i2cdetect -y 1 or i2cdetect -y 2

```
/code/p-sensors/src/1.3.0/BurnIn# i2cdetect -y 1
     0  1  2  3  4  5  6  7  8  9  a  b  c  d  e  f
00:                         -- -- -- -- -- -- -- -- 
10: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
20: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
30: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
40: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
50: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
60: -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- -- 
70: -- -- -- -- -- -- 76 --                         

2. Confirm I2C kernel modules are loaded
lsmod | grep i2c

```
(venv) root@pizeroaqi:/code/p-sensors/src/1.3.0/BurnIn# lsmod | grep i2c
i2c_bcm2835            12288  1
i2c_dev                12288  2
```
3. Validate voltages using multi-meter:

```
BME688 pin	Pi Zero pin	GPIO
VCC	Pin 1 (3.3V)	—
GND	Pin 6 (GND)	—
SDA	Pin 3	GPIO 2
SCL	Pin 5	GPIO 3
SDO	GND or 3.3V	sets address
```

BME688:
Measure: Pin 3 vs Pin 9 → should be ~3.0V
Measure: Pin 5 vs Pin 9 → should be ~3.0V
Measure: Pin 1 vs Pin 9 (GND) → should read 3.3V

PMS7003
```
PMS7003 pin	Pi Zero pin
VCC (5V)	Pin 2 or 4
GND	Pin 6
TX	Pin 10 (RXD, GPIO15)
RX	Pin 8 (TXD, GPIO14)
```


Testing Sensors PMS7003:

```
python3 - <<'EOF'
import serial
with serial.Serial('/dev/serial0', baudrate=9600, timeout=5) as s:
    data = s.read(100)
    print(repr(data))
EOF
b'' --> this means the sensor is not returning data
```

```
(venv) root@pizeroaqi:/code# python3 - <<'EOF'
import serial
with serial.Serial('/dev/serial0', baudrate=9600, timeout=5) as s:
    data = s.read(100)
    print(repr(data))
EOF
b'BM\x00\x1c\x00\x07\x00\x10\x00\x14\x00\x07\x00\x10\x00\x14\x03=\x02\x7f\x00@\x00\x00\x00\x00\x00\x00\x12\x00\x02\x14BM\x00\x1c\x00\x07\x00\x10\x00\x14\x00\x07\x00\x10\x00\x14\x038\x02{\x00>\x00\x00\x00\x00\x00\x00\x12\x00\x02\tBM\x00\x1c\x00\x07\x00\x10\x00\x13\x00\x07\x00\x10\x00\x13\x036\x02x\x00=\x00\x00\x00\x00\x00\x00\x12\x00\x02\x01BM\x00\x1c'

```


Test Airqread.py by running:

```
python3 PiZero_Air_Quality_Meter/airqread.py
[INFO] 2026-05-18 17:31:46,764 Starting BME688 setup
INITIALIZED BME68X
VARIANT BME688
INITIALIZED BSEC
BSEC VERSION: 2.0.6.1
320 100 100 100 200 200 200 320 320 320 
5 2 10 30 5 5 5 5 5 5 
SET HEATER CONFIG (PARALLEL MODE)
DUR PROF AFTER PI3G
5 2 10 30 5 5 5 5 5 5 
SET BSEC STATE RSLT 0
[INFO] 2026-05-18 17:31:46,907 Starting BME688 thread
SET BME68X CONFIG
SET HEATER CONFIG (FORCED MODE)
[INFO] 2026-05-18 17:31:47,156 Starting sensor and DB schedules
SET BME68X CONFIG
SET HEATER CONFIG (FORCED MODE)
BSEC SENSOR CONTROL RSLT 100
SET BME68X CONFIG
SET HEATER CONFIG (FORCED MODE)
BSEC SENSOR CONTROL RSLT 100
```
What the above means:

```
INITIALIZED BME68X          ← sensor chip found and initialised on I2C
VARIANT BME688              ← confirmed it's a BME688 (not BME680)
INITIALIZED BSEC            ← Bosch's air quality algorithm library loaded
BSEC VERSION: 2.0.6.1      ← matches the version the guide requires

320 100 100 100 ...         ← heater temperature profile (°C)
5 2 10 30 5 5 5 ...         ← heater duration profile (ms)
SET HEATER CONFIG           ← profile applied successfully

SET BSEC STATE RSLT 0       ← burn-in state file loaded (0 = success)

SET BME68X CONFIG           ┐
SET HEATER CONFIG           ├── repeating every ~3 seconds = BSEC control
BSEC SENSOR CONTROL RSLT 100 ┘   loop running normally (100 = success)


## Burn-In
`git clone https://github.com/mcalisterkm/p-sensors`

`cd ~/p-sensors/src/1.3.0/BurnIn/`

`nohup python3 burn_in.py &`

## Wait 24h ##. 
Put hand cleanser gel (60 / 70% alcohol) in front of sensor for a short while during burn in.

Copy new conf_ and state_ files from conf subfolder to conf subfolder in home (or where PiZero_Air_Quality_Meter is cloned to).

Update airqread.py with filename.


# Run Airqread.py

/dev/ttyS0 might not exist and this will be based on your configuration. Check if /dev/serial0. Update this in airqread.py by running this below:

`sed -i "s|/dev/ttyS0|/dev/serial0|g" /code/PiZero_Air_Quality_Meter/airqread.py`

The below might also be required based on which I2C bus number your device is running on:

bme = BME68X(cnst.BME68X_I2C_ADDR_LOW, 0)  # bus 0 doesn't exist
Earlier we confirmed /dev/i2c-0 doesn't exist — only /dev/i2c-1 and /dev/i2c-2. Change it to:

bme = BME68X(cnst.BME68X_I2C_ADDR_LOW, 1)  # use /dev/i2c-1

Execute Airqread.py by running:

`python3 airqread.py` --> this should run for atleast 15 mins so that data is written to influxdb

Sample Output:

```
(venv) root@pizeroaqi:/code# python3 PiZero_Air_Quality_Meter/airqread.py
[INFO] 2026-05-18 17:53:57,382 Starting BME688 setup
INITIALIZED BME68X
VARIANT BME688
INITIALIZED BSEC
BSEC VERSION: 2.0.6.1
320 100 100 100 200 200 200 320 320 320 
5 2 10 30 5 5 5 5 5 5 
SET HEATER CONFIG (PARALLEL MODE)
DUR PROF AFTER PI3G
5 2 10 30 5 5 5 5 5 5 
SET BSEC STATE RSLT 0
[INFO] 2026-05-18 17:53:57,523 Starting BME688 thread
SET BME68X CONFIG
SET HEATER CONFIG (FORCED MODE)
[INFO] 2026-05-18 17:53:57,773 Starting sensor and DB schedules
SET BME68X CONFIG
SET HEATER CONFIG (FORCED MODE)
BSEC SENSOR CONTROL RSLT 100
[INFO] 2026-05-18 18:00:00,783 DB Write
```

# InfluxDB

Run the below commands:

1. influx
2. USE airq
SELECT * FROM air_sensors ORDER BY time DESC LIMIT 10

Sample output:

```
name: air_sensors
time                breath_voc_accuracy breath_voc_equivalent co2_accuracy co2_equivalent gas_percentage     gas_percentage_accuracy humidity          iaq iaq_accuracy location pm10 pm1_0 pm2_5 raw_pressure temperature
----                ------------------- --------------------- ------------ -------------- --------------     ----------------------- --------          --- ------------ -------- ---- ----- ----- ------------ -----------
1779123600818997245 2                   0.3426457643508911    2            400            -2.082138776779175 2                       60.97412872314453 0   2            Bedroom  21   7     18    100000.125   18.112632751464844
```




## Integrating with Home Assistant 

I have used Mosquitto MQTT broker here installed on my Raspberry PI 4B running HAOS. Configuration is pretty simple with just using the MQTT port of your choice [1883 by default] and creating a username and password as a login in the configuration screen.

I have passed the below values as an environment file to be loaded during execution.

MQTT_USER=<username>
MQTT_PASSWORD=<password>
MQTT_HOST=<MQTT Broker host i.e., my Home Assistant IP>
MQTT_PORT=<MQTT Broker Port>
MQTT_TOPIC=<name of the topic>

Logs on HAOS when messages get published from PI Zero:


```
May 21 00:45:00 pizeroaqi python3[4537]: [INFO] 2026-05-21 00:45:00,005 DB Write
May 21 00:45:00 pizeroaqi python3[4537]: [INFO] 2026-05-21 00:45:00,017 MQTT published: {'pm1_0': 0, 'pm2_5': 2, 'pm10': 4, 'iaq': 34.9, 'temperature': 15.8, 'humid>
May 21 00:52:00 pizeroaqi python3[4537]: [INFO] 2026-05-21 00:52:00,907 DB Write
May 21 00:52:00 pizeroaqi python3[4537]: [INFO] 2026-05-21 00:52:00,915 MQTT published: {'pm1_0': 0, 'pm2_5': 2, 'pm10': 2, 'iaq': 35.5, 'temperature': 15.8, 'humid>
```

Log messages at Home Assistant side:

```
2026-05-21 00:45:00: Received PUBLISH from auto-C92343E9-9A1E-6993-1A9A-57DB633689A0 (d0, q0, r0, m0, 'air_quality/state_data', ... (190 bytes))
2026-05-21 00:45:00: Sending PUBLISH to 7cg3Y4QNSZq3gYudWqEKg6 (d0, q0, r0, m0, 'air_quality/state_data', ... (190 bytes))
2026-05-21 00:45:24: Received PINGREQ from auto-C92343E9-9A1E-6993-1A9A-57DB633689A0
2026-05-21 00:45:24: Sending PINGRESP to auto-C92343E9-9A1E-6993-1A9A-57DB633689A0
2026-05-21 00:45:50: Received PINGREQ from 7cg3Y4QNSZq3gYudWqEKg6
2026-05-21 00:45:50: Sending PINGRESP to 7cg3Y4QNSZq3gYudWqEKg6
...
2026-05-21 00:51:50: Received PINGREQ from 7cg3Y4QNSZq3gYudWqEKg6
2026-05-21 00:51:50: Sending PINGRESP to 7cg3Y4QNSZq3gYudWqEKg6
2026-05-21 00:52:00: Received PUBLISH from auto-C92343E9-9A1E-6993-1A9A-57DB633689A0 (d0, q0, r0, m0, 'air_quality/state_data', ... (190 bytes))
2026-05-21 00:52:00: Sending PUBLISH to 7cg3Y4QNSZq3gYudWqEKg6 (d0, q0, r0, m0, 'air_quality/state_data', ... (190 bytes))
```

