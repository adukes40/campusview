# Google sign-in

**Open question.** The approved plan said staff sign in with Google. In v1, sign-in is Superset's own login, and the base install uses Superset's own user accounts. Superset can be set up for Google sign-in through its config file, but that is not in the base install, and whether and when to turn it on is Austin's decision. See [../PLAN.md](../PLAN.md).

The outline below applies only if Google sign-in is turned on. It never contains a real client secret.

## The Google Cloud project

What to create: one project for CampusView, one OAuth client of the kind a web server uses, and the consent screen. Who in the district should own that project.

## The OAuth client

Which redirect URL must match Superset's sign-in callback. Which two values are needed (client id and client secret) and where the secret is stored (a config file on the server, not either git repo).

Google sign-in also needs Superset to be reachable at a real web address, which needs the reverse proxy and TLS that are not in the base install yet.

## Who may sign in

CampusView does not register people automatically. A Google account that has no matching Superset user, or no role, gets no data. How that pairs with default deny.

## When something fails

The usual mismatches, described without secrets: redirect URL does not match, the client id is for a different project, the user's email is not the one that was set up, the clock on the server is wrong.

## Rotating the secret

How to create a new client secret, put it in the server config file, restart Superset, and revoke the old secret. The district repo is not part of this.
