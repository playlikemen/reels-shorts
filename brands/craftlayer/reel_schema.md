# Compact reel script format (CraftLayer, "3 problems" reels)

`ops/gen_reels.py` turns each entry of `brands/craftlayer/scripts/*.json` (a JSON list) into a full showcase spec in
`specs/craftlayer/<id>.json`. English only. Voice: Kokoro at 1.2x, about 3.3 words a second.

```json
{
  "id": "CR-106",
  "topic": "Clinics: 3 problems",
  "audience": "clinic",                    // the owner type, lower case, used in "send this to a ___ owner"
  "demo_name": "Northstar Clinic",         // the CraftLayer concept demo shown on screens (never called a client)
  "domain": "northstarclinic.in",          // shown in browser bars / headers
  "keyword": "CLINIC",                     // one-word comment CTA, upper case, max 8 letters
  "sources": ["https://craftlayer-studio.github.io/industry-demos/..."],
  "hook": {
    "say": "Patients aren't choosing the *better* doctor. They're choosing the one they can *book*.",
    "title": "Better doctor?\nOr *easier booking*?",
    "tiles": [{"ic": "users", "label": "Your clinic"}, {"ic": "cal", "label": "Next door", "hot": true}]
  },
  "problems": [
    {
      "say": "Problem one: a patient calls at *9 PM* and nobody *picks up*.",
      "screen": "chat",                    // "chat" or "rows"
      "head": "Missed *calls*",            // screen title, one *accent*
      "chat": [{"t": "Hi, is Dr Mehta free tomorrow?"}, {"t": "Hello?? Anyone?"}],
      "rows": [{"t": "Unknown number", "s": "9:12 PM · missed", "bad": true}],
      "chip": "No reply till morning",
      "fix": {
        "say": "The fix: *online booking* that shows free slots, *24x7*.",
        "head": "Book a *slot*",
        "sub": "Dr Mehta · General physician",
        "rows": [{"t": "Tomorrow 10:30", "s": "Available", "v": "Book", "ic": "cal"}],
        "btn": "Confirm booking",
        "chip": "Confirmed on WhatsApp"
      }
    }
  ],
  "recap_say": "*Bookings*, *reminders* and *records*, all in one system.",
  "recap": [{"t": "Bookings", "s": "free slots 24x7"}, {"t": "Reminders", "s": "WhatsApp, automatic"}, {"t": "Records", "s": "one place"}],
  "cta_say": "Want this for your *clinic*? Comment *CLINIC* or send us a *DM*.",
  "caption": "Full Instagram caption (see rules).",
  "hashtags": ["#clinic", "#doctorsofindia", "..."],
  "tags": ["clinic website", "..."]
}
```

Rules:
- Exactly 3 problems. `chat` uses `chat` (2 or 3 short customer messages, add `"me": true` for the owner's reply);
  `rows` uses `rows` (3 or 4 items, `bad: true` marks red ones). Fix `rows` has 2 to 4 items.
- Every `say` is one or two short sentences, at most 20 words, with 1 to 3 `*accent*` words. Total spoken
  words for the reel: 110 to 140 (about 35 to 45 s). Numbers in `say` are written as words ("nine PM" is fine as "9 PM").
- Hook: the first sentence must stop the scroll in under 2 seconds. Name the owner's pain or a contrarian truth.
  No questions like "Do you own a clinic?". No greetings.
- Honesty: no statistics, percentages or claims about the market; no real client names; the demo business is
  fictional and carries a CONCEPT DEMO badge. Say "we can build this", never "our clients".
- Caption: hook line, the 3 problems with ✅ fixes, "<demo_name> is a concept demo.", "Send this to a <audience>
  owner who needs it.", the comment CTA, a blank line, "Voiceover is AI-generated.". 5 to 8 hashtags, last one #craftlayer.
- Icons: plate fire bell wifi cash bank card phone wallet star check pin clock coffee chat search menu globe gift
  arrow cal leaf tag users bolt.
