# Real-Time & Security Features - Joidy Documentation

This document describes the technical architecture and usage of the end-to-end real-time reactivity, global error handling, visual connectivity tracking, and advanced rate limiting subsystems implemented in Joidy.

---

## ⚡ 1. End-to-End Real-Time Reactivity (WebSockets)

To achieve instantaneous updates across the personal knowledge workspace, Joidy establishes a persistent WebSocket connection between SvelteKit and FastAPI.

### 1.1 Backend Architecture

- **Path:** [api/routers/websocket.py](file:///home/d4mag3/Documents/Repos/Joidy/api/routers/websocket.py)
- **Connection Manager:** A module-level single instance `manager` of `ConnectionManager` accepts client WebSocket sockets, tracks active connections, handles heartbeat `ping/pong` calls, and broadcasts JSON messages to all listening clients with automatic connection cleaning.
- **Service Integration:** Broadcasters are decoupled from HTTP-specific modules and invoked directly inside the core database mutation services. To invoke async FastAPI broadcasting from synchronous SQLAlchemy service code, Joidy uses non-blocking asynchronous wrapper functions:
  ```python
  def broadcast_xp_gained(xp: int, total_xp: int):
      try:
          loop = asyncio.get_running_loop()
          if loop.is_running():
              loop.create_task(notify_xp_gained(xp, total_xp))
      except RuntimeError:
          pass
  ```
- **Broadcasting Triggers:**
  - `process_event` ([gamification_engine.py](file:///home/d4mag3/Documents/Repos/Joidy/api/services/gamification_engine.py)): Centralizes the broadcast of XP gains (`xp_gained`) and streak changes (`streak_updated`) automatically after transaction commits.
  - `create_note` & `update_note` ([note_service.py](file:///home/d4mag3/Documents/Repos/Joidy/api/services/note_service.py)): Transmits note events (`note_created` & `note_updated`) right after save, enabling other devices or background processes (like the Obsidian vault watcher) to trigger HMR updates in the UI.

### 1.2 Frontend Integration

- **Path:** [+layout.svelte](file:///home/d4mag3/Documents/Repos/Joidy/frontend/src/routes/+layout.svelte)
- **Lifecycle Management:** In `onMount`, Svelte initiates a connection `connectWS()` using the configured `VITE_API_URL` environment variable. It features a robust reconnection mechanism with exponential backoff on dropouts, and automatically closes the WebSocket handle on component destroy/unload.
- **Client Handlers:**
  - `note_created` / `note_updated`: Shows a success/info notification and calls `loadNotes()` to refresh Svelte stores.
  - `xp_gained`: Triggers the floating XP float animation and calls `loadStats()` to refresh global metrics.
  - `streak_updated`: Triggers a glowing daily streak fire badge.

---

## 🛡️ 2. Advanced Rate Limiting Middleware

To secure the REST API against brute-force, scraping, or loops, Joidy enforces sliding window rate limiting.

- **Path:** [api/middleware/rate_limit.py](file:///home/d4mag3/Documents/Repos/Joidy/api/middleware/rate_limit.py)
- **Flexible Request Identification:** Instead of simple global or pure IP boundaries, the limiter checks request headers sequentially:
  1. `X-API-Key`: Uses the API key string prefix `apikey:<key>`.
  2. `Authorization: Bearer <token>`: Extracts the token and hashes it safely as `token:<token_prefix>` to avoid security logs leakage.
  3. `Client IP` (Fallback): Resolves via `X-Forwarded-For` proxy headers or direct socket address as `ip:<host>`.
- **Dynamic Tier Limits:**
  - **Anonymous / IP traffic:** Enforces a safe limit of `60 requests per minute`.
  - **Authenticated Keys / Bearer tokens:** Awards a higher limit of `120 requests per minute`.
- **Client Feedback Headers:** Successful responses append `X-RateLimit-Limit` and `X-RateLimit-Remaining` to keep clients informed about current quotas, returning a detailed JSON error body with a `429 Too Many Requests` code on limit exhaustion.

---

## 🔍 3. Global Error Interception

A unified interceptor simplifies Svelte page logic by handling connection drops and server issues globally.

- **Path:** [api.ts](file:///home/d4mag3/Documents/Repos/Joidy/frontend/src/lib/api.ts) & [notifications.ts](file:///home/d4mag3/Documents/Repos/Joidy/frontend/src/lib/stores/notifications.ts)
- **Decoupled Toasts:** The notifications store (`notifications.ts`) is completely isolated to resolve circular imports between the HTTP request wrapper and statistics stores. It implements the `'error'` toast type mapping to an `AlertTriangle` warning icon in [Toast.svelte](file:///home/d4mag3/Documents/Repos/Joidy/frontend/src/lib/components/Toast.svelte).
- **Generic `req()` Interceptor Wrapper:**
  - **Network Failures:** Captures `TypeError` or socket failures, throwing a unified `Error de red. No se pudo conectar con el servidor.` notification.
  - **Session Expired (401):** Triggers `session.logout()` to safely clean cache state and raises a session expired warning toast.
  - **Server-Side Errors (400-500+):** Automatically parses the response payload, extract messages, and raises a detailed visual error popup.

---

## 📡 4. Glassmorphic Connectivity Indicator

A premium connectivity badge displays visual indicators corresponding to browser network changes.

- **Path:** [+layout.svelte](file:///home/d4mag3/Documents/Repos/Joidy/frontend/src/routes/+layout.svelte)
- **Reactivity:** Subscribes to the global `isOnline` and `wasOffline` connection stores.
- **Premium Styling:** Uses a glassmorphism theme (`backdrop-filter`) with Harmonious colors:
  - **Offline State:** A pulsing, glowing red dot (`red-pulse` keyframes) with an overlay saying `Sin conexión`.
  - **Restored State:** A temporary pulsing green pill saying `Conectado` that disappears fluidly using Svelte's `fade` transitions after 4 seconds of successful reconnect.
