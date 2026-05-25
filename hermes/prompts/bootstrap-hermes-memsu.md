You are initializing memSu for Hermes.

Goal:
Install memSu skills for Hermes and verify Hermes can use the memSu CLI for
scoped long-term local memory.

Rules:
- Do not modify unrelated Hermes files.
- Do not edit Hermes config unless the user explicitly asks for it.
- Back up every config file before editing if an explicit config edit is needed.
- Prefer running memSu scripts over manually copying many files.
- If a required path or config is ambiguous, inspect first.
- Do not enable proactive external actions during bootstrap.
- After installation, run the doctor command and report exact results.

Steps:
1. Locate the memSu repository.
2. Inspect `scripts/install_hermes.ps1` and `scripts/doctor.ps1`.
3. Detect `HERMES_HOME`; default to `~/.hermes` if unset.
4. Run the installer with the resolved Hermes home.
5. Verify that memSu skills are installed.
6. Verify that memSu CLI commands are available from the resolved repo.
7. Verify Hermes can execute `python -m memsu doctor`.
8. Do not start a resident memSu service.
9. Create one synthetic test event and verify recall through the CLI.
10. Report:
   - installed paths
   - config changes
   - CLI status
   - smoke test result
   - anything requiring user action
