# Repository Problems and Recommendations

This document summarizes the issues found in the repository and recommended fixes. Add, edit, or request clarifications and I can update this file.

1) Hardcoded workspace path
- Problem: WORKSPACE_DIR = "/Volumes/new/LocalDubWorkspace" is hardcoded in backend/backend_server.py and README implies this path.
- Risk: Not portable across environments; causes crashes if path missing.
- Recommendation: Use an environment variable (e.g., LOCALDUB_WORKSPACE) with a sane default. Validate the path on startup and provide helpful error messages.

2) Hardcoded GCP project ID and location
- Problem: GCP_PROJECT_ID and GCP_LOCATION are set directly in backend/scripts/dubber.py.
- Risk: Leaks project identifiers; prevents multi-account usage; may expose sensitive metadata.
- Recommendation: Move these values to environment variables (e.g., GCP_PROJECT_ID, GCP_LOCATION) and load via os.getenv or a config library. Do not store credentials or secrets in code.

3) CORS is wide-open
- Problem: CORSMiddleware configured with allow_origins=["*"] in backend_server.py.
- Risk: Cross-origin requests from any origin are accepted; increases attack surface when other protections are missing.
- Recommendation: Restrict origins in production (or require API key/auth). Use configurable ALLOWED_ORIGINS.

4) No authentication/authorization
- Problem: Sensitive endpoints (create/delete upload) are unprotected.
- Risk: Malicious actors could upload, delete, or tamper with projects on any publicly accessible server.
- Recommendation: Add simple authentication (API key header, JWT, or OAuth) and role checks. At minimum, require an API key for destructive operations.

5) Filename sanitization and path traversal risk
- Problem: Uploaded filenames only have spaces replaced; they are used directly when saving files.
- Risk: Path traversal payloads, invalid characters, or unpredictable filenames may lead to file overwrite or injections.
- Recommendation: Sanitize filenames (e.g., use a secure_filename implementation) and generate internal IDs / random filenames. Validate input and avoid using user-supplied paths directly.

6) No upload size or type limits
- Problem: No checks on uploaded file sizes or strict content-type validation.
- Risk: Disk exhaustion or processing of malicious/incorrect file types.
- Recommendation: Enforce maximum file size per upload and verify content-type/magic bytes. Stream uploads to disk safely and enforce quotas.

7) Static mounts expose full workspace
- Problem: app.mount('/media', StaticFiles(directory=PROJECTS_DIR)) directly exposes project directories.
- Risk: Sensitive files in the workspace may be publicly available via /media.
- Recommendation: Serve only intended public assets or implement access checks; create a safe public subfolder or use token-based access paths.

8) Missing dependency manifest and install instructions for reproducible environments
- Problem: No requirements.txt, pyproject.toml, Pipfile, or lockfile is present.
- Risk: Reproducing or deploying the app is error-prone; package versions unknown.
- Recommendation: Add requirements.txt or pyproject.toml with pinned versions. Consider adding Dockerfile for reproducible runtime.

9) No environment/config management
- Problem: Settings (paths, GCP IDs, feature toggles) are hardcoded instead of configured.
- Risk: Hard to operate across environments (dev/staging/prod).
- Recommendation: Add a config layer (env vars, .env, or a config file). Document required env vars in README.

10) No tests or CI
- Problem: No unit or integration tests and no CI workflow.
- Risk: Regressions and manual deploy checks; risky for contributors.
- Recommendation: Add basic tests for API endpoints and scripts; add GitHub Actions to run linting and tests on PRs.

11) Subprocess & external tool handling
- Problem: Scripts call ffmpeg via subprocess without robust error handling; dubber.py requires ffmpeg in PATH.
- Risk: Silent failures or incomplete cleanup on errors.
- Recommendation: Validate presence of external binaries at startup; capture subprocess stderr for logs; fail gracefully with actionable errors.

12) Secrets handling & discovery risk
- Problem: GCP project ID present in code and other secrets may be present in other files.
- Risk: Sensitive information may be leaked if private keys or credentials were committed.
- Recommendation: Search repo history for secrets, remove them from code, and use env vars or secret management. Rotate any exposed credentials.

13) Lack of logging and structured error handling
- Problem: Minimal print statements in scripts and no centralized logging in backend.
- Risk: Hard to debug production issues and correlate events.
- Recommendation: Add Python logging (structured JSON optional) with log levels; return consistent error responses from API endpoints.

14) Input validation gaps
- Problem: Endpoints accept parameters (e.g., category, file_name) without strict validation or sanitization.
- Risk: Unexpected values may cause file access errors.
- Recommendation: Validate and sanitize all inputs; use pydantic models for API request bodies where appropriate.

15) No rate limiting or quotas
- Problem: No request throttling on API endpoints.
- Risk: DoS or accidental resource exhaustion.
- Recommendation: Implement rate limiting (e.g., via a middleware) for public deployments.

16) Frontend security considerations
- Problem: Frontend loads files served directly from /media; potential for XSS via crafted filenames or content.
- Risk: Cross-site scripting or injection in the browser UI.
- Recommendation: Escape filenames/metadata displayed in the UI; validate resources served and sanitize HTML where appropriate.

17) Missing packaging / deployment artifacts
- Problem: No Dockerfile, Compose file, or cloud deployment manifests.
- Risk: Hard to deploy consistently across environments.
- Recommendation: Add a Dockerfile and optional docker-compose for local development and a deployment guide.

18) No tests for script idempotency and timing assumptions
- Problem: Scripts depend on mtime checks and file naming conventions.
- Risk: Race conditions or inconsistent renaming may break incremental pipeline logic.
- Recommendation: Add unit/integration tests covering timestamp-based skipping logic and failure modes.

19) No coverage of concurrency/safety when multiple users trigger same project
- Problem: Filesystem-based locking not present.
- Risk: Concurrent runs may overwrite files or corrupt project state.
- Recommendation: Implement file-based locks, process locks, or use a small DB record to coordinate pipeline runs per project.

20) Missing dependency on requirements in repo and potential platform-specific assumptions
- Problem: README references macOS and Python versions; code may assume behavior only valid on macOS (like /Volumes path).
- Risk: Non-macOS users cannot run the app; unclear compatibility.
- Recommendation: Document supported OS and Python versions and make paths configurable.

---

Next steps / Quick wins:
- Add a .env.template and use os.getenv for all configurable values.
- Add requirements.txt with pinned package versions.
- Replace hardcoded paths and IDs with env vars and validate on startup.
- Add API key authentication for destructive endpoints and restrict CORS.
- Add secure_filename logic and file-size limits for uploads.
- Add a simple GitHub Actions workflow to run linting and tests.
- Create a Dockerfile for reproducible deployments.

If you'd like, I can:
- Open a PR with a starter requirements.txt and .env.template,
- Create a GitHub Actions workflow draft,
- Replace hardcoded settings in backend_server.py with environment variables and update README.

