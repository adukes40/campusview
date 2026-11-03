# Set up the product and district repos, and your servers

CampusView uses two git repos and at least two servers. This guide shows how to set them up for any district. It uses fake names throughout: the district `example-district`, the GitHub account `example-district`, and servers under `example.org`. Use your own names in their place.

Parts of this guide describe work that is not built yet. Those parts are marked **Not built yet**.

The release flow here comes from Austin (relayed by CampusView Engineer, 2026-11-03): production pins a release tag cut from `main`, and the dev server follows `dev`. Production pinning tags is the CampusView Engineer's reading of Austin's reply. The rules themselves are in [INVARIANTS.md](../INVARIANTS.md) and [DECISIONS.md](../DECISIONS.md).

## What goes where

| Place | What it holds | What it never holds |
| --- | --- | --- |
| Product repo, public: `adukes40/campusview` | Generic code, the installer, SQL for the reporting views, and these docs. The same for every district. | Anything about one district. Student data. Training files. Screenshots. Secrets. |
| District repo, private: for example `example-district/campusview-district` | That district's settings that are not secret: code mappings, branding, exported Superset dashboards, display name, time zone, and history length. | Secrets. Student data or extracts. |
| The server, outside both repos | Secrets in `/etc/campusview/campusview.env`. The TLS key. The deploy key that reads the district repo. Student extracts in the SFTP drop. | Nothing from here is copied into a repo. |
| The builder's computer | A clone of the product repo, and the training-database files used for testing. | Production data. |

A district does not fork the product repo. Every district runs the same public code. What makes a server belong to one district is its district repo and its own secrets.

## The branches and servers

| Name | Follows | Who uses it |
| --- | --- | --- |
| The builder's computer | Any working branch | The builder builds and tests here. This is the testing install, with the fictional training-database files. A separate fake-data server can be added later. |
| `dev` branch | `main` plus the changes being tried | Holds the next changes until Austin approves them. |
| Dev server, for example `cv-dev.example.org` | The `dev` branch | Austin checks changes here. It holds real district data and follows production rules for data and access: no sandbox database user, no training files, and no agent access. |
| Production server, for example `cv.example.org` | A release tag cut from `main`, such as `v1.3.0` | Staff. |

The product repo has a `dev` branch and basic CI (`.github/workflows/ci.yml`), which runs the tests on every push and pull request. **Not built yet:** release tags.

## How a change reaches production

1. The builder builds and tests on its own computer. It shows Austin screenshots of the result. The screenshots are shared outside the repo. They never go in the public repo.
2. The builder pushes the change to the `dev` branch. `dev` is `main` plus the new changes.
3. The dev server pulls `dev` and is updated. Austin checks it.
4. If it looks good, Austin merges `dev` into `main`.
5. A release tag is cut from `main`, as in [Tag a release](#tag-a-release). The CampusView Engineer reminds Austin to do this after each merge.
6. Austin moves the production server to that tag.

No server follows `main`. Production never follows a branch.

## Set up the product repo

There is nothing to set up for a new district. The product repo is public, and a server can read it without a key.

To make the `dev` branch the first time, a person with write access to the repo runs this on their own computer.

```bash
git clone https://github.com/adukes40/campusview.git
cd campusview
git switch -c dev origin/main
git push -u origin dev
```

After a change on `dev` is merged into `main`, bring `dev` back in line with `main` before the next change starts.

```bash
git switch dev
git pull
git merge origin/main
git push
```

## Create the district repo

1. On GitHub, create a new **private** repo, for example `example-district/campusview-district`. Add a README that says it holds district settings, no secrets, and no student data.
2. Add a `.gitignore` that keeps likely mistakes out:

   ```gitignore
   *.env
   *.key
   *.pem
   *.csv
   !map_*.csv
   ```

   `*.csv` keeps an extract from being committed. `!map_*.csv` puts the code-mapping files back in. The ten files sit at the checkout root, next to the README. On a server that root is `/opt/campusview-district`.

3. Copy `examples/district/` from the product repo into that root. Replace the `FAKE-` rows with this district's codes. `git add` the ten names and commit them in this private repo. Give write access only to the people who change district settings. A server never gets write access.

Put the files beside the README. The loader reads `map_grades.csv` in the directory you pass, for example `/opt/campusview-district/map_grades.csv`. It does not open a `mappings/` folder. Branding, dashboard exports, and the settings file come later.

Before every commit to the district repo, run `git status` and `git diff --cached` and check that no password, key, extract, or screenshot is listed.

## Give a server read access to the district repo

A server reads the private district repo with a **deploy key**: an SSH key that belongs to that one repo and can only read it. Make one key per server. If a server is lost, delete only its key.

The commands run as the Linux account that runs CampusView (question 1 in the installer). The examples call it `cvadmin`. If the account is `root` (the default on Debian), leave out `runuser -u cvadmin --` and use `/root/.ssh` in place of `/home/cvadmin/.ssh`.

### 1. Make the key on the server

On Debian, as root:

```bash
runuser -u cvadmin -- mkdir -p -m 700 /home/cvadmin/.ssh
runuser -u cvadmin -- ssh-keygen -t ed25519 -N '' -C 'campusview cv-dev.example.org' -f /home/cvadmin/.ssh/campusview_district
```

On Ubuntu:

```bash
sudo -u cvadmin mkdir -p -m 700 /home/cvadmin/.ssh
sudo -u cvadmin ssh-keygen -t ed25519 -N '' -C 'campusview cv-dev.example.org' -f /home/cvadmin/.ssh/campusview_district
```

The private key stays on the server. Never copy it into a repo, a ticket, or a chat.

### 2. Add the public key on GitHub

Show the public half. It ends in `.pub`, and it is safe to copy.

```bash
cat /home/cvadmin/.ssh/campusview_district.pub
```

In the district repo on GitHub, open **Settings**, then **Deploy keys**, then **Add deploy key**. Name it after the server, paste the public key, and leave **Allow write access** unticked.

### 3. Tell SSH which key to use

Add this to `/home/cvadmin/.ssh/config`. The name `github-district` is only a label, so the key is used for this repo and nothing else.

```text
Host github-district
    HostName github.com
    User git
    IdentityFile /home/cvadmin/.ssh/campusview_district
    IdentitiesOnly yes
```

Then, as that account, test it once. The first time, SSH shows GitHub's host key fingerprint. Compare it with the fingerprints GitHub publishes in its docs before you answer `yes`.

On Debian, as root:

```bash
runuser -u cvadmin -- ssh -T github-district
```

On Ubuntu:

```bash
sudo -u cvadmin ssh -T github-district
```

GitHub answers that you have authenticated but it does not provide shell access. That means the key works.

### 4. Clone the district repo

Use `/opt/campusview-district`, beside the install folder. The update command pulls that exact folder when it is a git checkout. **Not built yet:** a setting for this folder. The installer does not ask for it or clone it. The loader reads the directory when you pass that path. Nothing in the installer creates the checkout.

On Debian, as root:

```bash
mkdir -p /opt/campusview-district
chown cvadmin: /opt/campusview-district
runuser -u cvadmin -- git clone git@github-district:example-district/campusview-district.git /opt/campusview-district
```

On Ubuntu:

```bash
sudo mkdir -p /opt/campusview-district
sudo chown cvadmin: /opt/campusview-district
sudo -u cvadmin git clone git@github-district:example-district/campusview-district.git /opt/campusview-district
```

To pick up a change to district settings later, pull it. Only fast-forward, so the server never makes its own commits. On Debian, as root:

```bash
runuser -u cvadmin -- git -C /opt/campusview-district pull --ff-only
```

On Ubuntu, use `sudo -u cvadmin` in place of `runuser -u cvadmin --`.

The loader reads the code-mapping files from the district directory on each load. **Not built yet:** how CampusView picks up branding or other settings after a pull. Whether those need a restart is set when they are built.

## Set up a server

Do this once for the dev server and once for production. Each district sets up its own servers the same way, with its own district repo and its own secrets.

1. Pick a server that meets [Server requirements](server-requirements.md).
2. Run the installer as in [Install and upgrade](install-and-upgrade.md). Each server makes its own passwords and secret key. Do not copy the password file from one server to another.
3. Choose how people reach it. Production always uses HTTPS. Plain HTTP is for an on-prem test machine with fake data that is not on the internet. The dev server holds real data, but Austin accepted one exception (Austin, relayed by CampusView Engineer, 2026-11-03): the on-prem dev server may use plain HTTP during early testing. It must move to HTTPS before production gets Google sign-on or real users. Plain HTTP sends logins and data unencrypted across the network.
4. Give the server read access to the district repo and clone it, as above.
5. On the dev server, leave `CV_REF` as `dev`. On production, set `CV_REF` in `/etc/campusview/campusview.env` to the release tag.
6. Do not add the sandbox database user or training files to production or the dev server. They belong only on the testing install.

The installer checks out the product repo into the install folder at the ref in `CV_REF`. It does not clone the district repo.

## Update a server

Run the update command.

```bash
sudo bash /opt/campusview/install.sh --update
```

On the dev server, leave `CV_REF` as `dev`. On production, set `CV_REF` in `/etc/campusview/campusview.env` to the release tag. Then run the same command.

To go back to an older tag, run this.

```bash
sudo bash /opt/campusview/install.sh --update --allow-downgrade
```

On Debian as root, leave off `sudo`.

The command pulls `/opt/campusview-district` when that folder is already a checkout. The pull is `git pull --ff-only`. When the folder is not a checkout, you see one skip line, `No district checkout at /opt/campusview-district. Skipped.` The command does not clone the district repo.

The pull runs as the account that runs CampusView (`CV_RUN_USER`). If a different account owns the district folder, for example root runs CampusView and `cvadmin` owns the folder, git refuses it as `dubious ownership` and the update stops before the product moves.

## Tag a release

Cut a tag after Austin merges `dev` into `main` and the change looks right on the dev server. Tags look like `v1.3.0`: raise the last number for a fix, the middle number for new features, and the first number for a change that needs extra steps on upgrade.

Before you tag, check that CI passed on that `main` commit, and that the release installs on a clean machine and upgrades a machine on the previous tag. Basic CI exists. **Not built yet:** the clean-install and upgrade checks in CI.

On your own computer, with write access to the product repo:

```bash
git switch main
git pull
git tag -a v1.3.0 -m "CampusView v1.3.0"
git push origin v1.3.0
```

To see the tags that exist:

```bash
git tag --list 'v*' --sort=-v:refname
```

Do not move or delete a tag after it is pushed. If a release has a problem, fix it on `dev`, merge, and cut the next tag.

Change `CV_REF` in `/etc/campusview/campusview.env` to the new tag. Then run the update command.

## Keep secrets out of both repos

- Secrets live only in `/etc/campusview/campusview.env` on each server, mode 600. The TLS key and the deploy key also stay on the server.
- Neither repo ever holds a password, a key, a token, an extract, or a screenshot.
- If a secret is committed by mistake, deleting it in a new commit is not enough, because git keeps history. Change that password or key on the server first, then clean the repo.
- A deploy key that leaks can only read the district repo. Delete it on GitHub under **Deploy keys**, then make a new one.
