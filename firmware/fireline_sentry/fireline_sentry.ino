/*
  Fireline ESP32 sentry.

  The always-on, low-power half of the field unit. It reads the DHT11, decides the fire-risk tier,
  tells the Jetson when to scan, forwards heartbeats, and drives the status LEDs and buzzer.
  It talks only to the Jetson (MQTT broker on the Jetson, port 1883); the Jetson does the uplink.

  Arduino IDE setup (once):
    1. Boards Manager: install "esp32" by Espressif Systems. Board: "ESP32 Dev Module".
    2. Library Manager: install "PubSubClient" (Nick O'Leary), "DHT sensor library" (Adafruit),
       and "Adafruit Unified Sensor" (asked for by the DHT library).
    3. Edit the settings block below, plug in the ESP32, pick its COM port, Upload.
    4. Tools > Serial Monitor at 115200 baud to watch it work.

  Serial Monitor commands (handy when rehearsing, or if the hair dryer fails on stage):
    scan                       force a scan request
    fake 35 20                 pretend the sensor reads 35 C / 20 %   ("fake off" to stop)
    loc 28.6024 -81.2001 Juniper Prairie    stand-in for an NFC tag tap: report a new mounting spot

  Prototype note: this stays awake so MQTT and the LEDs keep working at the judging table.
  A production unit would deep-sleep between readings and cut the Jetson's power entirely.
*/
#include <WiFi.h>
#include <ESPmDNS.h>
#include <PubSubClient.h>
#include <DHT.h>

// ======================= settings: edit these =======================
const char* WIFI_SSID = "YOUR_HOTSPOT_NAME";   // 2.4 GHz only. iPhone: turn on "Maximize Compatibility"
const char* WIFI_PASS = "YOUR_HOTSPOT_PASSWORD";
const char* JETSON_HOST = "gw-jetson";          // the Jetson's hostname, without ".local"
IPAddress JETSON_FALLBACK_IP(172, 20, 10, 2);   // used only if mDNS fails; read it off the hotspot's device list
const bool DEMO_MODE = true;                    // shortens every interval so the demo plays out in a minute

// Pins: change to match your wiring. Use -1 for parts you did not wire up.
const int PIN_DHT = 4;
const int PIN_LED_GREEN = 25;
const int PIN_LED_YELLOW = 26;
const int PIN_LED_RED = 27;
const int PIN_BUZZER = 14;     // active buzzer (beeps when driven HIGH)
const int PIN_TAMPER = -1;     // lid microswitch between pin and GND, closed when the lid is shut
const int PIN_TEST_BTN = -1;   // push button / touch module to GND: "test alert", forces a scan
#define DHT_TYPE DHT11
// =====================================================================

const unsigned long READ_MS = DEMO_MODE ? 2000UL : 60000UL;        // DHT11 needs >= 1 s between reads
const unsigned long HB_MS = DEMO_MODE ? 10000UL : 60000UL;
const unsigned long SCAN_LOW_MS = DEMO_MODE ? 120000UL : 30UL * 60 * 1000;
const unsigned long SCAN_ELEV_MS = DEMO_MODE ? 20000UL : 5UL * 60 * 1000;
const unsigned long SCAN_CRIT_RETRY_MS = 5000UL;  // critical = continuous: re-ask whenever the Jetson is asleep
const int AGREE_NEEDED = 3;                       // hysteresis: 3 readings in a row before the tier changes

enum Tier { TIER_LOW, TIER_ELEV, TIER_CRIT };
const char* TIER_NAME[] = {"low", "elev", "crit"};

DHT dht(PIN_DHT, DHT_TYPE);
WiFiClient wifiClient;
PubSubClient mqtt(wifiClient);

Tier tier = TIER_LOW;
Tier candidate = TIER_LOW;
int agree = 0;
float tempBuf[3], rhBuf[3];
int bufCount = 0, bufNext = 0;
float temp = NAN, rh = NAN;
bool fakeOn = false;
float fakeTemp = 0, fakeRh = 0;
String jetsonState = "sleep";
unsigned long lastRead = 0, lastHb = 0, lastScan = 0, lastMqttTry = 0;
bool haveScanned = false;
int lastTamper = -1;
int lastBtn = HIGH;

// ---------- helpers ----------

void setPin(int pin, int value) {
  if (pin >= 0) digitalWrite(pin, value);
}

Tier computeTier(float t, float h) {
  if (h < 30 && t > 32) return TIER_CRIT;
  if (h <= 50 || t > 30) return TIER_ELEV;
  return TIER_LOW;
}

void publishJson(const char* topic, const char* json) {
  bool ok = mqtt.connected() && mqtt.publish(topic, json);
  Serial.printf("%s %s %s\n", ok ? "->" : "!! (not sent)", topic, json);
}

void sendHeartbeat() {
  char buf[128];
  snprintf(buf, sizeof(buf), "{\"risk\":\"%s\",\"temp\":%.1f,\"rh\":%.0f,\"bat\":100,\"up\":%lu}",
           TIER_NAME[tier], isnan(temp) ? 0.0 : temp, isnan(rh) ? 0.0 : rh, millis() / 1000);
  publishJson("unit/hb", buf);
  lastHb = millis();
}

void requestScan(const char* why) {
  char buf[96];
  snprintf(buf, sizeof(buf), "{\"risk\":\"%s\",\"temp\":%.1f,\"rh\":%.0f}",
           TIER_NAME[tier], isnan(temp) ? 0.0 : temp, isnan(rh) ? 0.0 : rh);
  Serial.printf("scan requested (%s)\n", why);
  publishJson("unit/scan", buf);
  lastScan = millis();
  haveScanned = true;
}

// ---------- LEDs + buzzer ----------
// green = low risk, yellow = elevated, yellow+red = critical ("orange"), solid red + chirp = smoke alert.
// The tier LED blinks while the Jetson is scanning.

void updateOutputs() {
  unsigned long now = millis();
  bool alert = jetsonState == "alert";
  bool blinkOff = jetsonState == "scan" && (now / 400) % 2 == 0;

  setPin(PIN_LED_GREEN, !alert && !blinkOff && tier == TIER_LOW);
  setPin(PIN_LED_YELLOW, !alert && !blinkOff && tier != TIER_LOW);
  setPin(PIN_LED_RED, alert || (!blinkOff && tier == TIER_CRIT));
  setPin(PIN_BUZZER, alert && (now % 2000) < 120);
}

// ---------- network ----------

void onMessage(char* topic, byte* payload, unsigned int len) {
  String msg;
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];
  if (String(topic) == "unit/state") {
    jetsonState = msg;
    Serial.printf("<- jetson is %s\n", msg.c_str());
  }
}

void ensureWifi() {
  if (WiFi.status() == WL_CONNECTED) return;
  Serial.printf("joining wifi %s", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  for (int i = 0; i < 40 && WiFi.status() != WL_CONNECTED; i++) {
    delay(500);
    Serial.print(".");
  }
  if (WiFi.status() == WL_CONNECTED) {
    Serial.printf("\nwifi ok, my ip %s\n", WiFi.localIP().toString().c_str());
    MDNS.begin("gw-sentry");
  } else {
    Serial.println("\nwifi failed; is the hotspot 2.4 GHz and the password right?");
  }
}

void ensureMqtt() {
  if (mqtt.connected() || WiFi.status() != WL_CONNECTED) return;
  if (millis() - lastMqttTry < 3000 && lastMqttTry != 0) return;
  lastMqttTry = millis();

  IPAddress ip = MDNS.queryHost(JETSON_HOST, 2000);
  if (ip == IPAddress(0, 0, 0, 0)) {
    Serial.printf("mDNS could not find %s.local, using fallback %s\n", JETSON_HOST,
                  JETSON_FALLBACK_IP.toString().c_str());
    ip = JETSON_FALLBACK_IP;
  }
  mqtt.setServer(ip, 1883);
  Serial.printf("connecting to MQTT on %s... ", ip.toString().c_str());
  if (mqtt.connect("gw-sentry")) {
    Serial.println("ok");
    mqtt.subscribe("unit/state");
    sendHeartbeat();
  } else {
    Serial.printf("failed (state %d); is mosquitto running on the Jetson?\n", mqtt.state());
  }
}

// ---------- sensor + tier logic ----------

void readSensor() {
  float t, h;
  if (fakeOn) {
    t = fakeTemp;
    h = fakeRh;
  } else {
    t = dht.readTemperature();
    h = dht.readHumidity();
    if (isnan(t) || isnan(h)) {
      Serial.println("DHT11 read failed; check wiring (data pin, 3.3V, GND)");
      return;
    }
  }
  // Average the last 3 readings: single DHT11 readings are noisy.
  tempBuf[bufNext] = t;
  rhBuf[bufNext] = h;
  bufNext = (bufNext + 1) % 3;
  if (bufCount < 3) bufCount++;
  float st = 0, sh = 0;
  for (int i = 0; i < bufCount; i++) {
    st += tempBuf[i];
    sh += rhBuf[i];
  }
  temp = st / bufCount;
  rh = sh / bufCount;

  Tier now = computeTier(temp, rh);
  if (now == tier) {
    agree = 0;
  } else {
    if (now == candidate) agree++;
    else {
      candidate = now;
      agree = 1;
    }
    if (agree >= AGREE_NEEDED) {
      Tier old = tier;
      tier = now;
      agree = 0;
      Serial.printf("tier %s -> %s\n", TIER_NAME[old], TIER_NAME[tier]);
      sendHeartbeat();
      if (tier > old) requestScan("risk went up");
    }
  }
  Serial.printf("%.1f C  %.0f %%  tier %s  jetson %s%s\n", temp, rh, TIER_NAME[tier], jetsonState.c_str(),
                fakeOn ? "  (fake reading)" : "");
}

void maybeScan() {
  if (jetsonState != "sleep") return;  // already scanning or alerting
  unsigned long since = millis() - lastScan;
  if (tier == TIER_CRIT && (!haveScanned || since >= SCAN_CRIT_RETRY_MS)) requestScan("critical");
  else if (tier == TIER_ELEV && (!haveScanned || since >= SCAN_ELEV_MS)) requestScan("elevated schedule");
  else if (tier == TIER_LOW && since >= SCAN_LOW_MS) requestScan("low schedule");
}

// ---------- optional inputs ----------

void checkInputs() {
  if (PIN_TAMPER >= 0) {
    int v = digitalRead(PIN_TAMPER);
    if (lastTamper == LOW && v == HIGH) publishJson("unit/tamper", "{}");  // lid opened
    lastTamper = v;
  }
  if (PIN_TEST_BTN >= 0) {
    int v = digitalRead(PIN_TEST_BTN);
    if (lastBtn == HIGH && v == LOW) requestScan("test button");
    lastBtn = v;
  }
}

void checkSerial() {
  if (!Serial.available()) return;
  String line = Serial.readStringUntil('\n');
  line.trim();
  if (line == "scan") {
    requestScan("serial command");
  } else if (line == "fake off") {
    fakeOn = false;
    Serial.println("using the real sensor again");
  } else if (line.startsWith("fake ")) {
    if (sscanf(line.c_str() + 5, "%f %f", &fakeTemp, &fakeRh) == 2) {
      fakeOn = true;
      Serial.printf("faking %.1f C / %.0f %%\n", fakeTemp, fakeRh);
    }
  } else if (line.startsWith("loc ")) {
    float lat, lon;
    int used = 0;
    if (sscanf(line.c_str() + 4, "%f %f %n", &lat, &lon, &used) >= 2) {
      String name = used > 0 ? line.substring(4 + used) : "";
      char buf[160];
      snprintf(buf, sizeof(buf), "{\"lat\":%.4f,\"lon\":%.4f,\"loc\":\"%s\"}", lat, lon, name.c_str());
      publishJson("unit/loc", buf);
    }
  } else if (line.length()) {
    Serial.println("commands: scan | fake <temp> <rh> | fake off | loc <lat> <lon> <name>");
  }
}

// ---------- main ----------

void setup() {
  Serial.begin(115200);
  delay(200);
  Serial.printf("\nFireline sentry, demo mode %s\n", DEMO_MODE ? "ON" : "off");
  for (int p : {PIN_LED_GREEN, PIN_LED_YELLOW, PIN_LED_RED, PIN_BUZZER})
    if (p >= 0) pinMode(p, OUTPUT);
  if (PIN_TAMPER >= 0) pinMode(PIN_TAMPER, INPUT_PULLUP);
  if (PIN_TEST_BTN >= 0) pinMode(PIN_TEST_BTN, INPUT_PULLUP);

  // Lamp test so you can see every LED works.
  setPin(PIN_LED_GREEN, HIGH); setPin(PIN_LED_YELLOW, HIGH); setPin(PIN_LED_RED, HIGH);
  delay(600);

  dht.begin();
  mqtt.setCallback(onMessage);
  ensureWifi();
}

void loop() {
  ensureWifi();
  ensureMqtt();
  mqtt.loop();

  unsigned long now = millis();
  if (now - lastRead >= READ_MS || lastRead == 0) {
    lastRead = now;
    readSensor();
    maybeScan();
  }
  if (now - lastHb >= HB_MS) sendHeartbeat();

  checkInputs();
  checkSerial();
  updateOutputs();
  delay(20);
}
