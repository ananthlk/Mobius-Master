# Mobius Chat — user guide (web app)

This guide covers **only the Mobius Chat web application** ([mobius-chat/frontend](../../mobius-chat/frontend)): the sidebar, main chat area, composer, uploads, and what to expect from answers. It does not replace developer setup; for running the stack locally, see [mobius-chat/README.md](../../mobius-chat/README.md).

---

## 1. What Mobius Chat does

You ask questions in natural language. The system:

1. **Receives** your message (and thread context when applicable).
2. **Plans** how to answer — which may include looking up policy documents, running tools (web search, NPI lookups, roster reports, etc.), or refusing parts of the question that need personal health information we do not have.
3. **Returns** an answer, often with citations when the answer comes from published materials.

The client typically **sends** a request and **polls** until a response is ready, so you may see a short delay while the worker runs. See [mobius-chat/docs/MODULES.md](../../mobius-chat/docs/MODULES.md) for the technical flow.

---

## 2. Patient vs non-patient (important)

Mobius Chat is built to answer **general** policy and operational questions from published materials and tools. It does **not** have access to **your** medical records, claims, or other patient-specific data.

- Questions that need **only** general plan or regulatory information can be answered when the corpus or tools have relevant information.
- Questions that require **your** private situation (“my medication,” “my claim,” “what did my doctor say”) are handled on a **patient** path that will **not** pull personal data — you should see a clear limitation or warning instead.

Details: [mobius-chat/docs/ARCHITECTURE.md](../../mobius-chat/docs/ARCHITECTURE.md) (patient vs non-patient architecture).

---

## 3. UI tour

### Sidebar

- **Logo and “Mobius Chat”** — product identity.
- **New chat** — starts a fresh conversation.
- **Recent searches** — collapsible list of recent activity.
- **Most helpful searches / Most helpful documents** — discovery shortcuts (when populated).
- **Signed in as** — shows **Guest** until you sign in; click to open account / sign-in (when auth is enabled). See [mobius-auth/README.md](../../mobius-auth/README.md).
- **LLM** — label for the configured model (informational).
- **Collapse** — chevron to collapse the sidebar for more room.

### Main area

- **Welcome** header with a short subtitle that may rotate.
- **Empty state (“Workspace overview”)** when there are no messages yet:
  - Intro copy about support for non-clinical work.
  - **Together, we will** — value bullets.
  - **Quick prompts** — buttons that fill the composer with example questions (you can edit before sending).
  - **Release updates** — themed suggestions with “Try:” links for sample queries (e.g. Sunshine timely filing, NPI profile, behavioral health prior auth).

### Status and uploads

- **Status banner** — transient messages (e.g. connection or processing notes). You can dismiss with **×**.
- **Upload summary (roster receipt)** — after a roster upload, a card may show headline, checks, optional alerts, next steps, and **Details for your records** for metadata. Dismiss with **×** when you are done reading it.

### Composer (bottom)

- **Message field** — type your question; placeholder: “Message Mobius Chat…”.
- **Agentic** — checkbox (on by default) for ReAct-style reasoning with tools when appropriate.
- **⋯ More options** — opens a menu:
  - **Upload file** — attach a file to **this chat** (see below).
  - **Add link** — may be disabled while marked “Coming soon.”
- **Send** — submits the message.

### Upload file

Opening **Upload file** shows a dialog:

- Files are attached to **this chat**; you can upload more over time.
- **File purpose**: e.g. **Roster for reconciliation** (CSV/Excel). Other purposes may appear later.
- For roster: enter **Organization name**, optionally **Send reconciliation request right after upload**, then choose **File** and submit.

Technical envelope behavior for credentialing/roster UIs is specified in [mobius-chat/docs/CREDENTIALING_UI_ENVELOPE_SPEC.md](../../mobius-chat/docs/CREDENTIALING_UI_ENVELOPE_SPEC.md) (for integrations and consistency).

### Config (header)

- The **hamburger (☰)** in the header opens configuration options implemented in the frontend (e.g. environment-specific settings). Exact options depend on your deployment.

---

## 4. Features you may use

| Feature | What it is for |
|---------|----------------|
| **Policy / handbook Q&A** | Questions about plans, appeals, prior authorization, enrollment, and similar — answered from the published corpus when available, possibly with citations. |
| **Quick prompts / Try links** | Safe examples to explore capabilities without writing a question from scratch. |
| **Web search / scrape** | When enabled by your deployment, the assistant may search the web or fetch a URL you provide — see [CAPABILITIES.md](CAPABILITIES.md). |
| **NPI and credentialing flows** | Lookups and reports depend on tool availability and whether you have started a credentialing report or uploaded a roster as required. |
| **Account** | Sign-in and profile via the sidebar user control when integrated with your auth backend. |

---

## 5. What to expect

- **Latency**: Complex questions take longer than a simple echo; the queue and worker run after you send.
- **Citations**: When the system uses published documents, answers may include source references. Coverage depends on retrieval and the responder.
- **“No relevant information”**: If nothing in the corpus matches, you may get a clear statement to that effect; your deployment may also allow web search as a fallback.
- **Errors**: If something fails, you may see a message in the status banner or in the thread. Persistent issues are for **your administrator** — not for pasting secrets or service account paths in chat.

For environment and service requirements (operators), see [mobius-chat/docs/ENV.md](../../mobius-chat/docs/ENV.md) — end users normally do not change these.

---

## 6. Related reading

- [CAPABILITIES.md](CAPABILITIES.md) — full list of tools and limitations.
- [mobius-chat/docs/ARCHITECTURE.md](../../mobius-chat/docs/ARCHITECTURE.md) — how planning, RAG, and critique fit together (technical).
