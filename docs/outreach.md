# Outreach

The email notice to authors on the site: one personal message per author, sent from the outreach mailbox (`SENDER` in `pyscripts/outreach.py`) through Microsoft Graph. The addresses, the send log and the previews live under the kept external root (`$EXTERNAL_KEPT_ROOT/outreach/`), never in the repo.

```
uv run -m pyscripts outreach render <batch.tsv> [--out DIR] [--backend live]
uv run -m pyscripts outreach login
uv run -m pyscripts outreach send <batch.tsv> [--dry-run] [--backend live] [--log FILE]
```

## Batches

A batch is a TSV with the header `semantic_id`, `email`, `source`. `source` is where the address came from, a key of `SOURCE_SENTENCES`: the footer's "Why you received this email" names it. The file's stem names the batch in the send log. The links carry no tag: the profile and login links lead to the recipient's own profile, so that page's visits in the site's request log are what a message brings.

## Content

`content` reads one author's evidence from the backend through `mcp_server` (`get_entity_profile`, `/peers`, the country breakdown `MAP_TREE`, `get_papers`, `get_impact_dag`, and `/ladder` once per batch), and `pick_facts` turns it into at most `FACTS` facts: the first that hold in this order, each one sentence and the card that shows it.

- Hit paper: the author's hit paper with the highest paper score, as its citations over its bar (the score squared) against the top-share bar of `PAPER_SCORE`; the `papers` card highlighting it.
- Field standing: the tightest `/ladder` band the author's citations from a citing field reach, from `STANDING_MAX_SHARE` up, naming up to `LISTED` fields in it; the `fields` card of `CITING_FIELDS_TREE` by citations, highlighting them.
- Countries citing in excess: up to `LISTED` countries outside the profile's partner nations (`collab-nation`) whose specialization (their share of the author's citation links over their `specBaseline`, as the site's specialization view reads it) reaches `EXCESS_MIN` over at least `EXCESS_MIN_LINKS` links; the `map` card by specialization, highlighting them.
- Momentum: the citations of the last `MOMENTUM_YEARS` finished years over those of the `MOMENTUM_YEARS` before (which need `MOMENTUM_MIN_CITES`), when it reaches `MOMENTUM_MIN_LEAD` times the median of the peers'; the `yearly` card over both windows.
- Citing hit papers: how many of `get_impact_dag`'s citing hits there are ("at least" at `TOP_HIT_PAPERS`) and the strongest of them; the `impact` card.

An author with no fact gets no message: `content` fails, and the batch with it. The profile link and the ORCID login link returning to the profile follow the facts. Links point at the site's canonical host (`LIVE_DOMAIN`), since the bare domain redirects there.

The letter is one block list (`letter`) rendered twice, as the plain-text and the HTML part of one `multipart/alternative` message (`message`); `render` writes each message as `<semantic id>.eml` and `.html`.

## Sending

`send` takes the (author, address) pairs of the batch the send log does not hold, at most `DAILY_CAP` in any `DAY_HOURS`, renders those messages first and fetches every card they show, which also fills the site's card cache, and stops before sending anything when a backend call or a card fails. It paces at `SENDS_PER_MINUTE`. Each pair is claimed in the send log (`SEND_LOG`) before its message goes to Graph and released only when the message certainly did not go out (Graph refused it or could not be reached), so a pair is never sent twice, even after a crash. `--dry-run` does everything but the claim and the send, and creates no log.

Graph receives the rendered MIME message as is (`POST /me/sendMail`, base64 MIME), so the preview is what goes out. It needs an app registration with the delegated `Mail.Send` permission: `OUTREACH_CLIENT_ID` names it and `OUTREACH_TENANT` the tenant (default: the sender's domain). `login` signs in with a device code, refuses an account other than `SENDER`, and keeps the refresh token in `TOKEN_PATH` (under `$XDG_CONFIG_HOME`, outside the repo and the synced roots, mode `TOKEN_MODE`); `send` refreshes the access token from it.
