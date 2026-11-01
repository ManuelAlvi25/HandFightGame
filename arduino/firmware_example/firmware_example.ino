/*
  Gesture Fighter - firmware de ejemplo (ESQUELETO, NO PROBADO EN HARDWARE FÍSICO)

  Lee un sensor ultrasónico (HC-SR04 o compatible), envía la distancia al PC y enciende
  los LEDs de vida que el PC le indica. Protocolo de texto por líneas (ver README y
  src/hardware/protocol.py):

    Arduino -> PC : HELLO:<placa>,<nLedJ>,<nLedE>   D:<cm>   PONG   ERR:<motivo>
    PC -> Arduino : PING   HP:<j%>,<e%>   LED:<bitsJ>,<bitsE>,<critJ><critE>
    Cada línea termina en "*XX\n" (XX = XOR en hex de los bytes anteriores a '*').

  Placas previstas (se elige automáticamente al compilar):
    - ESP32 (WiFi.h)                 - Arduino UNO R4 WiFi (WiFiS3.h)
    - Nano 33 IoT / MKR WiFi 1010 (WiFiNINA.h)
    - Cualquier otra placa: modo USB serie (en el PC: "transport": "serial")

  Modo Wi-Fi por defecto: la placa crea su propia red (punto de acceso) "GestureFighter";
  conecte la laptop a esa red y use host 192.168.4.1, puerto 5000 en hardware_config.json.
*/

#if defined(ESP32)
  #include <WiFi.h>
  #define BOARD_NAME "ESP32"
#elif defined(ARDUINO_UNOR4_WIFI)
  #include <WiFiS3.h>
  #define BOARD_NAME "UNO_R4_WIFI"
#elif defined(ARDUINO_SAMD_NANO_33_IOT) || defined(ARDUINO_SAMD_MKRWIFI1010)
  #include <WiFiNINA.h>
  #define BOARD_NAME "NINA"
#else
  #define USE_SERIAL_ONLY
  #define BOARD_NAME "SERIAL"
#endif

// ----------------------------- Configuración -------------------------------
#define WIFI_AP_MODE 1                 // 1 = la placa crea la red; 0 = se une a un router
const char* WIFI_SSID = "GestureFighter";
const char* WIFI_PASS = "pelea1234";   // mínimo 8 caracteres
const uint16_t TCP_PORT = 5000;
const unsigned long SENSOR_PERIOD_MS = 60;    // el HC-SR04 necesita >= 60 ms entre disparos
const unsigned long PC_TIMEOUT_MS = 3000;     // sin mensajes del PC -> LEDs en espera

#if defined(ESP32)
  // ECHO del HC-SR04 es de 5 V: usar divisor resistivo (p.ej. 1k/2k) hacia el pin de 3.3 V
  const int TRIG_PIN = 5, ECHO_PIN = 18;
  const int PLAYER_LEDS[] = {13, 12, 14, 27, 26};
  const int ENEMY_LEDS[]  = {25, 33, 32, 15, 4};
#else
  const int TRIG_PIN = 9, ECHO_PIN = 10;
  const int PLAYER_LEDS[] = {2, 3, 4, 5, 6};
  const int ENEMY_LEDS[]  = {7, 8, 11, 12, 13};
#endif
const int N_PLAYER = sizeof(PLAYER_LEDS) / sizeof(int);
const int N_ENEMY  = sizeof(ENEMY_LEDS) / sizeof(int);

// ----------------------------- Estado --------------------------------------
#ifndef USE_SERIAL_ONLY
WiFiServer server(TCP_PORT);
WiFiClient client;
#endif
Stream* pcLink = nullptr;
String rx;
unsigned long lastSensor = 0, lastRx = 0;
int healthPlayer = 100, healthEnemy = 100;

// ----------------------------- Protocolo -----------------------------------
String checksum(const String& p) {
  uint8_t x = 0;
  for (unsigned i = 0; i < p.length(); i++) x ^= (uint8_t)p[i];
  char buf[3];
  snprintf(buf, sizeof(buf), "%02X", x);
  return String(buf);
}

void sendLine(const String& payload) {
  if (pcLink) pcLink->print(payload + "*" + checksum(payload) + "\n");
}

void setLeds(const int* pins, int n, const String& bits) {
  for (int i = 0; i < n; i++) digitalWrite(pins[i], (i < (int)bits.length() && bits[i] == '1') ? HIGH : LOW);
}

void handleLine(String line) {
  line.trim();
  int star = line.lastIndexOf('*');
  if (star < 0) { sendLine("ERR:NOCHK"); return; }
  String payload = line.substring(0, star);
  if (!line.substring(star + 1).equalsIgnoreCase(checksum(payload))) { sendLine("ERR:CHK"); return; }
  lastRx = millis();
  int colon = payload.indexOf(':');
  String cmd = colon < 0 ? payload : payload.substring(0, colon);
  String args = colon < 0 ? "" : payload.substring(colon + 1);

  if (cmd == "PING") {
    sendLine("PONG");
  } else if (cmd == "HP") {
    int c = args.indexOf(',');
    healthPlayer = args.substring(0, c).toInt();
    healthEnemy = args.substring(c + 1).toInt();
    // TODO opcional: usar la vida para un zumbador, pantalla, etc.
  } else if (cmd == "LED") {
    int c1 = args.indexOf(','), c2 = args.indexOf(',', c1 + 1);
    setLeds(PLAYER_LEDS, N_PLAYER, args.substring(0, c1));
    setLeds(ENEMY_LEDS, N_ENEMY, args.substring(c1 + 1, c2));
    // args.substring(c2 + 1) = flags de vida crítica (el parpadeo ya viene calculado por el PC)
  } else {
    sendLine("ERR:CMD");
  }
}

void readLink() {
  while (pcLink && pcLink->available()) {
    char ch = pcLink->read();
    if (ch == '\n') { handleLine(rx); rx = ""; }
    else if (rx.length() < 120) rx += ch;
    else rx = "";  // línea demasiado larga: descartar
  }
}

// ----------------------------- Sensor --------------------------------------
float readDistanceCm() {
  digitalWrite(TRIG_PIN, LOW);  delayMicroseconds(2);
  digitalWrite(TRIG_PIN, HIGH); delayMicroseconds(10);
  digitalWrite(TRIG_PIN, LOW);
  unsigned long us = pulseIn(ECHO_PIN, HIGH, 25000UL);  // ~4 m máx.
  if (us == 0) return -1;  // sin eco
  return us / 58.0;
}

// ----------------------------- Setup / loop --------------------------------
void setup() {
  Serial.begin(115200);
  pinMode(TRIG_PIN, OUTPUT);
  pinMode(ECHO_PIN, INPUT);
  for (int i = 0; i < N_PLAYER; i++) { pinMode(PLAYER_LEDS[i], OUTPUT); digitalWrite(PLAYER_LEDS[i], HIGH); }
  for (int i = 0; i < N_ENEMY; i++)  { pinMode(ENEMY_LEDS[i], OUTPUT);  digitalWrite(ENEMY_LEDS[i], HIGH); }

#ifdef USE_SERIAL_ONLY
  pcLink = &Serial;
#else
  #if WIFI_AP_MODE
    WiFi.softAP(WIFI_SSID, WIFI_PASS);   // ESP32 / NINA / R4: IP por defecto 192.168.4.1
    Serial.print("Punto de acceso listo. IP: ");
    Serial.println(WiFi.softAPIP());
  #else
    WiFi.begin(WIFI_SSID, WIFI_PASS);
    while (WiFi.status() != WL_CONNECTED) { delay(500); Serial.print("."); }
    Serial.print("\nConectado. IP (poner en hardware_config.json): ");
    Serial.println(WiFi.localIP());
  #endif
  server.begin();
#endif
}

void loop() {
#ifndef USE_SERIAL_ONLY
  if (!client || !client.connected()) {
    WiFiClient c = server.available();
    if (c) {
      client = c;
      pcLink = &client;
      rx = "";
      lastRx = millis();
      sendLine(String("HELLO:") + BOARD_NAME + "," + N_PLAYER + "," + N_ENEMY);
    } else {
      pcLink = nullptr;
    }
  }
#else
  static bool hello = false;
  if (!hello) { sendLine(String("HELLO:") + BOARD_NAME + "," + N_PLAYER + "," + N_ENEMY); hello = true; lastRx = millis(); }
#endif

  readLink();

  if (pcLink && millis() - lastSensor >= SENSOR_PERIOD_MS) {
    lastSensor = millis();
    float d = readDistanceCm();
    if (d > 0) sendLine("D:" + String(d, 1));
  }

  // Watchdog: si el PC deja de hablar, LEDs alternados indicando "sin conexión"
  if (millis() - lastRx > PC_TIMEOUT_MS) {
    bool on = (millis() / 500) % 2;
    for (int i = 0; i < N_PLAYER; i++) digitalWrite(PLAYER_LEDS[i], on && i == 0);
    for (int i = 0; i < N_ENEMY; i++)  digitalWrite(ENEMY_LEDS[i], !on && i == 0);
  }
}
