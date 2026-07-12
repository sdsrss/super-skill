# Task: fix npm packaging before publish

`npm pack --dry-run` currently ships test files and `example.env` alongside
the build. The published tarball must contain exactly:

- `package.json`
- `README.md`
- `dist/index.js`

Fix the packaging configuration so the tarball matches exactly that set.
No `npm install` is needed (use `--dry-run`). Work inside this directory.
