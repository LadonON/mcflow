# doctor

`mcflow doctor` checks every external tool the workflow needs. For anything wrong, it prints a fix that works on the user's OS.

| File | Does |
|---|---|
| `env.py` | `SystemEnv`, the only way checks touch the machine (which, run, read files, list folders) |
| `java.py` | Finds JDKs through `JAVA_HOME`, the `java` on PATH (asked for its `java.home`, so shims are resolved) and the usual install folders. It reads each JDK's `release` file to get the version. |
| `checks.py` | One function per check, plus `ALL_CHECKS` in display order |
| `__init__.py` | Runs the checks and renders the table and fixes |

## Statuses

- **ok:** nothing to do.
- **warn:** mcflow works, but something deserves attention (the Paper version is no longer supported by PaperMC, `JAVA_HOME` points at an old JDK when a suitable one is installed, gh isn't signed in).
- **fail:** a required tool is missing or unusable. `doctor` exits with code 1.

## Adding a check

1. Write `check_<thing>(env, ctx) -> CheckResult` in `checks.py`. Every `FAIL` must carry a `fix`; a test enforces this.
2. Read versions and pins from `versions.toml` through `pins()`. Never hard-code them.
3. Add it to `ALL_CHECKS`.
4. Test it with `FakeEnv` (in `tests/conftest.py`), which scripts command output and confines file access to a temp folder.
