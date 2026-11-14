# templates

`project/` is copied into every workspace `mcflow init` creates. It's turned into files by `mcflow/scaffold.py`.

Naming rules:

- `*.tmpl` files are rendered with `${project_name}`, `${paper_version}` and `${java_minimum}`, then saved without the `.tmpl` suffix. Other `$` signs are left alone.
- `_gitignore` becomes `.gitignore`. A real `.gitignore` here would make git ignore parts of the template.
- `.gitkeep` keeps an otherwise empty folder in the package.

`mcflow.toml` isn't a template. It's generated from `ProjectConfig` in `mcflow/project.py`.

If you add a file here, add it to `EXPECTED_FILES` in `tests/test_scaffold.py`.
