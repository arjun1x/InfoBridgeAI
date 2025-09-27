#!/usr/bin/env python3
"""
AI Receptionist with Full Features and Never-Fail Performance Enhancements
Enhanced version with proper timezone support, availability checking, and lightning-fast responses

DEPENDENCIES:
=============
pip install twilio flask python-dotenv google-generativeai elevenlabs
pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib
pip install pytz  # REQUIRED for proper timezone handling with Google Calendar
pip install redis  # OPTIONAL for distributed caching

PERFORMANCE ENHANCEMENTS:
========================
- Zero dead air with instant acknowledgments
- Perfect caller memory system
- Multi-tier caching (memory + Redis)
- Predictive response engine
- Parallel processing with 10 workers
- Spam detection and chaos handling
- Performance monitoring with metrics
- VIP caller recognition
- Background availability caching

QUICK CUSTOMIZATION GUIDE:
==========================
1. SERVICES: Edit the 'services' list in BusinessConfig class
2. BUSINESS INFO: Edit these in your .env file
3. HOURS: Set in .env as JSON
4. TIMEZONE: Set your timezone in .env (e.g., 'America/New_York', 'America/Los_Angeles')
5. GOOGLE CALENDAR: Enable in .env and add credentials.json
"""

import os
import sys
print("Current working directory:", os.getcwd())
print("Python path:", sys.path)

# Load environment variables
from dotenv import load_dotenv

# Try multiple paths for .env file
possible_env_paths = [
    '.env',
    os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'),
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'),
]

env_loaded = False
for env_path in possible_env_paths:
    if os.path.exists(env_path):
        load_dotenv(env_path)
        print(f"✅ Loaded .env from: {env_path}")
        env_loaded = True
        break
    else:
        print(f"❌ .env not found at: {env_path}")

if not env_loaded:
    print("⚠️ WARNING: No .env file found! Using environment variables only.")

# Core imports
import json
import re
import base64
import time
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
from flask import Flask, request, Response, send_file, has_request_context
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse, Gather, Say, Play
import logging
from functools import wraps, lru_cache
import google.generativeai as genai
import tempfile
from io import BytesIO
import concurrent.futures
import threading
import queue
import hashlib
import traceback
from collections import defaultdict, deque
import pickle
import warnings
import random
from time import perf_counter
warnings.filterwarnings("ignore", category=DeprecationWarning)

# Try to import Redis for distributed caching (optional)
try:
    import redis
    REDIS_AVAILABLE = True
    print("✅ Redis available for distributed caching")
except ImportError:
    REDIS_AVAILABLE = False
    print("ℹ️ Redis not available - using in-memory cache only")

# Try to import pytz for timezone handling - CRITICAL FOR GOOGLE CALENDAR
try:
    import pytz
    PYTZ_AVAILABLE = True
    print("✅ pytz import OK - Timezone support enabled")
except ImportError:
    PYTZ_AVAILABLE = False
    print("⚠️ pytz not installed. Run: pip install pytz")
    print("⚠️ Google Calendar may not work properly without pytz!")

# ElevenLabs import
try:
    from elevenlabs import ElevenLabs
    ELEVENLABS_AVAILABLE = True
    print("✅ ElevenLabs import OK")
except ImportError as e:
    ELEVENLABS_AVAILABLE = False
    print(f"⚠️ ElevenLabs not installed. Run: pip install elevenlabs ({e})")
except Exception as e:
    ELEVENLABS_AVAILABLE = False
    print(f"⚠️ ElevenLabs import error: {e}")

# Google Calendar imports
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_CALENDAR_AVAILABLE = True
    print("✅ Google Calendar libraries OK")
except ImportError:
    GOOGLE_CALENDAR_AVAILABLE = False
    print("⚠️ Google Calendar libraries not installed. Run: pip install google-api-python-client google-auth-httplib2 google-auth-oauthlib")

print("Files in working directory:", os.listdir(os.getcwd()))

# Debug: Print environment variables status
print("\n🔍 Environment Variables Status:")
print(f"TWILIO_ACCOUNT_SID: {'✅ Set' if os.getenv('TWILIO_ACCOUNT_SID') else '❌ Not set'}")
print(f"TWILIO_AUTH_TOKEN: {'✅ Set' if os.getenv('TWILIO_AUTH_TOKEN') else '❌ Not set'}")
print(f"TWILIO_PHONE_NUMBER: {'✅ Set' if os.getenv('TWILIO_PHONE_NUMBER') else '❌ Not set'}")
print(f"BASE_URL: {os.getenv('BASE_URL', 'Not set')}")
print(f"GEMINI_API_KEY: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Not set'}")
print(f"ELEVENLABS_API_KEY: {'✅ Set' if os.getenv('ELEVENLABS_API_KEY') else '❌ Not set'}")
print(f"GOOGLE_CALENDAR_ENABLED: {os.getenv('GOOGLE_CALENDAR_ENABLED', 'false')}")
print(f"TIMEZONE: {os.getenv('TIMEZONE', 'America/New_York')}")
print("")

# ===========================
# PERFORMANCE MONITORING CLASS
# ===========================
class PerformanceMonitor:
    """Track and optimize system performance"""
    def __init__(self):
        self.metrics = defaultdict(lambda: {
            'count': 0,
            'total_time': 0,
            'min_time': float('inf'),
            'max_time': 0,
            'recent_times': deque(maxlen=100)
        })
        self.cache_hits = 0
        self.cache_misses = 0
        self.ai_timeouts = 0
        self.successful_calls = 0
        
    def track(self, operation: str):
        """Context manager for tracking operation time"""
        class Timer:
            def __init__(self, monitor, op):
                self.monitor = monitor
                self.op = op
                self.start = None
                
            def __enter__(self):
                self.start = perf_counter()
                return self
                
            def __exit__(self, *args):
                elapsed = perf_counter() - self.start
                metrics = self.monitor.metrics[self.op]
                metrics['count'] += 1
                metrics['total_time'] += elapsed
                metrics['min_time'] = min(metrics['min_time'], elapsed)
                metrics['max_time'] = max(metrics['max_time'], elapsed)
                metrics['recent_times'].append(elapsed)
                
        return Timer(self, operation)
    
    def get_stats(self):
        """Get performance statistics"""
        stats = {}
        for op, metrics in self.metrics.items():
            if metrics['count'] > 0:
                recent = list(metrics['recent_times'])
                stats[op] = {
                    'count': metrics['count'],
                    'avg_ms': (metrics['total_time'] / metrics['count']) * 1000,
                    'min_ms': metrics['min_time'] * 1000,
                    'max_ms': metrics['max_time'] * 1000,
                    'recent_avg_ms': (sum(recent) / len(recent) * 1000) if recent else 0
                }
        
        # Add cache stats
        total_cache_ops = self.cache_hits + self.cache_misses
        stats['cache'] = {
            'hit_rate': (self.cache_hits / total_cache_ops * 100) if total_cache_ops > 0 else 0,
            'hits': self.cache_hits,
            'misses': self.cache_misses
        }
        
        return stats

# ===========================
# CALLER DATABASE
# ===========================
@dataclass
class CallerProfile:
    """Store caller information for perfect memory"""
    phone_number: str
    name: Optional[str] = None
    company: Optional[str] = None
    preferred_service: Optional[str] = None
    call_count: int = 0
    last_call_date: Optional[str] = None
    appointments: List[Dict] = field(default_factory=list)
    preferences: Dict = field(default_factory=dict)
    vip_status: bool = False
    spam_score: float = 0.0
    notes: str = ""

class CallerDatabase:
    """Manage caller profiles for perfect memory"""
    def __init__(self, db_file='caller_database.json'):
        self.db_file = db_file
        self.profiles = {}
        self.load()
        # Auto-save every 5 minutes
        threading.Timer(300, self._auto_save).start()
    
    def load(self):
        """Load caller database from file"""
        try:
            if os.path.exists(self.db_file):
                with open(self.db_file, 'r') as f:
                    data = json.load(f)
                    for phone, profile_data in data.items():
                        self.profiles[phone] = CallerProfile(**profile_data)
                print(f"📞 Loaded {len(self.profiles)} caller profiles")
        except Exception as e:
            print(f"⚠️ Error loading caller database: {e}")
    
    def save(self):
        """Save caller database to file"""
        try:
            data = {}
            for phone, profile in self.profiles.items():
                data[phone] = {
                    'phone_number': profile.phone_number,
                    'name': profile.name,
                    'company': profile.company,
                    'preferred_service': profile.preferred_service,
                    'call_count': profile.call_count,
                    'last_call_date': profile.last_call_date,
                    'appointments': profile.appointments,
                    'preferences': profile.preferences,
                    'vip_status': profile.vip_status,
                    'spam_score': profile.spam_score,
                    'notes': profile.notes
                }
            with open(self.db_file, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving caller database: {e}")
    
    def _auto_save(self):
        """Auto-save database periodically"""
        self.save()
        threading.Timer(300, self._auto_save).start()
    
    def get_or_create(self, phone_number: str) -> CallerProfile:
        """Get existing or create new caller profile"""
        if phone_number not in self.profiles:
            self.profiles[phone_number] = CallerProfile(phone_number=phone_number)
        
        profile = self.profiles[phone_number]
        profile.call_count += 1
        profile.last_call_date = datetime.now().isoformat()
        
        # Check VIP status (10+ calls or marked VIP)
        if profile.call_count >= 10:
            profile.vip_status = True
        
        return profile
    
    def update_profile(self, phone_number: str, **kwargs):
        """Update caller profile information"""
        if phone_number in self.profiles:
            profile = self.profiles[phone_number]
            for key, value in kwargs.items():
                if hasattr(profile, key):
                    setattr(profile, key, value)

# ===========================
# MULTI-TIER CACHE SYSTEM
# ===========================
class MultiTierCache:
    """Multi-tier caching system for lightning-fast responses"""
    def __init__(self, redis_host='localhost', redis_port=6379):
        self.memory_cache = {}
        self.cache_stats = {'hits': 0, 'misses': 0}
        
        # Try to connect to Redis
        self.redis_client = None
        if REDIS_AVAILABLE:
            try:
                self.redis_client = redis.Redis(
                    host=redis_host,
                    port=redis_port,
                    decode_responses=True,
                    socket_connect_timeout=1
                )
                self.redis_client.ping()
                print("✅ Redis cache connected")
            except:
                self.redis_client = None
                print("ℹ️ Redis not available, using memory cache only")
    
    def get(self, key: str):
        """Get from cache (memory first, then Redis)"""
        # Check memory cache
        if key in self.memory_cache:
            self.cache_stats['hits'] += 1
            return self.memory_cache[key]
        
        # Check Redis if available
        if self.redis_client:
            try:
                value = self.redis_client.get(key)
                if value:
                    # Store in memory for next time
                    self.memory_cache[key] = value
                    self.cache_stats['hits'] += 1
                    return value
            except:
                pass
        
        self.cache_stats['misses'] += 1
        return None
    
    def set(self, key: str, value: str, ttl: int = 3600):
        """Set in cache (both memory and Redis)"""
        # Store in memory
        self.memory_cache[key] = value
        
        # Store in Redis if available
        if self.redis_client:
            try:
                self.redis_client.setex(key, ttl, value)
            except:
                pass
    
    @lru_cache(maxsize=128)
    def get_cached_response(self, context_hash: str):
        """Get cached response for a given context"""
        return self.get(f"response:{context_hash}")

# ===========================
# PREDICTIVE RESPONSE ENGINE
# ===========================
class PredictiveResponseEngine:
    """Predict and pre-generate likely responses"""
    def __init__(self):
        self.response_patterns = {
            'greeting': [
                "Thanks for calling! How can I help you today?",
                "Hello! What can I do for you?",
                "Good {time_of_day}! How may I assist you?"
            ],
            'name_request': [
                "May I have your name please?",
                "Can I get your name?",
                "What's your name?"
            ],
            'service_request': [
                "What service would you like?",
                "Which service interests you?",
                "What type of appointment do you need?"
            ],
            'date_request': [
                "What day works best for you?",
                "When would you like to come in?",
                "What date would you prefer?"
            ],
            'time_request': [
                "What time works for you?",
                "What time would be convenient?",
                "Do you prefer morning or afternoon?"
            ],
            'confirmation': [
                "Perfect! I've scheduled your {service} for {date} at {time}.",
                "You're all set for {date} at {time}!",
                "Great! Your {service} is booked for {date} at {time}."
            ]
        }
        
        self.predictions = {}
    
    def predict_next_response(self, session_state: str, context: Dict) -> str:
        """Predict the most likely next response"""
        if session_state == 'greeting':
            time_of_day = self._get_time_of_day()
            return self.response_patterns['greeting'][0].format(time_of_day=time_of_day)
        elif not context.get('name'):
            return random.choice(self.response_patterns['name_request'])
        elif not context.get('service'):
            return random.choice(self.response_patterns['service_request'])
        elif not context.get('date'):
            return random.choice(self.response_patterns['date_request'])
        elif not context.get('time'):
            return random.choice(self.response_patterns['time_request'])
        else:
            return self.response_patterns['confirmation'][0].format(
                service=context.get('service', 'appointment'),
                date=context.get('date', 'the selected date'),
                time=context.get('time', 'the selected time')
            )
    
    def _get_time_of_day(self):
        """Get current time of day for greetings"""
        hour = datetime.now().hour
        if hour < 12:
            return "morning"
        elif hour < 17:
            return "afternoon"
        else:
            return "evening"

# ===========================
# BUSINESS CONFIGURATION CLASS (ENHANCED)
# ===========================
@dataclass
class BusinessConfig:
    """
    CUSTOMIZE YOUR BUSINESS HERE:
    - Change the default values below
    - Or better: Set them in your .env file
    """
    # Basic Info
    name: str = "Bright Smile Dental"
    type: str = "dental"  # dental, medical, salon, restaurant, retail, service
    
    # Services/Products
    services: List[Dict[str, Any]] = field(default_factory=lambda: [
        {
            "name": "Consultation",
            "price": 150.00,
            "duration": 60,
            "description": "Professional consultation service",
            "keywords": ["consultation", "consult", "checkup", "check-up", "exam", "examination"],
            "priority": 1
        },
        {
            "name": "Full Service",
            "price": 300.00,
            "duration": 120,
            "description": "Complete service package",
            "keywords": ["full", "complete", "comprehensive", "deep cleaning", "full service"],
            "priority": 2
        },
        {
            "name": "Quick Assessment",
            "price": 75.00,
            "duration": 30,
            "description": "Brief evaluation service",
            "keywords": ["quick", "emergency", "urgent", "pain", "hurt", "ache", "assessment"],
            "priority": 0
        }
    ])
    
    # Business Hours
    hours: Dict[str, str] = field(default_factory=lambda: {
        "monday": "8:00 AM - 5:00 PM",
        "tuesday": "8:00 AM - 5:00 PM",
        "wednesday": "8:00 AM - 5:00 PM",
        "thursday": "8:00 AM - 5:00 PM",
        "friday": "8:00 AM - 5:00 PM",
        "saturday": "10:00 AM - 2:00 PM",
        "sunday": "Closed"
    })
    
    # Appointment Settings
    appointment_duration_minutes: int = 60
    buffer_time_minutes: int = 15
    max_advance_booking_days: int = 30
    
    # Available time slots
    available_times: List[str] = field(default_factory=lambda: [
        "8:00 AM", "8:30 AM", "9:00 AM", "9:30 AM", "10:00 AM", "10:30 AM", 
        "11:00 AM", "11:30 AM", "12:00 PM", "1:00 PM", "1:30 PM", "2:00 PM", 
        "2:30 PM", "3:00 PM", "3:30 PM", "4:00 PM", "4:30 PM"
    ])
    
    # Response Templates
    greeting: str = "Thanks for calling {name}, this is Sarah. How can I help you today?"
    appointment_prompt: str = "I'd be happy to help you schedule an appointment. What service are you interested in?"
    closing: str = "Thank you for calling {name}. Have a great day!"
    
    # Special Instructions
    special_instructions: str = ""
    ai_personality: str = "professional and friendly"
    
    # Out of scope keywords
    out_of_scope_keywords: List[str] = field(default_factory=lambda: [
        'politics', 'weather', 'sports', 'movies', 'restaurants', 'shopping',
        'vacation', 'travel', 'news', 'stocks', 'crypto', 'bitcoin',
        'real estate', 'cars', 'dating', 'relationships', 'personal'
    ])
    
    # Spam indicators
    spam_indicators: List[str] = field(default_factory=lambda: [
        'warranty', 'credit card', 'social security', 'irs', 'arrest',
        'legal action', 'suspension', 'verification required', 'press 1',
        'limited time offer', 'act now', 'congratulations'
    ])
    
    # Transition phrases for zero dead air
    transition_phrases: List[str] = field(default_factory=lambda: [
        "Got it, let me check that...",
        "Perfect, one moment...",
        "Absolutely, let me pull that up...",
        "Of course, just a second...",
        "Great, let me find that for you...",
        "Sure thing, checking now...",
        "Excellent, one moment please..."
    ])
    
    # Acknowledgment phrases
    acknowledgment_phrases: List[str] = field(default_factory=lambda: [
        "Perfect!", "Got it!", "Excellent!", "Great!",
        "Absolutely!", "Of course!", "Certainly!",
        "Wonderful!", "That's great!", "Understood!"
    ])
    
    @classmethod
    def from_env(cls):
        """Load configuration from environment variables"""
        config = cls()
        
        config.name = os.getenv('BUSINESS_NAME', config.name)
        config.type = os.getenv('BUSINESS_TYPE', config.type)
        
        # Load services as JSON
        services_json = os.getenv('BUSINESS_SERVICES')
        if services_json:
            try:
                services_data = json.loads(services_json)
                config.services = []
                for service in services_data:
                    if isinstance(service, str):
                        config.services.append({
                            "name": service,
                            "price": 100.00,
                            "duration": 60,
                            "description": service
                        })
                    elif isinstance(service, dict):
                        config.services.append(service)
            except json.JSONDecodeError:
                print("Warning: Could not parse BUSINESS_SERVICES from .env")
        
        # Load hours as JSON
        hours_json = os.getenv('BUSINESS_HOURS')
        if hours_json:
            try:
                config.hours = json.loads(hours_json)
            except json.JSONDecodeError:
                print("Warning: Could not parse BUSINESS_HOURS from .env")
        
        # Load appointment settings
        config.appointment_duration_minutes = int(os.getenv('APPOINTMENT_DURATION', '60'))
        config.buffer_time_minutes = int(os.getenv('BUFFER_TIME', '15'))
        config.max_advance_booking_days = int(os.getenv('MAX_ADVANCE_DAYS', '30'))
        
        # Load response templates
        config.greeting = os.getenv('GREETING_MESSAGE', config.greeting).replace('{name}', config.name)
        config.appointment_prompt = os.getenv('APPOINTMENT_PROMPT', config.appointment_prompt)
        config.closing = os.getenv('CLOSING_MESSAGE', config.closing).replace('{name}', config.name)
        
        # Special instructions and personality
        config.special_instructions = os.getenv('SPECIAL_INSTRUCTIONS', '')
        config.ai_personality = os.getenv('AI_PERSONALITY', 'professional and friendly')
        
        # Load out of scope keywords
        out_of_scope_json = os.getenv('OUT_OF_SCOPE_KEYWORDS')
        if out_of_scope_json:
            try:
                config.out_of_scope_keywords = json.loads(out_of_scope_json)
            except json.JSONDecodeError:
                pass
        
        return config
    
    def get_context_prompt(self):
        """Generate AI context based on business configuration with performance enhancements"""
        # Format services
        services_list_items = []
        for s in self.services:
            price = s['price']
            if price == int(price):
                price_str = f"${int(price)}"
            else:
                price_str = f"${price:.2f}"
            services_list_items.append(f"- {s['name']}: {s['description']} ({price_str}, {s['duration']} min)")
        
        services_list = "\n".join(services_list_items)
        hours_list = "\n".join([f"- {day.capitalize()}: {hours}" for day, hours in self.hours.items()])
        
        # Add detailed service explanations based on business type
        service_details = ""
        if self.type == 'dental':
            service_details = """
DETAILED SERVICE EXPLANATIONS (use when customers ask):
- Consultation/Checkup: Includes comprehensive oral exam, X-rays if needed, teeth cleaning, gum health assessment, and personalized treatment plan discussion.
- Full Service/Deep Cleaning: Includes everything in consultation plus deep scaling and root planing, fluoride treatment, and removal of tartar buildup.
- Quick Assessment/Emergency: For urgent dental pain, broken teeth, or immediate concerns. Includes focused exam and pain relief options.
"""
        elif self.type == 'medical':
            service_details = """
DETAILED SERVICE EXPLANATIONS (use when customers ask):
- Consultation: Comprehensive health assessment including vital signs, medical history review, and discussion of any health concerns.
- Full Service/Physical: Complete annual physical exam with blood work, EKG if needed, and preventive care recommendations.
- Quick Assessment: Brief visit for specific symptoms or prescription refills.
"""
        elif self.type == 'salon':
            service_details = """
DETAILED SERVICE EXPLANATIONS (use when customers ask):
- Consultation: Hair analysis, style consultation, and basic cut or trim with wash and blow-dry.
- Full Service: Complete hair transformation including cut, color or highlights, deep conditioning treatment, and styling.
- Quick Assessment: Express service for bang trims, quick touch-ups, or style consultations.
"""
        
        prompt = f"""You are Sarah, an AI receptionist for {self.name}, a {self.type} business.
Your personality is {self.ai_personality} - be warm, natural, and conversational.

SERVICES OFFERED:
{services_list}
{service_details}

BUSINESS HOURS:
{hours_list}

APPOINTMENT SETTINGS:
- Standard appointment duration: {self.appointment_duration_minutes} minutes
- Buffer time between appointments: {self.buffer_time_minutes} minutes
- Advance booking allowed up to {self.max_advance_booking_days} days

YOUR NEVER-FAIL SUPERPOWERS:
1. INSTANT RESPONSE: Always acknowledge immediately - never leave dead air
2. PERFECT MEMORY: Remember returning callers and their preferences
3. CHAOS HANDLING: Smoothly redirect confused or rambling callers
4. PROFESSIONAL FILTERING: Detect and handle spam professionally

YOUR ROLE:
1. Answer calls professionally and warmly with natural conversation
2. Schedule new appointments efficiently 
3. Help customers modify or cancel existing appointments
4. Be smart - don't ask for information you already have
5. Use context clues - if they say "checkup" for dental, that's likely a consultation
6. When they ask for "latest" time, check actual availability and offer the latest available
7. When they ask for "earliest" time, check actual availability and offer the earliest available
8. Keep responses informative but not too long (40-80 words ideal)
9. When customers ask what's included in a service, explain it naturally and helpfully
10. If customers seem unsure, briefly explain what each service includes
11. ALWAYS complete your sentences - never cut off mid-thought!
12. Only suggest times that are actually available according to the calendar
13. If a customer wants to modify/cancel, ask for their name or phone number to find their appointment

{self.special_instructions}

NATURAL CONVERSATION RULES:
- Sound human and warm - use phrases like "I'd be happy to help" or "That's perfect"
- Use acknowledgment phrases: "Got it", "Perfect", "Absolutely"
- Use transition phrases while processing: "Let me check that..."
- If you just asked for their name and they respond with 1-3 words, that's likely their name
- Don't extract "yeah", "yes", "sure" etc as names - these are just acknowledgments
- If we have their phone from caller ID, don't ask for it - just confirm it at the end
- Listen for preferences: "latest", "earliest", "morning", "afternoon"
- Be natural - use contractions like "I'll", "we've", "you're"
- When stating times, be crystal clear: say "ten AM" not "10 o'clock AM"
- If they give multiple pieces of info at once, acknowledge all of them
- Show empathy when customers mention pain or urgency
- When they ask questions, ALWAYS answer them before moving on
- If they ask what's included in a service, explain it clearly and enthusiastically
- ONLY offer times that are actually available in the calendar

Remember to:
- Be friendly, professional, and genuinely helpful
- Keep responses brief but informative for phone conversations
- Confirm all appointment details clearly
- Make smart inferences from context
- Answer all customer questions thoroughly
- Sound natural and conversational, not robotic
- ONLY offer times that are actually available in the calendar
- Help with modifications and cancellations when requested
"""
        return prompt

# ===========================
# DATA CLASSES (ENHANCED)
# ===========================
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

@dataclass
class Package:
    name: str
    price: float
    services: List[str]
    duration: str
    description: str

@dataclass
class CallSession:
    call_sid: str
    state: str = "greeting"
    customer_data: Dict = None
    attempts: int = 0
    audio_queue: queue.Queue = None
    out_of_scope_count: int = 0
    clarification_attempts: int = 0
    last_ai_response: str = ""
    conversation_context: List[Dict] = None
    modification_mode: str = None  # 'modify', 'cancel', or None
    existing_appointment: Appointment = None
    repetition_count: Dict = None
    caller_profile: CallerProfile = None  # Added for caller memory
    response_start_time: float = 0  # Added for performance tracking
    last_acknowledgment: str = ""  # Added for transition tracking
    
    def __post_init__(self):
        if self.customer_data is None:
            self.customer_data = {}
        if self.audio_queue is None:
            self.audio_queue = queue.Queue()
        if self.conversation_context is None:
            self.conversation_context = []
        if self.repetition_count is None:
            self.repetition_count = {}

# ===========================
# CIRCUIT BREAKER PATTERN (ENHANCED)
# ===========================
class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance"""
    def __init__(self, failure_threshold=5, recovery_timeout=60, success_threshold=2):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.success_threshold = success_threshold
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = 'closed'  # closed, open, half_open
    
    def call(self, func, *args, **kwargs):
        if self.state == 'open':
            if time.time() - self.last_failure_time > self.recovery_timeout:
                self.state = 'half_open'
                self.success_count = 0
            else:
                raise Exception("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            if self.state == 'half_open':
                self.success_count += 1
                if self.success_count >= self.success_threshold:
                    self.state = 'closed'
                    self.failure_count = 0
            return result
        except Exception as e:
            self.failure_count += 1
            self.last_failure_time = time.time()
            if self.failure_count >= self.failure_threshold:
                self.state = 'open'
            raise e
    
    def get_state(self):
        return {
            'state': self.state,
            'failures': self.failure_count,
            'successes': self.success_count
        }

# ===========================
# GOOGLE CALENDAR MANAGER - ENHANCED WITH CACHING
# ===========================
class GoogleCalendarManager:
    """Manages Google Calendar integration with proper timezone support and caching"""
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    
    def __init__(self, calendar_id=None):
        self.calendar_id = calendar_id or 'primary'
        self.service = None
        self.creds = None
        self.logger = logging.getLogger(__name__)
        
        # Timezone configuration - CUSTOMIZE IN .ENV
        self.timezone = os.getenv('TIMEZONE', 'America/New_York')
        # Options: America/Los_Angeles, America/Chicago, America/Denver, Europe/London, Asia/Tokyo, etc.
        
        # Owner email for calendar notifications
        self.owner_email = os.getenv('CALENDAR_OWNER_EMAIL', '')
        
        # Availability cache
        self.availability_cache = {}
        self.cache_ttl = 300  # 5 minutes
        
        # Validate timezone support
        if not PYTZ_AVAILABLE:
            print("⚠️ WARNING: pytz not installed. Google Calendar may not work properly!")
            print("⚠️ Install it with: pip install pytz")
        
        self._authenticate()
        
        # Start background availability refresh
        threading.Thread(target=self._refresh_availability_cache, daemon=True).start()
    
    def _authenticate(self):
        """Authenticate with Google Calendar API"""
        try:
            # Load existing token
            if os.path.exists('token.pickle'):
                with open('token.pickle', 'rb') as token:
                    self.creds = pickle.load(token)
            
            # If there are no (valid) credentials available, let the user log in
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if os.path.exists('credentials.json'):
                        flow = InstalledAppFlow.from_client_secrets_file(
                            'credentials.json', self.SCOPES)
                        self.creds = flow.run_local_server(port=0)
                    else:
                        print(f"❌ credentials.json not found. Download from Google Cloud Console.")
                        return
                
                # Save the credentials for the next run
                with open('token.pickle', 'wb') as token:
                    pickle.dump(self.creds, token)
            
            self.service = build('calendar', 'v3', credentials=self.creds)
            print(f"✅ Google Calendar authenticated successfully! (Timezone: {self.timezone})")
            
        except Exception as e:
            print(f"❌ Google Calendar authentication failed: {e}")
            self.logger.error(f"Error authenticating with Google Calendar: {e}")
            self.service = None
    
    def _refresh_availability_cache(self):
        """Refresh availability cache in background"""
        while True:
            try:
                if self.service:
                    # Cache next 7 days of availability
                    today = datetime.now()
                    business_config = BusinessConfig.from_env()
                    
                    for days_ahead in range(7):
                        date = today + timedelta(days=days_ahead)
                        date_str = date.strftime("%A, %B %d")
                        
                        for time_slot in business_config.available_times:
                            cache_key = f"{date_str}:{time_slot}"
                            self.availability_cache[cache_key] = {
                                'available': self._check_availability_internal(date_str, time_slot),
                                'timestamp': time.time()
                            }
                
                time.sleep(300)  # Refresh every 5 minutes
            except Exception as e:
                print(f"⚠️ Error refreshing availability cache: {e}")
                time.sleep(60)
    
    def check_availability(self, date_str, time_str):
        """Check if a time slot is available with caching"""
        cache_key = f"{date_str}:{time_str}"
        
        # Check cache first
        if cache_key in self.availability_cache:
            cached = self.availability_cache[cache_key]
            if time.time() - cached['timestamp'] < self.cache_ttl:
                return cached['available']
        
        # Fall back to real check
        return self._check_availability_internal(date_str, time_str)
    
    def _check_availability_internal(self, date_str, time_str):
        """Internal availability check"""
        if not self.service:
            return True  # If no calendar service, assume available
        
        try:
            # Parse date and time
            appointment_date = datetime.strptime(f"{date_str} {time_str}", "%A, %B %d %I:%M %p")
            current_year = datetime.now().year
            appointment_date = appointment_date.replace(year=current_year)
            
            # Check if date is in the past (compare just the date, not time)
            today = datetime.now().date()
            if appointment_date.date() < today:
                # If the date has passed this year, assume next year
                appointment_date = appointment_date.replace(year=current_year + 1)
            
            # Handle timezone properly with pytz
            if PYTZ_AVAILABLE:
                # Get the local timezone
                local_tz = pytz.timezone(self.timezone)
                
                # Localize the datetime to the correct timezone
                appointment_date = local_tz.localize(appointment_date)
                
                # Convert to UTC for API query
                appointment_date_utc = appointment_date.astimezone(pytz.UTC)
                
                # Create time range (check for 1 hour block)
                time_min = appointment_date_utc.isoformat()
                time_max = (appointment_date_utc + timedelta(hours=1)).isoformat()
            else:
                # Fallback without pytz - assume local time
                time_min = appointment_date.isoformat() + 'Z'
                time_max = (appointment_date + timedelta(hours=1)).isoformat() + 'Z'
            
            # Query calendar for conflicts
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            return len(events) == 0  # True if no conflicts
            
        except Exception as e:
            return True  # Assume available on error
    
    def create_appointment(self, appointment: Appointment):
        """Create a Google Calendar event with proper timezone and no invalid attendees"""
        if not self.service:
            return None
        
        try:
            # Parse date and time
            appointment_datetime = datetime.strptime(f"{appointment.date} {appointment.time}", "%A, %B %d %I:%M %p")
            if appointment_datetime.year == 1900:
                appointment_datetime = appointment_datetime.replace(year=datetime.now().year)
            
            # Check if date is in the past
            if appointment_datetime < datetime.now():
                appointment_datetime = appointment_datetime.replace(year=datetime.now().year + 1)
            
            # Get service duration
            duration_minutes = 60  # Default duration
            
            # Create event WITHOUT invalid attendees
            event = {
                'summary': f'{appointment.service} - {appointment.customer_name}',
                'description': (
                    f'Customer: {appointment.customer_name}\n'
                    f'Phone: {appointment.phone_number}\n'
                    f'Service: {appointment.service}\n'
                    f'Booked via: AI Receptionist\n\n'
                    f'📞 Call or text customer at: {appointment.phone_number}'
                ),
                'start': {
                    'dateTime': appointment_datetime.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': (appointment_datetime + timedelta(minutes=duration_minutes)).isoformat(),
                    'timeZone': self.timezone,
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 24 * 60},  # 1 day before
                        {'method': 'popup', 'minutes': 60},       # 1 hour before
                        {'method': 'email', 'minutes': 24 * 60},  # Email reminder
                    ],
                },
                'colorId': '2',  # Green color for appointments
            }
            
            # Only add valid email attendees if configured
            if self.owner_email and '@' in self.owner_email:
                event['attendees'] = [{'email': self.owner_email}]
            
            # Insert event
            event_result = self.service.events().insert(calendarId=self.calendar_id, body=event).execute()
            
            print(f"✅ Google Calendar event created: {event_result.get('htmlLink')}")
            return event_result.get('id')
            
        except Exception as e:
            print(f"❌ Error creating calendar event: {e}")
            self.logger.error(f"Calendar error details: {traceback.format_exc()}")
            return None
    
    def update_appointment(self, event_id: str, appointment: Appointment):
        """Update an existing Google Calendar event"""
        if not self.service or not event_id:
            return False
        
        try:
            # Parse date and time
            appointment_datetime = datetime.strptime(f"{appointment.date} {appointment.time}", "%A, %B %d %I:%M %p")
            if appointment_datetime.year == 1900:
                appointment_datetime = appointment_datetime.replace(year=datetime.now().year)
            
            # Check if date is in the past
            if appointment_datetime < datetime.now():
                appointment_datetime = appointment_datetime.replace(year=datetime.now().year + 1)
            
            duration_minutes = 60  # Default duration
            
            # Update event
            event = {
                'summary': f'{appointment.service} - {appointment.customer_name}',
                'description': (
                    f'Customer: {appointment.customer_name}\n'
                    f'Phone: {appointment.phone_number}\n'
                    f'Service: {appointment.service}\n'
                    f'Booked via: AI Receptionist\n'
                    f'📞 Call or text customer at: {appointment.phone_number}\n'
                    f'⚠️ MODIFIED: {datetime.now().strftime("%Y-%m-%d %H:%M")}'
                ),
                'start': {
                    'dateTime': appointment_datetime.isoformat(),
                    'timeZone': self.timezone,
                },
                'end': {
                    'dateTime': (appointment_datetime + timedelta(minutes=duration_minutes)).isoformat(),
                    'timeZone': self.timezone,
                },
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'popup', 'minutes': 24 * 60},
                        {'method': 'popup', 'minutes': 60},
                        {'method': 'email', 'minutes': 24 * 60},
                    ],
                },
                'colorId': '3',  # Purple color for modified appointments
            }
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=self.calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            print(f"✅ Google Calendar event updated: {updated_event.get('htmlLink')}")
            return True
            
        except Exception as e:
            print(f"❌ Error updating calendar event: {e}")
            self.logger.error(f"Calendar update error: {traceback.format_exc()}")
            return False
    
    def delete_appointment(self, event_id: str):
        """Delete a Google Calendar event"""
        if not self.service or not event_id:
            return False
        
        try:
            self.service.events().delete(
                calendarId=self.calendar_id,
                eventId=event_id
            ).execute()
            
            print(f"✅ Google Calendar event deleted: {event_id}")
            return True
            
        except Exception as e:
            print(f"❌ Error deleting calendar event: {e}")
            self.logger.error(f"Calendar delete error: {traceback.format_exc()}")
            return False
    
    def list_events(self, days=7):
        """List upcoming events with better display"""
        if not self.service:
            return []
        
        try:
            now = datetime.now()
            time_min = now.isoformat() + 'Z'
            time_max = (now + timedelta(days=days)).isoformat() + 'Z'
            
            print(f"\n📅 Fetching calendar events for next {days} days...")
            
            events_result = self.service.events().list(
                calendarId=self.calendar_id,
                timeMin=time_min,
                timeMax=time_max,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            if events:
                print(f"Found {len(events)} upcoming events:")
                for event in events:
                    start = event['start'].get('dateTime', event['start'].get('date'))
                    summary = event.get('summary', 'No title')
                    print(f"  • {summary}")
                    print(f"    Time: {start}")
            else:
                print("No upcoming events found.")
            
            return events
            
        except Exception as e:
            print(f"❌ Error listing events: {e}")
            return []

# ===========================
# MAIN RECEPTIONIST CLASS (ENHANCED WITH PERFORMANCE FEATURES)
# ===========================
class OutboundCallManager:
    def __init__(self, twilio_client, base_url, ai_model):
        self.client = twilio_client
        self.base_url = base_url
        self.ai_model = ai_model
        self.active_calls = {}

    def parse_user_objective(self, user_request: str):
        """Basic parser placeholder (avoids NameError if called)."""
        return (user_request or "").strip()

    def initiate_call(self, user_request, target_number, user_id):
        """Initiate an outbound call"""
        objective = self.parse_user_objective(user_request)
        call = self.client.calls.create(
            url=f"{self.base_url}/webhook/outbound_handler",
            to=target_number,
            from_=os.getenv('TWILIO_PHONE_NUMBER'),
            status_callback=f"{self.base_url}/webhook/outbound_status",
            record=True,
            machine_detection="DetectMessageEnd",
            send_digits=""
        )
        self.active_calls[call.sid] = {
            'user_id': user_id,
            'objective': objective,
            'target_number': target_number,
            'state': 'connecting',
            'menu_navigation': [],
            'transcript': []
        }
        def initiate_call(self, user_request, target_number, user_id):
            """Initiate an outbound call"""
            try:
                objective = self.parse_user_objective(user_request)
                call = self.client.calls.create(
                    url=f"{self.base_url}/webhook/outbound_handler",
                    to=target_number,
                    from_=os.getenv('TWILIO_PHONE_NUMBER'),
                    status_callback=f"{self.base_url}/webhook/outbound_status",
                    record=True,
                    machine_detection="DetectMessageEnd",
                    send_digits=""
                )
                self.active_calls[call.sid] = {
                    'user_id': user_id,
                    'objective': objective,
                    'target_number': target_number,
                    'state': 'connecting',
                    'menu_navigation': [],
                    'transcript': []
                }
                return call.sid
            except Exception as e:
                print(f"Error initiating call: {e}")
                return None




class TwilioAIReceptionist:
    def __init__(self):
        self.app = Flask(__name__)
        self.allowed_caller = os.getenv("MY_NUMBER" , "").strip()
        self.setup_logging()
        
        # Initialize performance monitor
        self.perf_monitor = PerformanceMonitor()
        
        # Load business configuration
        self.business_config = BusinessConfig.from_env()
        self.business_name = self.business_config.name
        self.business_hours = self._format_business_hours()
        
        # Initialize caller database
        self.caller_db = CallerDatabase()
        
        # Initialize caching system
        self.cache = MultiTierCache()
        
        # Initialize predictive engine
        self.predictive_engine = PredictiveResponseEngine()
        
        # Validate environment
        try:
            self.validate_environment()
        except ValueError as e:
            print(f"\n❌ Environment validation failed: {e}")
            print("\nPlease ensure your .env file contains:")
            print("TWILIO_ACCOUNT_SID=your_account_sid")
            print("TWILIO_AUTH_TOKEN=your_auth_token")
            print("TWILIO_PHONE_NUMBER=your_phone_number")
            print("BASE_URL=your_ngrok_url (optional)")
            raise
        
        self.account_sid = os.getenv('TWILIO_ACCOUNT_SID')
        self.auth_token = os.getenv('TWILIO_AUTH_TOKEN')
        self.twilio_phone_number = os.getenv('TWILIO_PHONE_NUMBER')
        
        self.client = Client(self.account_sid, self.auth_token)
        
        # Enhanced thread pool for parallel processing
        self.executor = concurrent.futures.ThreadPoolExecutor(
            max_workers=int(os.getenv('MAX_PARALLEL_TASKS', '10'))
        )
        
        # Initialize Google Calendar if enabled
        self.google_calendar = None
        if os.getenv('GOOGLE_CALENDAR_ENABLED', 'false').lower() == 'true' and GOOGLE_CALENDAR_AVAILABLE:
            if PYTZ_AVAILABLE:
                self.google_calendar = GoogleCalendarManager(os.getenv('GOOGLE_CALENDAR_ID'))
            else:
                print("⚠️ Google Calendar disabled - pytz is required for proper timezone support")
                print("⚠️ Install pytz with: pip install pytz")
        
        # Circuit breakers for external services
        self.gemini_circuit_breaker = CircuitBreaker(success_threshold=2)
        self.elevenlabs_circuit_breaker = CircuitBreaker(success_threshold=2)
        
        self.setup_elevenlabs()
        self.setup_gemini()
        
        # Performance settings
        self.enable_predictive = os.getenv('ENABLE_PREDICTIVE', 'true').lower() == 'true'
        self.enable_parallel = os.getenv('ENABLE_PARALLEL', 'true').lower() == 'true'
        self.response_timeout_ms = int(os.getenv('RESPONSE_TIMEOUT_MS', '500'))
        
        # Voice configuration
        self.voice_rotation = [
            os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9'),
        ]
        self.voice_index = 0
        
        self.voice_contexts = {
            'greeting': [os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9')],
            'confirmation': [os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9')],
            'thinking': [os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9')],
            'goodbye': [os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9')]
        }
        
        # Configuration settings
        self.conversation_style = os.getenv('CONVERSATION_STYLE', 'professional')
        self.use_filler_words = os.getenv('FILLER_WORDS', 'false').lower() == 'true'
        self.max_response_length = int(os.getenv('MAX_RESPONSE_LENGTH', '100'))
        
        self.enable_time_greetings = os.getenv('ENABLE_TIME_BASED_GREETINGS', 'false').lower() == 'true'
        self.enable_thinking = os.getenv('ENABLE_THINKING_SOUNDS', 'false').lower() == 'true'
        self.enable_acknowledgments = os.getenv('ENABLE_ACKNOWLEDGMENTS', 'true').lower() == 'true'
        self.vary_speech = os.getenv('VARY_SPEECH_RATE', 'false').lower() == 'true'
        
        self.speech_timeout = int(os.getenv('SPEECH_TIMEOUT', '2'))
        self.gather_timeout = int(os.getenv('GATHER_TIMEOUT', '5'))
        
        # Auto-correction mappings
        self.auto_corrections = self._load_auto_corrections()
        
        # Clarification templates
        self.clarification_templates = {
            'name': [
                "I didn't quite catch your name. Could you repeat it for me?",
                "Sorry, could you tell me your name again?",
                "I want to make sure I have your name correct. What was it?"
            ],
            'service': [
                f"I'm not sure which service you need. We offer {self._list_services()}.",
                f"Could you clarify what service you need? {self._list_services()}.",
                "Which of our services interests you?"
            ],
            'time': [
                "What time would work best for you?",
                "Could you give me a specific time?",
                "What time slot would be convenient? Morning or afternoon?"
            ],
            'date': [
                "Which day would you prefer? Today, tomorrow, or a specific date?",
                "Could you tell me what day works for you?",
                "When would you like to come in? What day?"
            ]
        }
        
        # Initialize data structures
        self.appointments = []
        self.appointments_file = 'appointments.json'
        self.packages = self.initialize_packages()
        self.call_sessions = {}
        self.audio_cache = {}
        self.response_predictions = {}
        
        # Out of scope keywords from business config
        self.out_of_scope_keywords = self.business_config.out_of_scope_keywords
        
        # Service descriptions from business config
        self.service_descriptions = self._generate_service_descriptions()
        
        # Common responses
        self.common_responses = self._generate_common_responses()
        
        # Available times from business config
        self.available_times = self.business_config.available_times
        
        # Setup routes and start background services
        self.setup_routes()
        self.load_appointments()
        self._start_background_services()
    
    def add_service(self, name, price, duration, description, keywords=None, priority=5):
        """Dynamically add a new service at runtime"""
        new_service = {
            "name": name,
            "price": price,
            "duration": duration,
            "description": description,
            "keywords": keywords or [],
            "priority": priority
        }
        self.business_config.services.append(new_service)
        print(f"✅ Added new service: {name}")
        
        # Update service descriptions
        self.service_descriptions = self._generate_service_descriptions()
        
        # Update packages
        key = name.lower().replace(' ', '_')
        self.packages[key] = Package(
            name=name,
            price=price,
            services=[description],
            duration=f"{duration} minutes",
            description=description
        )
    
    def remove_service(self, name):
        """Dynamically remove a service at runtime"""
        self.business_config.services = [
            s for s in self.business_config.services 
            if s['name'].lower() != name.lower()
        ]
        print(f"✅ Removed service: {name}")
        
        # Update service descriptions
        self.service_descriptions = self._generate_service_descriptions()
        
        # Remove from packages
        key = name.lower().replace(' ', '_')
        if key in self.packages:
            del self.packages[key]
    
    def list_current_services(self):
        """List all currently configured services"""
        print("\n📋 Current Services:")
        print("-" * 50)
        for service in sorted(self.business_config.services, key=lambda s: s.get('priority', 999)):
            print(f"• {service['name']}")
            print(f"  Price: {self.format_price(service['price'])}")
            print(f"  Duration: {service['duration']} minutes")
            print(f"  Description: {service['description']}")
            if service.get('keywords'):
                print(f"  Keywords: {', '.join(service['keywords'])}")
            print(f"  Priority: {service.get('priority', 'Not set')}")
            print()
        print("-" * 50)
    
    def validate_services(self):
        """Validate all services have required fields"""
        valid = True
        for i, service in enumerate(self.business_config.services):
            required_fields = ['name', 'price', 'duration', 'description']
            missing_fields = []
            
            for field in required_fields:
                if field not in service or service[field] is None:
                    missing_fields.append(field)
                    valid = False
            
            if missing_fields:
                print(f"⚠️ Service #{i+1} ({service.get('name', 'UNNAMED')}) missing fields: {', '.join(missing_fields)}")
            
            # Validate price is positive
            if 'price' in service and service['price'] <= 0:
                print(f"⚠️ Service '{service['name']}' has invalid price: ${service['price']}")
                valid = False
            
            # Validate duration is reasonable (5 min to 8 hours)
            if 'duration' in service and (service['duration'] < 5 or service['duration'] > 480):
                print(f"⚠️ Service '{service['name']}' has unusual duration: {service['duration']} minutes")
        
        # Check for duplicate service names
        service_names = [s['name'].lower() for s in self.business_config.services]
        if len(service_names) != len(set(service_names)):
            print("⚠️ WARNING: Duplicate service names detected!")
            valid = False
        
        if valid:
            print("✅ All services configured correctly!")
        return valid
    
    def get_service_by_name(self, name):
        """Get a specific service configuration by name"""
        for service in self.business_config.services:
            if service['name'].lower() == name.lower():
                return service
        return None
    
    def update_service_price(self, name, new_price):
        """Update the price of a specific service"""
        service = self.get_service_by_name(name)
        if service:
            old_price = service['price']
            service['price'] = new_price
            print(f"✅ Updated {name} price: ${old_price} → ${new_price}")
            
            # Update in packages too
            key = name.lower().replace(' ', '_')
            if key in self.packages:
                self.packages[key].price = new_price
        else:
            print(f"❌ Service '{name}' not found")
    
    def _format_business_hours(self):
        """Format business hours for speech"""
        days_open = []
        for day, hours in self.business_config.hours.items():
            if hours.lower() != 'closed':
                days_open.append(f"{day.capitalize()} {hours}")
        return ", ".join(days_open)
    
    def _list_services(self):
        """List services as a string for natural speech"""
        service_names = [s['name'] for s in self.business_config.services]
        if len(service_names) == 0:
            return "various services"
        elif len(service_names) == 1:
            return service_names[0]
        elif len(service_names) == 2:
            return f"{service_names[0]} and {service_names[1]}"
        else:
            return ", ".join(service_names[:-1]) + f", and {service_names[-1]}"
    
    def _load_auto_corrections(self):
        """Load auto-corrections based on business type"""
        base_corrections = {}
        
        # Add corrections specific to business type
        if self.business_config.type == 'dental':
            base_corrections.update({
                'feeling': 'filling',
                'feelings': 'fillings',
                'feel': 'fill',
                'felt': 'filled',
                'cleaning': ['cleaning', 'checkup'],
                'emergency': ['emergency', 'pain', 'urgent'],
                'filling': ['filling', 'cavity', 'hole'],
                'keys': 'teeth',
                'paid': 'pain',
                'tea': 'teeth',
                'tooth': 'teeth'
            })
        elif self.business_config.type == 'medical':
            base_corrections.update({
                'checkout': 'checkup',
                'physical': ['physical', 'exam', 'examination'],
                'ammual': 'annual',
                'docter': 'doctor'
            })
        elif self.business_config.type == 'salon':
            base_corrections.update({
                'died': 'dyed',
                'die': 'dye',
                'high lights': 'highlights',
                'low lights': 'lowlights'
            })
        elif self.business_config.type == 'restaurant':
            base_corrections.update({
                'reservation': ['reservation', 'table', 'booking'],
                'diner': 'dinner',
                'launch': 'lunch'
            })
        
        return base_corrections
    
    def _generate_service_descriptions(self):
        """Generate service descriptions from config"""
        descriptions = {}
        for service in self.business_config.services:
            descriptions[service['name'].lower()] = (
                f"{service['description']}. "
                f"It costs {self.format_price(service['price'])} and takes about {service['duration']} minutes."
            )
        return descriptions
    
    def _generate_common_responses(self):
        """Generate common responses based on business config"""
        # Format prices properly
        services_list = []
        for s in self.business_config.services:
            services_list.append(f"{s['name']} for {self.format_price(s['price'])}")
        
        services_text = "We offer " + ", ".join(services_list)
        
        return {
            "acknowledgments": [
                "Certainly",
                "Of course",
                "I understand",
                "Perfect",
                "Excellent",
                "Very good",
                "Thank you",
                "I've got that",
                "Absolutely",
                "That's great"
            ],
            "thinking": [
                "Let me check that for you",
                "One moment please",
                "Let me look that up",
                "I'll check on that",
                "Just a moment",
                "Let me find that information",
                "I'll verify that for you",
                "Let me pull up that information",
                "One moment while I check",
                "Let me see what's available"
            ],
            "anything_else": "Is there anything else I can help you with today?",
            "thank_you": f"Thank you for calling {self.business_config.name}. Have a wonderful day.",
            "processing": "Just a moment while I set that up for you",
            "out_of_scope": f"I'd be happy to help with {self.business_config.type} appointments and service information. How can I assist you with booking an appointment?",
            "services_offered": services_text + ". Which service would you like to book?",
            "appointment_lookup": "I'd be happy to check your appointment. May I have your name or phone number please?",
            "modification_options": "Would you like to change the date, change the time, or cancel your appointment?",
            "cancellation_warning": "I want to confirm that you'd like to cancel this appointment. Once cancelled, this cannot be undone. Should I proceed?"
        }
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_level = os.getenv('LOG_LEVEL', 'INFO')
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        
        logging.basicConfig(
            level=getattr(logging, log_level.upper()),
            format=log_format,
            handlers=[
                logging.FileHandler('receptionist.log'),
                logging.StreamHandler(sys.stdout)
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def format_price(self, price):
        """Format price to display nicely without unnecessary decimals"""
        if price == int(price):
            return f"${int(price)}"
        else:
            return f"${price:.2f}"
    
    def validate_environment(self):
        """Validate required environment variables"""
        required_vars = [
            'TWILIO_ACCOUNT_SID',
            'TWILIO_AUTH_TOKEN', 
            'TWILIO_PHONE_NUMBER'
        ]
        
        missing_vars = []
        for var in required_vars:
            value = os.getenv(var)
            if not value:
                missing_vars.append(var)
            elif var == 'TWILIO_ACCOUNT_SID' and not value.startswith('AC'):
                print(f"⚠️ Warning: {var} should start with 'AC'")
            elif var == 'TWILIO_PHONE_NUMBER' and not value.startswith('+'):
                print(f"⚠️ Warning: {var} should start with '+' (e.g., +1234567890)")
        
        if missing_vars:
            raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
        
        print("✅ Environment validation passed")
    
    def initialize_packages(self) -> Dict[str, Package]:
        """Initialize packages from business config"""
        packages = {}
        for service in self.business_config.services:
            key = service['name'].lower().replace(' ', '_')
            packages[key] = Package(
                name=service['name'],
                price=service['price'],
                services=[service['description']],
                duration=f"{service['duration']} minutes",
                description=service['description']
            )
        return packages
    
    def setup_gemini(self):
        """Setup Gemini AI with optimized settings"""
        self.gemini_api_key = os.getenv('GEMINI_API_KEY')
        self.use_ai = False
        
        if not self.gemini_api_key:
            print("ℹ️ No GEMINI_API_KEY found. Using basic conversation flow.")
            return
        
        try:
            genai.configure(api_key=self.gemini_api_key)
            
            # Configure safety settings to be more permissive
            self.safety_settings = [
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"}
            ]
            
            # Try models in order of preference
            models_to_try = [
                os.getenv('GEMINI_MODEL', 'gemini-2.0-flash-exp'),
                'gemini-1.5-flash',
                'gemini-1.5-pro',
                'gemini-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    self.model = genai.GenerativeModel(
                        model_name,
                        safety_settings=self.safety_settings,
                        generation_config={
                            'temperature': 0.3,  # Lower for consistency
                            'top_p': 0.8,
                            'top_k': 40,
                            'max_output_tokens': 150,  # Shorter for speed
                        }
                    )
                    
                    # Test the model
                    test_response = self.model.generate_content("Say 'Hello, I'm ready to help!'")
                    if test_response and test_response.text:
                        print(f"🚀 {model_name} enabled with optimized settings!")
                        self.use_ai = True
                        self.current_model = model_name
                        
                        # Start Gemini warm-up (keep this as requested)
                        self.executor.submit(self._keep_gemini_warm)
                        break
                except Exception as e:
                    print(f"⚠️ {model_name} failed: {e}")
                    continue
            
            if not self.use_ai:
                print("❌ All Gemini models failed. Using basic conversation flow.")
        
        except Exception as e:
            print(f"❌ Gemini setup failed: {e}")
            self.use_ai = False
    
    def setup_elevenlabs(self):
        """Setup ElevenLabs for voice synthesis"""
        self.use_elevenlabs = False
        try:
            if not ELEVENLABS_AVAILABLE:
                print("⚠️ ElevenLabs library not installed. Using Twilio default voice.")
                return
            
            api_key = os.getenv('ELEVENLABS_API_KEY')
            if not api_key:
                print("⚠️ ELEVENLABS_API_KEY not found. Using Twilio default voice.")
                return
            
            # Initialize ElevenLabs v2 client
            self.eleven_client = ElevenLabs(api_key=api_key)
            
            # Voice/model config
            self.voice_config = {
                'voice_id': os.getenv('ELEVENLABS_VOICE_ID', 'yj30vwTGJxSHezdAGsv9'),
                'model': os.getenv('ELEVENLABS_MODEL', 'eleven_turbo_v2_5'),
            }
            
            # Tiny test to verify credentials
            try:
                _ = self.eleven_client.text_to_speech.convert(
                    voice_id=self.voice_config['voice_id'], 
                    model_id=self.voice_config['model'], 
                    text='ok'
                )
                self.use_elevenlabs = True
                print(f"🎤 ElevenLabs enabled! Using voice {self.voice_config['voice_id']} ({self.voice_config['model']})")
            except Exception as e:
                print(f"⚠️ ElevenLabs test failed: {e}")
                self.use_elevenlabs = False
        except Exception as e:
            print(f"❌ ElevenLabs setup failed: {e}")
            self.use_elevenlabs = False
    
    def retry_with_backoff(self, func, max_retries=3, initial_delay=1):
        """Retry function with exponential backoff"""
        delay = initial_delay
        for attempt in range(max_retries):
            try:
                return func()
            except Exception as e:
                if attempt == max_retries - 1:
                    raise e
                print(f"Retry {attempt + 1}/{max_retries} after {delay}s delay...")
                time.sleep(delay)
                delay *= 2
    
    def _start_background_services(self):
        """Start background services"""
        # Keep Gemini warm (as requested)
        if self.use_ai:
            try:
                threading.Thread(target=self._keep_gemini_warm, daemon=True).start()
            except Exception as e:
                print(f"⚠️ Failed to start Gemini warm thread: {e}")
        
        # Performance stats logger
        def log_performance():
            while True:
                time.sleep(60)
                stats = self.perf_monitor.get_stats()
                if stats:
                    self.logger.info(f"Performance stats: {json.dumps(stats, indent=2)}")
        
        threading.Thread(target=log_performance, daemon=True).start()
    
    def _keep_gemini_warm(self):
        """Keep Gemini model warm"""
        while True:
            try:
                time.sleep(30)
                if self.use_ai:
                    warm_up_prompt = "Respond with 'ready' if you're active"
                    response = self.model.generate_content(
                        warm_up_prompt,
                        generation_config=genai.GenerationConfig(
                            max_output_tokens=10,
                            temperature=0.1
                        )
                    )
                    if response.text:
                        print("♨️ Gemini warm-up successful")
            except Exception as e:
                print(f"⚠️ Gemini warm-up failed: {e}")
                pass
    
    def generate_elevenlabs_audio_fast(self, text: str, voice_id: str = None, priority: bool = True):
        """Generate audio using ElevenLabs with caching"""
        if not getattr(self, 'use_elevenlabs', False):
            return None
        
        with self.perf_monitor.track('audio_generation'):
            def _generate():
                voice = voice_id or self.voice_config['voice_id']
                
                # Process text properly
                audio_text = self.clean_text_for_speech(text)
                audio_text = self.make_text_natural_for_speech(audio_text)
                audio_text = self.add_natural_pauses(audio_text)
                
                # Check cache
                cache_key = hashlib.md5(f"{voice}:{audio_text}".encode()).hexdigest()
                
                cached = self.cache.get(f"audio:{cache_key}")
                if cached:
                    self.perf_monitor.cache_hits += 1
                    return cached
                
                self.perf_monitor.cache_misses += 1
                
                print(f"🎤 Generating ElevenLabs audio for: '{audio_text[:60]}...'" )
                
                # Request audio stream from ElevenLabs
                stream = self.eleven_client.text_to_speech.convert(
                    voice_id=voice, 
                    model_id=self.voice_config['model'], 
                    text=audio_text,
                    optimize_streaming_latency=3  # Fastest setting
                )
                
                ts = datetime.now().strftime('%Y%m%d%H%M%S%f')
                filename = f"elevenlabs_{ts}.mp3"
                static_dir = os.path.join(os.path.dirname(__file__), 'static', 'audio')
                os.makedirs(static_dir, exist_ok=True)
                filepath = os.path.join(static_dir, filename)
                
                with open(filepath, 'wb') as f:
                    for chunk in stream:
                        if isinstance(chunk, bytes):
                            f.write(chunk)
                
                base_url = self._get_base_url()
                audio_url = f"{base_url}/static/audio/{filename}"
                
                # Cache the result
                self.cache.set(f"audio:{cache_key}", audio_url, ttl=3600)
                
                return audio_url
            
            try:
                if priority and hasattr(self, 'executor'):
                    future = self.executor.submit(lambda: self.elevenlabs_circuit_breaker.call(_generate))
                    return future.result(timeout=2)
                else:
                    return self.elevenlabs_circuit_breaker.call(_generate)
            except Exception as e:
                print(f"❌ ElevenLabs audio generation failed: {e}")
                return None
    
    def _get_base_url(self):
        """Get the base URL dynamically"""
        # First try environment variable
        base_url = os.getenv('BASE_URL')
        if base_url:
            return base_url.rstrip('/')
        
        # Try to get from Flask request context
        try:
            if has_request_context() and request:
                forwarded_proto = request.headers.get('X-Forwarded-Proto', request.scheme)
                forwarded_host = request.headers.get('X-Forwarded-Host', request.host)
                base_url = f"{forwarded_proto}://{forwarded_host}"
                os.environ['DYNAMIC_BASE_URL'] = base_url
                return base_url
        except Exception as e:
            print(f"⚠️ Could not get URL from request context: {e}")
        
        # Try cached dynamic URL
        cached_url = os.getenv('DYNAMIC_BASE_URL')
        if cached_url:
            return cached_url
        
        # Default fallback
        print("⚠️ WARNING: Using localhost URL - Twilio won't be able to access audio files!")
        print("⚠️ Set BASE_URL in your .env file to your ngrok or public URL")
        return "http://localhost:5000"
    
    def make_text_natural_for_speech(self, text: str) -> str:
        """Make text sound professional and clear for speech synthesis"""
        if not text:
            return text
        
        # Fix time pronunciation to be simple and clear
        time_replacements = [
            (r'\b8:00\s*AM\b', 'eight A M'),
            (r'\b8:30\s*AM\b', 'eight thirty A M'),
            (r'\b9:00\s*AM\b', 'nine A M'),
            (r'\b9:30\s*AM\b', 'nine thirty A M'),
            (r'\b10:00\s*AM\b', 'ten A M'),
            (r'\b10:30\s*AM\b', 'ten thirty A M'),
            (r'\b11:00\s*AM\b', 'eleven A M'),
            (r'\b11:30\s*AM\b', 'eleven thirty A M'),
            (r'\b12:00\s*PM\b', 'twelve noon'),
            (r'\b12:30\s*PM\b', 'twelve thirty P M'),
            (r'\b1:00\s*PM\b', 'one P M'),
            (r'\b1:30\s*PM\b', 'one thirty P M'),
            (r'\b2:00\s*PM\b', 'two P M'),
            (r'\b2:30\s*PM\b', 'two thirty P M'),
            (r'\b3:00\s*PM\b', 'three P M'),
            (r'\b3:30\s*PM\b', 'three thirty P M'),
            (r'\b4:00\s*PM\b', 'four P M'),
            (r'\b4:30\s*PM\b', 'four thirty P M'),
            (r'\b5:00\s*PM\b', 'five P M'),
        ]
        
        for pattern, replacement in time_replacements:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
        
        # General time pattern for any remaining times
        text = re.sub(r'\b(\d{1,2}):00\s*(AM|PM)\b', lambda m: f"{m.group(1)} {m.group(2)}", text)
        text = re.sub(r'\b(\d{1,2}):30\s*(AM|PM)\b', lambda m: f"{m.group(1)} thirty {m.group(2)}", text)
        text = re.sub(r'\b(\d{1,2}):15\s*(AM|PM)\b', lambda m: f"{m.group(1)} fifteen {m.group(2)}", text)
        text = re.sub(r'\b(\d{1,2}):45\s*(AM|PM)\b', lambda m: f"{m.group(1)} forty-five {m.group(2)}", text)
        
        # Use professional but natural contractions
        text = text.replace("I have", "I've")
        text = text.replace("I will", "I'll")
        text = text.replace("We have", "We've")
        text = text.replace("That is", "That's")
        text = text.replace("It is", "It's")
        text = text.replace("You are", "You're")
        text = text.replace("We are", "We're")
        
        return text
    
    def add_natural_pauses(self, text: str) -> str:
        """Add minimal, natural pauses to text for speech"""
        # Remove any existing multiple periods
        text = re.sub(r'\.{2,}', '.', text)
        
        # Clean up spacing around punctuation
        text = text.replace('.  ', '. ')
        text = text.replace(',  ', ', ')
        
        # Clean up any multiple spaces
        text = ' '.join(text.split())
        
        return text
    
    def clean_text_for_speech(self, text: str) -> str:
        """Clean text for speech synthesis"""
        if not text or text.strip() == "":
            return self.business_config.greeting
        
        text = str(text).strip()
        
        if text == "..." or text == "":
            return self.business_config.greeting
        
        # Remove HTML/XML tags
        text = re.sub(r'<[^>]*>', '', text)
        
        # Clean up special characters
        text = text.replace('&', 'and')
        text = text.replace('<', 'less than')
        text = text.replace('>', 'greater than')
        
        # Remove markdown formatting
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'_+', '', text)
        
        # Remove excessive dots
        text = re.sub(r'\.{2,}', '.', text)
        
        # Clean up spacing
        text = ' '.join(text.split())
        
        if not text.strip():
            return self.business_config.greeting
        
        return text.strip()
    
    def create_voice_response_fast(self, text: str, use_gather: bool = True, instant_ack: bool = True) -> VoiceResponse:
        """Create voice response with instant acknowledgment"""
        response = VoiceResponse()
        
        with self.perf_monitor.track('voice_response_creation'):
            clean_text = self.clean_text_for_speech(text)
            
            # For instant acknowledgment
            if instant_ack and use_gather and self.enable_acknowledgments:
                # Quick acknowledgment first
                ack = random.choice(self.business_config.acknowledgment_phrases)
                
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
                
                # Say acknowledgment immediately
                gather.say(ack, voice='alice')
                
                # Then generate and play the full response
                audio_url = None
                if self.use_elevenlabs:
                    audio_url = self.generate_elevenlabs_audio_fast(clean_text, priority=True)
                
                if audio_url and 'localhost' not in audio_url:
                    gather.play(audio_url)
                else:
                    gather.say(clean_text, voice='alice')
                
                gather.pause(length=0.5)
                response.append(gather)
            else:
                # Normal response without instant ack
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
                    
                    audio_url = None
                    if self.use_elevenlabs:
                        audio_url = self.generate_elevenlabs_audio_fast(clean_text, priority=True)
                    
                    if audio_url and 'localhost' not in audio_url:
                        gather.play(audio_url)
                    else:
                        gather.say(clean_text, voice='alice')
                    
                    gather.pause(length=0.5)
                    response.append(gather)
                else:
                    audio_url = None
                    if self.use_elevenlabs:
                        audio_url = self.generate_elevenlabs_audio_fast(clean_text, priority=True)
                    
                    if audio_url and 'localhost' not in audio_url:
                        response.play(audio_url)
                    else:
                        response.say(clean_text, voice='alice')
        
        return response
    
    def _generate_speech_hints(self):
        """Generate speech hints based on business type"""
        hints = ['appointment', 'book', 'schedule', 'yes', 'no', 'tomorrow', 'today', 'name', 'phone',
                 'cancel', 'change', 'modify', 'reschedule', 'check', 'my appointment']
        
        # Add service names
        for service in self.business_config.services:
            hints.append(service['name'].lower())
        
        # Add business-specific hints
        if self.business_config.type == 'dental':
            hints.extend(['tooth', 'pain', 'cleaning', 'filling', 'crown', 'emergency'])
        elif self.business_config.type == 'medical':
            hints.extend(['doctor', 'checkup', 'physical', 'sick', 'prescription'])
        elif self.business_config.type == 'salon':
            hints.extend(['haircut', 'color', 'styling', 'trim', 'highlights'])
        elif self.business_config.type == 'restaurant':
            hints.extend(['table', 'reservation', 'party', 'dinner', 'lunch'])
        
        return ','.join(hints)
    
    def detect_spam(self, caller_profile: CallerProfile, user_input: str) -> bool:
        """Detect spam calls using multiple signals"""
        spam_score = 0.0
        
        # Check for spam keywords
        user_input_lower = user_input.lower()
        for indicator in self.business_config.spam_indicators:
            if indicator in user_input_lower:
                spam_score += 0.3
        
        # Check call patterns
        if caller_profile.call_count > 10 and not caller_profile.appointments:
            spam_score += 0.2
        
        # Check for robocall patterns (very short responses)
        if len(user_input) < 5 and caller_profile.call_count > 3:
            spam_score += 0.2
        
        # Update caller's spam score
        caller_profile.spam_score = max(caller_profile.spam_score, spam_score)
        
        return spam_score > 0.5
    
    def handle_chaos(self, session: CallSession, user_input: str) -> str:
        """Handle confused or rambling callers"""
        # Detect confusion (very long input, no clear intent)
        if len(user_input) > 200 or user_input.count(',') > 5:
            return "I want to make sure I help you properly. Are you looking to schedule an appointment?"
        
        # Detect repetition
        if session.last_ai_response and user_input.lower() == session.last_ai_response.lower():
            return "It seems we might have a connection issue. Can you tell me what you need help with?"
        
        # Default redirection
        return None
    
    def setup_routes(self):
        """Setup Flask routes with enhanced handlers"""
        
        @self.app.route('/webhook/voice', methods=['GET','POST'])
        def handle_voice_call():
         from twilio.twiml.voice_response import VoiceResponse
         from_number = request.values.get("From" , "")
         vr = VoiceResponse()

         if self.allowed_caller and from_number != self.allowed_caller:
             vr.say("This line is in developer testing. Please try again later." , voice = "alice")
             vr.hangup()
             return Response(str(vr), mimetype='text/xml')

            
            
            
        try:
                with self.perf_monitor.track('voice_webhook'):
                    print("📞 Voice webhook called!")
                    self.logger.info("Voice webhook called")
                    return self.handle_incoming_call_enhanced()
        except Exception as e:
                self.logger.error(f"Error in voice webhook: {e}\n{traceback.format_exc()}")
                print(f"❌ Voice webhook error: {e}")
                print(traceback.format_exc())
                response = VoiceResponse()
                response.say("I'm sorry, I'm having technical difficulties. Please call back later.", voice='alice')
                response.hangup()
                return Response(str(response), mimetype='text/xml')
        
        @self.app.route('/webhook/gather', methods=['POST'])
        def handle_gather():
            try:
                with self.perf_monitor.track('gather_webhook'):
                    call_sid = request.values.get('CallSid')
                    speech_result = request.values.get('SpeechResult', '')
                    
                    self.logger.info(f"Gather webhook called - CallSid: {call_sid}, Speech: '{speech_result}'")
                    
                    if call_sid not in self.call_sessions:
                        self.logger.warning(f"Session not found for CallSid: {call_sid}, creating new session")
                        return self.handle_incoming_call_enhanced()
                    
                    if not speech_result:
                        self.logger.info("No speech detected, re-prompting")
                        response = VoiceResponse()
                        response.say("I didn't catch that. Could you please repeat?", voice='alice')
                        response.redirect('/webhook/voice', method='POST')
                        return str(response)
                    
                    session = self.call_sessions[call_sid]
                    session.response_start_time = time.time()
                    
                    print(f"🗣️ User said: '{speech_result}'")
                    self.logger.info(f"User said: '{speech_result}', State: {session.state}")
                    
                    return self.handle_user_input_lightning(call_sid, speech_result)
                    
            except Exception as e:
                self.logger.error(f"Error in gather webhook: {e}\n{traceback.format_exc()}")
                print(f"❌ Gather webhook error: {e}")
                response = VoiceResponse()
                response.say("Let me try that again.", voice='alice')
                response.redirect('/webhook/voice', method='POST')
                return str(response)
        
        @self.app.route('/webhook/process', methods=['GET','POST'])
        def handle_process():
            try:
                call_sid = request.values.get('CallSid')
                speech_result = request.values.get('SpeechResult', '')
                print(f"Processing input in /webhook/process:'{speech_result}' for CallSid: {call_sid}")
                return self.handle_user_input_lightning(call_sid, speech_result)
            except Exception as e:
                self.logger.error(f"Error in process webhook: {e}\n{traceback.format_exc()}")
                response = VoiceResponse()
                response.say("Let me try that again.", voice='alice')
                response.redirect('/webhook/voice', method='POST')
                return str(response)
        
        @self.app.route('/webhook/status', methods=['POST'])
        def handle_status():
            try:
                call_sid = request.values.get('CallSid')
                call_status = request.values.get('CallStatus')
                
                self.logger.info(f"Call status update - CallSid: {call_sid}, Status: {call_status}")
                
                # Clean up session if call ended
                if call_status in ['completed', 'failed', 'busy', 'no-answer']:
                    if call_sid in self.call_sessions:
                        # Save caller profile
                        session = self.call_sessions[call_sid]
                        if session.caller_profile:
                            self.caller_db.save()
                        del self.call_sessions[call_sid]
                        print(f"🧹 Cleaned up session for {call_sid}")
                
                return Response('', mimetype='text/plain')
                
            except Exception as e:
                self.logger.error(f"Error in status webhook: {e}")
                return Response('', mimetype='text/plain')
        
        @self.app.route('/static/audio/<filename>')
        def serve_audio(filename):
            try:
                audio_path = os.path.join(os.path.dirname(__file__), 'static', 'audio', filename)
                if not os.path.exists(audio_path):
                    time.sleep(0.5)
                if os.path.exists(audio_path):
                    return send_file(audio_path, mimetype='audio/mpeg')
                else:
                    self.logger.error(f"Audio file not found: {filename}")
                    return "File not found", 404
            except Exception as e:
                self.logger.error(f"Error serving audio: {e}")
                return "Error serving file", 500
        
        @self.app.route('/webhook/followup', methods=['POST'])
        def handle_followup():
            try:
                call_sid = request.values.get('CallSid')
                speech_result = request.values.get('SpeechResult', '').lower()
                
                response = VoiceResponse()
                
                if any(word in speech_result for word in ['yes', 'yeah', 'sure', 'please', 'another', 'something else', 'yep', 'definitely']):
                    followups = [
                        "Of course! What else can I help you with?",
                        "Absolutely! What would you like to know?",
                        "Sure thing! How else can I assist you?",
                        "I'd be happy to help! What do you need?"
                    ]
                    followup_text = followups[hash(call_sid) % len(followups)]
                    response.say(followup_text, voice='alice')
                    response.redirect('/webhook/voice', method='POST')
                else:
                    goodbyes = [
                        f"Perfect! Thanks for calling {self.business_config.name}. Have a wonderful day!",
                        f"Wonderful! Thank you for choosing {self.business_config.name}. Take care!",
                        "Great! We look forward to seeing you. Have a great day!",
                        "Excellent! Thanks for your time. Have a fantastic day!"
                    ]
                    goodbye_text = goodbyes[hash(call_sid) % len(goodbyes)]
                    response.say(goodbye_text, voice='alice')
                    response.hangup()
                
                return str(response)
                
            except Exception as e:
                self.logger.error(f"Error in followup webhook: {e}")
                response = VoiceResponse()
                response.say("Thank you for calling! Have a great day!", voice='alice')
                response.hangup()
                return str(response)
        
        @self.app.route('/webhook/final_check', methods=['POST'])
        def handle_final_check():
            try:
                call_sid = request.values.get('CallSid')
                speech_result = request.values.get('SpeechResult', '').lower()
                
                response = VoiceResponse()
                
                if any(word in speech_result for word in ['yes', 'yeah', 'question', 'else', 'another', 'change', 'different']):
                    response.say("Of course! What would you like to know?", voice='alice')
                    response.redirect('/webhook/voice', method='POST')
                else:
                    goodbye_messages = [
                        f"Perfect! Thank you for booking with {self.business_config.name}. We'll see you soon!",
                        f"Wonderful! Thanks for choosing {self.business_config.name}. Have a great day!",
                        f"Excellent! We look forward to your visit. Take care!",
                        f"Great! See you at your appointment. Have a fantastic day!"
                    ]
                    
                    goodbye = goodbye_messages[hash(call_sid) % len(goodbye_messages)]
                    
                    if getattr(self, 'use_elevenlabs', False):
                        goodbye_voice = self.voice_contexts['goodbye'][hash(call_sid) % len(self.voice_contexts['goodbye'])]
                        goodbye_audio = self.generate_elevenlabs_audio_fast(goodbye, voice_id=goodbye_voice)
                        if goodbye_audio and 'localhost' not in goodbye_audio:
                            response.play(goodbye_audio)
                        else:
                            response.say(goodbye, voice='alice')
                    else:
                        response.say(goodbye, voice='alice')
                    
                    response.pause(length=0.5)
                    response.hangup()
                
                return str(response)
                
            except Exception as e:
                self.logger.error(f"Error in final_check webhook: {e}")
                response = VoiceResponse()
                response.say("Thank you for calling! Have a great day!", voice='alice')
                response.hangup()
                return str(response)
        
        @self.app.route('/admin/appointments', methods=['GET'])
        def view_appointments():
            return self.get_appointments_json()
        
        @self.app.route('/admin/stats', methods=['GET'])
        def view_stats():
            return self.get_call_stats()
        
        @self.app.route('/admin/performance', methods=['GET'])
        def view_performance():
            """Performance metrics endpoint"""
            stats = self.perf_monitor.get_stats()
            circuit_states = {
                'gemini': self.gemini_circuit_breaker.get_state(),
                'elevenlabs': self.elevenlabs_circuit_breaker.get_state()
            }
            
            return json.dumps({
                'performance': stats,
                'circuit_breakers': circuit_states,
                'cache_stats': self.cache.cache_stats,
                'active_sessions': len(self.call_sessions),
                'caller_profiles': len(self.caller_db.profiles)
            }, indent=2)
        
        @self.app.route('/admin/calendar', methods=['GET'])
        def view_calendar():
            """Debug route to check calendar availability"""
            if not self.google_calendar:
                return "<h1>Google Calendar not enabled</h1>"
            
            # List events and check availability
            events = self.google_calendar.list_events(7)
            
            # Check availability for today and tomorrow
            today = datetime.now()
            today_str = today.strftime("%A, %B %d")
            tomorrow_str = (today + timedelta(days=1)).strftime("%A, %B %d")
            
            html = "<h1>📅 Google Calendar Debug</h1>"
            html += f"<h2>Timezone: {self.google_calendar.timezone}</h2>"
            html += f"<h2>pytz Available: {'✅ Yes' if PYTZ_AVAILABLE else '❌ No'}</h2>"
            html += f"<h2>Upcoming Events ({len(events)} total)</h2>"
            html += "<ul>"
            for event in events:
                start = event.get('start', {}).get('dateTime', 'No time')
                summary = event.get('summary', 'No title')
                html += f"<li>{summary} - {start}</li>"
            html += "</ul>"
            
            html += f"<h2>Available Times for {today_str}</h2>"
            html += "<ul>"
            for time_slot in self.available_times:
                is_available = self.google_calendar.check_availability(today_str, time_slot)
                status = "✅ Available" if is_available else "❌ Booked"
                html += f"<li>{time_slot}: {status}</li>"
            html += "</ul>"
            
            html += f"<h2>Available Times for {tomorrow_str}</h2>"
            html += "<ul>"
            for time_slot in self.available_times:
                is_available = self.google_calendar.check_availability(tomorrow_str, time_slot)
                status = "✅ Available" if is_available else "❌ Booked"
                html += f"<li>{time_slot}: {status}</li>"
            html += "</ul>"
            
            # First available slot
            next_available = self.get_first_available_time()
            if isinstance(next_available, tuple):
                html += f"<h2>Next Available Slot</h2>"
                html += f"<p>{next_available[0]} at {next_available[1]}</p>"
            
            return html
        
        @self.app.route('/test', methods=['GET'])
        def test():
            """Enhanced system status page with metrics"""
            base_url = self._get_base_url()
            
            # Get performance stats
            stats = self.perf_monitor.get_stats()
            perf_html = ""
            for op, metrics in stats.items():
                if isinstance(metrics, dict) and 'avg_ms' in metrics:
                    perf_html += f"<li>{op}: {metrics['avg_ms']:.1f}ms avg ({metrics['count']} calls)</li>"
            
            return f"""
            <h1>🚀 Never-Fail AI Receptionist Status</h1>
            <hr>
            <h2>Business Configuration</h2>
            <p><strong>Name:</strong> {self.business_config.name}</p>
            <p><strong>Type:</strong> {self.business_config.type}</p>
            <p><strong>Services:</strong> {self._list_services()}</p>
            <hr>
            <h2>System Status</h2>
            <p>✅ Never-Fail Features: ENABLED</p>
            <p>Caller Database: {len(self.caller_db.profiles)} profiles</p>
            <p>Cache Hit Rate: {self.cache.cache_stats['hits']/(self.cache.cache_stats['hits']+self.cache.cache_stats['misses']+0.01)*100:.1f}%</p>
            <p>Active Sessions: {len(self.call_sessions)}</p>
            <p>ElevenLabs: {'✅ Enabled' if self.use_elevenlabs else '❌ Disabled'}</p>
            <p>AI: {'✅ Enabled' if self.use_ai else '❌ Disabled'}</p>
            <p>Model: {self.current_model if self.use_ai else 'N/A'}</p>
            <p>Google Calendar: {'✅ Enabled' if self.google_calendar else '❌ Disabled'}</p>
            <p>pytz (timezone support): {'✅ Available' if PYTZ_AVAILABLE else '❌ Not installed'}</p>
            <p>Timezone: {os.getenv('TIMEZONE', 'America/New_York')}</p>
            <p>BASE_URL: {base_url}</p>
            <p>Webhook URL: {base_url}/webhook/voice</p>
            <hr>
            <h2>Performance Metrics</h2>
            <ul>
            {perf_html}
            </ul>
            <hr>
            <h2>Circuit Breakers</h2>
            <p>Gemini: {self.gemini_circuit_breaker.state} ({self.gemini_circuit_breaker.failure_count} failures)</p>
            <p>ElevenLabs: {self.elevenlabs_circuit_breaker.state} ({self.elevenlabs_circuit_breaker.failure_count} failures)</p>
            <hr>
            <h2>Environment Variables</h2>
            <ul>
                <li>TWILIO_ACCOUNT_SID: {'✅ Set' if os.getenv('TWILIO_ACCOUNT_SID') else '❌ Not set'}</li>
                <li>TWILIO_AUTH_TOKEN: {'✅ Set' if os.getenv('TWILIO_AUTH_TOKEN') else '❌ Not set'}</li>
                <li>TWILIO_PHONE_NUMBER: {'✅ Set' if os.getenv('TWILIO_PHONE_NUMBER') else '❌ Not set'}</li>
                <li>GEMINI_API_KEY: {'✅ Set' if os.getenv('GEMINI_API_KEY') else '❌ Not set'}</li>
                <li>ELEVENLABS_API_KEY: {'✅ Set' if os.getenv('ELEVENLABS_API_KEY') else '❌ Not set'}</li>
                <li>GOOGLE_CALENDAR_ENABLED: {os.getenv('GOOGLE_CALENDAR_ENABLED', 'false')}</li>
                <li>CALENDAR_OWNER_EMAIL: {os.getenv('CALENDAR_OWNER_EMAIL', 'Not set')}</li>
                <li>TIMEZONE: {os.getenv('TIMEZONE', 'America/New_York')}</li>
            </ul>
            <hr>
            <h2>Quick Links</h2>
            <ul>
                <li><a href="/admin/performance">Performance Details</a></li>
                <li><a href="/admin/appointments">View Appointments</a></li>
                <li><a href="/admin/stats">View Stats</a></li>
                {'<li><a href="/admin/calendar">Calendar Debug</a></li>' if self.google_calendar else ''}
            </ul>
            """
    
    def handle_incoming_call_enhanced(self):
        """Handle incoming calls with VIP recognition"""
        try:
            call_sid = request.values.get('CallSid')
            from_number = request.values.get('From')
            
            self.logger.info(f"Incoming call from {from_number}, CallSid: {call_sid}")
            print(f"📞 Incoming call from {from_number}")
            
            # Get or create caller profile
            caller_profile = self.caller_db.get_or_create(from_number)
            
            # Create new session with caller info
            session = CallSession(call_sid=call_sid)
            session.customer_data['from_number'] = from_number
            session.caller_profile = caller_profile
            self.call_sessions[call_sid] = session
            
            # Personalized greeting based on caller history
            if caller_profile.vip_status:
                if caller_profile.name:
                    greeting = f"Welcome back, {caller_profile.name}! Great to hear from you again. How can I help you today?"
                else:
                    greeting = f"Welcome back to {self.business_config.name}! You're one of our valued customers. How can I help you today?"
            elif caller_profile.call_count > 1:
                if caller_profile.name:
                    greeting = f"Welcome back, {caller_profile.name}! How can I help you today?"
                else:
                    greeting = f"Welcome back to {self.business_config.name}! How can I help you today?"
            else:
                hour = datetime.now().hour
                time_greeting = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
                greeting = f"{time_greeting}! Thanks for calling {self.business_config.name}, this is Sarah. How can I help you today?"
            
            response = self.create_voice_response_fast(greeting, use_gather=True, instant_ack=False)
            return Response(str(response), mimetype='text/xml')
        except Exception as e:
            self.logger.error(f"Error in handle_incoming_call_enhanced: {e}\n{traceback.format_exc()}")
            print(f"❌ Error in handle_incoming_call_enhanced: {e}")
            print(traceback.format_exc())
            response = VoiceResponse()
            response.say("Hello! I'm having a small technical issue. Please hold on.", voice='alice')
            response.pause(length=1)
            response.say("How can I help you today?", voice='alice')
            return Response(str(response), mimetype='text/xml')
    
    def handle_user_input_lightning(self, call_sid: str, speech_result: str):
        """Handle user input with lightning-fast processing"""
        try:
            if call_sid not in self.call_sessions:
                self.logger.warning(f"Session not found for {call_sid}, creating new")
                return self.handle_incoming_call_enhanced()
            
            session = self.call_sessions[call_sid]
            session.attempts += 1
            
            with self.perf_monitor.track('total_response_time'):
                # Check for spam
                if self.detect_spam(session.caller_profile, speech_result):
                    response = VoiceResponse()
                    response.say("I can only help with appointment scheduling. If you need assistance, please call back.", voice='alice')
                    response.hangup()
                    return str(response)
                
                # Check for chaos/confusion
                chaos_response = self.handle_chaos(session, speech_result)
                if chaos_response:
                    return str(self.create_voice_response_fast(chaos_response, use_gather=True))
                
                # Auto-correct common mistakes
                speech_result = self.auto_correct_input(speech_result)
                
                # Check if user wants to modify/cancel appointment
                if any(phrase in speech_result.lower() for phrase in [
                    'change my appointment', 'cancel my appointment', 'reschedule', 
                    'modify my appointment', 'check my appointment'
                ]):
                    return self.handle_appointment_modification(session, speech_result)
                
                # Check if user is asking about services
                if any(phrase in speech_result.lower() for phrase in ['what do you offer', 'what services', 'what do you do', 'services do you']):
                    response = self.create_voice_response_fast(self.common_responses["services_offered"], use_gather=True)
                    return str(response)
                
                # Check for empty or very short input
                if not speech_result.strip() or len(speech_result.strip()) < 2:
                    response = VoiceResponse()
                    response.say("I didn't catch that. Could you please repeat?", voice='alice')
                    response.redirect('/webhook/voice', method='POST')
                    return str(response)
                
                # Parallel processing if enabled
                if self.enable_parallel:
                    futures = {}
                    
                    # Start AI response generation
                    if self.use_ai:
                        futures['ai'] = self.executor.submit(
                            self._get_gemini_response_lightning, session, speech_result
                        )
                    
                    # Start extraction
                    futures['extract'] = self.executor.submit(
                        self.extract_booking_info, session, speech_result
                    )
                    
                    # Start predictive response
                    if self.enable_predictive:
                        futures['predict'] = self.executor.submit(
                            self.predictive_engine.predict_next_response,
                            session.state,
                            session.customer_data
                        )
                    
                    # Wait for results with timeout
                    try:
                        # Get extraction first (fastest)
                        if 'extract' in futures:
                            futures['extract'].result(timeout=0.1)
                        
                        # Check if booking complete
                        if self.check_booking_complete(session):
                            return self._finish_booking_lightning(session)
                        
                        # Get AI response or prediction
                        ai_response = None
                        if 'ai' in futures:
                            try:
                                ai_response = futures['ai'].result(
                                    timeout=self.response_timeout_ms / 1000
                                )
                            except concurrent.futures.TimeoutError:
                                self.perf_monitor.ai_timeouts += 1
                                # Fall back to prediction
                                if 'predict' in futures:
                                    ai_response = futures['predict'].result(timeout=0.05)
                        
                        if not ai_response and 'predict' in futures:
                            ai_response = futures['predict'].result(timeout=0.05)
                        
                        if not ai_response:
                            ai_response = self._get_instant_fallback(session, speech_result)
                        
                    except Exception as e:
                        print(f"⚠️ Parallel processing error: {e}")
                        ai_response = self._get_instant_fallback(session, speech_result)
                else:
                    # Sequential processing (fallback)
                    self.extract_booking_info(session, speech_result)
                    
                    if self.check_booking_complete(session):
                        return self._finish_booking_lightning(session)
                    
                    if self.use_ai:
                        ai_response = self._get_gemini_response_lightning(session, speech_result)
                    else:
                        ai_response = self._get_instant_fallback(session, speech_result)
                
                # Update session
                session.last_ai_response = ai_response
                session.conversation_context.append({"role": "user", "content": speech_result})
                session.conversation_context.append({"role": "assistant", "content": ai_response})
                session.conversation_context = session.conversation_context[-20:]
                
                # Check if AI is trying to confirm a completed booking
                confirming_words = ['confirmed', 'all set', 'booked', 'scheduled', "you're all set", "got you down for", "see you on", "scheduled you for"]
                if any(word in ai_response.lower() for word in confirming_words):
                    if self.check_booking_complete(session):
                        return self._finish_booking_lightning(session)
                
                # Create response with instant acknowledgment
                response_twiml = self.create_voice_response_fast(
                    ai_response,
                    use_gather=True,
                    instant_ack=True
                )
                
                return str(response_twiml)
                
        except Exception as e:
            self.logger.error(f"Error in handle_user_input_lightning: {e}\n{traceback.format_exc()}")
            print(f"❌ Error in handle_user_input_lightning: {e}")
            
            # Better error recovery
            response = VoiceResponse()
            response.say(
                "I apologize for the technical difficulty. Let me help you book your appointment. "
                "What service would you like to schedule?", 
                voice='alice'
            )
            response.redirect('/webhook/voice', method='POST')
            return str(response)
    
    def _get_gemini_response_lightning(self, session, user_input):
        """Get Gemini response with ultra-fast optimization"""
        if not self.use_ai:
            return self._get_instant_fallback(session, user_input)
        
        try:
            # Check cache first
            context_key = f"{session.state}:{session.customer_data}:{user_input}"
            context_hash = hashlib.md5(context_key.encode()).hexdigest()
            
            cached = self.cache.get_cached_response(context_hash)
            if cached:
                self.perf_monitor.cache_hits += 1
                return cached
            
            # Generate new response
            with self.perf_monitor.track('gemini_generation'):
                # Build context-aware prompt
                booking_status = self._get_booking_status(session)
                next_action = self._determine_next_action(session)
                
                # Check for caller history
                caller_note = ""
                if session.caller_profile:
                    if session.caller_profile.vip_status:
                        caller_note = "\nThis is a VIP customer - provide exceptional service!"
                    if session.caller_profile.preferred_service:
                        caller_note += f"\nThey usually book: {session.caller_profile.preferred_service}"
                
                prompt = f"""{self.business_config.get_context_prompt()}

Current booking status:
{booking_status}
{caller_note}

Customer just said: "{user_input}"

{next_action}

Respond in 40-80 words. Be natural, warm, and complete your sentences.
Use transition phrases like "Let me check that" when processing.
"""
                
                response = self.model.generate_content(
                    prompt,
                    generation_config={
                        'temperature': 0.3,
                        'max_output_tokens': 100
                    }
                )
                
                if response and response.text:
                    ai_text = self._clean_ai_response(response.text.strip())
                    # Cache the response
                    self.cache.set(f"response:{context_hash}", ai_text, ttl=1800)
                    return ai_text
                
        except Exception as e:
            print(f"⚠️ Gemini error: {e}")
        
        return self._get_instant_fallback(session, user_input)
    
    def _get_instant_fallback(self, session, user_input):
        """Get instant fallback response based on context"""
        # Use predictive engine first
        predicted = self.predictive_engine.predict_next_response(
            session.state,
            session.customer_data
        )
        
        if predicted:
            return predicted
        
        # Standard fallbacks
        if not session.customer_data.get('name'):
            return "I'd love to help you book an appointment. What's your name?"
        elif not session.customer_data.get('service'):
            return f"What type of service do you need, {session.customer_data.get('name', 'there')}?"
        elif not session.customer_data.get('date'):
            return "What day works best for you?"
        elif not session.customer_data.get('time'):
            return "What time would be convenient?"
        else:
            return "Let me confirm your appointment details."
    
    def _finish_booking_lightning(self, session):
        """Complete booking with lightning speed"""
        with self.perf_monitor.track('booking_completion'):
            # Check availability if calendar enabled
            if self.google_calendar:
                if not self.google_calendar.check_availability(
                    session.customer_data['date'],
                    session.customer_data['time']
                ):
                    response = VoiceResponse()
                    response.say(
                        f"I'm sorry, {session.customer_data['time']} is no longer available. "
                        "Let me find another time for you.",
                        voice='alice'
                    )
                    session.customer_data.pop('time', None)
                    response.redirect('/webhook/voice', method='POST')
                    return str(response)
            
            # Create appointment
            appointment = Appointment(
                customer_name=session.customer_data['name'],
                phone_number=session.customer_data.get('phone', session.customer_data.get('from_number', 'Unknown')),
                service=session.customer_data['service'],
                date=session.customer_data['date'],
                time=session.customer_data['time'],
                notes=session.customer_data.get('notes', ''),
                call_sid=session.call_sid,
                created_at=datetime.now().isoformat()
            )
            
            # Add to calendar
            if self.google_calendar:
                event_id = self.google_calendar.create_appointment(appointment)
                if event_id:
                    appointment.google_event_id = event_id
            
            # Save appointment
            self.appointments.append(appointment)
            self.save_appointments()
            
            # Update caller profile
            if session.caller_profile:
                session.caller_profile.appointments.append({
                    'date': appointment.date,
                    'time': appointment.time,
                    'service': appointment.service
                })
                if not session.caller_profile.name and session.customer_data.get('name'):
                    session.caller_profile.name = session.customer_data['name']
                if not session.caller_profile.preferred_service:
                    session.caller_profile.preferred_service = appointment.service
                self.caller_db.save()
            
            # Send SMS confirmation (async)
            self.executor.submit(self.send_sms_confirmation, appointment)
            
            # Create confirmation
            confirmation = f"Perfect! You're all set for {appointment.service} on {appointment.date} at {appointment.time}. "
            
            if session.caller_profile and session.caller_profile.vip_status:
                confirmation += "As always, we appreciate your continued trust in us. "
            
            confirmation += f"Thank you for choosing {self.business_config.name}!"
            
            response = VoiceResponse()
            
            # Use cached audio if available
            if self.use_elevenlabs:
                audio_url = self.generate_elevenlabs_audio_fast(confirmation, priority=True)
                if audio_url and 'localhost' not in audio_url:
                    response.play(audio_url)
                else:
                    response.say(confirmation, voice='alice')
            else:
                response.say(confirmation, voice='alice')
            
            response.pause(length=1)
            response.hangup()
            
            self.perf_monitor.successful_calls += 1
            
            return str(response)
    
    # Keep all the existing methods from the original file...
    # (All other methods remain the same as in the original file)
    
    def handle_appointment_modification(self, session, user_input):
        """Handle appointment modification/cancellation requests"""
        user_input_lower = user_input.lower()
        
        # Determine the type of modification
        if 'cancel' in user_input_lower:
            session.modification_mode = 'cancel'
        elif 'change' in user_input_lower or 'reschedule' in user_input_lower or 'modify' in user_input_lower:
            session.modification_mode = 'modify'
        else:
            session.modification_mode = 'check'
        
        # Try to find existing appointment
        appointments = []
        
        # Check if they provided name or phone in the same sentence
        name_match = re.search(r"(?:my name is|i'm|i am|this is)\s+([a-z]+(?:\s+[a-z]+)*)", user_input_lower)
        phone_match = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', user_input)
        
        if name_match:
            name = name_match.group(1).title()
            appointments = self.find_appointment_by_name(name)
        elif phone_match:
            phone = re.sub(r'[^\d]', '', phone_match.group(1))
            appointments = self.find_appointment_by_phone(phone)
        elif session.customer_data.get('from_number'):
            # Try using caller ID
            appointments = self.find_appointment_by_phone(session.customer_data['from_number'])
        
        if appointments:
            if len(appointments) == 1:
                # Found exactly one appointment
                session.existing_appointment = appointments[0]
                return self._handle_single_appointment_found(session, appointments[0])
            else:
                # Multiple appointments found
                return self._handle_multiple_appointments_found(session, appointments)
        else:
            # No appointment found, ask for identification
            response_text = "I'd be happy to help with your appointment."
            # No appointment found, ask for identification
            response_text = "I'd be happy to help with your appointment. Could you please tell me your name or the phone number you used to book?"
            response = self.create_voice_response_fast(response_text, use_gather=True)
            return str(response)
    
    def _handle_single_appointment_found(self, session, appointment):
        """Handle when a single appointment is found"""
        if session.modification_mode == 'cancel':
            # Confirm cancellation
            response_text = (f"I found your {appointment.service} appointment on {appointment.date} at {appointment.time}. "
                           "Are you sure you want to cancel this appointment? Say yes to confirm or no to keep it.")
            session.state = 'confirming_cancellation'
        elif session.modification_mode == 'modify':
            response_text = (f"I found your {appointment.service} appointment on {appointment.date} at {appointment.time}. "
                           "What would you like to change - the date, the time, or the service?")
            session.state = 'modification_choice'
        else:  # check
            response_text = (f"I found your appointment! You have a {appointment.service} scheduled for "
                           f"{appointment.date} at {appointment.time}. Is there anything you'd like to change?")
            session.state = 'check_modification'
        
        response = self.create_voice_response_fast(response_text, use_gather=True)
        return str(response)
    
    def _handle_multiple_appointments_found(self, session, appointments):
        """Handle when multiple appointments are found"""
        response_text = f"I found {len(appointments)} appointments for you. "
        for i, apt in enumerate(appointments[:3], 1):  # List up to 3
            response_text += f"Number {i}: {apt.service} on {apt.date} at {apt.time}. "
        response_text += "Which appointment would you like to modify? You can say the number or describe the appointment."
        
        session.state = 'selecting_appointment'
        response = self.create_voice_response_fast(response_text, use_gather=True)
        return str(response)
    
    def find_appointment_by_name(self, name):
        """Find appointments by customer name"""
        found = []
        for apt in self.appointments:
            if apt.customer_name and name.lower() in apt.customer_name.lower():
                found.append(apt)
        return found
    
    def find_appointment_by_phone(self, phone):
        """Find appointments by phone number"""
        # Clean phone number
        phone_digits = re.sub(r'[^\d]', '', phone)
        found = []
        for apt in self.appointments:
            apt_phone_digits = re.sub(r'[^\d]', '', apt.phone_number)
            if phone_digits in apt_phone_digits or apt_phone_digits in phone_digits:
                found.append(apt)
        return found
    
    def auto_correct_input(self, text):
        """Auto-correct common speech recognition mistakes"""
        text_lower = text.lower()
        
        # Apply auto-corrections
        for wrong, right in self.auto_corrections.items():
            if wrong in text_lower:
                if isinstance(right, list):
                    # Multiple possible corrections, use first one
                    text_lower = text_lower.replace(wrong, right[0])
                else:
                    text_lower = text_lower.replace(wrong, right)
        
        # Capitalize first letter and proper nouns
        words = text_lower.split()
        result = []
        for word in words:
            if word in ['i', "i'm", "i'll", "i'd", "i've"]:
                result.append(word.replace('i', 'I'))
            else:
                result.append(word)
        
        return ' '.join(result)
    
    def extract_booking_info(self, session: CallSession, user_input: str):
        """Extract booking information from user input with smart detection"""
        user_input_lower = user_input.lower()
        
        # Extract name (improved detection)
        if not session.customer_data.get('name'):
            # Direct name patterns
            name_patterns = [
                r"(?:my name is|i'm|i am|this is|it's)\s+([a-z]+(?:\s+[a-z]+)*)",
                r"^([a-z]+(?:\s+[a-z]+)*)(?:\s+here)?$",  # Just the name
            ]
            
            for pattern in name_patterns:
                match = re.search(pattern, user_input_lower)
                if match:
                    potential_name = match.group(1).strip()
                    # Filter out non-names
                    if potential_name not in ['yes', 'no', 'yeah', 'nope', 'sure', 'okay', 'ok', 'um', 'uh']:
                        if len(potential_name) > 1 and len(potential_name.split()) <= 4:
                            session.customer_data['name'] = potential_name.title()
                            break
        
        # Extract service with keyword matching
        if not session.customer_data.get('service'):
            for service in self.business_config.services:
                service_keywords = service.get('keywords', []) + [service['name'].lower()]
                for keyword in service_keywords:
                    if keyword in user_input_lower:
                        session.customer_data['service'] = service['name']
                        break
                if session.customer_data.get('service'):
                    break
        
        # Extract date
        if not session.customer_data.get('date'):
            date = self.extract_date(user_input_lower)
            if date:
                session.customer_data['date'] = date
        
        # Extract time
        if not session.customer_data.get('time'):
            time = self.extract_time(user_input_lower)
            if time:
                # Validate time is in available slots
                if time in self.available_times:
                    session.customer_data['time'] = time
                else:
                    # Find nearest available time
                    nearest = self.find_nearest_available_time(time)
                    if nearest:
                        session.customer_data['time'] = nearest
        
        # Extract phone if provided
        phone_match = re.search(r'(\d{3}[-.\s]?\d{3}[-.\s]?\d{4})', user_input)
        if phone_match:
            session.customer_data['phone'] = re.sub(r'[^\d]', '', phone_match.group(1))
    
    def extract_date(self, text):
        """Extract date from user input"""
        today = datetime.now()
        
        # Check for relative dates
        if any(word in text for word in ['today', 'now', 'right now', 'immediately']):
            return today.strftime("%A, %B %d")
        elif 'tomorrow' in text:
            return (today + timedelta(days=1)).strftime("%A, %B %d")
        elif 'day after tomorrow' in text:
            return (today + timedelta(days=2)).strftime("%A, %B %d")
        
        # Check for day names
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        for day_name in days:
            if day_name in text:
                return self._get_next_weekday(day_name)
        
        # Check for "next week"
        if 'next week' in text:
            return (today + timedelta(days=7)).strftime("%A, %B %d")
        
        # Check for specific dates (e.g., "January 15", "the 15th")
        month_names = ['january', 'february', 'march', 'april', 'may', 'june',
                      'july', 'august', 'september', 'october', 'november', 'december']
        
        for i, month in enumerate(month_names, 1):
            if month in text:
                # Try to find a day number
                day_match = re.search(r'\b(\d{1,2})(?:st|nd|rd|th)?\b', text)
                if day_match:
                    day = int(day_match.group(1))
                    if 1 <= day <= 31:
                        try:
                            date = datetime(today.year, i, day)
                            if date < today:
                                date = datetime(today.year + 1, i, day)
                            return date.strftime("%A, %B %d")
                        except ValueError:
                            pass
        
        return None
    
    def extract_time(self, text):
        """Extract time from user input"""
        # Remove dots that might be from speech recognition
        text = text.replace('.', '')
        
        # Common time patterns
        time_patterns = [
            r'\b(\d{1,2})\s*(?::|\.)?(\d{2})?\s*(a\.?m\.?|p\.?m\.?|am|pm)\b',
            r'\b(\d{1,2})\s*(o\'?clock)?\s*(in the\s+)?(morning|afternoon|evening)\b',
            r'\b(noon|midday|midnight)\b'
        ]
        
        for pattern in time_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                return self._parse_time_match(match, text)
        
        # Check for preferences
        if 'earliest' in text or 'first available' in text:
            return self.get_first_available_time()[1] if isinstance(self.get_first_available_time(), tuple) else self.available_times[0]
        elif 'latest' in text or 'last available' in text:
            return self.available_times[-1]
        elif 'morning' in text:
            for time in self.available_times:
                if 'AM' in time:
                    return time
        elif 'afternoon' in text:
            for time in self.available_times:
                if 'PM' in time and not time.startswith('12'):
                    return time
        
        return None
    
    def _parse_time_match(self, match, text):
        """Parse a regex match for time into standard format"""
        groups = match.groups()
        
        if 'noon' in text or 'midday' in text:
            return "12:00 PM"
        elif 'midnight' in text:
            return "12:00 AM"
        
        try:
            hour = int(groups[0])
            minutes = int(groups[1]) if groups[1] else 0
            
            # Determine AM/PM
            if len(groups) > 2 and groups[2]:
                period = 'AM' if 'a' in groups[2].lower() else 'PM'
            elif len(groups) > 3 and groups[3]:
                if 'morning' in groups[3]:
                    period = 'AM'
                elif 'evening' in groups[3] or 'afternoon' in groups[3]:
                    period = 'PM'
                else:
                    period = 'PM' if hour < 8 else 'AM'
            else:
                # Guess based on business hours
                period = 'PM' if 1 <= hour <= 7 else 'AM'
            
            # Format time
            if minutes == 0:
                return f"{hour}:00 {period}"
            else:
                return f"{hour}:{minutes:02d} {period}"
                
        except (ValueError, IndexError):
            return None
    
    def _get_next_weekday(self, day_name):
        """Get the date of the next occurrence of a weekday"""
        days = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
        target_day = days.index(day_name.lower())
        today = datetime.now()
        current_day = today.weekday()
        
        days_ahead = target_day - current_day
        if days_ahead <= 0:  # Target day already happened this week
            days_ahead += 7
        
        target_date = today + timedelta(days=days_ahead)
        return target_date.strftime("%A, %B %d")
    
    def find_nearest_available_time(self, requested_time):
        """Find the nearest available time slot"""
        # Parse requested time to minutes
        try:
            time_parts = re.search(r'(\d{1,2}):?(\d{2})?\s*(AM|PM)', requested_time, re.IGNORECASE)
            if not time_parts:
                return None
            
            req_hour = int(time_parts.group(1))
            req_min = int(time_parts.group(2)) if time_parts.group(2) else 0
            req_period = time_parts.group(3).upper()
            
            if req_period == 'PM' and req_hour != 12:
                req_hour += 12
            elif req_period == 'AM' and req_hour == 12:
                req_hour = 0
            
            req_minutes = req_hour * 60 + req_min
            
            # Find nearest available time
            best_time = None
            min_diff = float('inf')
            
            for time_slot in self.available_times:
                slot_parts = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM)', time_slot)
                if slot_parts:
                    slot_hour = int(slot_parts.group(1))
                    slot_min = int(slot_parts.group(2))
                    slot_period = slot_parts.group(3)
                    
                    if slot_period == 'PM' and slot_hour != 12:
                        slot_hour += 12
                    elif slot_period == 'AM' and slot_hour == 12:
                        slot_hour = 0
                    
                    slot_minutes = slot_hour * 60 + slot_min
                    
                    diff = abs(slot_minutes - req_minutes)
                    if diff < min_diff:
                        min_diff = diff
                        best_time = time_slot
            
            return best_time
            
        except Exception:
            return None
    
    def check_booking_complete(self, session: CallSession) -> bool:
        """Check if we have all required booking information"""
        required_fields = ['name', 'service', 'date', 'time']
        return all(session.customer_data.get(field) for field in required_fields)
    
    def get_first_available_time(self):
        """Get the first available appointment slot"""
        today = datetime.now()
        
        for days_ahead in range(self.business_config.max_advance_booking_days):
            check_date = today + timedelta(days=days_ahead)
            date_str = check_date.strftime("%A, %B %d")
            day_name = check_date.strftime("%A").lower()
            
            # Check if business is open
            if self.business_config.hours.get(day_name, 'Closed').lower() == 'closed':
                continue
            
            # Check each time slot
            for time_slot in self.available_times:
                # Skip past times for today
                if days_ahead == 0:
                    slot_hour = int(time_slot.split(':')[0])
                    slot_period = time_slot.split()[-1]
                    current_hour = today.hour
                    
                    if slot_period == 'PM' and slot_hour != 12:
                        slot_hour += 12
                    elif slot_period == 'AM' and slot_hour == 12:
                        slot_hour = 0
                    
                    if slot_hour <= current_hour:
                        continue
                
                # Check availability
                if self.google_calendar:
                    if self.google_calendar.check_availability(date_str, time_slot):
                        return date_str, time_slot
                else:
                    # No calendar, just return first slot
                    return date_str, time_slot
        
        return "No availability found"
    
    def _get_booking_status(self, session):
        """Get current booking status for context"""
        status_parts = []
        
        if session.customer_data.get('name'):
            status_parts.append(f"Name: {session.customer_data['name']}")
        if session.customer_data.get('service'):
            status_parts.append(f"Service: {session.customer_data['service']}")
        if session.customer_data.get('date'):
            status_parts.append(f"Date: {session.customer_data['date']}")
        if session.customer_data.get('time'):
            status_parts.append(f"Time: {session.customer_data['time']}")
        
        if not status_parts:
            return "No booking information collected yet"
        
        return "\n".join(status_parts)
    
    def _determine_next_action(self, session):
        """Determine what information to collect next"""
        if not session.customer_data.get('name'):
            return "ACTION: Ask for their name naturally"
        elif not session.customer_data.get('service'):
            return f"ACTION: Ask what service they need. Available: {self._list_services()}"
        elif not session.customer_data.get('date'):
            return "ACTION: Ask what day works for them"
        elif not session.customer_data.get('time'):
            return "ACTION: Ask what time they prefer"
        else:
            return "ACTION: Confirm the appointment details"
    
    def _clean_ai_response(self, text):
        """Clean up AI response text"""
        # Remove any markdown or formatting
        text = re.sub(r'\*+', '', text)
        text = re.sub(r'_+', '', text)
        text = re.sub(r'#+', '', text)
        
        # Remove any system-like messages
        lines = text.split('\n')
        cleaned_lines = []
        for line in lines:
            if not any(keyword in line.lower() for keyword in ['action:', 'note:', 'system:', 'status:']):
                cleaned_lines.append(line)
        
        text = ' '.join(cleaned_lines)
        
        # Ensure it's not too long
        if len(text.split()) > self.max_response_length:
            words = text.split()[:self.max_response_length]
            text = ' '.join(words) + '.'
        
        return text.strip()
    
    def send_sms_confirmation(self, appointment: Appointment):
        """Send SMS confirmation to customer"""
        try:
            if appointment.phone_number and appointment.phone_number != 'Unknown':
                message_body = (
                    f"Hi {appointment.customer_name}! This is a confirmation of your "
                    f"{appointment.service} appointment at {self.business_config.name} "
                    f"on {appointment.date} at {appointment.time}. "
                    f"Reply CANCEL to cancel or CHANGE to modify. See you soon!"
                )
                
                message = self.client.messages.create(
                    body=message_body,
                    from_=self.twilio_phone_number,
                    to=appointment.phone_number
                )
                
                self.logger.info(f"SMS confirmation sent to {appointment.phone_number}: {message.sid}")
                print(f"📱 SMS confirmation sent to {appointment.phone_number}")
        except Exception as e:
            self.logger.error(f"Failed to send SMS: {e}")
            print(f"❌ SMS failed: {e}")
    
    def save_appointments(self):
        """Save appointments to JSON file"""
        try:
            appointments_data = []
            for apt in self.appointments:
                appointments_data.append({
                    'customer_name': apt.customer_name,
                    'phone_number': apt.phone_number,
                    'service': apt.service,
                    'date': apt.date,
                    'time': apt.time,
                    'notes': apt.notes,
                    'call_sid': apt.call_sid,
                    'google_event_id': apt.google_event_id,
                    'created_at': apt.created_at
                })
            
            with open(self.appointments_file, 'w') as f:
                json.dump(appointments_data, f, indent=2)
            
            self.logger.info(f"Saved {len(appointments_data)} appointments")
        except Exception as e:
            self.logger.error(f"Error saving appointments: {e}")
    
    def load_appointments(self):
        """Load appointments from JSON file"""
        try:
            if os.path.exists(self.appointments_file):
                with open(self.appointments_file, 'r') as f:
                    appointments_data = json.load(f)
                
                self.appointments = []
                for apt_data in appointments_data:
                    self.appointments.append(Appointment(**apt_data))
                
                self.logger.info(f"Loaded {len(self.appointments)} appointments")
                print(f"📅 Loaded {len(self.appointments)} appointments from file")
        except Exception as e:
            self.logger.error(f"Error loading appointments: {e}")
            self.appointments = []
    
    def get_appointments_json(self):
        """Get appointments as JSON for admin view"""
        appointments_list = []
        for apt in self.appointments:
            appointments_list.append({
                'customer_name': apt.customer_name,
                'phone_number': apt.phone_number,
                'service': apt.service,
                'date': apt.date,
                'time': apt.time,
                'notes': apt.notes,
                'created_at': apt.created_at
            })
        
        return json.dumps(appointments_list, indent=2)
    
    def get_call_stats(self):
        """Get call statistics"""
        stats = {
            'total_appointments': len(self.appointments),
            'active_sessions': len(self.call_sessions),
            'services_booked': {},
            'appointments_by_day': {},
            'vip_customers': 0,
            'total_profiles': len(self.caller_db.profiles)
        }
        
        # Count services
        for apt in self.appointments:
            service = apt.service
            stats['services_booked'][service] = stats['services_booked'].get(service, 0) + 1
        
        # Count by day
        for apt in self.appointments:
            day = apt.date.split(',')[0] if ',' in apt.date else apt.date
            stats['appointments_by_day'][day] = stats['appointments_by_day'].get(day, 0) + 1
        
        # Count VIP customers
        for profile in self.caller_db.profiles.values():
            if profile.vip_status:
                stats['vip_customers'] += 1
        
        return json.dumps(stats, indent=2)
    
    def run(self, debug=True, port=5000):
        """Run the Flask application"""
        print("\n" + "="*60)
        print("🚀 NEVER-FAIL AI RECEPTIONIST STARTING...")
        print("="*60)
        print(f"Business: {self.business_config.name}")
        print(f"Type: {self.business_config.type}")
        print(f"Services: {self._list_services()}")
        print(f"Timezone: {os.getenv('TIMEZONE', 'America/New_York')}")
        print("-"*60)
        print(f"AI: {'✅ Enabled' if self.use_ai else '❌ Disabled'}")
        print(f"Voice: {'✅ ElevenLabs' if self.use_elevenlabs else '⚠️ Default'}")
        print(f"Calendar: {'✅ Google Calendar' if self.google_calendar else '❌ Disabled'}")
        print(f"Cache: {'✅ Redis + Memory' if REDIS_AVAILABLE else '⚠️ Memory only'}")
        print("-"*60)
        
        # Validate services configuration
        self.validate_services()
        
        # Show performance features
        print("\n📊 Performance Features:")
        print(f"• Predictive Responses: {'✅' if self.enable_predictive else '❌'}")
        print(f"• Parallel Processing: {'✅' if self.enable_parallel else '❌'}")
        print(f"• Caller Memory: ✅ ({len(self.caller_db.profiles)} profiles)")
        print(f"• Multi-tier Cache: ✅")
        print(f"• Circuit Breakers: ✅")
        print(f"• Zero Dead Air: ✅")
        
        print("\n🔗 Webhook URLs:")
        base_url = self._get_base_url()
        print(f"Voice URL: {base_url}/webhook/voice")
        print(f"Status Callback: {base_url}/webhook/status")
        
        print("\n📱 Admin Endpoints:")
        print(f"Status: {base_url}/test")
        print(f"Appointments: {base_url}/admin/appointments")
        print(f"Stats: {base_url}/admin/stats")
        print(f"Performance: {base_url}/admin/performance")
        if self.google_calendar:
            print(f"Calendar Debug: {base_url}/admin/calendar")
        
        print("\n✅ System ready! Waiting for calls...")
        print("="*60 + "\n")
        
        self.app.run(debug=debug, port=port, host='0.0.0.0')


# ===========================
# MAIN EXECUTION
# ===========================
if __name__ == '__main__':
    try:
        receptionist = TwilioAIReceptionist()
        receptionist.run(debug=True, port=5000)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down gracefully...")
        # Save any pending data
        if 'receptionist' in locals():
            receptionist.save_appointments()
            receptionist.caller_db.save()
            print("✅ Data saved successfully")
    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        print(traceback.format_exc())
        print("\nPlease check your configuration and try again.")