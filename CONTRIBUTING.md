# Contributing

## Git Workflow for the Repo

Please **do not push directly to `1.0`**. `1.0` is protected and changes need to go through a PR.

For each assignment/change:

**1. Make sure you're up to date**

```bash
git checkout 1.0
git pull origin 1.0
```

**2. Create a new branch**
Use a descriptive name:

```bash
git checkout -b your-name/assignment-name
```

Example:

```bash
git checkout -b john/project-1
```

**3. Make your changes**

**4. Commit your changes**

```bash
git add .
git commit -m "Add project 1"
```

**5. Push your branch**

```bash
git push -u origin your-name/assignment-name
```

**6. Open a Pull Request**
On GitHub, create a PR from your branch → `1.0`.

I'll review the PR and merge it into `1.0`.

**7. After the PR is merged, update your local `1.0`**

```bash
git checkout 1.0
git pull origin 1.0
```

Then create a new branch for your next change.
