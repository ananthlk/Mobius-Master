"""Skill implementations — one module per capability.

Import the run_* function directly:

    from mobius_skills_core.skills.google_search import run_google_search
    from mobius_skills_core.skills.web_scrape import run_web_scrape

Each module's docstring documents its parameters and the SkillResult it
returns. Consumers wrap these for their surface (chat SkillEnvelope,
MCP text return, etc.).
"""
