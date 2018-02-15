import _thread
import machine
import network
import ujson
import utime

global TOPIC
global TOPIC_SUB

DEBUG = True

# 5 minute
TEMP_PUB_TIME = 60000 * 5
DS18B20_PIN = 33
IDX = "77"
TOPIC = b'domoticz/in'
TOPIC_SUB = b'domoticz/out'
MQTT_SERVER = 'mqtt.local'
WIFI_MAX_TRIES = 20
SSID = 'SSID'
WIFI_PASSWORD = 'WIFI-PASSWORD'
MAX_WRITE_RTC_CALLS = 5

LED_BUILT_IN = 22
# MOC actiing on positive alternance is on pin 19
ALT_POSITIVE_PIN = 19
# MOC actiing on negative alternance is on pin 0
ALT_NEGATIVE_PIN = 0


def default_mode():
    """TODO: Docstring for default_mode.
    :returns: TODO

    """
    saved_mode = load_mode()
    if saved_mode:
        print("Found a saved a previous mode")
        current_mode = saved_mode
        AVAILABLE_MODES[current_mode]()
    else:
        print("No previous mode saved in memory. Falling back to confort")
        current_mode = 10
        confort()

    return current_mode


def confort():
    """TODO: Docstring for confort.
    :returns: TODO
    Confort mode means no signal on the pilote wire
    """
    print("CONFORT mode")
    global current_mode
    current_mode = 10
    alt_negative_pin.value(0)
    alt_positive_pin.value(0)


def confort_minus_1():
    """TODO: Docstring for confort_minus_1.

    :returns: TODO

    """
    print("CONFORT-1 mode")
    global current_mode
    current_mode = 40


def confort_minus_2():
    """TODO: Docstring for confort_minus_2.
    :returns: TODO

    """
    print("CONFORT-2 mode")
    global current_mode
    current_mode = 50


def eco():
    """TODO: Docstring for eco.
    :returns: TODO
    Eco mode means  full alt on the pilot wire
    """
    print("ECO mode")
    global current_mode
    current_mode = 20
    alt_negative_pin.value(1)
    alt_positive_pin.value(1)


def hors_gel():
    """TODO: Docstring for hors_gel.
    :returns: TODO
    Hors gel means only the negative alternance on the pilot wire
    """
    print("HORS-GEL mode")
    global current_mode
    current_mode = 30
    alt_negative_pin.value(1)
    alt_positive_pin.value(0)


def arret():
    """TODO: Docstring for arret.
    :returns: TODO

    """
    print("ARRET mode")
    global current_mode
    current_mode = 0
    alt_negative_pin.value(0)
    alt_positive_pin.value(1)


def load_mode():
    """TODO: Docstring for saved_mode.
    :returns: TODO

    """
    print('Loading previous mode')
    if 'current_mode' in locals():
        if current_mode:
            saved_mode = current_mode
        else:
            saved_mode = machine.nvs_getint('current_mode')
        return saved_mode
    else:
        return


def save_current_mode(mode, calls=0):
    """TODO: Docstring for save_current_mode.

    :mode: TODO
    :returns: TODO

    """
    print("Saving current mode: {}".format(mode))
    machine.nvs_setint('current_mode', mode)


def init_configuration(configuration_file_path):
    """TODO: Docstring for init_configuration.

    :configuration_file_path: TODO
    :returns: TODO

    """
    pass


AVAILABLE_MODES = {
    0: arret,
    10: confort,
    20: eco,
    30: hors_gel,
    40: confort_minus_1,
    50: confort_minus_2
}


def conncb(task):
    print("[{}] Connected".format(task))


def disconncb(task):
    print("[{}] Disconnected".format(task))


def subscb(task):
    print("[{}] Subscribed".format(task))


def pubcb(pub):
    print("[{}] Published: {}".format(pub[0], pub[1]))


def datacb(msg):
    data = ujson.loads(msg[2])
    if data.get("idx") == 78:
        value = int(data.get("svalue1"))
        save_current_mode(value)
        AVAILABLE_MODES[value]()


def wifi_connect():
    """TODO: Docstring for wifi_connect.
    :returns: TODO

    """
    nic = network.WLAN(network.STA_IF)
    if not nic.isconnected():
        print("Trying to connect to Wifi AP")
        nic.active(True)
        nic.connect(SSID, WIFI_PASSWORD)
        # nic.connect()
        print("Waiting for connection...")
        retries = 0
        while not nic.isconnected():
            if retries >= WIFI_MAX_TRIES:
                force_reset()
            utime.sleep_ms(500)
            print('.', end='')
            retries += 1
    print(nic.ifconfig())
    utime.sleep(1)
    print("Connecting to MQTT broker")
    global client
    SERVER = MQTT_SERVER
    CLIENT_ID = machine.unique_id()
    client = network.mqtt(CLIENT_ID, SERVER,
                          cleansession=True, autoreconnect=True,
                          connected_cb=conncb, disconnected_cb=disconncb,
                          subscribed_cb=subscb, published_cb=pubcb,
                          data_cb=datacb)
    while client.status()[0] is not 1:
        utime.sleep_ms(500)
        print('.', end='')
    print("Subscribing to domoticz topici: {}".format(TOPIC_SUB))
    client.subscribe(TOPIC_SUB)

    return nic


def init_onewire(ow):
    """TODO: Docstring for init_onewire.
    :returns: TODO

    """
    # scan for devices on the bus
    roms = []
    print("Scanning for 1wire devices")
    print("State of Onewire bus: {}".format(ds.get_pwrmode()))
    for i in range(10):
        roms = ow.scan()
        utime.sleep_ms(10)
        if len(roms) > 0:
            break
        print('.', end='')
    print('found devices:', roms)
    if len(roms) == 0:
        force_reset()
    return roms


def do_ds18b20(roms, ow):
    """TODO: Docstring for do_ds18b20.
    :returns: TODO

    """
    print("Gathering temperature")
    templist = []
    for i in range(10):
        ds.convert_read()
        templist.append(ds.read_temp())
        utime.sleep(1)
        print('.', end='')
    print()
    # Removing extrem values
    templist.remove(max(templist))
    templist.remove(max(templist))
    templist.remove(min(templist))
    templist.remove(min(templist))
    sum_temp = 0
    for temp in templist:
        sum_temp = sum_temp + temp
    tempc = "{:.2f}".format(sum_temp / 6)
    print("Final temp: {}".format(tempc))

    return tempc


def force_reset():
    """TODO: Docstring for force_reset.
    :returns: TODO

    """
    if DEBUG:
        print("Something got wrong, resetting in 5 seconds...")
        utime.sleep(1)
        print("Resetting in 4 seconds...")
        utime.sleep(1)
        print("Resetting in 3 seconds...")
        utime.sleep(1)
        print("Resetting in 2 seconds...")
        utime.sleep(1)
        print("Resetting in 1 seconds...")
        utime.sleep(1)
    print("Resetting...")
    machine.reset()


def do_flashes(pin):
    """TODO: Docstring for do_flashes.
    :returns: TODO

    """
    _thread.allowsuspend(True)
    while True:
        pin.value(not pin.value())
        utime.sleep_ms(250)
    pin.value(1)


def post_temp(temp, idx):
    """TODO: Docstring for post_temp.
    :returns: TODO

    """
    print('idx: {}'.format(idx))
    msg = (b'{{ "idx": {}, "nvalue": 0, "svalue": "{}" }}'.format(idx, temp))
    print(msg)
    print("Posting temp to domoticz")
    client.publish(TOPIC, msg)  # Publish sensor data to MQTT topic


def manage_temp():
    """TODO: Docstring for manage_temp.
    :returns: TODO

    """
    print("Managing temp")
    tempc = do_ds18b20(roms, ow)
    post_temp(tempc, IDX)
    utime.sleep(5)


def publish_sensors(timer):
    """TODO: Docstring for publish_sensors.
    :returns: TODO

    """
    _thread.resume(status_led_thread)
    manage_temp()
    publish_heating_mode()
    _thread.suspend(status_led_thread)
    # Making sure Status led is turned off
    pin.value(1)  # Pin is inverted for builtin


def publish_heating_mode():
    """ 
    Function used to publish the state of the MOCs 
    (i.e. the heating mode of the pilot wire)

    :returns: True if all went well publish 

    """
    mode = load_mode()
    idx = 78
    msg = (b'{{ "idx": {}, "nvalue": 0, "svalue": "{}" }}'.format(idx, mode))
    print(msg)
    print("Posting current heating mode to domoticz")
    if mode:
        client.publish(TOPIC, msg)  # Publish sensor data to MQTT topic
        return True
    else:
        print("Error loading saved mode")
        return False


print("Starting One wire module with embeded temperature sensor")
if DEBUG:
    machine.loglevel('*', machine.LOG_DEBUG)

if 4 == machine.wake_reason()[0]:
    print('Woke from a deep sleep')
else:
    print("Woke up from hard reboot ?")
utime.sleep(2)
pin = machine.Pin(LED_BUILT_IN, machine.Pin.OUT)
# Initialize the MOC3043 Pins
alt_positive_pin = machine.Pin(ALT_POSITIVE_PIN, machine.Pin.OUT)
alt_negative_pin = machine.Pin(ALT_NEGATIVE_PIN, machine.Pin.OUT)
current_mode = default_mode()

# the temperature device is on GPIO16
dat = machine.Pin(DS18B20_PIN, machine.Pin.IN)

# create the onewire object
ow = machine.Onewire(dat)
ds = machine.Onewire.ds18x20(ow, 0)

status_led_thread = _thread.start_new_thread(
    'th_led_flash', do_flashes, (pin,))

roms = init_onewire(ow)
nic = wifi_connect()
utime.sleep_ms(1000)
tempTimer = machine.Timer(2)
tempTimer.init(period=TEMP_PUB_TIME,
               mode=tempTimer.PERIODIC, callback=publish_sensors)
_thread.suspend(status_led_thread)

pin.value(1)
