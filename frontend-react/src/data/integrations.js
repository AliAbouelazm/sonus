// Full integration registry for Sonus
// logo: real brand logo URL — falls back to custom SVG (IntegrationIcon.jsx) or lettermark

// Shared mapping: integration_id → device_type prefix used to build device IDs
export const INTEGRATION_TO_DEVICE_PREFIX = {
  smart_lock: 'lock',
  smart_bulb: 'bulb',
  smart_fan:  'fan',
  smart_ac:   'ac',
}

export const CATEGORY_META = {
  software: { label: 'SOFTWARE', color: '#3B82F6', bg: 'rgba(59,130,246,0.08)' },
  hardware: { label: 'HARDWARE', color: '#F97316', bg: 'rgba(249,115,22,0.08)' },
  wearables: { label: 'WEARABLES', color: '#10B981', bg: 'rgba(16,185,129,0.08)' },
  communication: { label: 'COMMUNICATION', color: '#8B5CF6', bg: 'rgba(139,92,246,0.08)' },
}

export const INTEGRATIONS = [
  // ── SOFTWARE ──────────────────────────────────────────────────
  {
    id: 'google_calendar',
    name: 'Google Calendar',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/googlecalendar',
    color: '#4285F4',
    description: 'Sync your calendar events and schedule — one sign-in covers Gmail and Tasks too',
    auth_type: 'oauth',
    oauth_url: '/api/gcal/login',
    fields: [
      { name: 'client_id', label: 'Google Client ID', type: 'text', placeholder: '....apps.googleusercontent.com', required: true },
      { name: 'client_secret', label: 'Google Client Secret', type: 'password', placeholder: 'GOCSPX-...', required: true },
      { name: 'ics_url', label: 'Calendar ICS Feed URL (optional)', type: 'url', placeholder: 'https://calendar.google.com/calendar/ical/...', required: false },
    ],
    setup_instructions: [
      'Go to console.cloud.google.com and create (or open) a project',
      'Enable the Google Calendar, Gmail, and Tasks APIs',
      'Go to APIs & Services → Credentials → Create OAuth 2.0 Client ID',
      'Set type to "Web application" and add this redirect URI: http://127.0.0.1:8000/api/gcal/callback',
      'Copy the Client ID and Client Secret and paste them above, then click Save',
      'Click Connect to sign in — one Google sign-in covers Calendar, Gmail, and Tasks',
      'Optionally paste your ICS feed URL for read-only calendar access without OAuth',
    ],
    capabilities: ['get_events', 'create_event', 'update_event', 'delete_event'],
  },
  {
    id: 'canvas',
    name: 'Canvas LMS',
    category: 'software',
    color: '#E13F29',
    description: 'Track assignments, exams, and deadlines',
    auth_type: 'fields',
    fields: [
      { name: 'ics_url', label: 'Calendar Feed URL', type: 'url', placeholder: 'https://canvas.*.edu/feeds/calendars/...', required: true },
    ],
    setup_instructions: [
      'Open Canvas and go to Calendar',
      "Click 'Calendar Feed' at the bottom",
      'Copy the iCal URL and paste it here',
    ],
    capabilities: ['get_assignments', 'get_exams', 'get_deadlines'],
  },
  {
    id: 'weather',
    name: 'Weather',
    category: 'software',
    color: '#FF9500',
    description: 'Current conditions and forecasts',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'OpenWeatherMap API Key', type: 'password', placeholder: 'Your API key', required: true },
      { name: 'city', label: 'City', type: 'text', placeholder: 'e.g. New York', required: false },
    ],
    setup_instructions: [
      'Go to openweathermap.org and create a free account',
      'Navigate to API Keys in your account',
      'Copy your API key and paste it here',
      'Enter your city name',
    ],
    capabilities: ['get_current_weather', 'get_forecast', 'get_alerts'],
  },
  {
    id: 'gmail',
    name: 'Gmail',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/gmail',
    color: '#EA4335',
    description: 'Check and summarize your emails',
    auth_type: 'fields',
    fields: [],
    setup_instructions: [
      'Gmail uses the same Google account as Google Calendar',
      'Make sure Google Calendar is connected and signed in first',
      'Click Connect — no extra credentials needed',
    ],
    capabilities: ['get_unread_count', 'get_recent_emails', 'search_emails'],
  },
  {
    id: 'spotify',
    name: 'Spotify',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/spotify',
    color: '#1DB954',
    description: 'Control your music playback',
    auth_type: 'oauth',
    oauth_url: '/api/spotify/login',
    fields: [
      { name: 'client_id', label: 'Spotify Client ID', type: 'text', placeholder: 'Your Spotify app Client ID', required: true },
      { name: 'client_secret', label: 'Spotify Client Secret', type: 'password', placeholder: 'Your Spotify app Client Secret', required: true },
    ],
    setup_instructions: [
      'Go to developer.spotify.com/dashboard and log in',
      'Click "Create App" — give it any name',
      'Add this redirect URI: http://127.0.0.1:8000/api/spotify/callback',
      'Copy the Client ID and Client Secret and paste them above, then click Save',
      'Click Connect to sign in with Spotify',
      'Make sure Spotify is open on a device for playback control',
    ],
    capabilities: ['play', 'pause', 'skip', 'set_volume', 'get_current_track'],
  },
  {
    id: 'google_tasks',
    name: 'Google Tasks',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/googletasks',
    color: '#4285F4',
    description: 'Manage your to-do lists',
    auth_type: 'fields',
    fields: [],
    setup_instructions: [
      'Google Tasks uses the same Google account as Google Calendar',
      'Make sure Google Calendar is connected and signed in first',
      'Click Connect — no extra credentials needed',
    ],
    capabilities: ['get_tasks', 'create_task', 'complete_task'],
  },
  {
    id: 'notion',
    name: 'Notion',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/notion/e8e8f0',
    color: '#e8e8f0',
    description: 'Access your notes and databases',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'Integration Token', type: 'password', placeholder: 'secret_...', required: true },
    ],
    setup_instructions: [
      'Go to notion.so/my-integrations',
      'Create a new integration',
      'Copy the Internal Integration Token',
      'Share your Notion pages with the integration',
    ],
    capabilities: ['search_pages', 'read_page', 'create_page'],
  },
  {
    id: 'fatsecret',
    name: 'FatSecret',
    category: 'software',
    color: '#4CAF50',
    description: 'Food search, nutrition data, and calorie tracking',
    auth_type: 'fields',
    fields: [
      { name: 'consumer_key', label: 'Consumer Key', type: 'text', placeholder: 'Your FatSecret Consumer Key', required: true },
      { name: 'consumer_secret', label: 'Consumer Secret', type: 'password', placeholder: 'Your FatSecret Consumer Secret', required: true },
    ],
    setup_instructions: [
      'Go to platform.fatsecret.com and create a free developer account',
      "Create a new app — copy the Consumer Key and Consumer Secret (not Client ID/Secret)",
      'Paste them here and click Connect — diary access is set up automatically',
    ],
    capabilities: ['search_food', 'get_nutrition', 'log_food', 'track_calories'],
  },
  {
    id: 'todoist',
    name: 'Todoist',
    category: 'software',
    logo: 'https://cdn.simpleicons.org/todoist',
    color: '#E44332',
    description: 'Task management and to-dos',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'API Token', type: 'password', placeholder: 'Your API token', required: true },
    ],
    setup_instructions: [
      'Go to Todoist Settings → Integrations',
      'Copy your API token',
      'Paste it here',
    ],
    capabilities: ['get_tasks', 'create_task', 'complete_task'],
  },

  // ── HARDWARE ──────────────────────────────────────────────────
  {
    id: 'smart_lock',
    name: 'Smart Lock',
    category: 'hardware',
    color: '#9CA3AF',
    description: 'Control your door lock',
    auth_type: 'fields',
    allow_multiple: true,
    fields: [
      { name: 'connection_type', label: 'Connection Type', type: 'select', options: ['Home Assistant', 'August Lock', 'Simulated'], required: true },
      { name: 'ha_url', label: 'Home Assistant URL', type: 'url', placeholder: 'http://192.168.1.x:8123', required: false, show_if: { connection_type: 'Home Assistant' } },
      { name: 'ha_token', label: 'Long-Lived Access Token', type: 'password', required: false, show_if: { connection_type: 'Home Assistant' } },
      { name: 'entity_id', label: 'Entity ID', type: 'text', placeholder: 'lock.front_door', required: false, show_if: { connection_type: 'Home Assistant' } },
    ],
    setup_instructions: [
      'Choose your lock connection type',
      'For Home Assistant: enter URL + access token + entity ID',
      'For Simulated: no config needed — great for testing',
    ],
    capabilities: ['lock', 'unlock', 'get_state'],
  },
  {
    id: 'smart_bulb',
    name: 'Smart Light',
    category: 'hardware',
    color: '#FBBF24',
    description: 'Control lights with brightness and color',
    auth_type: 'fields',
    allow_multiple: true,
    fields: [
      { name: 'connection_type', label: 'Connection Type', type: 'select', options: ['Home Assistant', 'Philips Hue', 'Simulated'], required: true },
      { name: 'ha_url', label: 'Home Assistant URL', type: 'url', placeholder: 'http://192.168.1.x:8123', required: false, show_if: { connection_type: 'Home Assistant' } },
      { name: 'ha_token', label: 'Long-Lived Access Token', type: 'password', required: false, show_if: { connection_type: 'Home Assistant' } },
      { name: 'entity_id', label: 'Entity ID', type: 'text', placeholder: 'light.bedroom_lamp', required: false, show_if: { connection_type: 'Home Assistant' } },
    ],
    setup_instructions: [
      'Choose your light connection type',
      'For Home Assistant: enter URL + token + entity ID',
    ],
    capabilities: ['turn_on', 'turn_off', 'set_brightness', 'set_color_temp'],
  },
  {
    id: 'smart_fan',
    name: 'Smart Fan',
    category: 'hardware',
    color: '#60A5FA',
    description: 'Control fan power and speed',
    auth_type: 'fields',
    allow_multiple: true,
    fields: [
      { name: 'connection_type', label: 'Connection Type', type: 'select', options: ['Home Assistant', 'Bond Bridge', 'Simulated'], required: true },
    ],
    setup_instructions: ['Choose your fan connection type', 'For Simulated: no additional config needed'],
    capabilities: ['turn_on', 'turn_off', 'set_speed'],
  },
  {
    id: 'smart_ac',
    name: 'Thermostat / AC',
    category: 'hardware',
    color: '#06B6D4',
    description: 'Control room temperature',
    auth_type: 'fields',
    allow_multiple: false,
    fields: [
      { name: 'connection_type', label: 'Connection Type', type: 'select', options: ['Home Assistant', 'Sensibo', 'Simulated'], required: true },
      { name: 'api_key', label: 'API Key', type: 'password', placeholder: 'Sensibo API key', required: false, show_if: { connection_type: 'Sensibo' } },
    ],
    setup_instructions: ['Choose your AC/thermostat connection type', 'Simulated mode works great for testing'],
    capabilities: ['turn_on', 'turn_off', 'set_temp', 'set_mode'],
  },

  // ── WEARABLES ─────────────────────────────────────────────────
  {
    id: 'garmin',
    name: 'Garmin',
    category: 'wearables',
    logo: 'https://cdn.simpleicons.org/garmin/007CC3',
    color: '#007CC3',
    description: 'Activity, heart rate, and sleep data',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'Garmin Connect API Key', type: 'password', placeholder: 'Your API key', required: true },
    ],
    setup_instructions: ['Enable developer API access in Garmin Connect', 'Generate an API key and paste it here'],
    capabilities: ['get_activity', 'get_heart_rate', 'get_sleep'],
  },
  {
    id: 'oura',
    name: 'Oura Ring',
    category: 'wearables',
    color: '#6366F1',
    description: 'Sleep, readiness, and activity scores',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'Oura Personal Access Token', type: 'password', placeholder: 'Your token', required: true },
    ],
    setup_instructions: ['Go to cloud.ouraring.com', 'Navigate to Personal Access Tokens', 'Create a new token and paste it here'],
    capabilities: ['get_sleep_score', 'get_readiness', 'get_activity'],
  },
  {
    id: 'apple_health',
    name: 'Apple Health',
    category: 'wearables',
    logo: 'https://cdn.simpleicons.org/apple/e8e8f0',
    color: '#e8e8f0',
    description: 'Health and fitness data from your iPhone',
    auth_type: 'fields',
    fields: [
      { name: 'shortcut_url', label: 'Shortcut Webhook URL', type: 'url', placeholder: 'Generated by the Sonus shortcut', required: false },
    ],
    setup_instructions: ['Install the Sonus Apple Shortcuts integration', 'Run the shortcut to generate a webhook URL', 'Paste the URL here'],
    capabilities: ['get_steps', 'get_heart_rate', 'get_sleep'],
  },

  {
    id: 'whoop',
    name: 'Whoop',
    category: 'wearables',
    color: '#00F19C',
    description: 'Strain, recovery, HRV, and sleep performance',
    auth_type: 'fields',
    fields: [
      { name: 'api_key', label: 'Whoop API Key', type: 'password', placeholder: 'Your Whoop API key', required: true },
    ],
    setup_instructions: [
      'Go to app.whoop.com → Settings → Developer Tools',
      'Generate a personal API key',
      'Paste the key here',
    ],
    capabilities: ['get_recovery', 'get_strain', 'get_hrv', 'get_sleep'],
  },

  // ── COMMUNICATION ─────────────────────────────────────────────
  {
    id: 'ntfy',
    name: 'ntfy',
    category: 'communication',
    color: '#5C5C5C',
    description: 'Free push notifications to your phone',
    auth_type: 'fields',
    fields: [
      { name: 'ntfy_topic', label: 'ntfy Topic', type: 'text', placeholder: 'my-sonus-alerts', required: true },
    ],
    setup_instructions: [
      'Install the ntfy app on your phone (ntfy.sh)',
      'Pick a unique topic name (e.g. sonus-yourname)',
      'Subscribe to that topic in the app',
      'Paste the topic name here',
    ],
    capabilities: ['send_notification', 'send_alert'],
  },
  {
    id: 'twilio',
    name: 'Twilio SMS',
    category: 'communication',
    color: '#F22F46',
    description: 'Send real SMS text messages to your phone',
    auth_type: 'fields',
    fields: [
      { name: 'account_sid', label: 'Account SID', type: 'text', placeholder: 'AC...', required: true },
      { name: 'auth_token', label: 'Auth Token', type: 'password', placeholder: 'Your Twilio auth token', required: true },
      { name: 'from_number', label: 'Twilio Phone Number', type: 'tel', placeholder: '+15005550006', required: true },
      { name: 'phone_number', label: 'Your Phone Number', type: 'tel', placeholder: '+1 (555) 123-4567', required: true },
    ],
    setup_instructions: [
      'Go to console.twilio.com and create a free account',
      'Get a phone number from the Twilio console',
      'Copy your Account SID and Auth Token from the dashboard',
      'Enter your Twilio number and your personal number',
    ],
    capabilities: ['send_sms'],
  },
  {
    id: 'telegram',
    name: 'Telegram',
    category: 'communication',
    logo: 'https://cdn.simpleicons.org/telegram',
    color: '#26A5E4',
    description: 'Chat with Sonus directly from Telegram',
    auth_type: 'fields',
    fields: [
      { name: 'bot_token', label: 'Bot Token', type: 'password', placeholder: '123456:ABC-DEF...', required: true },
      { name: 'chat_id', label: 'Your Chat ID', type: 'text', placeholder: '123456789', required: true },
    ],
    setup_instructions: [
      'Open Telegram and message @BotFather',
      'Send /newbot and follow the prompts to create a bot',
      'Copy the bot token BotFather gives you',
      'Start a chat with your new bot, then message @userinfobot to get your Chat ID',
      'Paste both values here — you can then message Sonus directly from Telegram',
    ],
    capabilities: ['send_message', 'receive_message'],
  },
  {
    id: 'discord',
    name: 'Discord',
    category: 'communication',
    logo: 'https://cdn.simpleicons.org/discord',
    color: '#5865F2',
    description: 'Get Sonus updates in Discord',
    auth_type: 'fields',
    fields: [
      { name: 'webhook_url', label: 'Discord Webhook URL', type: 'url', placeholder: 'https://discord.com/api/webhooks/...', required: true },
    ],
    setup_instructions: ['Open Discord → Server Settings → Integrations', 'Click Webhooks → New Webhook', 'Copy the URL and paste it here'],
    capabilities: ['send_message', 'send_alert'],
  },
]

export function getByCategory(category) {
  return INTEGRATIONS.filter((i) => i.category === category)
}

export function getById(id) {
  return INTEGRATIONS.find((i) => i.id === id)
}

export const CATEGORIES_LEFT = ['software', 'wearables']
export const CATEGORIES_RIGHT = ['hardware', 'communication']
export const CATEGORIES_ALL = ['software', 'hardware', 'wearables', 'communication']
