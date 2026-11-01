# Google Cloud project and sign-in

Outline only. Step 1 proves Google sign-in. Step 2 writes the install prompts. This guide is filled in across those steps. It never contains a real client secret.

## The Google Cloud project

What to create: one project for CampusView, one OAuth client of the kind a web server uses, and the consent screen. Who in the district should own that project.

## The OAuth client

Which redirect URL must match the CampusView sign-in callback. Which two values the installer asks for (client id and client secret) and where the secret is stored (server env or Docker secret, not either git repo).

## Who may sign in

CampusView does not register people automatically. A system admin creates the user first, using the person's Google email. A Google account that has no CampusView user gets no access. How that pairs with default deny.

## First sign-in

The path the operator follows after install: create the system admin, sign in with Google, confirm a user with no role sees no students.

## When something fails

The usual mismatches, described without secrets: redirect URL does not match, the client id is for a different project, the user's email is not the one that was invited, the clock on the server is wrong.

## Rotating the secret

How to create a new client secret, put it in the server env, restart Django, and revoke the old secret. The district repo is not part of this.
