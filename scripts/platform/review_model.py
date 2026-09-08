#!/usr/bin/env python3
"""Who signs off a schema node, and for what.

Written after eight errors in the chat schema. Sorting them showed three
clusters, and only one is about reading code carefully:

  SCOPE      the model did not contain the thing at all
  RUNTIME    described the repo, not the running system
  PRECISION  read it, stated it too strongly

A code owner catches PRECISION well, SCOPE poorly (they share the author's
assumption about what counts as part of the system), and RUNTIME not at all —
they read the same repository the author does. So more reviewers of the same
kind would not have helped. The lenses have to differ, and each has to have a
question it alone is accountable for.

A node is SIGNED only when all three lenses have signed it. Two of three is
not "mostly signed" — the unsigned lens names exactly which error class is
still unguarded on that node.
"""

LENSES = {
 "owner": {
   "question": "Does the code do what this says, exactly and no more strongly?",
   "catches": "precision",
   "who": "the seat that owns the module",
   "must_check": [
     "every line number and file path resolves",
     "conditions are stated in full — not one of four presented as the gate",
     "nothing is claimed about a neighbouring module's behaviour",
   ],
 },
 "runtime": {
   "question": "Is this what the DEPLOYED service actually does right now?",
   "catches": "runtime",
   "who": "a seat with deploy access, reading the live env — not the repo",
   "must_check": [
     "every env var: code default vs the value on the running revision",
     "flags whose name implies an effect they no longer have",
     "which environment was checked, named explicitly — dev is not prod",
   ],
 },
 "scope": {
   "question": "What is missing? What does this node touch that is not on the page?",
   "catches": "scope",
   "who": "a seat OUTSIDE the module — chosen per node by what the node claims",
   "must_check": [
     "does it delegate to a module the catalogue does not contain",
     "is there a surface, store or config the description never mentions",
     "would someone using this from outside need something not written here",
   ],
 },
}

# The scope lens is assigned by what the node claims, so the reviewer has a
# real stake in the answer rather than a general opinion.
SCOPE_LENS_BY_SUBJECT = {
 "storage":  "Database seat (Platform Architects) — chat_threads, Redis, state persistence",
 "prompt":   "LLM Agent — prompt blocks, compositions, model routing",
 "ux":       "Chat Frontend/UX — what the user actually sees",
 "retrieval":"Payor Policy / RAG — corpus, budgets, retrieval contracts",
}

def signed(node_reviews: dict) -> bool:
    return all(node_reviews.get(l) == "signed" for l in LENSES)

def unguarded(node_reviews: dict) -> list[str]:
    """The error classes still unguarded on this node."""
    return [LENSES[l]["catches"] for l in LENSES if node_reviews.get(l) != "signed"]
