import os
import asyncio
from dotenv import load_dotenv
import sys
from datetime import datetime, timedelta
import random
import json
import re
import requests
from textblob import TextBlob
import logging
import nltk
from anthropic import AsyncAnthropic, AnthropicError
import psutil
import pygame
import pytz
import httpx
import traceback
import socket
import time
import warnings
import tempfile
import uuid
from elevenlabs import ElevenLabs, VoiceSettings

# Suppress pygame pkg_resources warning
warnings.filterwarnings("ignore", category=UserWarning, module="pygame.pkgdata")

# Log versions for debugging
logging.basicConfig(filename='may_assistant.log', level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logging.info(f"Python version: {sys.version}")
logging.info(f"httpx version: {httpx.__version__}")
print(f"DEBUG: httpx version: {httpx.__version__}")

# Download NLTK data
try:
    nltk.download('punkt', quiet=True)
    nltk.download('averaged_perceptron_tagger', quiet=True)
    nltk.download('brown', quiet=True)
except Exception as e:
    logging.error(f"NLTK download error: {e}\n{traceback.format_exc()}")
    print(f"❌ NLTK download error: {e}")

# Clear proxy environment variables
for var in ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY"]:
    if os.getenv(var):
        logging.warning(f"Removing environment variable {var} to prevent httpx issues")
        print(f"DEBUG: Removing environment variable {var}")
        os.environ.pop(var, None)

# Load API keys
load_dotenv()
HUME_API_KEY = os.getenv("HUME_API_KEY")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
ELEVENLABS_API_KEY = os.getenv("ELEVENLABS_API_KEY")

# Debug: Print masked API keys
if HUME_API_KEY:
    logging.info(f"Loaded Hume API key: {'***' + HUME_API_KEY[-4:] if len(HUME_API_KEY) > 4 else HUME_API_KEY}")
    print(f"DEBUG: Loaded Hume API key: {'***' + HUME_API_KEY[-4:] if len(HUME_API_KEY) > 4 else HUME_API_KEY}")
else:
    logging.warning("No Hume API key loaded from .env")
    print("DEBUG: No Hume API key loaded from .env")

if ANTHROPIC_API_KEY:
    logging.info(f"Loaded Anthropic API key: {'***' + ANTHROPIC_API_KEY[-4:] if len(ANTHROPIC_API_KEY) > 4 else ANTHROPIC_API_KEY}")
    print(f"DEBUG: Loaded Anthropic API key: {'***' + ANTHROPIC_API_KEY[-4:] if len(ANTHROPIC_API_KEY) > 4 else ANTHROPIC_API_KEY}")
else:
    logging.warning("No Anthropic API key provided - using default response logic")
    print("DEBUG: No Anthropic API key provided - using default response logic")

if ELEVENLABS_API_KEY:
    logging.info(f"Loaded ElevenLabs API key: {'***' + ELEVENLABS_API_KEY[-4:] if len(ELEVENLABS_API_KEY) > 4 else ELEVENLABS_API_KEY}")
    print(f"DEBUG: Loaded ElevenLabs API key: {'***' + ELEVENLABS_API_KEY[-4:] if len(ELEVENLABS_API_KEY) > 4 else ELEVENLABS_API_KEY}")
else:
    logging.warning("No ElevenLabs API key provided")
    print("DEBUG: No ElevenLabs API key provided")

# Wake words and termination words
WAKE_WORDS = ["may"]
TERMINATION_WORDS = ["goodbye", "bye", "see you later", "talk to you later", "stop listening", "go to sleep", "sleep now"]

# ESP32 Configuration - CHANGE THIS TO YOUR ESP32'S IP ADDRESS
ESP32_IP = ""  # <<< UPDATE THIS WITH YOUR ESP32'S IP
ESP32_PORT = 8888

class ESP32Comm:
    """ESP32 Communication Handler"""
    def __init__(self, esp32_ip, esp32_port=8888):
        self.esp32_ip = esp32_ip
        self.esp32_port = esp32_port
        self.socket = None
        self.connected = False
        self.connect()
   
    def connect(self):
        """Establish connection to ESP32"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(2.0)
            self.socket.connect((self.esp32_ip, self.esp32_port))
            self.connected = True
            logging.info(f"Connected to ESP32 at {self.esp32_ip}:{self.esp32_port}")
            print(f"✅ Connected to ESP32 at {self.esp32_ip}:{self.esp32_port}")
        except Exception as e:
            self.connected = False
            logging.warning(f"Failed to connect to ESP32: {e}")
            print(f"⚠️ ESP32 connection failed: {e}")
   
    def send(self, message_type, text=""):
        """Send message to ESP32"""
        if not self.connected:
            return
       
        try:
            message = f"{message_type}|{text}\n"
            self.socket.sendall(message.encode('utf-8'))
            logging.info(f"Sent to ESP32: {message_type} - {text[:50]}")
        except Exception as e:
            logging.warning(f"Failed to send to ESP32: {e}")
            self.connected = False
            self.connect()
   
    def send_listening(self):
        self.send("LISTENING")
   
    def send_input(self, text):
        self.send("INPUT", text)
   
    def send_response(self, text):
        self.send("RESPONSE", text)
   
    def send_speaking(self):
        self.send("SPEAKING")
   
    def send_ready(self):
        self.send("READY")
   
    def close(self):
        if self.socket:
            try:
                self.socket.close()
                logging.info("ESP32 connection closed")
            except:
                pass
            self.connected = False

class MayAssistant:
    def __init__(self):
        logging.info("Initializing MayAssistant")
        print("DEBUG: Initializing MayAssistant")
       
        # ESP32 Display Integration
        try:
            self.esp32 = ESP32Comm(ESP32_IP, ESP32_PORT)
        except Exception as e:
            logging.warning(f"ESP32 not available: {e}")
            print(f"⚠️ ESP32 not available: {e}")
            self.esp32 = None
       
        self.config_file = "config.json"
        try:
            self.load_config()
        except Exception as e:
            logging.error(f"Failed to load config: {e}\n{traceback.format_exc()}")
            print(f"❌ Failed to load config: {e}")
        
        self.timezone = None
        try:
            self.timezone = pytz.timezone(self.config.get('timezone', 'Asia/Kolkata'))
            logging.info(f"Timezone set to {self.timezone}")
            print(f"DEBUG: Timezone set to {self.timezone}")
        except pytz.exceptions.UnknownTimeZoneError as e:
            logging.error(f"Invalid timezone in config: {e}. Falling back to UTC")
            print(f"❌ Invalid timezone in config: {e}. Falling back to UTC")
            self.timezone = pytz.UTC
        
        # Initialize ElevenLabs client
        self.elevenlabs_client = None
        self.elevenlabs_voice_id = self.config.get('elevenlabs_voice_id', 'cgSgspJ2msm6clMCkdW9')  # Default: George voice
        if ELEVENLABS_API_KEY:
            try:
                self.elevenlabs_client = ElevenLabs(api_key=ELEVENLABS_API_KEY)
                logging.info("ElevenLabs client initialized")
                print("✅ ElevenLabs client initialized")
                self.tts_status = "Online (ElevenLabs)"
            except Exception as e:
                logging.error(f"ElevenLabs init error: {e}\n{traceback.format_exc()}")
                print(f"❌ ElevenLabs init error: {e}")
                self.tts_status = "Offline"
        else:
            self.tts_status = "Offline (No API key)"
        
        self.conversation_active = False
        self.user_name = None
        self.context = []
        self.hume_api_key = HUME_API_KEY
        self.anthropic_api_key = ANTHROPIC_API_KEY
        self.is_speaking = False
        self.interrupted = False
        self.calibrated = False
        self.language = 'en-US'
        self.hume_api_status = None
        self.anthropic_api_status = None
        
        try:
            if self.anthropic_api_key:
                custom_client = httpx.AsyncClient(
                    http2=True,
                    timeout=10.0,
                    trust_env=False
                )
                self.anthropic_client = AsyncAnthropic(
                    api_key=self.anthropic_api_key,
                    default_headers={"anthropic-version": "2023-06-01"},
                    http_client=custom_client
                )
                logging.info("AsyncAnthropic initialized with custom HTTP client")
                print("DEBUG: AsyncAnthropic initialized with custom HTTP client")
            else:
                self.anthropic_client = None
                self.anthropic_api_status = "Offline (No API key)"
        except Exception as e:
            logging.error(f"AsyncAnthropic initialization error: {e}\n{traceback.format_exc()}")
            print(f"❌ AsyncAnthropic initialization error: {e}")
            self.anthropic_client = None
            self.anthropic_api_status = f"Offline (Error: {str(e)[:50]}...)"

        self.reminders = []
        self.battery_thresholds = {20: False, 10: False, 5: False}
        try:
            self.last_battery_check = datetime.now(self.timezone)
            logging.info("Battery check initialized")
            print("DEBUG: Battery check initialized")
        except Exception as e:
            logging.error(f"Failed to initialize last_battery_check: {e}\n{traceback.format_exc()}")
            print(f"❌ Failed to initialize last_battery_check: {e}")
            self.last_battery_check = datetime.utcnow().replace(tzinfo=pytz.UTC)

        try:
            pygame.mixer.init()
            logging.info("Pygame mixer initialized")
            print("DEBUG: Pygame mixer initialized")
        except Exception as e:
            logging.error(f"Pygame mixer init error: {e}\n{traceback.format_exc()}")
            print(f"❌ Pygame mixer init error: {e}")

        # Audio recording buffer for STT
        self.audio_buffer = []

        logging.info("MayAssistant initialization complete")
        print("DEBUG: MayAssistant initialization complete")

    def load_config(self):
        default_config = {
            "reminders": [],
            "timezone": "Asia/Kolkata",
            "elevenlabs_voice_id": "JBFqnCBsd6RMkjVDRZzb"  # George voice ID
        }
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    self.config = json.load(f)
                self.reminders = self.config.get('reminders', [])
            else:
                self.config = default_config
                self.save_config()
        except Exception as e:
            logging.error(f"Config error: {e}\n{traceback.format_exc()}")
            print(f"❌ Config error: {e}")
            self.config = default_config

    def save_config(self):
        try:
            self.config['reminders'] = self.reminders
            self.config['elevenlabs_voice_id'] = self.elevenlabs_voice_id
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
        except Exception as e:
            logging.error(f"Config save error: {e}\n{traceback.format_exc()}")
            print(f"❌ Config save error: {e}")

    async def list_voices(self):
        """List available ElevenLabs voices - requires API permission"""
        if not self.elevenlabs_client:
            return "ElevenLabs is not configured."
        
        try:
            response = self.elevenlabs_client.voices.get_all()
            voice_list = [f"{v.name} (ID: {v.voice_id})" for v in response.voices]
            return f"Available voices: {', '.join(voice_list)}"
        except Exception as e:
            logging.error(f"Failed to list voices: {e}")
            # Return common voice IDs if API fails
            return "Common voices: George (JBFqnCBsd6RMkjVDRZzb), Rachel (21m00Tcm4TlvDq8ikWAM), Bella (EXAVITQu4vr4xnSDxMaL)"

    async def change_voice(self, voice_name_or_id):
        """Change the ElevenLabs voice"""
        if not self.elevenlabs_client:
            return "ElevenLabs is not configured."
        
        # Common voice IDs
        common_voices = {
            "george": "JBFqnCBsd6RMkjVDRZzb",
            "rachel": "21m00Tcm4TlvDq8ikWAM",
            "bella": "EXAVITQu4vr4xnSDxMaL",
            "adam": "pNInz6obpgDQGcFmaJgB",
            "antoni": "ErXwobaYiN019PkySvjV"
        }
        
        # Check if it's a known voice name
        voice_lower = voice_name_or_id.lower()
        if voice_lower in common_voices:
            self.elevenlabs_voice_id = common_voices[voice_lower]
            self.save_config()
            return f"Voice changed to {voice_name_or_id.title()}"
        
        # Otherwise assume it's a voice ID
        self.elevenlabs_voice_id = voice_name_or_id
        self.save_config()
        return f"Voice ID set to {voice_name_or_id}"

    async def speak(self, text):
        """Speak using ElevenLabs TTS"""
        if self.esp32:
            self.esp32.send_speaking()
        
        if not self.elevenlabs_client:
            print(f"🔊 May says: {text}")
            logging.warning("ElevenLabs not available, text only output")
            return
        
        temp_audio_path = None
        try:
            self.is_speaking = True
            print(f"🔊 May says: {text}")
            logging.info(f"Speaking with ElevenLabs: {text}")
            
            # Generate audio and save to temporary file
            # Using eleven_turbo_v2_5 for free tier compatibility
            audio_generator = self.elevenlabs_client.text_to_speech.convert(
                voice_id=self.elevenlabs_voice_id,
                text=text,
                model_id="eleven_turbo_v2_5",  # Updated for free tier
                output_format="mp3_44100_128"
            )
            
            # Create temp file but don't auto-delete
            temp_audio_fd, temp_audio_path = tempfile.mkstemp(suffix='.mp3')
            os.close(temp_audio_fd)  # Close file descriptor
            
            # Write audio data to file
            with open(temp_audio_path, 'wb') as f:
                for chunk in audio_generator:
                    if chunk:
                        f.write(chunk)
            
            # Ensure file is written
            time.sleep(0.1)
            
            # Play audio using pygame
            pygame.mixer.music.load(temp_audio_path)
            pygame.mixer.music.play()
            
            # Wait for audio to finish
            while pygame.mixer.music.get_busy():
                pygame.time.Clock().tick(10)
            
            # Clean up
            pygame.mixer.music.unload()
            time.sleep(0.1)  # Small delay before deletion
            
            try:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    os.unlink(temp_audio_path)
            except Exception as cleanup_error:
                logging.warning(f"Could not delete temp file: {cleanup_error}")
            
            self.is_speaking = False
            if self.esp32:
                self.esp32.send_ready()
                
        except Exception as e:
            logging.error(f"ElevenLabs TTS error: {e}\n{traceback.format_exc()}")
            print(f"❌ Speech error: {e}")
            self.is_speaking = False
            # Clean up temp file on error
            try:
                if temp_audio_path and os.path.exists(temp_audio_path):
                    time.sleep(0.1)
                    os.unlink(temp_audio_path)
            except:
                pass

    def stop_speaking(self):
        """Stop current speech"""
        self.interrupted = True
        self.is_speaking = False
        try:
            pygame.mixer.music.stop()
        except:
            pass

    def listen_elevenlabs(self, timeout=5, phrase_time_limit=None):
        """Listen and transcribe using local speech recognition (Google)"""
        try:
            import speech_recognition as sr
            
            recognizer = sr.Recognizer()
            recognizer.energy_threshold = 2000
            recognizer.dynamic_energy_threshold = True
            
            print("🎤 Listening...")
            if self.esp32:
                self.esp32.send_listening()
            
            with sr.Microphone() as source:
                # Adjust for ambient noise
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                
                try:
                    audio = recognizer.listen(source, timeout=timeout, phrase_time_limit=phrase_time_limit)
                    
                    # Use Google Speech Recognition (free)
                    text = recognizer.recognize_google(audio)
                    text = text.strip()
                    
                    print(f"📝 You said: {text}")
                    if self.esp32:
                        self.esp32.send_input(text)
                    return text
                    
                except sr.WaitTimeoutError:
                    return None
                except sr.UnknownValueError:
                    return None
                except sr.RequestError as e:
                    logging.error(f"Speech recognition error: {e}")
                    print(f"❌ Recognition error: {e}")
                    return None
                
        except Exception as e:
            logging.error(f"STT error: {e}\n{traceback.format_exc()}")
            print(f"❌ STT error: {e}")
            return None

    def listen(self, timeout=5, phrase_time_limit=None, show_listening=True):
        """Listen using Google Speech Recognition (free alternative)"""
        return self.listen_elevenlabs(timeout=timeout, phrase_time_limit=phrase_time_limit)

    def check_wake_word(self, text):
        """Check for wake word in text"""
        if not text:
            return False, None
        text_lower = text.lower()
        for word in WAKE_WORDS:
            if word in text_lower:
                query = text_lower.replace(word, "").strip()
                return True, query if query else None
        return False, None

    def check_termination(self, text):
        """Check for termination phrases"""
        if not text:
            return False
        text_lower = text.lower()
        return any(term in text_lower for term in TERMINATION_WORDS)

    def set_reminder(self, reminder_text, when):
        """Set a reminder"""
        try:
            reminder_time = datetime.now(self.timezone) + timedelta(minutes=when)
            self.reminders.append({"text": reminder_text, "time": reminder_time.isoformat()})
            self.save_config()
            return f"Reminder set for {when} minutes from now."
        except Exception as e:
            logging.error(f"Reminder error: {e}")
            return "Failed to set reminder."

    async def check_reminders(self):
        """Check and announce due reminders"""
        try:
            now = datetime.now(self.timezone)
            due_reminders = []
            for reminder in self.reminders[:]:
                reminder_time = datetime.fromisoformat(reminder['time'])
                if now >= reminder_time:
                    due_reminders.append(reminder)
                    self.reminders.remove(reminder)
            
            if due_reminders:
                self.save_config()
                for reminder in due_reminders:
                    await self.speak(f"Reminder: {reminder['text']}")
        except Exception as e:
            logging.error(f"Check reminders error: {e}")

    def check_battery(self):
        """Check battery and return warning if needed"""
        try:
            now = datetime.now(self.timezone)
            if (now - self.last_battery_check).total_seconds() < 300:
                return None
            
            self.last_battery_check = now
            battery = psutil.sensors_battery()
            if battery:
                percent = battery.percent
                for threshold, alerted in self.battery_thresholds.items():
                    if percent <= threshold and not alerted:
                        self.battery_thresholds[threshold] = True
                        return f"Battery at {percent}%. Please charge soon."
                if percent > 20:
                    self.battery_thresholds = {20: False, 10: False, 5: False}
        except Exception as e:
            logging.error(f"Battery check error: {e}")
        return None

    def fallback_sentiment(self, text):
        """Fallback sentiment analysis"""
        try:
            blob = TextBlob(text)
            polarity = blob.sentiment.polarity
            if polarity > 0.3:
                return "positive"
            elif polarity < -0.3:
                return "negative"
            else:
                return "neutral"
        except:
            return "neutral"

    async def detect_emotions_fast(self, text):
        """Detect emotions using Hume AI API"""
        if not self.hume_api_key or self.hume_api_key.startswith("YOUR"):
            # Fallback to TextBlob sentiment analysis
            sentiment = self.fallback_sentiment(text)
            emotion_map = {"positive": "Joy", "negative": "Sadness", "neutral": "Calm"}
            emotion = emotion_map.get(sentiment, "Calm")
            print(f"😊 Emotion detected (TextBlob): {emotion}")
            return {"primary": emotion, "score": 0.5}
        
        try:
            print("🧠 Analyzing emotions with Hume AI...")
            # Use Hume AI API for emotion detection
            url = "https://api.hume.ai/v0/batch/jobs"
            headers = {
                "X-Hume-Api-Key": self.hume_api_key,
                "Content-Type": "application/json"
            }
            
            payload = {
                "models": {
                    "language": {
                        "granularity": "word"
                    }
                },
                "text": [text]
            }
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                response = await client.post(url, json=payload, headers=headers)
                
                if response.status_code == 200 or response.status_code == 201:
                    data = response.json()
                    job_id = data.get("job_id")
                    
                    if job_id:
                        # Wait briefly for processing
                        await asyncio.sleep(1)
                        
                        # Get predictions
                        pred_url = f"https://api.hume.ai/v0/batch/jobs/{job_id}/predictions"
                        pred_response = await client.get(pred_url, headers=headers)
                        
                        if pred_response.status_code == 200:
                            pred_data = pred_response.json()
                            
                            # Parse emotions from response
                            try:
                                predictions = pred_data[0]["results"]["predictions"]
                                if predictions and len(predictions) > 0:
                                    emotions = predictions[0]["models"]["language"]["grouped_predictions"][0]["predictions"][0]["emotions"]
                                    
                                    # Find top 3 emotions
                                    sorted_emotions = sorted(emotions, key=lambda x: x["score"], reverse=True)
                                    top_emotions = sorted_emotions[:3]
                                    
                                    top_emotion = top_emotions[0]
                                    emotion_name = top_emotion["name"].title()
                                    emotion_score = top_emotion["score"]
                                    
                                    # Display emotion analysis
                                    print(f"\n{'='*50}")
                                    print(f"🎭 EMOTION ANALYSIS (Hume AI)")
                                    print(f"{'='*50}")
                                    print(f"Primary: {emotion_name} ({emotion_score:.1%})")
                                    if len(top_emotions) > 1:
                                        print(f"Secondary: {top_emotions[1]['name'].title()} ({top_emotions[1]['score']:.1%})")
                                    if len(top_emotions) > 2:
                                        print(f"Tertiary: {top_emotions[2]['name'].title()} ({top_emotions[2]['score']:.1%})")
                                    print(f"{'='*50}\n")
                                    
                                    logging.info(f"Hume emotion detected: {emotion_name} (score: {emotion_score:.2f})")
                                    
                                    # Send to ESP32
                                    if self.esp32:
                                        emotion_display = f"Emotion: {emotion_name}"
                                        self.esp32.send("EMOTION", emotion_display)
                                    
                                    return {"primary": emotion_name, "score": emotion_score, "top3": top_emotions}
                            except (KeyError, IndexError) as e:
                                logging.warning(f"Could not parse Hume response: {e}")
                
                logging.warning(f"Hume API returned status {response.status_code}")
                
        except Exception as e:
            logging.error(f"Hume API error: {e}\n{traceback.format_exc()}")
            print(f"⚠️ Hume error, using fallback sentiment analysis")
        
        # Fallback to sentiment analysis
        sentiment = self.fallback_sentiment(text)
        emotion_map = {"positive": "Joy", "negative": "Sadness", "neutral": "Calm"}
        emotion = emotion_map.get(sentiment, "Calm")
        print(f"😊 Emotion detected (fallback): {emotion}")
        return {"primary": emotion, "score": 0.5}

    async def diagnostics(self):
        """Run system diagnostics"""
        print("\n=== System Diagnostics ===")
        print(f"Anthropic API: {self.anthropic_api_status or 'Online' if self.anthropic_client else 'Offline'}")
        print(f"Hume API: {'Online' if self.hume_api_key and not self.hume_api_key.startswith('YOUR') else 'Offline (No API key)'}")
        print(f"ElevenLabs TTS: {self.tts_status}")
        print(f"Speech Recognition: Google (Free)")
        print(f"ESP32 Display: {'Connected' if self.esp32 and self.esp32.connected else 'Disconnected'}")
        print("========================\n")

    def get_emotion_aware_response(self, query, emotions):
        """Generate emotion-aware response"""
        emotion = emotions.get("primary", "Calm") if emotions else "Calm"
        
        print(f"💭 Crafting emotion-aware response for: {emotion}")
        
        responses = {
            "Joy": ["I'm glad you're happy!", "That's wonderful to hear!", "Your positivity is contagious!"],
            "Excitement": ["I love your enthusiasm!", "That sounds amazing!", "How exciting!"],
            "Sadness": ["I'm here for you.", "Take your time, I'm listening.", "It's okay to feel this way."],
            "Distress": ["I understand this is difficult.", "You're not alone in this.", "Let's work through this together."],
            "Anger": ["I hear your frustration.", "That sounds really challenging.", "Your feelings are valid."],
            "Anxiety": ["Take a deep breath. I'm here.", "Let's take this one step at a time.", "It's okay to feel worried."],
            "Calm": ["How can I help you?", "I'm listening.", "Go ahead, I'm here."],
            "Surprise": ["Wow, that's unexpected!", "Tell me more!", "Interesting!"],
            "Fear": ["I'm here with you.", "You're safe to share.", "Let's talk about it."]
        }
        
        response = random.choice(responses.get(emotion, responses["Calm"]))
        print(f"✨ Selected response based on {emotion} emotion")
        return response

    def get_casual_response(self, query):
        """Get casual conversational response"""
        query_lower = query.lower()
        
        casual_responses = {
            "how are you": ["I'm doing great, thanks for asking!", "All good here!", "I'm well, how about you?"],
            "what's up": ["Not much, just here to help!", "Ready to assist!", "All set to chat!"],
            "hello": ["Hello!", "Hi there!", "Hey!"],
            "thanks": ["You're welcome!", "Happy to help!", "Anytime!"],
            "help": ["I can help with reminders, answer questions, and chat with you!", "Just ask me anything!"]
        }
        
        for key, responses in casual_responses.items():
            if key in query_lower:
                return random.choice(responses)
        
        return None

    async def conversation_mode(self):
        """Enter active conversation mode"""
        self.conversation_active = True
        print("💬 Entering conversation mode - speak naturally, no need to say 'May' again")
        await self.speak("I'm listening. What would you like to know?")
        
        while self.conversation_active:
            text = self.listen(timeout=10, phrase_time_limit=10)
            
            if text is None:
                print("⏱️ No input detected")
                await self.speak("Still here. What else would you like to know?")
                continue
            
            print(f"\n{'='*50}")
            print(f"💬 YOU: {text}")
            print(f"{'='*50}")
            
            if self.esp32:
                self.esp32.send_input(text)
            
            # Check for termination
            if self.check_termination(text):
                await self.speak("Goodbye! Say my name if you need me again.")
                self.conversation_active = False
                if self.esp32:
                    self.esp32.send_ready()
                print("👋 Exiting conversation mode\n")
                break
            
            # Detect emotions
            print("🔍 Analyzing your emotional state...")
            emotions = await self.detect_emotions_fast(text)
            
            # Check for casual response first
            casual_response = self.get_casual_response(text)
            if casual_response:
                response = casual_response
                print(f"💭 Using casual response")
            else:
                print(f"🤖 Generating AI response with emotional context...")
                response = await self.process_with_claude(text, emotions)
            
            print(f"\n{'='*50}")
            print(f"🤖 MAY: {response}")
            print(f"{'='*50}\n")
            
            if self.esp32:
                self.esp32.send_response(response)
            
            await self.speak(response)
            
            # Add to context
            self.context.append(f"User: {text} | May: {response}")
            if len(self.context) > 5:
                self.context.pop(0)

    async def process_with_claude(self, query, emotions=None):
        """Process query with Claude API"""
        query_lower = query.lower()
        
        # Handle time queries
        if any(keyword in query_lower for keyword in ['time', 'clock', 'hour', 'what time']):
            try:
                time_str = datetime.now(self.timezone).strftime('%I:%M %p')
                return f"It's {time_str}."
            except:
                return "Sorry, I can't access the time right now."
        
        # Handle date queries
        if any(keyword in query_lower for keyword in ['date', 'day is it', 'today']):
            try:
                date_str = datetime.now(self.timezone).strftime('%A, %B %d')
                return f"Today is {date_str}."
            except:
                return "Sorry, I can't access the date right now."
        
        # Use Claude API if available
        if not self.anthropic_client:
            return self.get_emotion_aware_response(query, emotions)
        
        try:
            # Build emotion context string
            emotion_str = ""
            if emotions and emotions.get('primary'):
                emotion_name = emotions['primary']
                emotion_score = emotions.get('score', 0)
                emotion_str = f"\n\n[EMOTIONAL CONTEXT - User is feeling {emotion_name} (confidence: {emotion_score:.0%}). Respond with empathy and acknowledge their emotional state when appropriate.]"
                
                # Add additional emotions if available
                if 'top3' in emotions and len(emotions['top3']) > 1:
                    other_emotions = [f"{e['name'].title()} ({e['score']:.0%})" for e in emotions['top3'][1:]]
                    emotion_str += f"\nSecondary emotions: {', '.join(other_emotions)}"
            
            context_str = f"\nRecent conversation: {'; '.join(self.context[-3:])}" if self.context else ''
            
            prompt = (
                f"You are May, a friendly and empathetic voice assistant. "
                f"Respond naturally and conversationally (max 100 tokens).\n\n"
                f"User's question: {query}"
                f"{emotion_str}"
                f"{context_str}\n\n"
                f"Keep your tone warm, engaging, and emotionally intelligent."
            )
            
            models_to_try = [
                "claude-sonnet-4-5-20250929",
                "claude-3-5-sonnet-20241022"
            ]
            
            for model in models_to_try:
                try:
                    message = await self.anthropic_client.messages.create(
                        model=model,
                        max_tokens=100,
                        temperature=0.7,
                        messages=[{"role": "user", "content": prompt}]
                    )
                    response = message.content[0].text.strip()
                    logging.info(f"Claude response ({model}): {response}")
                    return response
                except AnthropicError as e:
                    logging.warning(f"Claude API error with model {model}: {e}")
                    continue
            
            return self.get_emotion_aware_response(query, emotions)
        except Exception as e:
            logging.error(f"Claude processing error: {e}\n{traceback.format_exc()}")
            return self.get_emotion_aware_response(query, emotions)

    async def passive_listening(self):
        """Main passive listening loop"""
        print("🔊 May Assistant is running in passive mode. Say 'May' to wake me up.")
        await self.speak("May is ready. Say my name to start talking.")
        
        while True:
            try:
                await self.check_reminders()
                battery_warning = self.check_battery()
                if battery_warning:
                    await self.speak(battery_warning)

                text = self.listen(timeout=None, phrase_time_limit=8, show_listening=False)
                if text is None:
                    continue

                wake_detected, query = self.check_wake_word(text)
                if wake_detected:
                    if self.esp32:
                        self.esp32.send_ready()
                    print("✅ Wake word detected!")
                    
                    # If there's a query immediately after wake word, process it
                    if query and len(query.strip()) > 0:
                        emotions = await self.detect_emotions_fast(query)
                        response = await self.process_with_claude(query, emotions)
                        if self.esp32:
                            self.esp32.send_response(response)
                        await self.speak(response)
                        self.context.append(f"User: {query} | May: {response}")
                        if len(self.context) > 5:
                            self.context.pop(0)
                    
                    # Enter conversation mode
                    await self.conversation_mode()
                    
            except KeyboardInterrupt:
                print("\n🛑 Shutting down May Assistant...")
                await self.speak("Goodbye!")
                if self.esp32:
                    self.esp32.close()
                break
            except Exception as e:
                logging.error(f"Error in passive listening loop: {e}\n{traceback.format_exc()}")
                await asyncio.sleep(1)

async def main():
    assistant = MayAssistant()
    await assistant.diagnostics()
    
    try:
        await assistant.passive_listening()
    except KeyboardInterrupt:
        print("\n🛑 Assistant terminated by user.")
        await assistant.speak("Shutting down. Goodbye!")
    except Exception as e:
        logging.error(f"Fatal error in main: {e}\n{traceback.format_exc()}")
        print(f"❌ Fatal error: {e}")
    finally:
        if assistant.esp32:
            assistant.esp32.close()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Program terminated.")
    except Exception as e:
        logging.critical(f"Unhandled exception: {e}\n{traceback.format_exc()}")
        print(f"💥 Critical error: {e}")