/*
 * ESP32 SH110X OLED + INMP441 Microphone for May Voice Assistant
 * Feature: Auto-scrolling text for long messages
 */

#include <WiFi.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SH110X.h>
#include <driver/i2s.h>

// ====================== PINS ======================
#define OLED_SDA 21
#define OLED_SCL 22
#define MIC_SCK  14
#define MIC_WS   15
#define MIC_SD   32
// ==================================================

// WiFi credentials - CHANGE THESE!
const char* ssid = "";
const char* password = "";

WiFiServer server(8888);
WiFiClient client;

// OLED Display
#define SCREEN_WIDTH  128
#define SCREEN_HEIGHT 64
#define OLED_RESET    -1
Adafruit_SH1106G display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

#define SH1106_OFFSET 2

// I2S Configuration
#define I2S_PORT     I2S_NUM_0
#define SAMPLE_RATE  16000
#define BUFFER_SIZE  512

// Scrolling text variables
String scrollText = "";
String scrollTitle = "";
int scrollPosition = 0;
unsigned long lastScrollTime = 0;
const int SCROLL_DELAY = 2000;  // 2 seconds per screen
const int SCROLL_SPEED = 300;   // milliseconds between scroll updates
bool isScrolling = false;
int totalLines = 0;
int currentPage = 0;

// State variables
String currentInput = "";
String currentResponse = "";
bool isListening = false;
bool isSpeaking = false;
bool microphoneEnabled = false;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=== May Assistant ESP32 (SH110X OLED with Scrolling) ===");

  Wire.begin(OLED_SDA, OLED_SCL);

  // Try 0x3C first, change to 0x3D if screen stays blank
  if (!display.begin(0x3C, true)) {
    Serial.println(F("SH110X allocation failed - try address 0x3D"));
    while (true);
  }

  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SH110X_WHITE);
  display.setCursor(0, 0);
  display.println("May Assistant");
  display.println("Initializing...");
  display.display();

  setupI2SMicrophone();

  // Connect to WiFi
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println("Connecting WiFi...");
  display.display();

  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }
  Serial.println("\nWiFi connected");
  Serial.print("IP: ");
  Serial.println(WiFi.localIP());

  server.begin();
  displayReady();
}

void loop() {
  if (!client.connected()) {
    client = server.available();
    if (client) {
      Serial.println("Client connected");
      displayReady();
    }
  }

  if (client && client.connected() && client.available()) {
    String data = client.readStringUntil('\n');
    data.trim();
    if (data.length() > 0) {
      Serial.println("Received: " + data);
      handleCommand(data);
    }
  }

  if (microphoneEnabled && client && client.connected()) {
    streamMicrophoneData();
  }

  // Handle scrolling
  if (isScrolling) {
    updateScrollingText();
  }

  delay(10);
}

// ==================== I2S MICROPHONE ====================
void setupI2SMicrophone() {
  i2s_config_t i2s_config = {
    .mode = (i2s_mode_t)(I2S_MODE_MASTER | I2S_MODE_RX),
    .sample_rate = SAMPLE_RATE,
    .bits_per_sample = I2S_BITS_PER_SAMPLE_32BIT,
    .channel_format = I2S_CHANNEL_FMT_ONLY_LEFT,
    .communication_format = I2S_COMM_FORMAT_I2S,
    .intr_alloc_flags = ESP_INTR_FLAG_LEVEL1,
    .dma_buf_count = 4,
    .dma_buf_len = BUFFER_SIZE,
    .use_apll = false
  };

  i2s_pin_config_t pin_config = {
    .bck_io_num = MIC_SCK,
    .ws_io_num = MIC_WS,
    .data_out_num = -1,
    .data_in_num = MIC_SD
  };

  esp_err_t err = i2s_driver_install(I2S_PORT, &i2s_config, 0, NULL);
  if (err != ESP_OK) {
    Serial.printf("I2S driver install failed: %d\n", err);
    return;
  }
  err = i2s_set_pin(I2S_PORT, &pin_config);
  if (err != ESP_OK) {
    Serial.printf("I2S set pin failed: %d\n", err);
    return;
  }
  Serial.println("INMP441 Microphone initialized");
}

void streamMicrophoneData() {
  int32_t samples[BUFFER_SIZE];
  size_t bytes_read = 0;

  esp_err_t result = i2s_read(I2S_PORT, &samples, sizeof(samples), &bytes_read, portMAX_DELAY);

  if (result == ESP_OK && bytes_read > 0) {
    int16_t samples_16bit[BUFFER_SIZE];
    int num_samples = bytes_read / sizeof(int32_t);

    for (int i = 0; i < num_samples; i++) {
      samples_16bit[i] = (int16_t)(samples[i] >> 16);
    }

    if (client && client.connected()) {
      client.write((uint8_t*)samples_16bit, num_samples * sizeof(int16_t));
    }
  }
}

// ==================== COMMAND HANDLING ====================
void handleCommand(String data) {
  int sep = data.indexOf('|');
  if (sep == -1) return;

  String type = data.substring(0, sep);
  String text = data.substring(sep + 1);

  if (type == "LISTENING") {
    isListening = true;
    isSpeaking = false;
    microphoneEnabled = true;
    isScrolling = false;
    displayListening();
  } else if (type == "STOP_LISTENING") {
    microphoneEnabled = false;
    isListening = false;
    isScrolling = false;
  } else if (type == "INPUT") {
    currentInput = text;
    isListening = false;
    microphoneEnabled = false;
    displayInputScrolling(text);
  } else if (type == "RESPONSE") {
    currentResponse = text;
    displayResponseScrolling(text);
  } else if (type == "SPEAKING") {
    isSpeaking = true;
    displaySpeakingScrolling();
  } else if (type == "READY") {
    isListening = false;
    isSpeaking = false;
    microphoneEnabled = false;
    isScrolling = false;
    displayReady();
  } else if (type == "MIC_START") {
    microphoneEnabled = true;
  } else if (type == "MIC_STOP") {
    microphoneEnabled = false;
  }
}

// ==================== SCROLLING TEXT FUNCTIONS ====================
void startScrollingText(String title, String text) {
  scrollTitle = title;
  scrollText = text;
  scrollPosition = 0;
  currentPage = 0;
  lastScrollTime = millis();
  isScrolling = true;
  
  // Calculate total lines needed
  const uint8_t maxChars = 21;
  int pos = 0;
  totalLines = 0;
  
  while (pos < text.length()) {
    int endPos = pos + maxChars;
    if (endPos > text.length()) endPos = text.length();
    
    if (endPos < text.length()) {
      int lastSpace = text.lastIndexOf(' ', endPos);
      if (lastSpace > pos) endPos = lastSpace;
    }
    
    pos = endPos;
    while (pos < text.length() && text.charAt(pos) == ' ') pos++;
    totalLines++;
  }
  
  // Show first page immediately
  displayScrollPage();
}

void updateScrollingText() {
  if (!isScrolling) return;
  
  unsigned long currentTime = millis();
  
  // Auto-scroll every SCROLL_DELAY milliseconds
  if (currentTime - lastScrollTime >= SCROLL_DELAY) {
    lastScrollTime = currentTime;
    scrollPosition += 6;  // Scroll by 6 lines (almost one full screen)
    
    // Check if we've reached the end
    if (scrollPosition >= totalLines) {
      scrollPosition = 0;  // Loop back to start
      currentPage = 0;
    }
    
    displayScrollPage();
  }
}

void displayScrollPage() {
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  
  // Display title
  display.println(scrollTitle);
  display.drawLine(0, 8, SCREEN_WIDTH, 8, SH110X_WHITE);
  
  // Display text starting from scrollPosition
  const uint8_t maxChars = 21;
  const uint8_t lineHeight = 8;
  const int maxVisibleLines = 6;
  uint8_t y = 12;
  int pos = 0;
  int currentLine = 0;
  
  // Skip to scrollPosition
  while (pos < scrollText.length() && currentLine < scrollPosition) {
    int endPos = pos + maxChars;
    if (endPos > scrollText.length()) endPos = scrollText.length();
    
    if (endPos < scrollText.length()) {
      int lastSpace = scrollText.lastIndexOf(' ', endPos);
      if (lastSpace > pos) endPos = lastSpace;
    }
    
    pos = endPos;
    while (pos < scrollText.length() && scrollText.charAt(pos) == ' ') pos++;
    currentLine++;
  }
  
  // Display visible lines
  int linesDisplayed = 0;
  while (pos < scrollText.length() && linesDisplayed < maxVisibleLines) {
    int endPos = pos + maxChars;
    if (endPos > scrollText.length()) endPos = scrollText.length();
    
    if (endPos < scrollText.length()) {
      int lastSpace = scrollText.lastIndexOf(' ', endPos);
      if (lastSpace > pos) endPos = lastSpace;
    }
    
    String line = scrollText.substring(pos, endPos);
    line.trim();
    
    display.setCursor(0, y);
    display.println(line);
    
    pos = endPos;
    while (pos < scrollText.length() && scrollText.charAt(pos) == ' ') pos++;
    
    y += lineHeight;
    linesDisplayed++;
    currentLine++;
  }
  
  // Show scroll indicator if there's more content
  if (currentLine < totalLines) {
    display.setCursor(120, 56);
    display.print("v");  // Down arrow indicator
  }
  if (scrollPosition > 0) {
    display.setCursor(120, 12);
    display.print("^");  // Up arrow indicator
  }
  
  display.display();
}

// ==================== DISPLAY FUNCTIONS ====================
void displayReady() {
  isScrolling = false;
  display.clearDisplay();
  display.setTextSize(2);
  display.setCursor(20, 0);
  display.println("MAY");
  display.setTextSize(1);
  display.setCursor(0, 25);
  display.println("Ready");
  display.print("IP: ");
  display.println(WiFi.localIP());
  display.setCursor(0, 50);
  display.println("Mic: INMP441");
  display.display();
}

void displayListening() {
  isScrolling = false;
  display.clearDisplay();
  display.setTextSize(1);
  display.setCursor(0, 0);
  display.println("Status: LISTENING");
  display.setTextSize(2);
  display.setCursor(10, 25);
  display.println(" [...]");
  display.setTextSize(1);
  display.setCursor(0, 50);
  display.println("Mic active");
  display.display();
}

void displayInputScrolling(String text) {
  if (text.length() > 100) {  // If text is long, enable scrolling
    startScrollingText("You said:", text);
  } else {
    // Short text, display normally
    isScrolling = false;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("You:");
    displayMultiLineText(text, 10);
    display.display();
  }
}

void displayResponseScrolling(String text) {
  if (text.length() > 100) {  // If text is long, enable scrolling
    startScrollingText("May says:", text);
  } else {
    // Short text, display normally
    isScrolling = false;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("May:");
    displayMultiLineText(text, 10);
    display.display();
  }
}

void displaySpeakingScrolling() {
  if (currentResponse.length() > 100) {
    startScrollingText("May speaking:", currentResponse);
  } else {
    isScrolling = false;
    display.clearDisplay();
    display.setTextSize(1);
    display.setCursor(0, 0);
    display.println("May speaking:");
    if (currentResponse.length() > 0) {
      displayMultiLineText(currentResponse, 10);
    } else {
      display.setTextSize(2);
      display.setCursor(10, 25);
      display.println(" ...");
    }
    display.display();
  }
}

void displayMultiLineText(String text, uint8_t startY) {
  const uint8_t maxChars = 21;
  const uint8_t lineHeight = 8;
  uint8_t y = startY + SH1106_OFFSET;
  int pos = 0;
  int lines = 0;
  const int maxLines = 6;

  while (pos < text.length() && lines < maxLines) {
    int endPos = pos + maxChars;
    if (endPos > text.length()) endPos = text.length();

    // Prefer breaking at space
    if (endPos < text.length()) {
      int lastSpace = text.lastIndexOf(' ', endPos);
      if (lastSpace > pos) endPos = lastSpace;
    }

    String line = text.substring(pos, endPos);
    line.trim();

    display.setCursor(0, y);
    display.println(line);

    pos = endPos;
    while (pos < text.length() && text.charAt(pos) == ' ') pos++;

    y += lineHeight;
    lines++;
  }
  
  // Show "..." if text is truncated
  if (pos < text.length()) {
    display.setCursor(115, y - lineHeight);
    display.print("...");
  }
}