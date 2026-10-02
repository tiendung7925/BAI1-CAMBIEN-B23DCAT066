#include <WiFi.h>
#include <PubSubClient.h>
#include <DHTesp.h>
#include <time.h>
#include <sys/time.h>

// ======================================================
// 1. WIFI CONFIGURATION
// ======================================================

const char* WIFI_SSID = "Wokwi-GUEST";
const char* WIFI_PASSWORD = "";


// ======================================================
// 2. MQTT CONFIGURATION
// ======================================================

const char* MQTT_SERVER = "broker.hivemq.com";
const int MQTT_PORT = 1883;

const char* MQTT_TOPIC = "iot/B23DCAT066/telemetry";


// ======================================================
// 3. DEVICE INFORMATION
// ======================================================

const char* STUDENT_ID = "B23DCAT066";
const char* DEVICE_ID = "esp32-B23DCAT066";


// ======================================================
// 4. SENSOR PIN CONFIGURATION
// ======================================================

const int DHT_PIN = 15;

const int TRIG_PIN = 5;
const int ECHO_PIN = 18;

const int LED_PIN = 2;


// ======================================================
// 5. SYSTEM CONFIGURATION
// ======================================================

const unsigned long SEND_INTERVAL_MS = 5000;

const unsigned long MQTT_RECONNECT_INTERVAL = 5000;


// ======================================================
// 6. NTP CONFIGURATION
// ======================================================

// UTC timezone
const char* NTP_SERVER = "pool.ntp.org";

const long GMT_OFFSET_SEC = 0;

const int DAYLIGHT_OFFSET_SEC = 0;


// ======================================================
// 7. OBJECTS
// ======================================================

WiFiClient wifiClient;

PubSubClient mqttClient(wifiClient);

DHTesp dht;


// ======================================================
// 8. TIMER VARIABLES
// ======================================================

unsigned long lastSend = 0;

unsigned long lastMQTTAttempt = 0;


// ======================================================
// 9. SEQUENCE NUMBER
// ======================================================

unsigned long sequenceNumber = 0;


// ======================================================
// 10. CONNECT WIFI
// ======================================================

void connectWiFi() {

  if (WiFi.status() == WL_CONNECTED) {
    return;
  }

  Serial.println();
  Serial.println("=================================");
  Serial.println("Connecting to WiFi...");
  Serial.println("=================================");

  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  unsigned long startAttempt = millis();

  while (WiFi.status() != WL_CONNECTED &&
         millis() - startAttempt < 15000) {

    delay(500);

    Serial.print(".");
  }

  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {

    Serial.println("WiFi connected!");

    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());

  } else {

    Serial.println("WiFi connection failed.");

  }
}


// ======================================================
// 11. CONFIGURE NTP
// ======================================================

void configureTime() {

  Serial.println();
  Serial.println("Synchronizing time with NTP...");

  configTime(
      GMT_OFFSET_SEC,
      DAYLIGHT_OFFSET_SEC,
      NTP_SERVER
  );

  struct tm timeinfo;

  unsigned long start = millis();

  while (!getLocalTime(&timeinfo) &&
         millis() - start < 10000) {

    Serial.print(".");

    delay(500);
  }

  Serial.println();

  if (getLocalTime(&timeinfo)) {

    Serial.println("NTP time synchronized.");

    Serial.print("Current UTC time: ");
    Serial.println(&timeinfo, "%Y-%m-%d %H:%M:%S");

  } else {

    Serial.println("WARNING: NTP synchronization failed.");

  }
}


// ======================================================
// 12. GET UNIX TIMESTAMP IN MILLISECONDS
// ======================================================

uint64_t getUnixTimestampMs() {

  struct timeval tv;

  if (gettimeofday(&tv, nullptr) != 0) {

    return 0;

  }

  // Kiểm tra xem thời gian đã được đồng bộ chưa
  if (tv.tv_sec < 1700000000) {

    return 0;

  }

  uint64_t timestampMs =
      (uint64_t)tv.tv_sec * 1000ULL
      + (uint64_t)(tv.tv_usec / 1000);

  return timestampMs;
}


// ======================================================
// 13. CONNECT MQTT
// ======================================================

void connectMQTT() {

  if (WiFi.status() != WL_CONNECTED) {
    return;
  }

  if (mqttClient.connected()) {
    return;
  }

  unsigned long now = millis();

  // Không thử kết nối liên tục
  if (now - lastMQTTAttempt < MQTT_RECONNECT_INTERVAL) {
    return;
  }

  lastMQTTAttempt = now;

  String clientId =
      "ESP32-B23DCAT066-" +
      String((uint32_t)ESP.getEfuseMac(), HEX);

  Serial.print("Connecting MQTT... ");

  if (mqttClient.connect(clientId.c_str())) {

    Serial.println("SUCCESS");

  } else {

    Serial.print("FAILED, rc=");
    Serial.println(mqttClient.state());

  }
}


// ======================================================
// 14. READ HC-SR04 DISTANCE
// ======================================================

float readDistanceCm() {

  // Đảm bảo TRIG ở LOW trước khi phát xung
  digitalWrite(TRIG_PIN, LOW);

  delayMicroseconds(2);

  // Phát xung 10 microseconds
  digitalWrite(TRIG_PIN, HIGH);

  delayMicroseconds(10);

  digitalWrite(TRIG_PIN, LOW);


  // Đọc thời gian ECHO
  unsigned long duration =
      pulseIn(ECHO_PIN, HIGH, 30000);


  // Timeout
  if (duration == 0) {

    return NAN;

  }


  // Công thức:
  // distance = time * speed_of_sound / 2

  float distance =
      duration * 0.0343f / 2.0f;


  // Kiểm tra phạm vi hợp lệ
  if (distance < 2.0f ||
      distance > 400.0f) {

    return NAN;

  }

  return distance;
}


// ======================================================
// 15. SETUP
// ======================================================

void setup() {

  Serial.begin(115200);

  delay(1000);

  Serial.println();
  Serial.println("=================================");
  Serial.println("      IoT ENVIRONMENT SYSTEM");
  Serial.println("      Student: B23DCAT066");
  Serial.println("=================================");


  // ----------------------------------------------------
  // HC-SR04
  // ----------------------------------------------------

  pinMode(TRIG_PIN, OUTPUT);

  pinMode(ECHO_PIN, INPUT);


  // ----------------------------------------------------
  // LED
  // ----------------------------------------------------

  pinMode(LED_PIN, OUTPUT);

  digitalWrite(LED_PIN, LOW);


  // ----------------------------------------------------
  // DHT22
  // ----------------------------------------------------

  dht.setup(
      DHT_PIN,
      DHTesp::DHT22
  );


  // ----------------------------------------------------
  // WiFi
  // ----------------------------------------------------

  connectWiFi();


  // ----------------------------------------------------
  // NTP
  // ----------------------------------------------------

  if (WiFi.status() == WL_CONNECTED) {

    configureTime();

  }


  // ----------------------------------------------------
  // MQTT
  // ----------------------------------------------------

  mqttClient.setServer(
      MQTT_SERVER,
      MQTT_PORT
  );


  // ----------------------------------------------------
  // MQTT BUFFER
  // ----------------------------------------------------

  mqttClient.setBufferSize(512);


  Serial.println();
  Serial.println("System initialized.");

}


// ======================================================
// 16. LOOP
// ======================================================

void loop() {

  // ----------------------------------------------------
  // WIFI
  // ----------------------------------------------------

  if (WiFi.status() != WL_CONNECTED) {

    connectWiFi();

  }


  // ----------------------------------------------------
  // MQTT
  // ----------------------------------------------------

  if (!mqttClient.connected()) {

    connectMQTT();

  }

  mqttClient.loop();


  // ----------------------------------------------------
  // SEND INTERVAL
  // ----------------------------------------------------

  unsigned long now = millis();

  if (now - lastSend < SEND_INTERVAL_MS) {

    return;

  }

  lastSend = now;


  // ----------------------------------------------------
  // READ DHT22
  // ----------------------------------------------------

  TempAndHumidity data =
      dht.getTempAndHumidity();


  float temperature =
      data.temperature;

  float humidity =
      data.humidity;


  // ----------------------------------------------------
  // READ HC-SR04
  // ----------------------------------------------------

  float distance =
      readDistanceCm();


  // ----------------------------------------------------
  // VALIDATE DHT22
  // ----------------------------------------------------

  if (isnan(temperature)) {

    Serial.println(
        "ERROR: Invalid temperature"
    );

    return;

  }

  if (isnan(humidity)) {

    Serial.println(
        "ERROR: Invalid humidity"
    );

    return;

  }


  // ----------------------------------------------------
  // VALIDATE DISTANCE
  // ----------------------------------------------------

  if (isnan(distance)) {

    Serial.println(
        "WARNING: Invalid distance"
    );

    return;

  }


  // ----------------------------------------------------
  // GET UNIX TIMESTAMP
  // ----------------------------------------------------

  uint64_t timestampMs =
      getUnixTimestampMs();


  if (timestampMs == 0) {

    Serial.println(
        "ERROR: Invalid system timestamp"
    );

    return;

  }


  // ----------------------------------------------------
  // INCREMENT SEQUENCE
  // ----------------------------------------------------

  sequenceNumber++;


  // ----------------------------------------------------
  // CREATE JSON
  // ----------------------------------------------------

  char payload[512];

  snprintf(
      payload,
      sizeof(payload),

      "{"
      "\"student_id\":\"%s\","
      "\"device_id\":\"%s\","
      "\"seq\":%lu,"
      "\"timestamp_ms\":%llu,"
      "\"temperature\":%.2f,"
      "\"humidity\":%.2f,"
      "\"distance\":%.2f"
      "}",

      STUDENT_ID,
      DEVICE_ID,
      sequenceNumber,
      timestampMs,
      temperature,
      humidity,
      distance
  );


  // ----------------------------------------------------
  // MQTT PUBLISH
  // ----------------------------------------------------

  bool published = false;

  if (mqttClient.connected()) {

    published =
        mqttClient.publish(
            MQTT_TOPIC,
            payload,
            false
        );

  }


  // ----------------------------------------------------
  // SERIAL OUTPUT
  // ----------------------------------------------------

  Serial.println("---------------------------------");

  Serial.print("Temperature : ");
  Serial.print(temperature);
  Serial.println(" C");

  Serial.print("Humidity    : ");
  Serial.print(humidity);
  Serial.println(" %");

  Serial.print("Distance    : ");
  Serial.print(distance);
  Serial.println(" cm");

  Serial.print("Sequence    : ");
  Serial.println(sequenceNumber);

  Serial.print("Timestamp   : ");
  Serial.println((unsigned long long)timestampMs);

  Serial.print("MQTT        : ");

  Serial.println(
      published ? "PUBLISHED" : "FAILED"
  );

  Serial.print("Payload     : ");

  Serial.println(payload);


  // ----------------------------------------------------
  // LED INDICATOR
  // ----------------------------------------------------

  if (published) {

    digitalWrite(
        LED_PIN,
        HIGH
    );

    delay(80);

    digitalWrite(
        LED_PIN,
        LOW
    );

  }

}