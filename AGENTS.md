# Project Notes for Coding Assistants

- The user's local runtime is a conda environment named `eval`.
- The Codex desktop runtime may differ. In this session, `python` resolved to `D:\ProgramData\anaconda3\python.exe`, not the user's `eval` environment.
- Prefer treating local command results as a lightweight sanity check unless the command is explicitly run inside conda env `eval`.
- Before full backend/frontend verification, the user may need to run commands from their `eval` environment.
- For local backend development without MySQL, keep `backend/.env` using `DATABASE_URL=sqlite:///./agent_eval.db`. A later duplicate MySQL `DATABASE_URL` line will override SQLite and cause startup to fail if MySQL is not running on `localhost:3306`.
