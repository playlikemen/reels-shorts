# CampusLoop growth playbook

Written 2026-11-19 from the account's own numbers (37 reels, 30,658 views, 181 shares) and a crawl of the site. Update it every Sunday after running `python3.11 ops/ig_report.py campusloop --sheet`.

## The loop

Reel or story → `campusloop.space/ig` (bio link) → sign-up with college email → invite card and share sheet → friends arrive through `/join?invite=<username>` or `?ref=<username>` → they share too.

Each joint is now measurable:

| Step | Where to look |
|---|---|
| Reel performance | sheet tab `@campusloop-insights` (shares per 1,000 views is the key number) |
| Clicks from Instagram | `/admin/links`, rows whose code starts with `utm:instagram` |
| Invites | `/invites` leaderboard, `referral_count` |
| Sign-ups | `/admin/analytics` |

## Weekly schedule

One reel a day at 19:30 IST. The scheduler refuses a second reel on the same day.

| Day | Post | Made by |
|---|---|---|
| Mon | Founder clip: what shipped this week, shown on the phone | you, 30 s |
| Tue | Campus truth (engine) | automatic |
| Wed | Carousel: notes and past papers for one branch, or "5 things seniors won't tell you" | manual upload for now |
| Thu | Founder clip: one number and one mistake from this week | you, 30 s |
| Fri | Campus truth (engine) | automatic |
| Sat | Founder or campus clip: a real place on campus, a real question to students | you, 30 s |
| Sun | Product moment: screen recording of a real poll result or the share sheet | you, 20 s |

Stories every day, 2 to 4 frames: a confession of the day made with the in-app share sheet (ask the author first unless it is anonymous and harmless), a poll sticker, the invite leaderboard top 3 on Fridays, a countdown sticker before every fest.

Stopped: fantasy, horror and riddle stories (0 to 3 shares each) and feature ads (about 200 views, 2 to 4 s watched).

## Founder clips: how to record

- Phone upright, face a window or a lamp, phone mic within an arm's length. No music while recording.
- First sentence is the hook, said to camera, under 3 seconds. Say it before anything else.
- One idea per clip. 20 to 40 seconds. End with a question people can answer in a comment.
- Drop the file in `inbox/campusloop/` and run:

```
python3.11 ops/clip.py inbox/campusloop/day1.mp4 --brand campusloop --id CL-201 \
  --hook "I built an app only my college can use" --topic "Founder / why" \
  --caption "Day 1 of building CampusLoop from my hostel room. What should I build next?" \
  --schedule "2026-11-21 19:30"
```

### First six scripts

1. Hook: "I built an app only my college can use." Why a campus needs its own space, 47 group chats, one place. Ask: "What is the one thing your college group chat gets wrong?"
2. Hook: "We posted 13 reels in one day. Here is what happened." Show the insights sheet. Lesson: one a day. Ask: "What should we never post again?"
3. Hook: "This is the most shared thing we ever made." Show the 75% attendance reel numbers (103 shares). Ask: "What is your attendance right now?"
4. Hook: "Your invite link is worth 50 points." Screen-record the invite card and the leaderboard. Ask: "Who in your class would top this board?"
5. Hook: "Anonymous means anonymous. Here is how." Show an anonymous post and the story card with no name. Ask: "Would you post if nobody knew it was you?"
6. Hook: "Rate my hostel room startup setup." Pan the desk, the posters, the laptop. Ask: "What is missing?"

## Campus truth topics (engine, `specs/campusloop/`)

Done: CL-101 attendance maths, CL-102 group project, CL-103 night before the exam.
Next: mess food rating by day of week; the four kinds of hostel Wi-Fi; placement season group chat; "I'll start from Monday" timeline; lab record deadline maths; fresher vs final year walking to class; canteen order ranking as a poll (written for the reel, label it as an example).

Every one ends with "Send this to the friend who ...". Shares are the goal, not likes.

## Instagram features to use

| Feature | How |
|---|---|
| Bio link | Set to `https://campusloop.space/ig` |
| Pinned reels | Pin the founder reel, the attendance reel, and the newest founder clip |
| Highlights | How it works · Confessions · Notes · Wins |
| Collab posts | Invite fest and club pages as collaborators on event reels; their followers see it |
| Trial reels | Test a new hook on non-followers before posting to the grid |
| Comment keyword | Reply to "LINK" comments with the invite link (manual, or Instagram's built-in automated replies) |
| Broadcast channel | "CampusLoop updates": one message when a campus opens or a feature ships |
| Story stickers | Poll, question, countdown and link stickers; these cannot be set through the API |

## Startup plan

| Stage | When | One number | What to do |
|---|---|---|---|
| 1. One campus | weeks 1 to 2 | 300 verified BIT Mesra students | Invite leaderboard with a small prize for the top 3, founder clips, share cards in hostel WhatsApp groups |
| 2. Density | weeks 3 to 4 | 30% of them active each week | Daily confession-of-the-day story, fest and club collabs, 5 ambassadors with their own invite links |
| 3. Next campuses | weeks 5 to 8 | 150 verified at each of 3 campuses | Pick them from `/college-request` and `utm`/`ref` clicks; open with one ambassador each |
| 4. Keep or cut | every Sunday | shares per 1,000 views | Keep formats above the account median, stop the ones below it twice in a row |

These are targets to steer by, not forecasts.

## Not automated yet

- Carousels and stories are posted by hand; the scheduler posts reels only.
- YouTube Shorts for CampusLoop is off (`"youtube": null`). The `@MyCampusloop` connection exists (`youtube_bosom-eye`); turn it on in `brand.json` after the StackShade upload canary passes.
