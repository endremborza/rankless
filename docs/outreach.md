# Outreach

The email notice to authors on the site: one personal message per author, sent from the outreach mailbox (`SENDER` in `pyscripts/outreach.py`) through Microsoft Graph. The addresses, the send log and the previews live under the kept external root (`$EXTERNAL_KEPT_ROOT/outreach/`), never in the repo.

```
uv run -m pyscripts outreach render <batch.tsv> [--out DIR] [--backend live]
uv run -m pyscripts outreach login
uv run -m pyscripts outreach send <batch.tsv> [--dry-run] [--backend live] [--log FILE]
```

## Batches

A batch is a TSV with the header `semantic_id`, `email`, `source`. `source` is where the address came from, a key of `SOURCE_SENTENCES`: the footer's "Why you received this email" names it. A source whose sentence still holds `PLACEHOLDER` renders but does not send. The file's stem names the batch, and every link in its messages carries it as `?ref=<batch>`, so the site's request log counts each batch's visits. The cards carry none, so a card is one cache entry and an image fetch counts no open.

## Content

`content` fills one author's message from the backend through `mcp_server` (`get_entity_profile`, `get_peers`, `get_citation_tree`), as the site's cards draw it:

- citing countries: the first `LISTED` level-1 nodes, by citation links, of the breakdown the `map` card draws by default (`MAP_TREE`, the first with countries at level 1, from the first of `TREE_SPECS.yearBreaks`), node 0 left out as the map leaves it out; the `map` card highlights them (`hl`);
- peers: the first `LISTED` of `/peers`, in served order; the `peers` card compares with the first;
- co-authors: the first `LISTED` of `relations["paper-authors"]`, the order the `network` card ranks them in; the card highlights them (`with`) and exists only from the network kind's minimum node count;
- the `tree` card, the profile link and the ORCID login link returning to the profile.

A section whose card the author lacks is left out with its card. Links point at the site's canonical host (`LIVE_DOMAIN`), since the bare domain redirects there.

The letter is one block list (`letter`) rendered twice, as the plain-text and the HTML part of one `multipart/alternative` message (`message`); `render` writes each message as `<semantic id>.eml` and `.html`.

## Sending

`send` takes the (author, address) pairs of the batch the send log does not hold, at most `DAILY_CAP` in any `DAY_HOURS`, renders those messages first and fetches every card they show, which also fills the site's card cache, and stops before sending anything when a backend call or a card fails. It paces at `SENDS_PER_MINUTE`. Each pair is claimed in the send log (`SEND_LOG`) before its message goes to Graph and released only when the message certainly did not go out (Graph refused it or could not be reached), so a pair is never sent twice, even after a crash. `--dry-run` does everything but the refusal of an unworded source, the claim and the send, and creates no log.

Graph receives the rendered MIME message as is (`POST /me/sendMail`, base64 MIME), so the preview is what goes out. It needs an app registration with the delegated `Mail.Send` permission: `OUTREACH_CLIENT_ID` names it and `OUTREACH_TENANT` the tenant (default: the sender's domain). `login` signs in with a device code, refuses an account other than `SENDER`, and keeps the refresh token in `TOKEN_PATH` (under `$XDG_CONFIG_HOME`, outside the repo and the synced roots, mode `TOKEN_MODE`); `send` refreshes the access token from it.
