# StackShade Brand & Content Guidelines

- **Brand Handle**: `@stackshade` (Instagram), `@StackShade` (YouTube)
- **Instagram**: [https://www.instagram.com/stackshade/](https://www.instagram.com/stackshade/) (Composio account `instagram_create-beta`)
- **YouTube Shorts**: [https://www.youtube.com/@StackShade/shorts](https://www.youtube.com/@StackShade/shorts) (Composio account `youtube_run-retin`)
- **Google Sheet Tracker**: [Reels or Shorts Sheet](https://docs.google.com/spreadsheets/d/1wnwYwhGw4kdhC5lHf6MCU208yRslGoppBzHkezUfYEk/edit) (Tab: `@StackShade`)
- **Google Drive Storage**: [Reels & Shorts Drive Folder](https://drive.google.com/drive/folders/1upAISpZAnmyDDYki_FH9tK-FVh_djqLS) (Folder ID: `1upAISpZAnmyDDYki_FH9tK-FVh_djqLS`)
- **Tagline**: "Complex engineering concepts broken down simply."
- **Audience**: Software engineers, computer science students, backend developers, system architects, and technical indie hackers.
- **Voice**: Authoritative, punchy, visually intuitive, zero-fluff, educational.

---

## Content Pillars

1. **System Design & Backend Architecture**:
   - High-throughput systems (Kafka, RabbitMQ, Redis, PostgreSQL, DynamoDB)
   - Cache-aside, read-through, write-back patterns
   - Sharding, replication, consensus (Raft, Paxos)
   - Rate limiting, circuit breakers, load balancers

2. **AI Engineering & Autonomous Agents**:
   - ReAct loops, tool calling, MCP servers
   - Vector databases, embeddings, hybrid search
   - Context compression & token economics

3. **Under The Hood / Computer Systems**:
   - Memory hierarchy (CPU Cache L1/L2/L3 vs RAM vs NVMe vs Network)
   - Linux internals: epoll, virtual memory, cgroups
   - Network protocols: HTTP/2 vs HTTP/3, QUIC, WebSockets, gRPC

4. **Algorithms & Mental Models**:
   - Two pointers, sliding window, topological sort, LRU Cache
   - Big-O visual comparisons and memory trade-offs

---

## Visual Design & Specs

- **Resolution**: 1080 x 1920 (Vertical 9:16 aspect ratio).
- **Frame Rate**: 30 FPS.
- **Video Codec**: H.264 (`yuv420p`, CRF 18, `+faststart`).
- **Audio Codec**: AAC stereo, code-synthesized or licensed tech-synth bed.
- **Duration**: 12 to 30 seconds (maximum retention).
- **Safe Area**:
  - Keep all titles, code, and key graphics inside the central vertical zone.
  - Keep top **250 px** clear (Instagram/YouTube header, search, audio bar).
  - Keep bottom **420 px** clear (captions, user account handle, engagement pills).
- **Color Palette**:
  - Background: Deep Obsidian / Cyber Jet (`#070a10`, `#0d111c`)
  - Primary Neon: Cyan / Electric Blue (`#38bdf8`, `#00f2fe`)
  - Secondary Neon: Mint Emerald (`#10b981`), Amber Gold (`#f59e0b`), Radiant Violet (`#a855f7`)
  - Surfaces: Frosted Glass (`rgba(18, 24, 38, 0.85)` with `rgba(56, 189, 248, 0.2)` border)
  - Typography: Primary Code `JetBrains Mono`, Headings `Inter` (Bold 700 / ExtraBold 900)

---

## Video Structure Rules

1. **The 1-Second Hook**:
   - Clear, intriguing problem statement or counter-intuitive question readable within 0.8s.
   - Example: *"Why Redis is 100x Faster Than MySQL"*, *"How AI Agents Actually Code"*.
2. **The Visual Insight (Body)**:
   - Dynamic motion graphics, step-by-step architecture diagrams, or live animated code.
   - Never show walls of plain text; every beat must have motion or state change.
3. **The Engineering Takeaway**:
   - Direct conclusion or practical mental model.
4. **Call To Action (CTA)**:
   - Final 2 seconds: "Follow @stackshade for daily engineering breakdowns" / "Subscribe @StackShade".
