	# May Voice Assistant 🎙️

A voice-activated AI assistant powered by Claude (Anthropic), featuring emotion detection via Hume AI, natural speech synthesis with ElevenLabs, and an ESP32-powered OLED display with scrolling text support.

## ✨ Features

- 🗣️ **Wake Word Activation**: Say "May" to activate the assistant
- 🤖 **AI-Powered Responses**: Uses Claude Sonnet 4 for intelligent, context-aware conversations
- 😊 **Emotion Detection**: Analyzes user emotions using Hume AI API (with TextBlob fallback)
- 🔊 **Natural Text-to-Speech**: High-quality voice synthesis via ElevenLabs
- 🎤 **Speech Recognition**: Google Speech Recognition for voice input
- 📟 **ESP32 OLED Display**: Real-time visual feedback with auto-scrolling for long messages
- 🎙️ **INMP441 Microphone**: Hardware microphone integration with ESP32
- ⏰ **Reminders**: Set time-based reminders
- 🔋 **Battery Monitoring**: Low battery warnings
- 💬 **Conversation Mode**: Continuous conversation without repeating wake word

## 🛠️ Hardware Requirements

### Main Computer
- Python 3.8 or higher
- Microphone for voice input
- Speakers for audio output

### ESP32 Setup (Optional but Recommended)
- ESP32 Development Board
- SH1106/SH1107 OLED Display (128x64)
- INMP441 I2S Microphone Module
- Jumper wires

#### Wiring Diagram
```
OLED Display (I2C):
- SDA → GPIO 21
- SCL → GPIO 22
- VCC → 3.3V
- GND → GND

INMP441 Microphone (I2S):
- SCK  → GPIO 14
- WS   → GPIO 15
- SD   → GPIO 32
- VDD  → 3.3V
- GND  → GND
- L/R  → GND (for left channel)
```

## 📦 Installation

### 1. Clone the Repository
```bash
git clone https://github.com/yourusername/may-assistant.git
cd may-assistant
```

### 2. Create Virtual Environment
```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Install PyAudio (Windows)
If you encounter issues with PyAudio on Windows:
```bash
pip install pipwin
pipwin install pyaudio
```

### 5. Set Up Environment Variables
Create a `.env` file in the project root:
```env
ANTHROPIC_API_KEY=your_anthropic_api_key_here
HUME_API_KEY=your_hume_api_key_here
ELEVENLABS_API_KEY=your_elevenlabs_api_key_here
```

### 6. Configure ESP32 (Optional)
1. Open the Arduino `.ino` file (document 4)
2. Update WiFi credentials:
   ```cpp
   const char* ssid = "your_wifi_ssid";
   const char* password = "your_wifi_password";
   ```
3. Upload to ESP32 using Arduino IDE
4. Note the IP address displayed on the OLED
5. Update `may.py` with ESP32 IP:
   ```python
   ESP32_IP = "192.168.1.xxx"  # Your ESP32's IP
   ```

## 🚀 Usage

### Start the Assistant
```bash
python may.py
```

### Voice Commands
1. **Activate**: Say "May" to wake the assistant
2. **Ask Questions**: After activation, ask anything naturally
3. **Exit Conversation**: Say "goodbye", "bye", or "stop listening"

### Example Interactions
```
You: "May, what time is it?"
May: "It's 2:30 PM."

You: "May, set a reminder for 10 minutes"
May: "Reminder set for 10 minutes from now."

You: "May, tell me a joke"
May: [Responds with AI-generated joke]
```

## 🎨 Voice Customization

Change ElevenLabs voice (common voices):
```python
# In conversation, say:
"May, change voice to Rachel"
"May, change voice to George"
"May, change voice to Bella"
```

Or set voice ID in `config.json`:
```json
{
  "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb"
}
```

## 📊 System Diagnostics

The assistant displays system status on startup:
```
=== System Diagnostics ===
Anthropic API: Online
Hume API: Online
ElevenLabs TTS: Online (ElevenLabs)
Speech Recognition: Google (Free)
ESP32 Display: Connected
========================
```

## 🔧 Configuration

### config.json
```json
{
  "rate": 175,
  "volume": 1.0,
  "reminders": [],
  "timezone": "Asia/Kolkata",
  "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb"
}
```

### Supported Timezones
Change timezone in `config.json`:
- `"Asia/Kolkata"` (India)
- `"America/New_York"` (US Eastern)
- `"Europe/London"` (UK)
- `"Asia/Tokyo"` (Japan)
- See [pytz documentation](https://pypi.org/project/pytz/) for more

## 🐛 Troubleshooting

### Common Issues

**PyAudio Installation Fails**
```bash
# Windows
pip install pipwin
pipwin install pyaudio

# macOS
brew install portaudio
pip install pyaudio

# Linux (Ubuntu/Debian)
sudo apt-get install python3-pyaudio
```

**ESP32 Connection Fails**
- Verify ESP32 is on same WiFi network
- Check IP address matches in `may.py`
- Ensure port 8888 is open

**Speech Recognition Not Working**
- Check microphone permissions
- Test microphone in system settings
- Ensure microphone is not muted

**ElevenLabs API Errors**
- Verify API key in `.env`
- Check ElevenLabs account limits
- Free tier has character limits per month

**Claude API Errors**
- Verify Anthropic API key
- Check API rate limits
- Ensure API key has correct permissions

## 📝 API Keys

### Required APIs
1. **Anthropic Claude** (Required)
   - Sign up: https://console.anthropic.com/
   - Get API key from dashboard

2. **ElevenLabs** (Recommended)
   - Sign up: https://elevenlabs.io/
   - Free tier: 10,000 characters/month
   - Get API key from profile settings

3. **Hume AI** (Optional)
   - Sign up: https://hume.ai/
   - Falls back to TextBlob sentiment analysis if not provided

## 📁 Project Structure

```
may-assistant/
├── may.py                 # Main assistant script
├── config.json           # User configuration
├── requirements.txt      # Python dependencies
├── .env                  # API keys (not in Git!)
├── .gitignore           # Git ignore rules
├── README.md            # This file
└── esp32_oled.ino       # ESP32 firmware (Arduino)
```

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Open a Pull Request


## 🙏 Acknowledgments

- **Anthropic** for Claude AI
- **ElevenLabs** for natural TTS
- **Hume AI** for emotion detection
- **ESP32** community for hardware support


## 🔮 Future Enhancements

- [ ] Multi-language support
- [ ] Custom wake word training
- [ ] Smart home integration
- [ ] Calendar integration
- [ ] Weather forecasts
- [ ] Music playback control
- [ ] Multi-user profiles

---

**Made with ❤️ by MAY team**

*Say "May" and start talking!*
