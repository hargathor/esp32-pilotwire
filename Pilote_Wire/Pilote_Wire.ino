#include <WiFi.h>
#include <PubSubClient.h>
#include <DallasTemperature.h>

#define uS_TO_S_FACTOR 1000000 /* Conversion factor for micro seconds to seconds */

WiFiClient espClient;
PubSubClient client(espClient);
long lastReconnectAttempt = 0;
// TODO: use DNS server and names instead
const char* MQTT_SERVER = "mqtt.local";
const int MQTT_PORT = 1883;
char* TOPIC = "domoticz/in";
const char* IDX = "77";
// Publication time of the temperature in microseconds (10mn)
const int TEMP_PUB_TIME = uS_TO_S_FACTOR * 60 * 1;

// Wifi Configuration
const char* ssid     = "ssid";
const char* password = "password";
const int NB_RETRIES = 50;

// Timer for the temp publication
hw_timer_t * tempTimer = NULL;

// Built in led for status
const int LED_BUILT_IN_PIN = 22;

// *** GPIO pin number for DS18B20
const int TEMP_PIN = 33;
DeviceAddress roomThermometer;
OneWire oneWire(TEMP_PIN);
DallasTemperature sensors(&oneWire);
float tempc = 0.0;

int ledState = 0;

// GPIO for MOC3043 positive alt
const int ALT_POSITIVE = 19;

// GPIO for MOC3043 negative alt
const int ALT_NEGATIVE = 0;

/**
   OneWire functions related to the DS18B20 probe
*/
// function to print a device address
void printAddress(DeviceAddress deviceAddress)
{
  for (uint8_t i = 0; i < 8; i++)
  {
    // zero pad the address if necessary
    if (deviceAddress[i] < 16) Serial.print("0");
    Serial.print(deviceAddress[i], HEX);
  }
}

void initOneWireDevices() {
  Serial.println("Locating Devices......");
  // Must be called before search()
  oneWire.reset_search();
  // assigns the first address found to outsideThermometer
  if (!oneWire.search(roomThermometer)) {
    Serial.println("Unable to find address for roomThermometer");
    Serial.println("Will restart in 5 seconds");
    delay(1000 * 5);
    ESP.restart();
  }
  // show the addresses we found on the bus
  Serial.print("Device 0 Address: ");
  printAddress(roomThermometer);
  Serial.println();
  // set the resolution to 9 bit
  sensors.setResolution(roomThermometer, 9);
  Serial.print("Device 0 Resolution: ");
  Serial.println(sensors.getResolution(roomThermometer), DEC);
  Serial.print(sensors.getDeviceCount(), DEC);
  Serial.println(" devices.");
  printLine();
}

void getTemp() {
  //Serial.println("Requesting temperature...");
  // Send the command to get temperatures
  sensors.requestTemperatures();
  tempc = sensors.getTempCByIndex(0);
  if (tempc == -127.00) {
    getTemp();
  }
}

void postTemp() {
  Serial.println("Trying to post temp to MQTT broker");
  while (!client.connected()) {
    Serial.println("Connecting to MQTT...");

    if (client.connect("ESP32_Outside_temp_sensor")) {

      Serial.println("connected");
      String msg = "{ \"idx\": ";
      msg += IDX;
      msg += ", \"nvalue\": 0, \"svalue\": \"";
      msg += tempc;
      msg += "\"}";
      Serial.println(msg);
      if (client.publish(TOPIC, (char *)msg.c_str())) {
        Serial.println("Publish ok");
      }
      else {
        Serial.println("Publish failed");
      }

    } else {

      Serial.print("failed with state ");
      Serial.print(client.state());
      delay(2000);

    }
  }
}

/**
   Gather temperature with probe on pin 33
   and post it to the MQTT server
*/
void IRAM_ATTR manageTemp() {
  digitalWrite(LED_BUILT_IN_PIN, LOW);
  getTemp();
  delay(500);
  postTemp();
  digitalWrite(LED_BUILT_IN_PIN, HIGH);
}

/**
   Utils functions
*/
void callback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("] ");
  for (int i = 0; i < length; i++) {
    Serial.print((char)payload[i]);
  }
  Serial.println();
}

boolean reconnect() {
  if (client.connect("arduinoClient")) {
    // Once connected, publish an announcement...
    client.publish("outTopic", "hello world");
    // ... and resubscribe
    client.subscribe("inTopic");
  }
  return client.connected();
}

void blinkLed(int ledToBlink) {
  // Blink LED while we're connecting:
  digitalWrite(ledToBlink, ledState);
  ledState = (ledState + 1) % 2; // Flip ledState
  delay(250);
}

void printLine()
{
  if (Serial.available()) {

    Serial.println();
    for (int i = 0; i < 30; i++)
      Serial.print("-");
    Serial.println();
  }
}

/*
  Method to print the reason by which ESP32
  has been awaken from sleep
*/
void print_wakeup_reason() {
  esp_sleep_wakeup_cause_t wakeup_reason;

  wakeup_reason = esp_sleep_get_wakeup_cause();

  switch (wakeup_reason)
  {
    case 1  : Serial.println("Wakeup caused by external signal using RTC_IO"); break;
    case 2  : Serial.println("Wakeup caused by external signal using RTC_CNTL"); break;
    case 3  : Serial.println("Wakeup caused by timer"); break;
    case 4  : Serial.println("Wakeup caused by touchpad"); break;
    case 5  : Serial.println("Wakeup caused by ULP program"); break;
    default : Serial.println("Wakeup was not caused by deep sleep"); break;
  }
}

void connectToWiFi(const char * ssid, const char * pwd)
{
  if (Serial.available()) {
    printLine();
    Serial.println("Connecting to WiFi network: " + String(ssid));
  }
  WiFi.begin(ssid, pwd);
  int retries = 0;
  while (WiFi.status() != WL_CONNECTED)
  {
    if (retries >= NB_RETRIES) {
      printLine();
      Serial.println("Cannot connect to wifi");
      Serial.println("Going to restart now");
      printLine();
      ESP.restart();
    }
    Serial.print(".");
    delay(500);
    retries++;
  }
  if (Serial.available()) {
    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
    printLine();
  }
}

/**
   Pilot wire functions
*/

// No signal toward pilot wire
void modeConfort() {

}

// Full alt
void modeEco() {

}

// Only negative alt
void modeHorsGel() {

}

// Only positive alt
void modeArret() {

}

void setup() {
  Serial.begin(115200);
  // set the LED pin mode
  pinMode(LED_BUILT_IN_PIN, OUTPUT);
  pinMode(ALT_NEGATIVE, OUTPUT);
  pinMode(ALT_POSITIVE, OUTPUT);
  delay(10);
  print_wakeup_reason();
  connectToWiFi(ssid, password);
  delay(500);
  sensors.begin();
  delay(250);
  initOneWireDevices();
  delay(100);
  client.setServer(MQTT_SERVER, MQTT_PORT);
  client.setCallback(callback);
  lastReconnectAttempt = 0;



  // Use 1st timer of 4 (counted from zero).
  // Set 80 divider for prescaler
  // (see ESP32 Technical Reference Manual for more info).
  tempTimer = timerBegin(0, 80, true);

  // Attach onTimer function to our timer.
  timerAttachInterrupt(tempTimer, &manageTemp, true);

  // Set alarm to call onTimer function every second (value in microseconds).
  // Repeat the alarm (third parameter)
  timerAlarmWrite(tempTimer, TEMP_PUB_TIME, true);

  // Start an alarm
  timerAlarmEnable(tempTimer);

  // Turn off the builtin led
  digitalWrite(LED_BUILT_IN_PIN, HIGH);

  // TODO: Create MQTT subscriber to adjust the pilote wire program
  // TODO: Create parallel task for led blink while working
}

void loop() {
  if (!client.connected()) {
    long now = millis();
    if (now - lastReconnectAttempt > 5000) {
      lastReconnectAttempt = now;
      // Attempt to reconnect
      if (reconnect()) {
        lastReconnectAttempt = 0;
      }
    }
  } else {
    // Client connected
    client.loop();
  }
}
