# Sonus — Plain English Guide

This is the no-jargon explanation of what Sonus is, how it works, and what you can do with it.

---

## What is Sonus?

Sonus is like a smart home assistant that actually thinks. Instead of you programming "every day at 7pm turn on the lights", you just talk to it and it figures out what to do. Over time it learns your habits and starts doing things automatically without you asking.

Think of it like this:
- **Normal smart home**: You set up rules. Rules run. Rules never change.
- **Sonus**: You talk to it. It learns. It starts anticipating what you need.

---

## The Two Pages

When you open Sonus in your browser you see two pages:

### 1. Integrations (the Brain page)
This is where you connect your apps and devices. There's a brain graphic in the middle. On the left panel you'll see your software and wearables, on the right your devices and communication apps. Drag anything onto the brain to connect it.

Once something is connected to the brain, Sonus can use it.

**Example:** Drag "Spotify" onto the brain → now you can say "play chill music" and it works.

### 2. Chat
This is where you talk to Sonus. Type anything in natural language. Sonus will use whatever integrations you've connected to respond.

---

## Demo Mode vs Train Mode

There's a toggle somewhere in the UI that switches between two modes.

### Demo Mode (default)
Sonus just responds to you. You ask, it answers or does the thing. Nothing happens in the background. This is good when you're just getting started or testing.

### Train Mode
This is where it gets interesting. Two things run in the background:

**1. The Biometric Loop** — if you have a wearable connected (Garmin, Whoop, Oura, Apple Watch), Sonus checks your health data every 30–60 seconds. It learns what's normal for you. When something unusual happens — like your stress goes way up — it can automatically do something about it without you asking.

> Example: You're working late, your Garmin shows stress=78 (your normal is 40). Sonus dims the lights to warm yellow and turns on the AC. It then checks in 10 minutes to see if your stress went back down. If that worked, it'll do it more confidently next time.

**2. The Thinking Loop** — Sonus looks at patterns it has learned about you every 2–5 minutes. If it's confident enough that you like something at a certain time, it just does it.

> Example: Every weeknight around 9pm you dim the bedroom lights. After seeing this happen many times, Sonus starts doing it automatically. The first few times it asks "should I do this?" — once you say yes enough times, it just does it on its own.

---

## What Can I Say to Sonus?

Here are real examples of things you can say in the chat:

### Controlling devices
```
"Turn on the living room light"
"Set the bedroom lamp to 50% brightness and warm white"
"Lock the front door"
"Turn the fan on"
"Set the AC to 72 degrees"
```

### Music
```
"Play something chill"
"Pause the music"
"Skip this song"
"Play my studying playlist on Spotify"
```

### Calendar & school
```
"What do I have today?"
"Do I have any assignments due this week?"
"What time is my first class tomorrow?"
"Remind me to submit the lab report in 3 hours"
```

### Weather
```
"What's the weather right now?"
"Should I bring an umbrella tomorrow?"
"How hot is it going to be this weekend?"
```

### Food & health (with FatSecret)
```
"Log 200g of chicken breast for lunch"
"What did I eat today?"
"How many calories have I had so far?"
"Search for the nutrition info for a banana"
```

### Email & tasks
```
"Do I have any unread emails?"
"What are my pending Google Tasks?"
"Create a task to call the dentist"
```

### Setting up scenarios
```
"Set me up for studying"
"I'm going to sleep"
"Get me ready for the gym"
"I'm hosting guests tonight"
```

### Teaching Sonus
```
"I like warm lights when I'm relaxing"
"Always turn on the fan when I start studying"
"Never play loud music after 10pm"
"I prefer the AC at 70 when I'm sleeping"
```

---

## Connecting Each Integration

Here's what each integration does and the fastest way to set it up.

### Google Calendar
Sonus can tell you what's on your schedule, check for conflicts, and create events.

**Setup:** Click Connect → sign in with Google → done. One sign-in also unlocks Gmail and Google Tasks.

### Canvas LMS
Sonus can tell you about upcoming assignments and deadlines.

**Setup:**
1. Open Canvas → go to Calendar
2. At the bottom of the calendar, click "Calendar Feed"
3. Copy that link
4. Paste it into the Canvas field in Sonus

### Weather
Sonus can check current conditions and forecasts.

**Setup:**
1. Go to openweathermap.org → sign up (free)
2. Go to API Keys in your account
3. Copy the key → paste it in Sonus
4. Type your city name

### Spotify
Sonus can play, pause, skip, and search for music.

**Setup:** Click Connect → sign in with Spotify → done. Make sure Spotify is open on one of your devices.

### FatSecret (calorie tracking)
Sonus can search foods, get nutrition info, and log what you eat to a diary.

**Setup:**
1. Go to platform.fatsecret.com → create a free developer account
2. Create a new app
3. Copy the **Consumer Key** and **Consumer Secret** (not Client ID/Secret — those are different)
4. Paste them in Sonus → click Connect. The diary is set up automatically.

### ntfy (phone notifications)
Sonus can send push notifications to your phone for free.

**Setup:**
1. Install the ntfy app on your phone (search "ntfy" in App Store or Play Store)
2. Pick a topic name — anything unique like `sonus-yourname`
3. In the app, subscribe to that topic
4. In Sonus, enter the same topic name → done

### Telegram
You can message Sonus directly from Telegram (like texting it).

**Setup:**
1. Open Telegram → search for @BotFather
2. Send `/newbot` → follow the steps → copy the token it gives you
3. Start a chat with your new bot
4. Message @userinfobot to get your Chat ID
5. Paste both into Sonus

### Discord
Sonus sends updates to a Discord channel.

**Setup:**
1. Open Discord → your server → Settings → Integrations → Webhooks
2. Click New Webhook → copy the URL
3. Paste it in Sonus

### Garmin / Whoop / Oura
These feed real-time health data to the biometric loop in Train mode. Without at least one wearable, Train mode can't detect stress or heart rate changes.

**Setup:** Each needs an API key from their developer portals. You get them by creating a developer account on each platform.

### Smart Lights / Fan / Lock / AC
Sonus can control real smart home devices through:
- **Home Assistant** — if you run Home Assistant locally
- **Simulated** — works immediately, great for testing (no real hardware needed)
- **Native APIs** — Philips Hue, Sensibo, etc.

---

## How Train Mode Actually Learns

Let's say you've connected a Garmin and some smart lights.

### Week 1
- Sonus watches your stress levels every minute
- It calculates your "normal" stress (maybe 40 on a scale of 0–100)
- When your stress hits 72 (way above normal), Sonus tries dimming the lights
- 10 minutes later it checks — did your stress go down? If yes, that worked.

### Week 2
- Sonus has now tried the lights-dimming thing 8 times
- 6 out of 8 times your stress went down → effectiveness = 75%
- Now when your stress spikes, it dims the lights **automatically** without asking

### Week 3 and beyond
- Sonus notices you always turn on the fan around 9pm on weekdays
- It asks: "Should I turn on the fan?" — you say yes
- A few days later it just does it on its own
- If you ever say "no" or undo it quickly, it backs off and stops being so confident

### The confidence number
Every learned behavior has a confidence score from 0 to 1.
- **0.0–0.49**: Sonus doesn't act on this yet
- **0.50–0.84**: Sonus will ask "Should I do this?"
- **0.85–1.0**: Sonus does it automatically

If you keep saying yes → confidence goes up. If you undo it or say no → confidence goes down. Patterns that you haven't interacted with in a week slowly decay (get less confident) so outdated habits don't stick forever.

---

## Running the Tests

If you're developing or just want to see the system work in isolation:

```bash
# Run all 47 tests — uses a fake in-memory database, no real devices needed
/opt/homebrew/bin/python3 -m pytest tests/train_mode/ -v -s -W ignore::DeprecationWarning
```

You'll see output like:
```
🤖 WS autonomous_action  pattern='Evening lights dim'  confidence=0.91
     device= living_room_bulb  action= set_color_temp  params={'temp': 'warm'}

💡 WS pattern_suggestion  pattern='Maybe fan on'  confidence=0.60
```

`🤖` means Sonus executed it automatically (confidence ≥ 0.85).
`💡` means Sonus is asking for your approval (confidence 0.50–0.84).

### The CLI simulator
Want to see a full scenario play out without touching your real setup?

```bash
# Stress escalation with minimal devices (1 bulb + 1 AC)
/opt/homebrew/bin/python3 tests/train_mode/simulate.py --mode few --scenario stress

# HR spike with full device set (7 devices, 4 wearables merged)
/opt/homebrew/bin/python3 tests/train_mode/simulate.py --mode many --scenario hr

# Calm day — nothing should trigger
/opt/homebrew/bin/python3 tests/train_mode/simulate.py --mode few --scenario calm
```

This uses a throwaway temp database so it never touches your real `sonus.db`.

---

## Common Questions

**Do I need all the integrations?**
No. Sonus works fine with just a few. The more you connect, the more context it has. The minimum useful setup is: AI key + 1 smart device + chat.

**Do I need a wearable for Train mode?**
For the biometric loop (stress/HR monitoring), yes. Without a wearable, the biometric loop runs but has nothing to read. The thinking loop (pattern learning) works without wearables.

**Will Sonus do things I don't want?**
In Demo mode, never — it only acts when you ask. In Train mode, only after confidence is ≥ 0.85, which requires many confirmations from you first. And you can always undo anything.

**What AI does it use?**
By default TAMU Chat (GPT-4o via the TAMU API). You can point it at any OpenAI-compatible API by changing `AI_BASE_URL` and `AI_MODEL` in `.env`.

**Is my data sent anywhere?**
Your conversation goes to the LLM API you configure (TAMU Chat or OpenAI). Everything else — device states, patterns, biometrics, calendar data — stays on your machine in `sonus.db`.

**How do I reset everything?**
Delete `sonus.db` and restart. The database is recreated fresh on next start.
