import logging
import threading
import schedule
import json
import paho.mqtt.client as mqtt
from pathlib import Path
from time import sleep
from influxdb import InfluxDBClient
from bme68x import BME68X
import bme68xConstants as cnst
import bsecConstants as bsec
from pms7003 import Pms7003Sensor,PmsSensorException
from dotenv import load_dotenv
import os

# Amend this to your state file name
state_file_name = "state_data-76-1644683649517.txt"

# Last BME688 BSEC readings stored here
g_bme688_bsec_data = {}
g_pms7003_data = {}

load_dotenv()
# MQTT configuration from environment variables
MQTT_HOST     = os.getenv('MQTT_HOST')
MQTT_PORT     = int(os.getenv('MQTT_PORT'))
MQTT_USER     = os.getenv('MQTT_USER')
MQTT_PASSWORD = os.getenv('MQTT_PASSWORD')
MQTT_TOPIC    = os.getenv('MQTT_TOPIC', 'air_quality/state')

logging.basicConfig(format='[%(levelname)s] %(asctime)s %(message)s', level=logging.INFO)
logger = logging.getLogger()

# # Connect to local instance
# client = InfluxDBClient(host='localhost', port=8086)
# # Use airq database (created by running client.create_database('airq'))
# client.switch_database('airq')

# Connect to PMS7003 sensor using serial
pms_sensor = Pms7003Sensor('/dev/serial0')

## BME688 state file reading
## from https://github.com/mcalisterkm/p-sensors/blob/master/src/1.3.0/BurnIn/read_conf.py
def read_bme688_state_file(state_file_name):
    state_path = str(Path(__file__).resolve().parent.joinpath('conf', state_file_name))
    state_file = open(state_path, 'r')
    # strip the brackets [.....]
    state_str =  state_file.read()[1:-1]
    # split on delimiter ,
    state_list = state_str.split(",")
    state_int = [int(x) for x in state_list]
    return(state_int)
    # Debug - Checking the right types are present
    # print(state_int)
    # print("-----------------\n")
    # print(type(state_int))
    # print(type(state_int[1]))

## BME688 setup 
## from https://github.com/mcalisterkm/p-sensors/blob/master/src/1.3.0/BurnIn/read_conf.py
def bme688_setup():
    # Set params
    temp_prof = [320, 100, 100, 100, 200, 200, 200, 320, 320, 320]
    dur_prof =[5, 2, 10, 30, 5, 5, 5, 5, 5, 5]
    # Initialise the sensor
    #  BME68X_I2C_ADDR_LOW is the pimoroni BME688 I2C default address
    #  BME68X_I2C_ADDR_HIGH is the PI3G BME688 I2C default address
    bme = BME68X(cnst.BME68X_I2C_ADDR_LOW, 0)
    logging.debug(bme.set_heatr_conf(cnst.BME68X_ENABLE, temp_prof, dur_prof, cnst.BME68X_PARALLEL_MODE))
    sleep(0.1)
    # logging.info(bme.get_bsec_state())
    state_int = read_bme688_state_file(state_file_name) # read burn in state file
    logging.debug(bme.set_bsec_state(state_int))
    logging.debug("Config set....")
    logging.debug(bme.set_sample_rate(bsec.BSEC_SAMPLE_RATE_LP))
    logging.debug("Rate Set")
    
    return bme

## Reading BME688 data
## from https://github.com/pi3g/bme68x-python-library/blob/main/examples/parallel_mode.py
def bme688_get_data(sensor):
    data = {}
    try:
        data = sensor.get_bsec_data()
    except Exception as e:
        logging.error(e)
        return None
    if data == None or data == {}:
        sleep(0.1)
        return None
    else:
        sleep(3)
        return data

## BME688 read data 
## from https://github.com/mcalisterkm/p-sensors/blob/master/src/1.3.0/BurnIn/read_conf.py
# modified to prevent infinite loop and store result in a global variable
def bme688_read():
    global g_bme688_bsec_data
    try:
        # Called continuously so that BSEC learns and updates
        # BME688 reading
        logging.debug("Read BME688")

        # Reading may take a few seconds
        bsec_data = bme688_get_data(bme)
        tries = 0
        while bsec_data == None:
            bsec_data = bme688_get_data(bme)
            tries += 1
            if tries > 300:
                raise Exception("No data retrieved from BME688")

        logging.debug(f"BME688 out: {bsec_data}")

        # Save value in global result
        g_bme688_bsec_data = bsec_data
        # Sample: {
        #   'sample_nr': 136, 'timestamp': 431867731812262, 'iaq': 16.5640869140625, 'iaq_accuracy': 2, 
        #   'static_iaq': 6.463951110839844, 'static_iaq_accuracy': 2, 'co2_equivalent': 425.8558044433594, 'co2_accuracy': 2, 
        #   'breath_voc_equivalent': 0.37781664729118347, 'breath_voc_accuracy': 2, 'raw_temperature': 26.79345703125, 
        #   'raw_pressure': 101746.6953125, 'raw_humidity': 40.00993347167969, 'raw_gas': 6471.68798828125, 'stabilization_status': 0, 
        #   'run_in_status': 0, 'temperature': 21.753707885742188, 'humidity': 54.111968994140625, 'comp_gas_value': 4.563065528869629, 
        #   'comp_gas_accuracy': 0, 'gas_percentage': -0.8414490222930908, 'gas_percentage_accuracy': 2
        # }
    except Exception as e:
        logging.error(e)

def bme688_thread():
    while True:
        bme688_read()
        # Wait 1 second before reading again
        sleep(1)

def pms7003_read():
    global g_pms7003_data
    try:
        # Sleep 50 seconds before wakeup
        sleep(50)

        logging.debug("Wakeup PMS7003")

        # Wake up PMS7003 sensor
        pms_sensor.wakeup()
        # Sleep 60 seconds, then read
        sleep(60)
        dictOutput = pms_sensor.read()

        logging.debug(f"PMS7003 out: {dictOutput}")
        
        logging.debug("Sleep PMS7003")
        # sleep after reading
        pms_sensor.sleep()

        g_pms7003_data = dictOutput
        # Sample: {
        #   'pm1_0cf1': 2, 'pm2_5cf1': 4, 'pm10cf1': 4, 
        #   'pm1_0': 2, 'pm2_5': 4, 'pm10': 4, 
        #   'n0_3': 792, 'n0_5': 204, 'n1_0': 52, 'n2_5': 0, 'n5_0': 0, 'n10': 0
        # }
    except Exception as e:
        logging.error(e)

def mqtt_publish_discovery(client):
    sensors = [
        ("pm1_0",                 "PM1.0",              "µg/m³", None),
        ("pm2_5",                 "PM2.5",              "µg/m³", None),
        ("pm10",                  "PM10",               "µg/m³", None),
        ("iaq",                   "Air Quality IAQ",    "IAQ",   None),
        ("temperature",           "Temperature",        "°C",    "temperature"),
        ("humidity",              "Humidity",           "%",     "humidity"),
        ("raw_pressure",          "Pressure",           "hPa",   "pressure"),
        ("co2_equivalent",        "CO2 Equivalent",     "ppm",   None),
        ("breath_voc_equivalent", "Breath VOC",         "ppm",   None),
        ("gas_percentage",        "Gas Percentage",     "%",     None),
    ]
    for field, name, unit, device_class in sensors:
        config_topic = f"homeassistant/sensor/air_quality/{field}/config"
        payload = {
            "name": name,
            "state_topic": MQTT_TOPIC,
            "unit_of_measurement": unit,
            "value_template": f"{{{{ value_json.{field} }}}}",
            "unique_id": f"air_quality_{field}",
            "device": {
                "identifiers": ["pizero_air_quality"],
                "name": "Pi Zero Air Quality",
                "model": "BME688 + PMS7003",
                "manufacturer": "Custom"
            }
        }
        if device_class:
            payload["device_class"] = device_class
        client.publish(config_topic, json.dumps(payload), retain=True)
    logging.info("MQTT discovery messages published")
def write_to_db():
    try:
        if g_pms7003_data and g_bme688_bsec_data:
            logging.info("DB Write")
            json_write_body = [
                {
                    "measurement": "air_sensors",
                    "tags": {"location": "Preyas's Office Room"},
                    "fields": {
                        "pm1_0":                  g_pms7003_data['pm1_0'],
                        "pm2_5":                  g_pms7003_data['pm2_5'],
                        "pm10":                   g_pms7003_data['pm10'],
                        "iaq":                    g_bme688_bsec_data["iaq"],
                        "iaq_accuracy":           g_bme688_bsec_data["iaq_accuracy"],
                        "temperature":            g_bme688_bsec_data["temperature"],
                        "humidity":               g_bme688_bsec_data["humidity"],
                        "raw_pressure":           g_bme688_bsec_data["raw_pressure"],
                        "co2_equivalent":         g_bme688_bsec_data["co2_equivalent"],
                        "co2_accuracy":           g_bme688_bsec_data["co2_accuracy"],
                        "breath_voc_equivalent":  g_bme688_bsec_data["breath_voc_equivalent"],
                        "breath_voc_accuracy":    g_bme688_bsec_data["breath_voc_accuracy"],
                        "gas_percentage":         g_bme688_bsec_data["gas_percentage"],
                        "gas_percentage_accuracy":g_bme688_bsec_data["gas_percentage_accuracy"],
                    }
                }
            ]
            # Write to InfluxDB
            #client.write_points(json_write_body)

            # Publish to MQTT
            mqtt_payload = {
                "pm1_0":                  g_pms7003_data['pm1_0'],
                "pm2_5":                  g_pms7003_data['pm2_5'],
                "pm10":                   g_pms7003_data['pm10'],
                "iaq":                    round(g_bme688_bsec_data["iaq"], 1),
                "temperature":            round(g_bme688_bsec_data["temperature"], 1),
                "humidity":               round(g_bme688_bsec_data["humidity"], 1),
                "raw_pressure":           round(g_bme688_bsec_data["raw_pressure"] / 100, 1),
                "co2_equivalent":         round(g_bme688_bsec_data["co2_equivalent"], 1),
                "breath_voc_equivalent":  round(g_bme688_bsec_data["breath_voc_equivalent"], 2),
                "gas_percentage":         round(g_bme688_bsec_data["gas_percentage"], 1),
            }
            mqtt_client.publish(MQTT_TOPIC, json.dumps(mqtt_payload))
            logging.info(f"MQTT published: {mqtt_payload}")
    except Exception as e:
        logging.error(e)


if __name__ == "__main__":
    # Connect to MQTT broker
    mqtt_client = mqtt.Client()
    mqtt_client.username_pw_set(MQTT_USER, MQTT_PASSWORD)
    mqtt_client.connect(MQTT_HOST, MQTT_PORT)
    mqtt_client.loop_start()

    # Publish discovery so HA creates the entities automatically
    mqtt_publish_discovery(mqtt_client)

    # PMS7003 writes happen every 15 minutes, 4x an hour
    # Schedule starts two minutes before intended read time
    schedule.every().hour.at(":13").do(pms7003_read)
    schedule.every().hour.at(":28").do(pms7003_read)
    schedule.every().hour.at(":43").do(pms7003_read)
    schedule.every().hour.at(":58").do(pms7003_read)

    # DB writes happen every 15 minutes, 4x an hour
    schedule.every().hour.at(":15").do(write_to_db)
    schedule.every().hour.at(":30").do(write_to_db)
    schedule.every().hour.at(":45").do(write_to_db)
    schedule.every().hour.at(":00").do(write_to_db)

    logging.info("Starting BME688 setup")
    bme = bme688_setup()

    logging.info("Starting BME688 thread")
    bme688_t = threading.Thread(target=bme688_thread)
    bme688_t.start()

    logging.info("Starting sensor and DB schedules")
    while True:
        schedule.run_pending()
        sleep(1)
