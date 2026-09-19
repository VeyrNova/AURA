# AURA - Public GitHub repository plan

Goal: publish the complete functional AURA codebase while publishing zero personal secrets.

The repository should include source/runtime/UI/voice engines/Skills/Maps-GPS/weather/search/files/productivity/
memory logic/Desktop Intelligence/security/Developer Fabric/i18n/tests and documentation.

The repository must exclude developer API keys, OAuth tokens, cookies, local memory databases, conversation history,
private voice/reference samples, local AI models, logs, caches and generated roadmap/build history.

Mandatory rules:
1. Every user enters their own API keys locally in AURA Settings/onboarding.
2. Real secrets are never committed; only a blank .env.example is public.
3. Provider state may show configured/not configured but never expose full secrets.
4. Profile export excludes secrets by default.
5. Voice engine/voice is user-selectable; private developer voice samples stay out of GitHub.
6. AI models are provisioned/downloaded after clone/install.
7. ZIP/EXE/MSI distribution artifacts belong in GitHub Releases.
8. Active Chromium dist assets are not globally ignored.
9. Run a final secret scan immediately before first push.

Files scanned: 98152
Tree size: 11.99 GB
Estimated normal Git content: 75.13 MB
Estimated tracked content including candidate LFS: 75.13 MB

No AURA source file was modified by this audit.
