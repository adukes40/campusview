# Set up the product and district repos, and your servers

CampusView uses two git repos and at least two servers. This guide shows how to set them up for any district. It uses fake names throughout: the district `example-district`, the GitHub account `example-district`, and servers under `example.org`. Use your own names in their place.

Parts of this guide describe work that is not built yet. Those parts are marked **Not built yet**. One choice is still open, and it is marked **Pending Austin's decision**.

The release flow here comes from Austin (relayed by CampusView Engineer, 2026-11-03). Some older docs still say production runs a release tag. Those rules have not been changed yet. Until they are, [INVARIANTS.md](../INVARIANTS.md) and [DECISIONS.md](../DECISIONS.md) are the record.

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
| The builder's computer | Any working branch | The builder builds and tests here. |
| `dev` branch | `main` plus the changes being tried | Holds the next changes until Austin approves them. |
| Dev server, for example `cv-dev.example.org` | The `dev` branch | Austin checks changes here. It is set up like production, so it behaves almost the same. |
| Production server, for example `cv.example.org` | `main`, or a tag cut from `main`. **Pending Austin's decision.** | Staff. |

**Not built yet:** the product repo has no `dev` branch, no release tags, and no CI workflow today.

## How a change reaches production

1. The builder builds and tests on its own computer. It shows Austin screenshots of the result. The screenshots are shared outside the repo. They never go in the public repo.
2. The builder pushes the change to the `dev` branch. `dev` is `main` plus the new changes.
3. The dev server pulls `dev` and is updated. Austin checks it.
4. If it looks good, Austin merges `dev` into `main`.
5. Austin updates the production server. Whether production then follows `main` directly, or a tag cut from `main`, is **Pending Austin's decision**.

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
   ```

3. Give write access only to the people who change district settings. A server never gets write access.

**Not built yet:** the folder layout inside the district repo. The loader in step 1 reads code-mapping files from it ([DATA_CONTRACT.md](../DATA_CONTRACT.md)). Branding, dashboard exports, and the settings file come later. Until the layout is set, the repo holds only its README.

Before every commit to the district repo, run `git status` and `git diff --cached` and check that no password, key, extract, or screenshot is listed.

## Give a server read access to the district repo

A server reads the private district repo with a **deploy key**: an SSH key that belongs to that one repo and can only read it. Make one key per server. If a server is lost, delete only its key.

The commands run as the Linux account that runs CampusView (question 1 in the installer). The examples call it `cvadmin`. If you chose `root`, run the Debian commands as written and leave out `runuser -u cvadmin --`.

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

**Not built yet:** the folder CampusView reads district files from. The installer does not ask for it, and nothing reads it yet. `/opt/campusview-district` is the proposed folder, beside the install folder.

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

**Not built yet:** how CampusView picks up new district settings after a pull. Mapping files are read on each load, once the loader exists. Whether branding or other settings need a restart is set when they are built.

## Set up a server

Do this once for the dev server and once for production. Each district sets up its own servers the same way, with its own district repo and its own secrets.

1. Pick a server that meets [Server requirements](server-requirements.md).
2. Run the installer as in [Install and upgrade](install-and-upgrade.md). Each server makes its own passwords and secret key. Do not copy the password file from one server to another.
3. Choose how people reach it. Plain HTTP is only for a test server that is on-prem and not on the internet. Production uses HTTPS.
4. Give the server read access to the district repo and clone it, as above.
5. On the dev server, set it to follow `dev`. On production, set it to follow `main` or a tag. **Not built yet**, and the production choice is **Pending Austin's decision**.

Today the installer is fetched from `main` as a single file. It does not clone the product repo, does not read a branch or a tag, and does not know about the district repo.

## Update a server

**Not built yet.** There is no update command. Today, running `install.sh` again only re-checks the base install; it does not pull new product code. When the update command exists, it will:

- pull the branch or tag the server follows, from the product repo
- pull the district repo with `--ff-only`
- run migrations, then restart the services
- leave the password file, the district repo's history, and the SFTP drop alone

## Keep secrets out of both repos

- Secrets live only in `/etc/campusview/campusview.env` on each server, mode 600. The TLS key and the deploy key also stay on the server.
- Neither repo ever holds a password, a key, a token, an extract, or a screenshot.
- If a secret is committed by mistake, deleting it in a new commit is not enough, because git keeps history. Change that password or key on the server first, then clean the repo.
- A deploy key that leaks can only read the district repo. Delete it on GitHub under **Deploy keys**, then make a new one.
