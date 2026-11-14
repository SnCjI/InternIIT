/*
 * Multispectral LED Driver — Phase 1 Firmware
 * ESP32 — 5-channel PWM controller (500 Hz, 10-bit, inverted output)
 *
 * Architecture:
 *   Host PC --(USB / Virtual COM Port)--> ESP32 --(5x LEDC PWM)--> 5x Constant-Current Drivers --> LEDs
 *
 * This firmware generates 5 independent, flicker-free PWM dimming signals
 * using the ESP32's hardware LEDC peripheral, and exposes a simple
 * text-based UART command protocol so a host (microscopy control software)
 * can set channel intensity in real time.
 *
 * Command protocol (newline-terminated ASCII over Serial):
 *   SET <ch> <duty>      -> set channel <ch> (0-4) to <duty> (0-100 %)
 *   ALL <duty>           -> set all channels to <duty> (0-100 %)
 *   OFF                  -> turn all channels off
 *   STATUS               -> print current duty cycle of all channels
 *
 * Examples:
 *   SET 0 75             -> UV channel to 75% intensity
 *   ALL 0                -> all channels off
 */

#include <Arduino.h>

// ---------- Channel / pin configuration ----------
const uint8_t NUM_CHANNELS = 5;

// GPIO pins used for each PWM dimming output (adjust to match your PCB net names)
const uint8_t LED_PIN[NUM_CHANNELS] = { 4, 5, 18, 19, 21 };

// Human-readable channel names, matching the block diagram
const char* CHANNEL_NAME[NUM_CHANNELS] = { "UV", "Blue", "Green", "Red", "NIR" };

// LEDC configuration
const uint32_t PWM_FREQ_HZ    = 500;    // Verify against the LDD-H datasheet DIM PWM frequency range
const uint8_t  PWM_RESOLUTION = 10;     // 10-bit -> duty range 0-1023
const uint32_t MAX_DUTY       = (1UL << PWM_RESOLUTION) - 1;   // 1023

// NOTE: each output drives an NPN open-collector stage on the LDD-H DIM input,
// which inverts the signal. The duty written to the LEDC is therefore
// MAX_DUTY - requested duty, so SET/ALL give the requested LED brightness.

// Track current duty (0-100 %) per channel, for STATUS reporting
float currentDutyPercent[NUM_CHANNELS] = { 0, 0, 0, 0, 0 };

// ---------- Setup ----------
void setup() {
  Serial.begin(115200);
  //while(!Serial); 
  delay(200);

  Serial.println("Done!");
  for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
    // ledcAttach: new-style API (ESP32 Arduino core 3.x). If your Wokwi core
    // is 2.x, replace with: ledcSetup(ch, PWM_FREQ_HZ, PWM_RESOLUTION); ledcAttachPin(LED_PIN[ch], ch);
    ledcAttach(LED_PIN[ch], PWM_FREQ_HZ, PWM_RESOLUTION);
    ledcWrite(LED_PIN[ch], MAX_DUTY);   // start OFF (inverted output)
  }

  Serial.println(F("=== Multispectral LED Driver — Phase 1 ==="));
  Serial.println(F("5 channels ready: UV, Blue, Green, Red, NIR"));
  printHelp();
}

// ---------- Main loop ----------
void loop() {
  static String line = "";

  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n' || c == '\r') {
      if (line.length() > 0) {
        handleCommand(line);
        line = "";
      }
    } else {
      line += c;
    }
  }
}

// ---------- Command handling ----------
void handleCommand(String cmdLine) {
  cmdLine.trim();
  cmdLine.toUpperCase();

  if (cmdLine.startsWith("SET")) {
    int ch, duty;
    if (sscanf(cmdLine.c_str(), "SET %d %d", &ch, &duty) == 2) {
      setChannel(ch, duty);
    } else {
      Serial.println(F("ERR bad SET syntax. Use: SET <ch 0-4> <duty 0-100>"));
    }

  } else if (cmdLine.startsWith("ALL")) {
    int duty;
    if (sscanf(cmdLine.c_str(), "ALL %d", &duty) == 1) {
      for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) setChannel(ch, duty);
    } else {
      Serial.println(F("ERR bad ALL syntax. Use: ALL <duty 0-100>"));
    }

  } else if (cmdLine == "OFF") {
    for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) setChannel(ch, 0);
    Serial.println(F("OK all channels off"));

  } else if (cmdLine == "STATUS") {
    printStatus();

  } else if (cmdLine == "HELP") {
    printHelp();

  } else {
    Serial.println(F("ERR unknown command. Type HELP."));
  }
}

void setChannel(int ch, int dutyPercent) {
  if (ch < 0 || ch >= NUM_CHANNELS) {
    Serial.println(F("ERR channel out of range (0-4)"));
    return;
  }
  dutyPercent = constrain(dutyPercent, 0, 100);

  uint32_t dutyCounts = (uint32_t)((dutyPercent / 100.0f) * MAX_DUTY);

  ledcWrite(LED_PIN[ch], MAX_DUTY - dutyCounts);   // inverted for NPN open-collector DIM stage
  currentDutyPercent[ch] = dutyPercent;

  Serial.print(F("OK ch"));
  Serial.print(ch);
  Serial.print(F(" ("));
  Serial.print(CHANNEL_NAME[ch]);
  Serial.print(F(") = "));
  Serial.print(dutyPercent);
  Serial.println(F("%"));
}

void printStatus() {
  Serial.println(F("--- Channel status ---"));
  for (uint8_t ch = 0; ch < NUM_CHANNELS; ch++) {
    Serial.print(F("ch"));
    Serial.print(ch);
    Serial.print(F(" ("));
    Serial.print(CHANNEL_NAME[ch]);
    Serial.print(F(") pin "));
    Serial.print(LED_PIN[ch]);
    Serial.print(F(": "));
    Serial.print(currentDutyPercent[ch]);
    Serial.println(F("%"));
  }
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  SET <ch 0-4> <duty 0-100>"));
  Serial.println(F("  ALL <duty 0-100>"));
  Serial.println(F("  OFF"));
  Serial.println(F("  STATUS"));
}
