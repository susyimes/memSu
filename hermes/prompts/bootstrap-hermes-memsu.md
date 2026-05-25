You are initializing memSu for Hermes.

Goal:
Install memSu as Hermes' external memory provider and configure Hermes to use
memSu for scoped long-term local memory.

Rules:
- Do not modify unrelated Hermes files.
- Back up every config file before editing.
- Prefer running memSu scripts over manually copying many files.
- If a required path or config is ambiguous, inspect first.
- Do not enable proactive external actions during bootstrap.
- After installation, run the doctor command and report exact results.

Steps:
1. Locate the memSu repository.
2. Inspect `scripts/install_hermes.ps1` and `scripts/doctor.ps1`.
3. Detect `HERMES_HOME`; default to `~/.hermes` if unset.
4. Run the installer with the resolved Hermes home.
5. Verify that the memory provider exists under Hermes plugins.
6. Verify that memSu skills are installed.
7. Ensure Hermes config contains:
   - `memory.enabled = true`
   - `memory.provider = memsu`
8. Start or verify the local memSu service.
9. Run the doctor script.
10. Create one synthetic test event and verify recall.
11. Report:
   - installed paths
   - config changes
   - service status
   - smoke test result
   - anything requiring user action

