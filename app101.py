#!/usr/bin/env python3

import os
import sys
import json
import re
import time
import random
import hashlib
import pickle
import logging
import traceback
import tempfile
import warnings
from io import BytesIO
from pathlib import Path
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional, Tuple, Any, Union
from collections import defaultdict, deque
from functools import wraps, lru_cache
from contextlib import contextmanager
import threading
import queue
import concurrent.futures

from flask import Flask, request, Response, send_file, jsonify, render_template_string, has_request_context
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Play
import google.generativeai as genai
from dotenv import load_dotenv

warnings.filterwarnings("ignore", category=DeprecationWarning)

class ConfigManager:
    def __init__(self):
        self.load_environment()
        self.validate_config()
        
    def load_environment(self):
        possible_paths = ['.env', Path(__file__).parent / '.env', Path(__file__).parent.parent / '.env']
        for env_path in possible_paths:
            if Path(env_path).exists():
                load_dotenv(env_path)
                print(f"✅ Loaded .env from: {env_path}")
                return
        print("⚠️ No .env file found, using environment variables only")
    
    def validate_config(self):
        required = {
            'TWILIO_ACCOUNT_SID': 'Twilio Account SID',
            'TWILIO_AUTH_TOKEN': 'Twilio Auth Token',
            'TWILIO_PHONE_NUMBER': 'Twilio Phone Number'
        }
        missing = [f"{key} ({desc})" for key, desc in required.items() if not os.getenv(key)]
        if missing:
            raise ValueError(f"Missing required configuration: {', '.join(missing)}")
        print("✅ Configuration validated successfully")
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        return os.getenv(key, default)
    
    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        value = os.getenv(key, str(default)).lower()
        return value in ('true', '1', 'yes', 'on')
    
    @staticmethod
    def get_int(key: str, default: int = 0) -> int:
        try:
            return int(os.getenv(key, str(default)))
        except ValueError:
            return default

@dataclass
class Service:
    name: str
    price: float
    duration: int
    description: str
    keywords: List[str] = field(default_factory=list)
    priority: int = 0
    
    def matches_input(self, text: str) -> bool:
        text_lower = text.lower()
        if self.name.lower() in text_lower:
            return True
        return any(keyword.lower() in text_lower for keyword in self.keywords)

@dataclass
class BusinessConfig:
    name: str = "Bright Smile Dental"
    type: str = "dental"
    services: List[Service] = field(default_factory=list)
    hours: Dict[str, str] = field(default_factory=dict)
    timezone: str = "America/New_York"
    appointment_duration: int = 60
    buffer_time: int = 15
    max_advance_days: int = 30
    personality: str = "professional and friendly"
    
    @classmethod
    def from_env(cls) -> 'BusinessConfig':
        config = cls()
        config.name = ConfigManager.get('BUSINESS_NAME', config.name)
        config.type = ConfigManager.get('BUSINESS_TYPE', config.type)
        config.timezone = ConfigManager.get('TIMEZONE', config.timezone)
        config.appointment_duration = ConfigManager.get_int('APPOINTMENT_DURATION', 60)
        config.buffer_time = ConfigManager.get_int('BUFFER_TIME', 15)
        config.max_advance_days = ConfigManager.get_int('MAX_ADVANCE_DAYS', 30)
        config.personality = ConfigManager.get('AI_PERSONALITY', config.personality)
        config.services = cls._load_services()
        config.hours = cls._load_hours()
        return config
    
    @staticmethod
    def _load_services() -> List[Service]:
        services_json = ConfigManager.get('BUSINESS_SERVICES')
        if services_json:
            try:
                services_data = json.loads(services_json)
                return [Service(**service) if isinstance(service, dict) else 
                       Service(name=service, price=100.0, duration=60, description=service)
                       for service in services_data]
            except Exception as e:
                print(f"⚠️ Error loading services: {e}")
        
        return [
            Service(name="Quick Assessment" , price=100.00,duration=30,description="Quick assessment appointment",keywords=["assessment","quick","evaluation","check","check-up"],priority=1),

            Service(name="Consultation", price=150.00, duration=60,
                   description="Professional consultation",
                   keywords=["consultation", "consult", "checkup", "exam"], priority=1),
            Service(name="Cleaning", price=200.00, duration=90,
                   description="Professional teeth cleaning",
                   keywords=["cleaning", "clean", "hygiene"], priority=2),
            Service(name="Emergency", price=300.00, duration=45,
                   description="Emergency dental care",
                   keywords=["emergency", "urgent", "pain", "hurt", "ache"], priority=0)
        ]
    
    @staticmethod
    def _load_hours() -> Dict[str, str]:
        hours_json = ConfigManager.get('BUSINESS_HOURS')
        if hours_json:
            try:
                return json.loads(hours_json)
            except Exception as e:
                print(f"⚠️ Error loading hours: {e}")
        
        return {
            "monday": "8:00 AM - 5:00 PM", "tuesday": "8:00 AM - 5:00 PM",
            "wednesday": "8:00 AM - 5:00 PM", "thursday": "8:00 AM - 5:00 PM",
            "friday": "8:00 AM - 5:00 PM", "saturday": "10:00 AM - 2:00 PM",
            "sunday": "Closed"
        }

@dataclass
class Appointment:
    customer_name: str
    phone_number: str
    service: str
    date: str
    time: str
    notes: str = ""
    call_sid: str = ""
    google_event_id: str = ""
    created_at: str = ""
    status: str = "confirmed"
    
    def to_dict(self) -> dict:
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: dict) -> 'Appointment':
        return cls(**data)

@dataclass
class CallSession:
    call_sid: str
    state: str = "greeting"
    customer_data: Dict = field(default_factory=dict)
    attempts: int = 0
    conversation_history: List[Dict] = field(default_factory=list)
    emotion_state: str = "neutral"
    urgency_level: float = 0.5
    last_response: str = ""
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_message(self, role: str, content: str):
        self.conversation_history.append({
            "role": role, "content": content,
            "timestamp": datetime.now().isoformat()
        })

class EmotionalIntelligence:
    def __init__(self):
        self.emotion_patterns = {
            'pain': {
                'keywords': ['hurt', 'pain', 'ache', 'sore', 'throbbing', 'burning', 'sharp'],
                'intensity': 0.9,
                'responses': ["Oh no, that sounds really uncomfortable!",
                            "I'm so sorry you're in pain.",
                            "That must be really difficult."]
            },
            'frustration': {
                'keywords': ['frustrated', 'annoying', 'irritated', 'upset', 'angry', "don't understand"],
                'intensity': 0.7,
                'responses': ["I completely understand your frustration.",
                            "I hear you, let me help sort this out.",
                            "I know this can be confusing, let me clarify."]
            },
            'anxiety': {
                'keywords': ['worried', 'anxious', 'nervous', 'scared', 'concerned', 'afraid'],
                'intensity': 0.8,
                'responses': ["I understand you're concerned.",
                            "No worries at all, we'll take care of you.",
                            "Let me help put your mind at ease."]
            },
            'happiness': {
                'keywords': ['great', 'wonderful', 'perfect', 'excellent', 'amazing', 'fantastic'],
                'intensity': 0.3,
                'responses': ["That's wonderful to hear!",
                            "I love your enthusiasm!",
                            "Your positive energy is contagious!"]
            }
        }
    
    def analyze(self, text: str) -> Dict[str, Any]:
        text_lower = text.lower()
        emotions_detected = {}
        
        for emotion, data in self.emotion_patterns.items():
            score = sum(1 for keyword in data['keywords'] if keyword in text_lower)
            if score > 0:
                emotions_detected[emotion] = score * data['intensity']
        
        if not emotions_detected:
            return {'emotion': 'neutral', 'intensity': 0.3, 'empathy_needed': 0.3}
        
        primary_emotion = max(emotions_detected, key=emotions_detected.get)
        intensity = emotions_detected[primary_emotion]
        
        return {
            'emotion': primary_emotion,
            'intensity': min(intensity, 1.0),
            'empathy_needed': intensity,
            'all_emotions': emotions_detected
        }
    
    def get_response(self, emotion: str) -> str:
        if emotion in self.emotion_patterns:
            return random.choice(self.emotion_patterns[emotion]['responses'])
        return ""

class ConversationFlow:
    def __init__(self):
        self.listening_cues = ["Mm-hmm", "I see", "Right", "Got it", 
                              "Of course", "Okay", "Sure", "I understand"]
        self.transitions = {
            'clarification': ["Just to make sure I understand...",
                            "So what you're saying is...", "Let me confirm..."],
            'topic_change': ["Now, regarding...", "Moving on to...", "About the..."],
            'back_on_track': ["So, getting back to your appointment...",
                            "Let's focus on getting you scheduled...",
                            "About your booking..."]
        }
        self.fillers = {
            'thinking': ['um', 'uh', 'hmm', 'let me see', 'well'],
            'agreement': ['yeah', 'mm-hmm', 'right', 'exactly', 'absolutely'],
            'transition': ['so', 'now', 'alright', 'okay', 'well then']
        }
    
    def add_natural_elements(self, text: str, context: Dict) -> str:
        # Remove any system-like phrases that might have slipped through
        system_phrases = [
            "let me check", "checking the system", "wait for response",
            "checking bookings", "system shows", "I'll need to verify",
            "let me verify", "checking availability", "one moment",
            "please wait", "processing", "searching"
        ]
        
        text_lower = text.lower()
        for phrase in system_phrases:
            if phrase in text_lower:
                # Replace with natural alternatives
                replacements = {
                    "let me check": "I see",
                    "checking the system": "Looking at the schedule",
                    "wait for response": "",
                    "checking bookings": "I have",
                    "system shows": "It looks like",
                    "I'll need to verify": "I can see",
                    "let me verify": "Perfect",
                    "checking availability": "I have",
                    "one moment": "Alright",
                    "please wait": "So",
                    "processing": "",
                    "searching": "Looking at"
                }
                for old, new in replacements.items():
                    text = text.replace(old, new)
                    text = text.replace(old.capitalize(), new.capitalize())
        
        # Add natural filler only if appropriate
        if random.random() < 0.15 and context.get('is_thinking'):
            filler = random.choice(self.fillers['thinking'])
            text = f"{filler.capitalize()}, {text}"
        
        # Add smooth transitions
        if context.get('show_understanding') and random.random() < 0.3:
            cue = random.choice(["Perfect", "Great", "Wonderful", "Excellent", "Alright"])
            text = f"{cue}! {text}"
        
        if context.get('topic_change'):
            transition = random.choice(["Now", "So", "Alright"])
            text = f"{transition}, {text}"
        
        # Clean up any double punctuation
        text = re.sub(r'([.!?])\s*\1+', r'\1', text)
        text = re.sub(r'\s+', ' ', text).strip()
        
        return text

class PersonalitySystem:
    def __init__(self, config: BusinessConfig):
        self.config = config
        self.traits = {'warmth': 0.8, 'professionalism': 0.7, 'humor': 0.3,
                      'patience': 0.9, 'efficiency': 0.7}
        self.backstory = {'name': 'Sarah', 'years_experience': 5,
                         'favorite_part': 'helping people feel better',
                         'personality': config.personality}
    
    def apply_personality(self, text: str, context: Dict) -> str:
        if context.get('emotion') == 'pain' and self.traits['warmth'] > 0.7:
            if random.random() < 0.6:
                text = f"Oh dear, {text}"
        
        if context.get('urgency', 0) > 0.7 and self.traits['efficiency'] > 0.6:
            if random.random() < 0.5:
                text = f"Let me handle this quickly. {text}"
        
        return text

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, recovery_timeout: int = 60):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.last_failure_time = None
        self.is_open = False
        self._lock = threading.Lock()
    
    def call(self, func, *args, **kwargs):
        with self._lock:
            if self.is_open:
                if time.time() - self.last_failure_time > self.recovery_timeout:
                    self.is_open = False
                    self.failure_count = 0
                else:
                    raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            with self._lock:
                self.failure_count = 0
            return result
        except Exception as e:
            with self._lock:
                self.failure_count += 1
                self.last_failure_time = time.time()
                if self.failure_count >= self.failure_threshold:
                    self.is_open = True
            raise e

class GoogleCalendarManager:
    def __init__(self, calendar_id: str = 'primary'):
        self.calendar_id = calendar_id
        self.service = None
        self.timezone = ConfigManager.get('TIMEZONE', 'America/New_York')
        self.logger = logging.getLogger(__name__)
        self.appointment_duration = ConfigManager.get_int('APPOINTMENT_DURATION', 60)
        self._lock = threading.Lock()
        self._import_dependencies()
        self._authenticate()
    
    def _import_dependencies(self):
        try:
            global pytz, Credentials, InstalledAppFlow, Request, build, HttpError
            import pytz
            from google.oauth2.credentials import Credentials
            from google_auth_oauthlib.flow import InstalledAppFlow
            from google.auth.transport.requests import Request
            from googleapiclient.discovery import build
            from googleapiclient.errors import HttpError
            self.dependencies_available = True
            print("✅ Google Calendar dependencies loaded")
        except ImportError as e:
            self.dependencies_available = False
            print(f"⚠️ Google Calendar dependencies not available: {e}")
    
    def _authenticate(self):
        if not self.dependencies_available:
            return
        
        try:
            SCOPES = ['https://www.googleapis.com/auth/calendar.events']
            creds = None
            
            if Path('token.pickle').exists():
                with open('token.pickle', 'rb') as token:
                    creds = pickle.load(token)
            
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    if Path('credentials.json').exists():
                        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
                        creds = flow.run_local_server(port=0)
                    else:
                        print("⚠️ credentials.json not found")
                        return
                
                with open('token.pickle', 'wb') as token:
                    pickle.dump(creds, token)
            
            self.service = build('calendar', 'v3', credentials=creds)
            print(f"✅ Google Calendar authenticated (Timezone: {self.timezone})")
            print(f"⚠️ IMPORTANT: Only ONE appointment allowed per time slot!")
            
        except Exception as e:
            self.logger.error(f"Calendar authentication failed: {e}")
            print(f"⚠️ Google Calendar authentication failed: {e}")
    
    def check_availability(self, date_str: str, time_str: str, exclude_event_id: str = None) -> Tuple[bool, Optional[str]]:
        if not self.service:
            return (True, None)
        
        try:
            with self._lock:
                appointment_date = self._parse_appointment_datetime(date_str, time_str)
                appointment_end = appointment_date + timedelta(minutes=self.appointment_duration)
                
                local_tz = pytz.timezone(self.timezone)
                if appointment_date.tzinfo is None:
                    appointment_date = local_tz.localize(appointment_date)
                    appointment_end = local_tz.localize(appointment_end.replace(tzinfo=None))
                
                appointment_date_utc = appointment_date.astimezone(pytz.UTC)
                appointment_end_utc = appointment_end.astimezone(pytz.UTC)
                
                buffer_minutes = 15
                time_min = (appointment_date_utc - timedelta(minutes=buffer_minutes)).isoformat()
                time_max = (appointment_end_utc + timedelta(minutes=buffer_minutes)).isoformat()
                
                print(f"🔍 Checking availability for {date_str} at {time_str}")
                
                events_result = self.service.events().list(
                    calendarId=self.calendar_id,
                    timeMin=time_min,
                    timeMax=time_max,
                    singleEvents=True,
                    orderBy='startTime',
                    maxResults=50
                ).execute()
                
                events = events_result.get('items', [])
                
                for event in events:
                    if exclude_event_id and event.get('id') == exclude_event_id:
                        continue
                    
                    event_start_str = event.get('start', {}).get('dateTime')
                    event_end_str = event.get('end', {}).get('dateTime')
                    event_summary = event.get('summary', 'Appointment')
                    
                    if event_start_str and event_end_str:
                        event_start = datetime.fromisoformat(event_start_str.replace('Z', '+00:00'))
                        event_end = datetime.fromisoformat(event_end_str.replace('Z', '+00:00'))
                        
                        event_start_local = event_start.astimezone(local_tz)
                        event_end_local = event_end.astimezone(local_tz)
                        
                        has_overlap = (
                            (appointment_date >= event_start_local and appointment_date < event_end_local) or
                            (appointment_end > event_start_local and appointment_end <= event_end_local) or
                            (appointment_date <= event_start_local and appointment_end >= event_end_local) or
                            (event_start_local <= appointment_date and event_end_local >= appointment_end)
                        )
                        
                        if has_overlap:
                            conflict_time = event_start_local.strftime('%I:%M %p')
                            print(f"   ❌ CONFLICT DETECTED: {event_summary} at {conflict_time}")
                            conflict_msg = f"already booked from {event_start_local.strftime('%I:%M %p')} to {event_end_local.strftime('%I:%M %p')}"
                            return (False, conflict_msg)
                
                print(f"   ✅ Time slot is AVAILABLE - no conflicts found!")
                return (True, None)
                
        except Exception as e:
            self.logger.error(f"Availability check error: {e}")
            print(f"❌ Error checking availability: {e}")
            return (False, "unable to verify availability due to system error")
    
    def _parse_appointment_datetime(self, date_str: str, time_str: str) -> datetime:
        appointment_date = datetime.strptime(f"{date_str} {time_str}", "%A, %B %d %I:%M %p")
        current_year = datetime.now().year
        appointment_date = appointment_date.replace(year=current_year)
        
        today = datetime.now().date()
        if appointment_date.date() < today:
            appointment_date = appointment_date.replace(year=current_year + 1)
        
        return appointment_date
    
    def find_next_available_slots(self, date_str: str, preferred_time: str = None, count: int = 3) -> List[str]:
        if not self.service:
            return []
        
        available_slots = []
        time_slots = [
            "8:00 AM", "8:30 AM", "9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM",
            "11:00 AM", "11:30 AM", "12:00 PM", "12:30 PM", "1:00 PM", "1:30 PM",
            "2:00 PM", "2:30 PM", "3:00 PM", "3:30 PM", "4:00 PM", "4:30 PM", "5:00 PM"
        ]
        
        if preferred_time and preferred_time in time_slots:
            idx = time_slots.index(preferred_time)
            reordered = []
            for i in range(len(time_slots)):
                if idx + i < len(time_slots):
                    reordered.append(time_slots[idx + i])
                if idx - i >= 0 and i > 0:
                    reordered.append(time_slots[idx - i])
            time_slots = reordered
        
        for time_slot in time_slots:
            if len(available_slots) >= count:
                break
            
            is_available, _ = self.check_availability(date_str, time_slot)
            if is_available:
                available_slots.append(time_slot)
        
        return available_slots
    
    def create_appointment(self, appointment: Appointment) -> Tuple[bool, Optional[str], Optional[str]]:
        if not self.service:
            return (False, None, "Calendar service not available")
        
        try:
            with self._lock:
                is_available, conflict_details = self.check_availability(appointment.date, appointment.time)
                
                if not is_available:
                    error_msg = f"Cannot book {appointment.time} on {appointment.date} - slot is {conflict_details}"
                    print(f"❌ BOOKING BLOCKED: {error_msg}")
                    return (False, None, error_msg)
                
                appointment_datetime = self._parse_appointment_datetime(appointment.date, appointment.time)
                
                event = {
                    'summary': f'BOOKED: {appointment.service} - {appointment.customer_name}',
                    'description': (f'⚠️ TIME SLOT OCCUPIED - NO DOUBLE BOOKING\n\n'
                                  f'Customer: {appointment.customer_name}\n'
                                  f'Phone: {appointment.phone_number}\n'
                                  f'Service: {appointment.service}\n'
                                  f'Notes: {appointment.notes}\n\n'
                                  f'📞 Contact: {appointment.phone_number}'),
                    'start': {'dateTime': appointment_datetime.isoformat(), 'timeZone': self.timezone},
                    'end': {'dateTime': (appointment_datetime + timedelta(minutes=self.appointment_duration)).isoformat(),
                           'timeZone': self.timezone},
                    'reminders': {'useDefault': False,
                                'overrides': [{'method': 'popup', 'minutes': 60},
                                            {'method': 'email', 'minutes': 24 * 60}]},
                    'colorId': '11'
                }
                
                result = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
                event_id = result.get('id')
                
                time.sleep(0.5)
                is_still_available, _ = self.check_availability(appointment.date, appointment.time, exclude_event_id=event_id)
                
                if is_still_available:
                    print(f"⚠️ Warning: Slot still shows as available after booking!")
                
                print(f"✅ Calendar event created successfully: {result.get('htmlLink')}")
                print(f"✅ Time slot {appointment.time} on {appointment.date} is now BLOCKED")
                return (True, event_id, None)
                
        except Exception as e:
            error_msg = f"Failed to create calendar event: {str(e)}"
            self.logger.error(error_msg)
            return (False, None, error_msg)

class ElevenLabsManager:
    def __init__(self):
        self.client = None
        self.enabled = False
        self.voice_config = {}
        self.audio_cache = {}
        self.circuit_breaker = CircuitBreaker()
        self._initialize()
    
    def _initialize(self):
        try:
            # Import Eleven Labs library
            from elevenlabs import generate, set_api_key, Voice, VoiceSettings
            self.elevenlabs_module = sys.modules['elevenlabs']
            
            # Check for Eleven Labs API key
            api_key = ConfigManager.get('ELEVENLABS_API_KEY')
            
            if not api_key:
                print("⚠️ Eleven Labs API key not found in environment")
                return
            
            # Set the API key
            set_api_key(api_key)
            
            # Configure voice settings
            self.voice_config = {
                'voice_id': ConfigManager.get('ELEVENLABS_VOICE_ID', 'EXAVITQu4vr4xnSDxMaL'),  # Default to Sarah voice
                'model_id': ConfigManager.get('ELEVENLABS_MODEL', 'eleven_monolingual_v1'),
                'stability': float(ConfigManager.get('ELEVENLABS_STABILITY', '0.5')),
                'similarity_boost': float(ConfigManager.get('ELEVENLABS_SIMILARITY', '0.75')),
                'style': float(ConfigManager.get('ELEVENLABS_STYLE', '0.0')),
                'use_speaker_boost': ConfigManager.get_bool('ELEVENLABS_SPEAKER_BOOST', True)
            }
            
            # Test the connection with a simple generation
            test_audio = generate(
                text="Ready",
                voice=self.voice_config['voice_id'],
                model=self.voice_config['model_id']
            )
            
            if test_audio:
                self.enabled = True
                print(f"✅ Eleven Labs initialized with voice {self.voice_config['voice_id']}")
                print(f"   Model: {self.voice_config['model_id']}")
            
        except ImportError:
            print("⚠️ elevenlabs library not installed. Run: pip install elevenlabs")
        except Exception as e:
            print(f"⚠️ Eleven Labs initialization failed: {e}")
    
    def generate_audio(self, text: str, voice_id: str = None, priority: bool = False) -> Optional[str]:
        if not self.enabled:
            return None
        
        def _generate():
            from elevenlabs import generate, Voice, VoiceSettings
            
            processed_text = self._process_text(text)
            
            # Create cache key
            cache_key = hashlib.md5(f"{voice_id or self.voice_config['voice_id']}:{processed_text}".encode()).hexdigest()
            if cache_key in self.audio_cache:
                print(f"📦 Using cached audio for: '{processed_text[:50]}...'")
                return self.audio_cache[cache_key]
            
            print(f"🎤 Generating Eleven Labs audio for: '{processed_text[:60]}...'")
            
            try:
                # Generate speech with Eleven Labs
                audio_data = generate(
                    text=processed_text,
                    voice=Voice(
                        voice_id=voice_id or self.voice_config['voice_id'],
                        settings=VoiceSettings(
                            stability=self.voice_config['stability'],
                            similarity_boost=self.voice_config['similarity_boost'],
                            style=self.voice_config.get('style', 0.0),
                            use_speaker_boost=self.voice_config.get('use_speaker_boost', True)
                        )
                    ),
                    model=self.voice_config['model_id']
                )
                
                # Save audio file
                timestamp = datetime.now().strftime('%Y%m%d%H%M%S%f')
                filename = f"audio_{timestamp}.mp3"
                filepath = Path('static/audio') / filename
                filepath.parent.mkdir(parents=True, exist_ok=True)
                
                # Write the audio data to file
                with open(filepath, 'wb') as f:
                    f.write(audio_data)
                
                if not filepath.exists() or filepath.stat().st_size == 0:
                    print(f"❌ Audio file creation failed: {filepath}")
                    return None
                
                base_url = self._get_base_url()
                audio_url = f"{base_url}/static/audio/{filename}"
                
                # Cache the result
                self.audio_cache[cache_key] = audio_url
                
                print(f"✅ Audio generated successfully: {audio_url}")
                return audio_url
                
            except Exception as e:
                print(f"❌ Eleven Labs error: {e}")
                return None
        
        try:
            if priority:
                from concurrent.futures import ThreadPoolExecutor
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(lambda: self.circuit_breaker.call(_generate))
                    return future.result(timeout=4.0)
            else:
                return self.circuit_breaker.call(_generate)
        except Exception as e:
            print(f"⚠️ Audio generation failed: {e}")
            return None
    
    def _process_text(self, text: str) -> str:
        if not text or text.strip() == "":
            return text
        
        result = text
        
        if random.random() < 0.2 and len(result) >= 2:
            fillers = ["Well, ", "So, ", "Alright, ", "Okay, so ", "Um, "]
            result = random.choice(fillers) + result[0].lower() + result[1:]
        
        time_replacements = [
            (r'\b8:00\s*AM\b', 'eight in the morning'),
            (r'\b9:00\s*AM\b', 'nine AM'),
            (r'\b10:00\s*AM\b', 'ten in the morning'),
            (r'\b11:00\s*AM\b', 'eleven AM'),
            (r'\b12:00\s*PM\b', 'noon'),
            (r'\b1:00\s*PM\b', 'one in the afternoon'),
            (r'\b2:00\s*PM\b', 'two PM'),
            (r'\b3:00\s*PM\b', 'three in the afternoon'),
            (r'\b4:00\s*PM\b', 'four PM'),
            (r'\b5:00\s*PM\b', 'five in the evening'),
        ]
        
        for pattern, replacement in time_replacements:
            result = re.sub(pattern, replacement, result, flags=re.IGNORECASE)
        
        contractions = [
            ("I have", "I've"), ("I will", "I'll"), ("I am", "I'm"),
            ("We have", "We've"), ("We will", "We'll"), ("That is", "That's"),
            ("It is", "It's"), ("You are", "You're"), ("Do not", "Don't"),
            ("Cannot", "Can't"), ("Would not", "Wouldn't"), ("Could not", "Couldn't"),
            ("Should not", "Shouldn't"), ("Will not", "Won't"),
        ]
        
        for formal, casual in contractions:
            result = result.replace(formal, casual)
            result = result.replace(formal.lower(), casual.lower())
        ## PAUSE SETTINGS IF NEEDED
        #if len(result) > 60 and ',' not in result:
            #words = result.split()
            #if len(words) > 10:
                #pause_point = len(words) // 2
                #words[pause_point] = words[pause_point] + ","
                #result = " ".join(words)
        
        result = re.sub(r'<[^>]*>', '', result)
        result = result.replace('&', 'and')
        result = result.replace('<', 'less than')
        result = result.replace('>', 'greater than')
        result = re.sub(r'\*+', '', result)
        result = re.sub(r'_+', '', result)
        result = re.sub(r'\.{2,}', '.', result)
        result = re.sub(r',\s*,', ',', result)
        result = ' '.join(result.split())
        
        return result.strip()
    
    def _get_base_url(self) -> str:
        base_url = ConfigManager.get('BASE_URL')
        if base_url:
            return base_url.rstrip('/')
        
        try:
            if has_request_context() and request:
                proto = request.headers.get('X-Forwarded-Proto', request.scheme)
                host = request.headers.get('X-Forwarded-Host', request.host)
                return f"{proto}://{host}"
        except:
            pass
        
        return "http://localhost:5000"

class GeminiManager:
    def __init__(self):
        self.model = None
        self.enabled = False
        self.circuit_breaker = CircuitBreaker()
        self._initialize()
    
    def _initialize(self):
        api_key = ConfigManager.get('GEMINI_API_KEY')
        if not api_key:
            print("⚠️ Gemini API key not found")
            return
        
        try:
            genai.configure(api_key=api_key)
            
            safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            models_to_try = [
                ConfigManager.get('GEMINI_MODEL', 'gemini-2.0-flash-exp'),
                'gemini-1.5-flash', 'gemini-1.5-pro', 'gemini-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    self.model = genai.GenerativeModel(
                        model_name,
                        safety_settings=safety_settings,
                        generation_config={
                            'temperature': 0.8, 'top_p': 0.85,
                            'top_k': 50, 'max_output_tokens': 200,
                        }
                    )
                    
                    response = self.model.generate_content("Say 'Ready'")
                    if response and response.text:
                        self.enabled = True
                        print(f"✅ Gemini {model_name} initialized")
                        break
                except:
                    continue
            
            if not self.enabled:
                print("⚠️ No Gemini models available")
                
        except Exception as e:
            print(f"⚠️ Gemini initialization failed: {e}")
    
    def generate_response(self, prompt: str, **kwargs) -> Optional[str]:
        if not self.enabled:
            return None
        
        def _generate():
            config = {
                'temperature': kwargs.get('temperature', 0.8),
                'top_p': kwargs.get('top_p', 0.85),
                'top_k': kwargs.get('top_k', 50),
                'max_output_tokens': kwargs.get('max_output_tokens', 200)
            }
            
            response = self.model.generate_content(prompt, generation_config=config)
            
            if hasattr(response, 'text') and response.text:
                return response.text.strip()
            
            return None
        
        try:
            return self.circuit_breaker.call(_generate)
        except Exception as e:
            print(f"⚠️ Gemini generation failed: {e}")
            return None

class DataStore:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.appointments_file = self.data_dir / "appointments.json"
        self.appointments: List[Appointment] = []
        self._lock = threading.Lock()
        self.load_appointments()
    
    def load_appointments(self):
        try:
            if self.appointments_file.exists():
                with open(self.appointments_file, 'r') as f:
                    data = json.load(f)
                    self.appointments = [Appointment.from_dict(item) for item in data]
                print(f"📂 Loaded {len(self.appointments)} appointments")
        except Exception as e:
            print(f"⚠️ Error loading appointments: {e}")
            self.appointments = []
    
    def save_appointments(self):
        with self._lock:
            try:
                data = [apt.to_dict() for apt in self.appointments]
                with open(self.appointments_file, 'w') as f:
                    json.dump(data, f, indent=2)
                print(f"💾 Saved {len(self.appointments)} appointments")
            except Exception as e:
                print(f"⚠️ Error saving appointments: {e}")
    
    def add_appointment(self, appointment: Appointment):
        with self._lock:
            self.appointments.append(appointment)
            self.save_appointments()
    
    def find_appointments(self, **criteria) -> List[Appointment]:
        results = []
        
        with self._lock:
            for apt in self.appointments:
                match = True
                for key, value in criteria.items():
                    if hasattr(apt, key):
                        apt_value = getattr(apt, key)
                        if isinstance(value, str) and isinstance(apt_value, str):
                            if value.lower() not in apt_value.lower():
                                match = False
                                break
                        elif apt_value != value:
                            match = False
                            break
                
                if match:
                    results.append(apt)
        
        return results

class TwilioAIReceptionist:
    def __init__(self):
        self.config_manager = ConfigManager()
        self.business_config = BusinessConfig.from_env()
        
        self.app = Flask(__name__)
        self.setup_logging()
        
        self.twilio_client = Client(
            ConfigManager.get('TWILIO_ACCOUNT_SID'),
            ConfigManager.get('TWILIO_AUTH_TOKEN')
        )
        self.twilio_phone = ConfigManager.get('TWILIO_PHONE_NUMBER')
        
        self.speech_timeout = ConfigManager.get_int('SPEECH_TIMEOUT', 4)
        self.gather_timeout = ConfigManager.get_int('GATHER_TIMEOUT', 8)
        
        self.data_store = DataStore()
        self.calendar_manager = None
        self.elevenlabs_manager = ElevenLabsManager()
        self.gemini_manager = GeminiManager()
        
        if ConfigManager.get_bool('GOOGLE_CALENDAR_ENABLED'):
            self.calendar_manager = GoogleCalendarManager(
                ConfigManager.get('GOOGLE_CALENDAR_ID', 'primary')
            )
            if self.calendar_manager.service:
                print("🔒 Calendar Mode: STRICT - Only ONE appointment per time slot!")
                print("⚠️  System will PREVENT double-booking automatically")
        else:
            print("📅 Google Calendar: Disabled (set GOOGLE_CALENDAR_ENABLED=true to enable)")
        
        self.emotional_intelligence = EmotionalIntelligence()
        self.conversation_flow = ConversationFlow()
        self.personality_system = PersonalitySystem(self.business_config)
        
        self.call_sessions: Dict[str, CallSession] = {}
        self.session_lock = threading.Lock()
        
        self.executor = concurrent.futures.ThreadPoolExecutor(max_workers=10)
        
        self.setup_routes()
        self.start_background_tasks()
        
        print("✅ Twilio AI Receptionist initialized successfully!")
        if self.calendar_manager and self.calendar_manager.service:
            print("⚠️  IMPORTANT: Calendar is in STRICT MODE - No double-booking allowed!")
    
    def setup_logging(self):
        log_level = ConfigManager.get('LOG_LEVEL', 'INFO')
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('receptionist.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        
        self.logger = logging.getLogger(__name__)
    
    def start_background_tasks(self):
        def cleanup_audio():
            while True:
                try:
                    time.sleep(300)
                    audio_dir = Path('static/audio')
                    if audio_dir.exists():
                        for file in audio_dir.iterdir():
                            if file.is_file():
                                age = time.time() - file.stat().st_mtime
                                if age > 3600:
                                    file.unlink()
                                    print(f"🧹 Cleaned up {file.name}")
                    
                    if hasattr(self.elevenlabs_manager, 'audio_cache'):
                        if len(self.elevenlabs_manager.audio_cache) > 100:
                            items = list(self.elevenlabs_manager.audio_cache.items())
                            self.elevenlabs_manager.audio_cache = dict(items[-50:])
                            print("🧹 Trimmed audio cache to 50 items")
                            
                except Exception as e:
                    self.logger.error(f"Audio cleanup error: {e}")
        
        threading.Thread(target=cleanup_audio, daemon=True).start()
        
        def cleanup_sessions():
            while True:
                try:
                    time.sleep(60)
                    with self.session_lock:
                        now = datetime.now()
                        expired = []
                        for sid, session in self.call_sessions.items():
                            age = (now - session.created_at).total_seconds()
                            if age > 1800:
                                expired.append(sid)
                        
                        for sid in expired:
                            del self.call_sessions[sid]
                            print(f"🧹 Cleaned up session {sid}")
                except Exception as e:
                    self.logger.error(f"Session cleanup error: {e}")
        
        threading.Thread(target=cleanup_sessions, daemon=True).start()
        
        def keep_gemini_warm():
            while True:
                try:
                    time.sleep(30)
                    if self.gemini_manager.enabled:
                        self.gemini_manager.generate_response(
                            "respond with 'ready'",
                            max_output_tokens=10,
                            temperature=0.1
                        )
                        print("♨️ Gemini warm-up successful")
                except Exception as e:
                    self.logger.error(f"Gemini warm-up error: {e}")
        
        if self.gemini_manager.enabled:
            threading.Thread(target=keep_gemini_warm, daemon=True).start()
        
        if self.elevenlabs_manager.enabled:
            try:
                greeting = f"Thanks for calling {self.business_config.name}, this is Sarah. How can I help you today?"
                self.greeting_audio_url = self.elevenlabs_manager.generate_audio(greeting, priority=True)
                if self.greeting_audio_url:
                    print(f"🎤 Pre-generated greeting audio: {self.greeting_audio_url}")
            except Exception as e:
                print(f"⚠️ Could not pre-generate greeting: {e}")
    
    def setup_routes(self):
        @self.app.route('/')
        def index():
            return render_template_string('''
                <h1>🤖 Twilio AI Receptionist Status</h1>
                <hr>
                <h2>Configuration</h2>
                <p><b>Business:</b> {{ business_name }}</p>
                <p><b>Type:</b> {{ business_type }}</p>
                <p><b>Services:</b> {{ services }}</p>
                <hr>
                <h2>System Status</h2>
                <p>ElevenLabs : {{ elevenlabs_status }}</p>
                <p>Gemini AI: {{ gemini_status }}</p>
                <p>Google Calendar: {{ calendar_status }}</p>
                <p>Active Sessions: {{ active_sessions }}</p>
                <p>Total Appointments: {{ total_appointments }}</p>
                <hr>
                <h2>⚠️ Calendar Settings</h2>
                <p><b>Mode:</b> STRICT - Only ONE appointment per time slot</p>
                <p><b>Double-booking:</b> ❌ PREVENTED</p>
                <p><b>Conflict Detection:</b> ✅ ACTIVE</p>
                <hr>
                <h2>Testing & Admin</h2>
                <ul>
                    <li><a href="/test/calendar">📅 Test Calendar Availability</a></li>
                    <li><a href="/api/appointments">📋 View All Appointments (JSON)</a></li>
                </ul>
                <hr>
                <h2>Webhook URL</h2>
                <p>{{ webhook_url }}/webhook/voice</p>
            ''', 
                business_name=self.business_config.name,
                business_type=self.business_config.type,
                services=', '.join([s.name for s in self.business_config.services]),
                elevenlabs_status='✅ Enabled' if self.elevenlabs_manager.enabled else '❌ Disabled',
                gemini_status='✅ Enabled' if self.gemini_manager.enabled else '❌ Disabled',
                calendar_status='✅ Enabled (STRICT MODE)' if self.calendar_manager else '❌ Disabled',
                active_sessions=len(self.call_sessions),
                total_appointments=len(self.data_store.appointments),
                webhook_url=ConfigManager.get('BASE_URL', 'http://localhost:5000')
            )
        
        @self.app.route('/webhook/voice', methods=['POST'])
        def handle_voice():
            return self.handle_incoming_call()
        
        @self.app.route('/webhook/gather', methods=['POST'])
        def handle_gather():
            return self.handle_speech_input()
        
        @self.app.route('/webhook/status', methods=['POST'])
        def handle_status():
            return self.handle_call_status()
        
        @self.app.route('/static/audio/<filename>')
        def serve_audio(filename):
            try:
                audio_path = Path('static/audio') / filename
                if audio_path.exists():
                    return send_file(audio_path, mimetype='audio/mpeg')
                return "File not found", 404
            except Exception as e:
                self.logger.error(f"Error serving audio: {e}")
                return "Error", 500
        
        @self.app.route('/webhook/final_check', methods=['POST'])
        def handle_final_check():
            try:
                call_sid = request.values.get('CallSid')
                speech_result = request.values.get('SpeechResult', '').lower()
                
                print(f"📊 Final check response: '{speech_result}'")
                
                response = VoiceResponse()
                
                if any(word in speech_result for word in ['yes', 'yeah', 'question', 'else', 'another', 'change', 'different']):
                    followup_text = "Of course! What would you like to know?"
                    
                    if self.elevenlabs_manager.enabled:
                        audio_url = self.elevenlabs_manager.generate_audio(followup_text, priority=True)
                        if audio_url and 'localhost' not in audio_url:
                            gather = Gather(
                                input='speech',
                                action='/webhook/gather',
                                method='POST',
                                speechTimeout=self.speech_timeout,
                                timeout=self.gather_timeout,
                                language='en-US'
                            )
                            gather.play(audio_url)
                            response.append(gather)
                        else:
                            response.say(followup_text, voice='alice')
                            response.redirect('/webhook/voice', method='POST')
                    else:
                        response.say(followup_text, voice='alice')
                        response.redirect('/webhook/voice', method='POST')
                else:
                    goodbye_messages = [
                        f"Perfect! Thank you for booking with {self.business_config.name}. We'll see you soon!",
                        f"Wonderful! Thanks for choosing {self.business_config.name}. Have a great day!",
                        f"Excellent! We look forward to your visit. Take care!",
                        f"Great! See you at your appointment. Have a fantastic day!"
                    ]
                    
                    goodbye = goodbye_messages[hash(call_sid) % len(goodbye_messages)]
                    
                    if self.elevenlabs_manager.enabled:
                        goodbye_audio = self.elevenlabs_manager.generate_audio(goodbye, priority=True)
                        if goodbye_audio and 'localhost' not in goodbye_audio:
                            response.play(goodbye_audio)
                        else:
                            response.say(goodbye, voice='alice')
                    else:
                        response.say(goodbye, voice='alice')
                    
                    response.pause(length=0.2)
                    response.hangup()
                
                return Response(str(response), mimetype='text/xml')
                
            except Exception as e:
                self.logger.error(f"Error in final_check: {e}")
                response = VoiceResponse()
                response.say("Thank you for calling! Have a great day!", voice='alice')
                response.hangup()
                return Response(str(response), mimetype='text/xml')
        
        @self.app.route('/api/appointments')
        def get_appointments():
            appointments = [apt.to_dict() for apt in self.data_store.appointments]
            return jsonify(appointments)
        
        @self.app.route('/test/calendar')
        def test_calendar():
            if not self.calendar_manager:
                return "Calendar not enabled", 200
            
            today = datetime.now()
            tomorrow = today + timedelta(days=1)
            
            results = []
            results.append("<h1>📅 Calendar Availability Test</h1>")
            results.append("<h2>⚠️ STRICT MODE: Only ONE appointment per time slot allowed!</h2>")
            results.append("<hr>")
            
            today_str = today.strftime("%A, %B %d")
            results.append(f"<h3>Today ({today_str})</h3>")
            results.append("<table border='1' style='border-collapse: collapse; width: 100%;'>")
            results.append("<tr><th>Time</th><th>Status</th><th>Details</th></tr>")
            
            for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]:
                is_available, conflict = self.calendar_manager.check_availability(today_str, time_slot)
                if is_available:
                    status = "✅ AVAILABLE"
                    color = "green"
                    details = "Ready for booking"
                else:
                    status = "❌ BOOKED"
                    color = "red"
                    details = f"Slot is {conflict}"
                
                results.append(f"<tr>")
                results.append(f"<td>{time_slot}</td>")
                results.append(f"<td style='color: {color}; font-weight: bold;'>{status}</td>")
                results.append(f"<td>{details}</td>")
                results.append(f"</tr>")
            
            results.append("</table>")
            
            tomorrow_str = tomorrow.strftime("%A, %B %d")
            results.append(f"<h3>Tomorrow ({tomorrow_str})</h3>")
            results.append("<table border='1' style='border-collapse: collapse; width: 100%;'>")
            results.append("<tr><th>Time</th><th>Status</th><th>Details</th></tr>")
            
            for time_slot in ["9:00 AM", "10:00 AM", "11:00 AM", "12:00 PM", "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM"]:
                is_available, conflict = self.calendar_manager.check_availability(tomorrow_str, time_slot)
                if is_available:
                    status = "✅ AVAILABLE"
                    color = "green"
                    details = "Ready for booking"
                else:
                    status = "❌ BOOKED"
                    color = "red"
                    details = f"Slot is {conflict}"
                
                results.append(f"<tr>")
                results.append(f"<td>{time_slot}</td>")
                results.append(f"<td style='color: {color}; font-weight: bold;'>{status}</td>")
                results.append(f"<td>{details}</td>")
                results.append(f"</tr>")
            
            results.append("</table>")
            
            results.append("<hr>")
            results.append("<h3>🔒 Double-Booking Prevention Features:</h3>")
            results.append("<ul>")
            results.append("<li>✅ Real-time availability checking before confirming any appointment</li>")
            results.append("<li>✅ Thread-safe locking to prevent race conditions</li>")
            results.append("<li>✅ Automatic conflict detection with detailed messages</li>")
            results.append("<li>✅ Alternative time suggestions when slots are taken</li>")
            results.append("<li>✅ Final verification before creating calendar events</li>")
            results.append("<li>✅ Clear user messaging when requested times are unavailable</li>")
            results.append("</ul>")
            
            return "".join(results), 200
    
    def handle_incoming_call(self):
        try:
            call_sid = request.values.get('CallSid')
            from_number = request.values.get('From')
            
            self.logger.info(f"Incoming call from {from_number}, CallSid: {call_sid}")
            
            with self.session_lock:
                session = CallSession(call_sid=call_sid)
                session.customer_data['from_number'] = from_number
                self.call_sessions[call_sid] = session
            
            greeting = f"Thanks for calling {self.business_config.name}, this is Sarah. How can I help you today?"
            
            if hasattr(self, 'greeting_audio_url') and self.greeting_audio_url:
                response = VoiceResponse()
                gather = Gather(
                    input='speech',
                    action='/webhook/gather',
                    method='POST',
                    speechTimeout=4,
                    timeout=8,
                    language='en-US'
                )
                gather.play(self.greeting_audio_url)
                response.append(gather)
            else:
                response = self.create_voice_response(greeting, use_gather=True)
            
            return Response(str(response), mimetype='text/xml')
            
        except Exception as e:
            self.logger.error(f"Error handling incoming call: {e}")
            response = VoiceResponse()
            response.say("I'm sorry, I'm having technical difficulties. Please call back.", voice='alice')
            response.hangup()
            return Response(str(response), mimetype='text/xml')
    
    def handle_speech_input(self):
        try:
            call_sid = request.values.get('CallSid')
            speech_result = request.values.get('SpeechResult', '')
            
            self.logger.info(f"Speech input from {call_sid}: {speech_result}")
            
            with self.session_lock:
                session = self.call_sessions.get(call_sid)
                if not session:
                    return self.handle_incoming_call()
            
            session.add_message('user', speech_result)
            
            response_text = self.process_user_input(session, speech_result)
            
            is_booking_complete = any(phrase in response_text for phrase in [
                "Perfect! You're all set",
                "Wonderful! I've successfully booked",
                "Excellent! Your appointment is confirmed",
                "Perfect! I've got you scheduled",
                "Wonderful! Your",
                "Excellent! You're all set"
            ])
            
            if is_booking_complete:
                response = VoiceResponse()
                
                if self.elevenlabs_manager.enabled:
                    audio = self.elevenlabs_manager.generate_audio(response_text, priority=True)
                    if audio and 'localhost' not in audio:
                        response.play(audio)
                    else:
                        response.say(response_text, voice='alice')
                else:
                    response.say(response_text, voice='alice')
                
                response.pause(length=2)
                
                gather = Gather(
                    input='speech',
                    action='/webhook/final_check',
                    method='POST',
                    speechTimeout=3,
                    timeout=5,
                    language='en-US'
                )
                gather.say("Is there anything else I can help you with?", voice='alice')
                response.append(gather)
                
                response.pause(length=1)
                response.say("Thank you for calling! Have a great day!", voice='alice')
                response.hangup()
            else:
                response = self.create_voice_response(response_text, use_gather=True)
            
            return Response(str(response), mimetype='text/xml')
            
        except Exception as e:
            self.logger.error(f"Error handling speech input: {e}")
            response = VoiceResponse()
            response.say("Let me try that again.", voice='alice')
            response.redirect('/webhook/voice', method='POST')
            return Response(str(response), mimetype='text/xml')
    
    def handle_call_status(self):
        call_sid = request.values.get('CallSid')
        call_status = request.values.get('CallStatus')
        
        self.logger.info(f"Call {call_sid} status: {call_status}")
        
        if call_status in ['completed', 'failed', 'busy', 'no-answer']:
            with self.session_lock:
                if call_sid in self.call_sessions:
                    del self.call_sessions[call_sid]
                    print(f"🧹 Cleaned up session for {call_sid}")
        
        return Response('', mimetype='text/plain')
    
    def create_voice_response(self, text: str, use_gather: bool = True, priority: bool = True) -> VoiceResponse:
        response = VoiceResponse()
        
        audio_url = None
        if self.elevenlabs_manager.enabled:
            audio_url = self.elevenlabs_manager.generate_audio(text, priority=priority)
        
        if use_gather:
            gather = Gather(
                input='speech',
                action='/webhook/gather',
                method='POST',
                speechTimeout=self.speech_timeout,
                timeout=self.gather_timeout,
                language='en-US',
                hints=self._generate_speech_hints(),
                actionOnEmptyResult=False,
                profanityFilter=False
            )
            
            if audio_url and 'localhost' not in audio_url:
                gather.play(audio_url)
            else:
                gather.say(text, voice='alice')
            
            response.append(gather)
        else:
            if audio_url and 'localhost' not in audio_url:
                response.play(audio_url)
            else:
                response.say(text, voice='alice')
        
        return response
    
    def _generate_speech_hints(self):
        hints = ['appointment', 'book', 'schedule', 'yes', 'no', 'tomorrow', 
                'today', 'morning', 'afternoon', 'name', 'phone']
        
        for service in self.business_config.services:
            hints.append(service.name.lower())
            hints.extend(service.keywords)
        
        hints.extend(['nine', 'ten', 'eleven', 'twelve', 'one', 'two', 'three', 'four'])
        
        return ','.join(set(hints))
    
    def process_user_input(self, session: CallSession, user_input: str) -> str:
        self.logger.info(f"Processing input from {session.call_sid}: {user_input}")
        
        user_input = self._auto_correct_input(user_input)
        
        emotion_data = self.emotional_intelligence.analyze(user_input)
        session.emotion_state = emotion_data['emotion']
        session.urgency_level = emotion_data['intensity']
        
        # Track what we're asking for
        if not session.customer_data.get('name'):
            session.state = "gathering_name"
        elif not session.customer_data.get('service'):
            session.state = "gathering_service"
        elif not session.customer_data.get('date'):
            session.state = "gathering_date"
        elif not session.customer_data.get('time'):
            session.state = "gathering_time"
        else:
            session.state = "confirming"
        
        self.extract_booking_info(session, user_input)
        
        if self._is_user_insisting_on_unavailable_time(session, user_input):
            return self._handle_unavailable_time_insistence(session)
        
        if self.is_booking_complete(session):
            print(f"🎉 Booking ready for {session.call_sid}")
            return self.complete_booking(session)
        
        if self.gemini_manager.enabled:
            ai_response = self.generate_ai_response(session, user_input)
            if ai_response:
                self.logger.info(f"AI response for {session.call_sid}: {ai_response}")
                return ai_response
        if session.customer_data.get('time') and any(phrase in user_input.lower() for phrase in ['works perfectly', 'that sounds good','perfect','great', 'yes please','confirm','yes']):
            if self.is_booking_complete(session):
                return self.complete_booking(session)
            
        fallback = self.generate_fallback_response(session)
        self.logger.info(f"Fallback response for {session.call_sid}: {fallback}")
        return fallback
    
    def _auto_correct_input(self, user_input: str) -> str:
        corrections = {}
        
        if self.business_config.type == 'dental':
            corrections.update({
                'feeling': 'filling', 'feelings': 'fillings', 'keys': 'teeth',
                'paid': 'pain', 'tea': 'teeth', 'tooth': 'teeth',
                'too': 'tooth', 'route': 'root', 'route canal': 'root canal',
            })
        elif self.business_config.type == 'medical':
            corrections.update({'point': 'appointment', 'a point': 'appointment'})
        
        corrections.update({
            'book and': 'booking', 'a pointment': 'appointment',
            'schedule and': 'scheduling',
        })
        
        user_input_lower = user_input.lower()
        for wrong, right in corrections.items():
            if wrong in user_input_lower:
                user_input = re.sub(rf'\b{wrong}\b', right, user_input, flags=re.IGNORECASE)
                print(f"🔄 Auto-corrected '{wrong}' to '{right}'")
        
        return user_input
    
    def _is_user_insisting_on_unavailable_time(self, session: CallSession, user_input: str) -> bool:
        insistence_keywords = [
            "i really need", "i must have", "only time", "has to be",
            "no other time", "really want", "specifically", "definitely"
        ]
        
        text_lower = user_input.lower()
        has_insistence = any(keyword in text_lower for keyword in insistence_keywords)
        
        if session.customer_data.get('last_unavailable_time'):
            time_mentioned = self.extract_time(user_input)
            if time_mentioned == session.customer_data['last_unavailable_time']:
                return True
        
        return has_insistence and session.customer_data.get('unavailable_time')
    
    def _handle_unavailable_time_insistence(self, session: CallSession) -> str:
        unavailable_time = session.customer_data.get('unavailable_time', 'that time')
        date = session.customer_data.get('date', 'that day')
        
        session.customer_data['last_unavailable_time'] = unavailable_time
        
        alternatives = []
        if self.calendar_manager and session.customer_data.get('date'):
            alternatives = self.calendar_manager.find_next_available_slots(
                session.customer_data['date'], unavailable_time, count=3
            )
        
        if session.emotion_state == 'frustration' or session.urgency_level > 0.7:
            response = (f"I completely understand how important {unavailable_time} is for you, "
                       f"and I really wish I could book it. Unfortunately, that exact time slot "
                       f"has already been reserved by another patient. ")
        else:
            response = (f"I'm really sorry, but {unavailable_time} on {date} is definitely not available - "
                       f"it's already been booked by someone else. ")
        
        if alternatives:
            response += f"The closest available times I have are {', '.join(alternatives[:2])}. "
            response += "Would either of those work instead?"
        else:
            tomorrow = (datetime.now() + timedelta(days=1)).strftime("%A, %B %d")
            response += f"Would you like me to check {unavailable_time} on a different day? "
            response += f"Perhaps {tomorrow}?"
        
        session.customer_data.pop('unavailable_time', None)
        
        return response
    
    def extract_booking_info(self, session: CallSession, text: str):
        if not session.customer_data.get('name'):
            # More flexible name extraction patterns
            patterns = [
                r"(?:my name is|i'm|i am)\s+([a-z]+(?:\s+[a-z]+)?)",
                r"(?:the name (?:could be|is|would be))\s+([a-z]+(?:\s+[a-z]+)?)",
                r"(?:full name is)\s+([a-z]+(?:\s+[a-z]+)?)",
                r"(?:it's|its)\s+([a-z]+(?:\s+[a-z]+)?)",
                r"(?:call me|i'm called)\s+([a-z]+(?:\s+[a-z]+)?)",
            ]
            
            for pattern in patterns:
                name_match = re.search(pattern, text, re.I)
                if name_match:
                    session.customer_data['name'] = name_match.group(1).title()
                    print(f"📍 Extracted name: {session.customer_data['name']}")
                    break
            if not session.customer_data.get('time') and session.customer_data.get('date'):
                time = self.extract_time(text)
                if not time and "9:00" in text.lower():
                    time = "9:00 AM"
                if time:
                    self._check_and_set_time(session, time)
            # If no pattern matched but the response seems to be answering the name question
            if not session.customer_data.get('name') and session.state == "gathering_name":
                # Clean up spelled-out names like "Tim t, i m"
                cleaned_text = re.sub(r'\b([a-z])[,.\s]+(?=[a-z]\b)', r'\1', text, flags=re.I)
                
                # Remove common filler words
                filler_words = ['yes', 'no', 'the', 'is', 'could', 'be', 'name', 'full', 'okay', 'uh', 'um', 'its', "it's", 'and']
                words = cleaned_text.split()
                name_words = []
                
                for word in words:
                    clean_word = word.strip('.,!?').lower()
                    if clean_word not in filler_words and clean_word.replace('-', '').replace("'", '').isalpha():
                        # Check if it looks like a name (capitalized or all letters)
                        if len(clean_word) > 1:
                            name_words.append(word.strip('.,!?'))
                
                # If we found potential name words, use them
                if name_words and len(name_words) <= 3:
                    session.customer_data['name'] = ' '.join(name_words).title()
                    print(f"📍 Extracted name (direct): {session.customer_data['name']}")
        
        if not session.customer_data.get('service'):
            for service in self.business_config.services:
                if service.matches_input(text):
                    session.customer_data['service'] = service.name
                    print(f"📍 Extracted service: {service.name}")
                    break
        
        if not session.customer_data.get('date'):
            date = self.extract_date(text)
            if date:
                session.customer_data['date'] = date
                print(f"📍 Extracted date: {date}")
                
                if session.customer_data.get('preferred_time'):
                    self._check_and_set_time(session, session.customer_data['preferred_time'])
        
        if not session.customer_data.get('time') and session.customer_data.get('date'):
            time = self.extract_time(text)
            if time:
                self._check_and_set_time(session, time)
        elif not session.customer_data.get('time') and not session.customer_data.get('date'):
            time = self.extract_time(text)
            if time:
                session.customer_data['preferred_time'] = time
                print(f"📍 Stored preferred time: {time} (waiting for date)")
        
        if not session.customer_data.get('phone'):
            phone_match = re.search(r'(\d{3})[-.\s]?(\d{3})[-.\s]?(\d{4})', text)
            if phone_match:
                session.customer_data['phone'] = ''.join(phone_match.groups())
                print(f"📍 Extracted phone: {session.customer_data['phone']}")
            elif session.customer_data.get('from_number'):
                session.customer_data['phone'] = session.customer_data['from_number']
    
    def _check_and_set_time(self, session: CallSession, time: str) -> bool:
        date = session.customer_data.get('date')
        if not date:
            return False
        
        if self.calendar_manager:
            is_available, conflict_details = self.calendar_manager.check_availability(date, time)
            
            if is_available:
                session.customer_data['time'] = time
                print(f"✅ Time {time} on {date} is AVAILABLE and reserved")
                return True
            else:
                session.customer_data['unavailable_time'] = time
                session.customer_data['conflict_reason'] = conflict_details
                print(f"❌ Time {time} on {date} is NOT available: {conflict_details}")
                
                alternatives = self.calendar_manager.find_next_available_slots(date, time, count=3)
                session.customer_data['alternative_times'] = alternatives
                
                return False
        else:
            session.customer_data['time'] = time
            print(f"📍 Set time: {time} (no calendar verification)")
            return True
    
    def extract_date(self, text: str) -> Optional[str]:
        text_lower = text.lower()
        today = datetime.now()
        
        if 'today' in text_lower:
            return today.strftime("%A, %B %d")
        elif 'tomorrow' in text_lower:
            return (today + timedelta(days=1)).strftime("%A, %B %d")
        
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day in days:
            if day in text_lower:
                days_ahead = (days.index(day) - today.weekday()) % 7
                if days_ahead == 0:
                    days_ahead = 7
                target_date = today + timedelta(days=days_ahead)
                return target_date.strftime("%A, %B %d")
        
        return None
    
    def extract_time(self, text: str) -> Optional[str]:
        patterns = [
            (r'(\d{1,2}):(\d{2})\s*(am|pm)', lambda m: f"{m[1]}:{m[2]} {m[3].upper()}"),
            (r'(\d{1,2})\s*(am|pm)', lambda m: f"{m[1]}:00 {m[2].upper()}"),
            (r'(\d{1,2})\s*00', lambda m: f"{m[1]}:00 AM" if int(m[1]) < 12 else f"{m[1]}:00 PM"),
        ]
        
        for pattern, formatter in patterns:
            match = re.search(pattern, text.lower())
            if match:
                return formatter(match.groups())
            #If no patterns deteteced use gemeni to understand
        if self.gemini_manager.enabled:
            prompt = f"""Extract the time from this text : "{text}"

            Common examples:
            -"nine hundred" or "900" = 9:00 AM
            - "three thirty" = 3:30 PM
            -"noon" = 12:00 PM
            -"half past two" = 2:30 PM
            -"quarter to three" = 2:45 PM
            Return ONLY the time in 12-hour format (e.g., "2:30 PM") or return "NONE" if no time is found.
            Do not include any other text."""

            response = self.gemini_manager.generate_response(prompt,
                    temperature=0.1, max_output_tokens=20)
            if response and response.strip() != "NONE":
                if re.match(r'\d{1,2}:\d{2}\s*(AM|PM)', response.strip()):
                    return response.strip()
        time_words = {
            'morning': '9:00 AM',
            'afternoon': '12:00 PM',
            'evening': '5:00 PM',
        }
        for word, time in time_words.items():
            if word in text.lower():
                return time
        return None
    def _format_time_from_digits(self, hour:str, minute: str) -> str:
        h = int(hour)
        return f"{h}:{minute} { 'AM' if h < 12 else 'PM' }"
    def _format_military_time(self, time_str: str) -> str:
        if len(time_str) == 3:
            hour = int(time_str[0])
            minute = int(time_str[1:3])
        else:
            hour = int(time_str[:2])
            minute = int(time_str[2:4])
            if 0 <= hour < 24 and 0 <= minute < 60:
                return f"{hour % 12 or 12}:{minute:02d} {'AM' if hour < 12 else 'PM'}"
            
    def is_booking_complete(self, session: CallSession) -> bool:
        required = ['name', 'service', 'date', 'time']
        return all(session.customer_data.get(field) for field in required)
    
    def complete_booking(self, session: CallSession) -> str:
        date = session.customer_data['date']
        time = session.customer_data['time']
        
        if self.calendar_manager:
            print(f"🔒 FINAL AVAILABILITY CHECK: {date} at {time}")
            is_available, conflict_details = self.calendar_manager.check_availability(date, time)
            
            if not is_available:
                print(f"❌ BOOKING BLOCKED: Slot is {conflict_details}")
                
                alternatives = self.calendar_manager.find_next_available_slots(date, time, count=3)
                
                if alternatives:
                    alt_text = ", ".join(alternatives[:2])
                    if len(alternatives) > 2:
                        alt_text += f", or {alternatives[2]}"
                    
                    return (f"Oh no! I'm so sorry, but someone just booked the {time} slot on {date}. "
                           f"That time is {conflict_details}. "
                           f"However, I have these times available on the same day: {alt_text}. "
                           f"Which one would work better for you?")
                else:
                    return (f"I'm really sorry, but the {time} slot on {date} is {conflict_details}. "
                           f"Unfortunately, we don't have any other times available that day. "
                           f"Would you like to try a different day? Tomorrow perhaps?")
        
        appointment = Appointment(
            customer_name=session.customer_data['name'],
            phone_number=session.customer_data.get('phone', session.customer_data.get('from_number', '')),
            service=session.customer_data['service'],
            date=session.customer_data['date'],
            time=session.customer_data['time'],
            call_sid=session.call_sid,
            created_at=datetime.now().isoformat(),
            status='pending'
        )
        
        calendar_success = False
        if self.calendar_manager:
            success, event_id, error_msg = self.calendar_manager.create_appointment(appointment)
            
            if success and event_id:
                appointment.google_event_id = event_id
                appointment.status = 'confirmed'
                calendar_success = True
                print(f"✅ BOOKING CONFIRMED: {appointment.time} on {appointment.date} is now BLOCKED")
            else:
                print(f"❌ CALENDAR BOOKING FAILED: {error_msg}")
                
                alternatives = self.calendar_manager.find_next_available_slots(date, time, count=3)
                
                if "already booked" in (error_msg or "").lower():
                    if alternatives:
                        alt_text = ", ".join(alternatives[:2])
                        return (f"Oh, I apologize! Someone just booked that {time} slot while we were talking. "
                               f"The system shows it's {error_msg}. "
                               f"But don't worry, I have {alt_text} still available. Which would you prefer?")
                    else:
                        return (f"I'm so sorry, but that time slot just got booked by someone else. "
                               f"Would you like to try a different day?")
                else:
                    appointment.status = 'pending_manual'
                    appointment.notes = f"Calendar sync failed: {error_msg}"
        
        self.data_store.add_appointment(appointment)
        
        if calendar_success:
            confirmations = [
                f"Perfect! You're all set for your {appointment.service} on {appointment.date} at {appointment.time}. "
                f"This time slot is now reserved exclusively for you!",
                
                f"Wonderful! I've successfully booked your {appointment.service} for {appointment.date} at {appointment.time}. "
                f"No one else can book this time - it's all yours!",
                
                f"Excellent! Your appointment is confirmed for {appointment.date} at {appointment.time}. "
                f"I've blocked off this time slot just for you!"
            ]
        else:
            confirmations = [
                f"I've noted your appointment for {appointment.service} on {appointment.date} at {appointment.time}. "
                f"We'll send you a confirmation shortly.",
                
                f"Your {appointment.service} request for {appointment.date} at {appointment.time} has been received. "
                f"Someone will call you back to confirm.",
            ]
        
        confirmation = random.choice(confirmations)
        
        if session.emotion_state == 'pain':
            confirmation += " I hope we can help you feel better soon!"
        elif session.emotion_state == 'anxiety':
            confirmation += " Don't worry, we'll take great care of you!"
        
        confirmation += " Is there anything else I can help you with today?"
        
        return confirmation
    
    def generate_ai_response(self, session: CallSession, user_input: str) -> Optional[str]:
        unavailable_context = ""
        if session.customer_data.get('unavailable_time'):
            unavailable_time = session.customer_data['unavailable_time']
            conflict_reason = session.customer_data.get('conflict_reason', 'already booked')
            alternatives = session.customer_data.get('alternative_times', [])
            
            unavailable_context = f"\n⚠️ IMPORTANT: The user just requested {unavailable_time} but it's {conflict_reason}!"
            if alternatives:
                unavailable_context += f"\nAvailable alternatives: {', '.join(alternatives[:3])}"
                unavailable_context += "\nYou MUST inform them the time is taken and suggest these alternatives!"
            
            session.customer_data.pop('unavailable_time', None)
            session.customer_data.pop('conflict_reason', None)
        
        booking_status = self.get_booking_status_with_availability(session)
        next_action = self.determine_next_action(session)
        
        emotional_context = ""
        if session.emotion_state != 'neutral':
            emotional_context = f"\nCaller emotion: {session.emotion_state} (intensity: {session.urgency_level})"
        
        # Make it clear what we already have
        already_have = []
        if session.customer_data.get('name'):
            already_have.append(f"Name: {session.customer_data['name']}")
        if session.customer_data.get('service'):
            already_have.append(f"Service: {session.customer_data['service']}")
        if session.customer_data.get('date'):
            already_have.append(f"Date: {session.customer_data['date']}")
        if session.customer_data.get('time'):
            already_have.append(f"Time: {session.customer_data['time']}")
            
        info_collected = "\nAlready collected: " + ", ".join(already_have) if already_have else "\nNo information collected yet"
        
        prompt = f"""You are Sarah, a warm and professional receptionist at {self.business_config.name} having a natural phone conversation.

Current booking:
{booking_status}
{info_collected}
{emotional_context}
{unavailable_context}

Customer just said: "{user_input}"
They are responding to your previous question.

{next_action}

CRITICAL RULES:
1. Speak NATURALLY like a real human receptionist - never mention checking systems, waiting for responses, or any technical processes
2. Use smooth transitions: "Perfect!", "Great!", "Wonderful!", "Alright!", "Excellent!"
3. NEVER say things like "let me check", "wait for response", "checking bookings", "system shows", "I'll need to verify"
4. Instead say things like "I have you down for...", "That time is available!", "How about...", "Would you prefer..."
5. Never ask for information you already have (shown above)
6. Keep responses brief (40-80 words) and conversational
7. Use contractions (I'll, we've, that's, you're)

Remember: You're Sarah, not a computer. Speak warmly and naturally, as if you already know the information."""
        
        ai_response = self.gemini_manager.generate_response(prompt)
        
        if ai_response:
            context = {
                'emotion': session.emotion_state,
                'urgency': session.urgency_level,
                'has_conflict': bool(unavailable_context),
                'show_understanding': True,  # Always show understanding
                'is_thinking': False  # Never show thinking
            }
            
            ai_response = self.personality_system.apply_personality(ai_response, context)
            ai_response = self.conversation_flow.add_natural_elements(ai_response, context)
            
            # Final cleanup to ensure natural speech
            ai_response = self._clean_ai_response(ai_response)
            
            session.last_response = ai_response
            session.add_message('assistant', ai_response)
            
            return ai_response
        
        return None
    
    def _clean_ai_response(self, response: str) -> str:
        """Clean AI response to sound more natural"""
        # Remove any system-like language
        system_terms = [
            "checking the system", "let me check", "wait a moment",
            "processing", "verifying", "system shows", "database",
            "updating records", "accessing", "retrieving"
        ]
        
        response_lower = response.lower()
        for term in system_terms:
            if term in response_lower:
                response = response.replace(term, "")
                response = response.replace(term.capitalize(), "")
        
        # Fix any broken sentences from removal
        response = re.sub(r'\s+', ' ', response)
        response = re.sub(r'^\s*,\s*', '', response)
        response = re.sub(r'\.\s*\.', '.', response)
        
        return response.strip()
    
    def generate_fallback_response(self, session: CallSession) -> str:
        if session.customer_data.get('unavailable_time'):
            unavailable_time = session.customer_data['unavailable_time']
            conflict_reason = session.customer_data.get('conflict_reason', 'already booked')
            alternatives = session.customer_data.get('alternative_times', [])
            
            session.customer_data.pop('unavailable_time', None)
            session.customer_data.pop('conflict_reason', None)
            
            if alternatives:
                alt_text = ", ".join(alternatives[:2])
                if len(alternatives) > 2:
                    alt_text += f", or {alternatives[2]}"
                return (f"I'm sorry, but {unavailable_time} is {conflict_reason}. "
                       f"However, I have these times available: {alt_text}. "
                       f"Which would work best for you?")
            else:
                return (f"Unfortunately, {unavailable_time} is {conflict_reason}. "
                       f"Would you like to try a different time or perhaps another day?")
        
        if not session.customer_data.get('name'):
            return "I'd be happy to help you book an appointment. May I have your name please?"
        elif not session.customer_data.get('service'):
            services = ', '.join([s.name for s in self.business_config.services])
            return f"What service would you like to book? We offer {services}."
        elif not session.customer_data.get('date'):
            return "What day works best for you?"
        elif not session.customer_data.get('time'):
            if self.calendar_manager:
                date = session.customer_data['date']
                available_times = self.calendar_manager.find_next_available_slots(date, count=4)
                if available_times:
                    return f"What time would you prefer? I have {', '.join(available_times[:3])} available."
            return "What time would you prefer?"
        else:
            return "Let me confirm your appointment details."
    
    def get_booking_status_with_availability(self, session: CallSession) -> str:
        status = []
        
        for field in ['name', 'service', 'date']:
            if session.customer_data.get(field):
                status.append(f"{field.title()}: {session.customer_data[field]}")
        
        if session.customer_data.get('time'):
            time = session.customer_data['time']
            date = session.customer_data.get('date')
            
            if date and self.calendar_manager:
                is_available, _ = self.calendar_manager.check_availability(date, time)
                if is_available:
                    status.append(f"Time: {time} ✅ (available)")
                else:
                    status.append(f"Time: {time} ❌ (NO LONGER AVAILABLE - need new time!)")
            else:
                status.append(f"Time: {time}")
        
        if session.customer_data.get('date') and not session.customer_data.get('time'):
            if self.calendar_manager:
                date = session.customer_data['date']
                available_times = self.calendar_manager.find_next_available_slots(date, count=5)
                if available_times:
                    status.append(f"Available times: {', '.join(available_times)}")
        
        if session.customer_data.get('phone'):
            status.append(f"Phone: {session.customer_data['phone']}")
        
        return '\n'.join(status) if status else "No information collected yet"
    
    def determine_next_action(self, session: CallSession) -> str:
        if not session.customer_data.get('name'):
            return "Ask for their name in a friendly way - something like 'May I have your name please?' or 'Who am I booking this for?'"
        elif not session.customer_data.get('service'):
            services_str = ', '.join([s.name for s in self.business_config.services])
            return f"Now naturally transition to asking what service they need. Mention we offer: {services_str}."
        elif not session.customer_data.get('date'):
            return "Great! Now smoothly ask what day works best - like 'What day were you hoping to come in?' or 'When would you like to schedule this?'"
        elif not session.customer_data.get('time'):
            return "Perfect! Now naturally ask about timing - like 'What time works best for you?' or 'Do you prefer morning or afternoon?'"
        else:
            return "Everything's collected! Confirm their appointment with enthusiasm - 'Perfect! I have you scheduled for...'"
    
    def run(self, host: str = '0.0.0.0', port: int = 5000, debug: bool = False):
        print("\n" + "="*60)
        print("🤖 TWILIO AI RECEPTIONIST ACTIVATED")
        print("="*60)
        print(f"📞 Business: {self.business_config.name}")
        print(f"🏢 Type: {self.business_config.type}")
        print(f"🎤 Voice: {'ElevenLabs' if self.elevenlabs_manager.enabled else 'Twilio'}")
        print(f"🤖 AI: {'Gemini' if self.gemini_manager.enabled else 'Rule-based'}")
        
        if self.calendar_manager:
            print(f"📅 Calendar: ✅ Enabled (STRICT MODE - One booking per slot)")
            print(f"⚠️  Double-booking: PREVENTED")
            print(f"🔒 Conflict Detection: ACTIVE")
        else:
            print(f"📅 Calendar: ❌ Disabled")
        
        print(f"\n🚀 Server starting on http://{host}:{port}")
        print(f"📌 Configure Twilio webhook: {ConfigManager.get('BASE_URL', f'http://localhost:{port}')}/webhook/voice")
        print("="*60)
        print("\n🎉 ALL SYSTEMS GO - READY FOR INCOMING CALLS! 🎉\n")
        print("="*60 + "\n")
        
        self.app.run(host=host, port=port, debug=debug)

if __name__ == '__main__':
    try:
        receptionist = TwilioAIReceptionist()
        
        print("\n🎭 ULTRA-HUMAN MODE ACTIVATED!")
        print("📊 Emotional Intelligence: ONLINE")
        print("🗣️ Natural Speech Patterns: ENABLED")
        print("🧠 Personality Module: LOADED")
        print("=" * 60 + "\n")
        
        receptionist.run()
    except KeyboardInterrupt:
        print("\n👋 Shutting down Twilio AI Receptionist...")
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        print(traceback.format_exc())
        sys.exit(1)