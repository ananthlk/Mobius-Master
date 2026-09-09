# Corpus Linking Template — Connect Docs to RCM Gates

> **For:** All product-docs contributors  
> **Purpose:** Make explicit which RCM gate(s) each doc enables  
> **Status:** Template ready; gradual rollout across existing docs

---

## Why Link?

Users reading product docs should see how their feature connects to Mobius's larger vision. When they read "payor policies," they should see "this unlocks Gate 4 (Payor Policies & Benefits) in Tier B."

**Before:**
```
## Payor Lookup
Ask Mobius about payer contact info and benefits…
```

**After:**
```
## Payor Lookup

🎯 **Enables:** Gate 4 (Payor Policies & Benefits) in Tier B  
See [The Mobius Model](mobius-model.md#gate-4-payor-policies--benefits) for context on why this gate matters.

Ask Mobius about payer contact info and benefits…
```

---

## Template

Add this section near the top of each doc (after the headline, before the main content):

```markdown
🎯 **Enables:** Gate N (Gate Name) in Tier [A/B/C]  
See [The Mobius Model](mobius-model.md#gate-n-gate-name) for context on why this gate matters.
```

**Format rules:**
- Use 🎯 emoji (gating indicator)
- Link to mobius-model.md with anchor to the specific gate section
- Tier letter in brackets [A/B/C]
- Gate number + name must match the Mobius Model exactly
- One line; if multiple gates, comma-separate them

---

## Examples

### Single gate

**mobius-chat.md:**
```markdown
🎯 **Enables:** Gates 4–7 (Payor Policies, Authorization, Coding, Chat Interface) in Tier B  
See [The Mobius Model](mobius-model.md) for context.
```

**credentialing-and-roster.md:**
```markdown
🎯 **Enables:** Gate 5 (Credentialing) in Tier B  
See [The Mobius Model](mobius-model.md#gate-5-credentialing) for context.
```

### Multiple gates

**rag-backend.md:**
```markdown
🎯 **Enables:** Gates 3–4 (Eligibility Verification, Payor Policies) in Tier B  
See [The Mobius Model](mobius-model.md) for context on how retrieval powers both gates.
```

### Multi-tier

**appeals-agent-spec.md:**
```markdown
🎯 **Enables:** Gate 6 (Authorization / Appeals) in Tier B→C  
See [The Mobius Model](mobius-model.md#gate-6-authorization--appeals) for context.
```

---

## Which Docs Need Linking?

**In scope (actively maintained):**
- ✅ mobius-chat.md — Gates 4–7
- ✅ rag-backend.md — Gates 3–4
- ✅ credentialing-and-roster.md — Gate 5
- ✅ lexicon.md — Gate 4 (tagging drives query routing)
- ✅ skills.md — various (granular per skill)
- ✅ payor-readiness.md — Gate 4
- ✅ appeals-agent-spec.md — Gate 6

**Out of scope (archived or aspirational):**
- ❌ mobius-os.md (not deployed)
- ❌ user-and-auth.md (peripheral)
- ❌ infrastructure.md (dev plumbing)
- ❌ future roadmap docs (template only)

---

## Anchor Format (For Mobius Model)

To make linking work, mobius-model.md uses consistent anchor IDs:

```markdown
### **Gate 1: Claim Closure**
### **Gate 2: Denial Management**
### **Gate 3: Eligibility Verification**
…
```

Markdown auto-generates anchors from headers:
- `Gate 1: Claim Closure` → `#gate-1-claim-closure`
- `Gate 4: Payor Policies & Benefits` → `#gate-4-payor-policies--benefits`

Test the anchor in your link before committing.

---

## Rollout Plan

| Phase | Timeline | Docs | Owner |
|-------|----------|------|-------|
| **Phase 1** | 2026-07-30 (now) | Create template + examples | PA |
| **Phase 2** | 2026-08-15 | Link core 5 docs (chat, rag, cred, lex, appeals) | PA + relevant agents |
| **Phase 3** | 2026-08-30 | Link skill docs + payor-readiness | PA |
| **Phase 4** | Q4 2026 | Audit for any missed docs | PA quarterly review |

---

## How to Verify Your Links

1. **Check the anchor exists** in mobius-model.md (copy the gate header, paste into anchor format)
2. **Test the link** in GitHub preview or locally
3. **Verify the gate name** matches Mobius Model exactly (no typos, no rewording)
4. **Check the tier** [A/B/C] matches the gate's tier

**Example verification:**
- mobius-chat.md links to `#gate-4-payor-policies--benefits`
- mobius-model.md has header `### **Gate 4: Payor Policies & Benefits**` ✅
- Anchor auto-generates correctly ✅
- Tier B is correct ✅

---

## FAQ

**Q: What if a doc enables multiple gates?**  
A: List them comma-separated, or note "Gates N–M" if they're sequential.

**Q: What if a gate isn't live yet?**  
A: Link to it anyway. The link documents the intent; mobius-model.md has the status.

**Q: What if a doc is aspirational (not deployed)?**  
A: Don't link. Document the gate only when the code is live. See "In scope" above.

**Q: Should I update the gate description in mobius-model.md based on what I learn?**  
A: Only if the gate meaning changed. Gate descriptions are locked by PA (they drive sign-offs). For tweaks, file a doc_stale tag.

---

## Example Linked Docs (After Rollout)

### mobius-chat.md (updated)

```markdown
# Mobius Chat

🎯 **Enables:** Gates 4–7 (Payor Policies, Authorization/Appeals, Coding, Chat Interface) in Tier B  
See [The Mobius Model](mobius-model.md) for context on how Chat surfaces these gates.

The conversational interface that powers answered policy questions, guided appeals, and real-time skill dispatch.

## Purpose
…
```

### credentialing-and-roster.md (updated)

```markdown
# Credentialing & Roster Reconciliation

🎯 **Enables:** Gate 5 (Credentialing) in Tier B  
See [The Mobius Model](mobius-model.md#gate-5-credentialing) for context on why shared credentialing unlocks network-scale operations.

Provider enrollment, roster reconciliation, and ghost-billing detection.

## Purpose
…
```

---

## Questions?

If a doc's gate alignment is unclear, file a doc_stale tag with the PA agent. We'll refine the linking guidelines as we roll out.

---

*Template created: 2026-07-30*  
*Owned by: Product-Awareness Architect*  
*Next review: 2026-08-30 (Phase 3)*
