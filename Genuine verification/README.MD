# MC Launcher: Account Verification Experiments

A small standalone project for figuring out how "genuine account verification" should actually work. The UI is just a shell — the point is the verification layer.

> This directory only copies styles and the avatar module from the main project. It never modifies the main project.

## How to run

```powershell
cd "experiments/Genuine verification"
pip install -r requirements.txt
python main.py
```

Self-tests (no window):

```powershell
python -m core.verify.selftest       # SLP / Query protocol (offline fake server)
python -m core.verify.selftest_ali   # authlib-injector protocol + external-login verifier (offline)
python -m core.verify.selftest_ms    # Microsoft six-step chain + account storage (offline fake server)
python -m core.verify.yggdrasil <site> [character name]   # query a real verification site
python -m core.verify.mcping <server>                     # query a real server's online player list
python -m core.verify.srv <domain>                        # query SRV records
python tools\smoke_test.py           # UI: window/styles/three panels/accounts page/Fusion
python tools\e2e_test.py             # full chain: fake server → verifier → UI → avatar
```

## There are three verification methods now

| | Microsoft login | External login (authlib-injector) | Player list (the old way) |
|---|---|---|---|
| What the user fills in | Their own Azure client ID | Verification site address + character name (+ optional password) | Server address + player name |
| Who verifies | Mojang/Microsoft | Third-party verification site | Mojang/Microsoft (done by the server) |
| What it proves | This is a genuine account, and it's yours | The account exists on that site; a password proves it's yours | This is a genuine account |
| Is it real genuine-account verification | ✅ Checks entitlements | ❌ Unrelated to Mojang | ✅ But only meaningful on an online-mode server |
| Needs a password | Goes through Microsoft's official page; the password never passes through us | Not for name lookup; yes for proving ownership | No |
| Interaction | Interactive (device code + polling) | One query | One query |

⚠️ The three methods carry very different levels of certainty. The UI spells out, everywhere, what a given pass actually means.

---

## 1. Microsoft login (genuine account)

### First, the conclusion: the old method (copying a link) is dead

The old flow had the browser end up at `https://login.live.com/oauth20_desktop.srf?code=...`, and the user copied the whole URL back into the launcher. That path no longer works — Microsoft redirects it to `oauth20_desktop.srf?removed=true`, and the code is never obtained.

There are two proper paths now (the ones the Minecraft Wiki lists):

| Path | User experience | Notes |
|---|---|---|
| Device code (what this experiment uses) | Shows a code; the user enters it at `microsoft.com/link` | No local port, no copying long URLs. PCL CE uses this too |
| Authorization code + loopback | Opens the browser automatically and redirects back after authorization | Smoothest, but requires spinning up a temporary local HTTP server to receive the callback |

The device code flow is actually closer to the old experience than "copy the link": it still opens a browser to log in, but replaces "copy a long URL" with "type six characters", and you don't have to transcribe a URL by hand.

### The six-step chain

```
1. OAuth2: get Microsoft access_token   login.microsoftonline.com/consumers/oauth2/v2.0/devicecode → /token
2. Xbox Live auth                       user.auth.xboxlive.com/user/authenticate
3. XSTS authorization                   xsts.auth.xboxlive.com/xsts/authorize
4. Minecraft login                      api.minecraftservices.com/authentication/login_with_xbox
5. Check game ownership                 api.minecraftservices.com/entitlements/mcstore   ← only this step counts as "genuine"
6. Fetch profile (name/UUID/skin)       api.minecraftservices.com/minecraft/profile
```

Step 5 cannot be skipped. Any ordinary Microsoft account can get through the first four steps — an account that hasn't bought the game can still obtain a Minecraft access_token. So "can log in" and "owns the game" are two different things.

The failure reasons at each step are completely different, so errors carry `step` (which step failed), `code`, and a `hint`. Collapsing all of it into "login failed" tells the user nothing.

### How to set up Microsoft login (this is the procedure you asked for)

The following is compiled from the Minecraft Wiki and Microsoft Q&A. Both hard gates are at step 4.

**① Register an Azure app** (no client secret needed)

`portal.azure.com` → Microsoft Entra ID → App registrations → New registration

- Supported account types: pick the one other than "Accounts in this organizational directory only" — you need to be able to sign in personal Microsoft accounts (the code hard-codes the `consumers` tenant, see below)
- No client secret needed (public clients don't use one)

**② Enable "Allow public client flows"**

App → Authentication → at the bottom, "Allow public client flows" → Yes
(The device code flow depends on this; without it, requesting a device code fails immediately with `invalid_client`.)

If you also want the "authorization code + loopback" flow, add the "Mobile and desktop applications" platform and check `https://login.microsoftonline.com/common/oauth2/nativeclient`.

**③ Copy the "Application (client) ID"** → paste it into the input field on this program's "Microsoft login" page

**④ ⚠️ Apply for Minecraft API permission (the most easily overlooked and most blocking step)**

Go to <https://aka.ms/mce-reviewappid> and submit the form.

Without this, step 4 always returns 403 `Invalid app registration` — configuring permissions in the Azure portal alone is not enough; Mojang adds a manual review on top.

#### What this step actually is (not a paid service, not game development)

It's not a paid Azure feature, and it's not "you must make games to use it". It's a whitelist maintained by Mojang: the list of apps allowed to call `api.minecraftservices.com`.

The rumor going around (including an answer from a moderator on Microsoft Q&A) is that "you need to join the Xbox Developer program / ID@Xbox" — that's wrong. A developer (Minelys Launcher) actually asked ID@Xbox and got this:

> Sorry, but this is not something the ID team can help with.
> Minecraft is not managed by the ID team.

#### The real path exists, and someone succeeded

Another developer (louka) posted a success story in the same thread (2026-08-29):

> The solution was to submit the application's Client ID for approval through
> Minecraft's official AppID registration process.
> After submitting the form, I received an email from Mojang Enforcement
> confirming that the application had met the required criteria and had been
> approved for their allow list.

The process:

```
1. Submit the form   https://aka.ms/mce-reviewappid
2. Mojang Enforcement reviews it
3. Approved → client_id is added to the allow list → the 403 at step 4 disappears
```

The key point is "someone succeeded" — not "there's theoretically a path".

#### The review looks at "your launcher", not "what games you've made"

The subject of the application is an app (a Client ID), not a person or a company. The review asks "is this app a legitimate Minecraft launcher", not "what caliber of games has this developer made".

⚠️ Another common misconception: thinking "ship a hit game → join ID@Xbox → get Minecraft permission". That chain is broken — ID@Xbox itself says "Minecraft is not managed by the ID team". The two are completely independent; joining ID@Xbox does not get you the MC allow list.

(Incidentally: Playground Games / Turn 10 are Microsoft first-party studios going through internal channels — there's no "apply for the allow list" step at all. And Forza has nothing to do with MC account authentication, so it's meaningless as an analogy.)

Conversely, this is good news: the success story sounds like an indie developer's small launcher, not a AAA title. So the bar is more likely "is this a real launcher / do you follow the rules" than "is your work impressive enough".

#### One thing that's still unclear

The review criteria are not public. An indie developer asked whether there's a manual review channel for individual developers without a D-U-N-S number (a business identifier), and the question currently has no answer. So: individuals may pass, or a company identity may be required — but submitting the form is free and doesn't require a card, so it's worth a try.

So there are three realistically viable paths:

- Submit the form (there are success stories)
- You already have / can obtain an approved client_id
- Or use the external login (authlib-injector) path — it doesn't require Microsoft to approve anything

**⑤ Two other hard rules** (already hard-coded, but good to know)

- You must use the `consumers` tenant. Using an AAD tenant ID or `common` fails outright, and it only allows personal Microsoft accounts (enterprise accounts can't get in)
- The scope must include `XboxLive.signin`, otherwise step 2 fails in a very hard-to-understand way

### ⚠️ Stuck at portal login: `AADSTS16000` / `ADIBizaUX`

If you see this in the Azure portal (not in this program):

```
interaction_required: AADSTS16000: User account from identity provider 'live.com'
does not exist in tenant 'Microsoft Services' and cannot access the application
'74658136-14ec-4630-ad9b-26e160ff0fc6'(ADIBizaUX) in that tenant.
```

This is not a bug and not caused by us — `ADIBizaUX` is the portal's own client ID. The reason is:

- When you sign in to the portal with a personal Microsoft account (Outlook / Hotmail / live.com), it automatically connects to the "Microsoft Services" system tenant (ID `f8cdef31-a31e-4b4a-93e4-5f571e91255a`)
- That tenant has no directory. So you can't do any administrative operations in it: creating users, creating groups, registering apps — none of it works
- Entra ID → Overview shows that this is the tenant ID; Settings shows there's no associated directory

**Solution: create your own tenant** (free, no purchase required)

1. Open an InPrivate / incognito window (to avoid SSO carrying the login state automatically — if you don't clear it, the problem keeps recurring)
2. Go to <https://azure.microsoft.com/free/> and click "Start free / Try Azure for free"
3. The signup flow lets you create a new directory (tenant); once done, you're the global administrator of that tenant
4. After that, "App registrations" works

(Another route: <https://portal.azure.com/#create/Microsoft.AzureActiveDirectory>, but it requires you to already be in a tenant that has a directory. So the first time, you still have to go through the route above.)

> References: [Can't use Azure Portal](https://learn.microsoft.com/en-au/answers/questions/5846780/cant-use-azure-portal) and [Unable to create OAuth app due to login errors](https://learn.microsoft.com/en-ca/answers/questions/5519679/unable-to-create-oauth-app-due-to-login-errors) — both are Microsoft support responses saying the same thing.

⚠️ But first think about whether it's worth it: even after setting up a tenant and an app, step ④ (the Minecraft API permission allow list) is still waiting. That gate isn't "pay money" or "make games" — it's just filling out a form and waiting for review, and there are success stories (see ④ above). If all you want is a working genuine-account verification, the external login path is already fully usable, and you don't need to wait for review.

#### Does creating a tenant cost money?

Registering an app itself is free, but you need a tenant first, and the "create a tenant" entry point has a barrier:

| Step | Cost |
|---|---|
| Entra ID Free tier | Free (the P2 requirement was dropped in 2021) |
| App registration | Free |
| Creating a tenant ← where it gets stuck | See below |

Both official routes have barriers:

1. **Azure free account** → create a tenant, get the Entra ID Free tier. Requires a credit card (used only for identity verification; nothing is charged within the free limits, but you need an international card)
2. **Microsoft 365 Developer Program** → free E5 sandbox tenant. Now has eligibility requirements: the official wording is
   > Eligible members include Visual Studio Enterprise or Professional subscribers,
   > ISV Success Program or Microsoft AI Cloud Partner Program participants,
   > and Premier or Unified Support customers.

   In other words, the free tenant that used to be available to anyone is no longer available to individual hobbyists.

The only route that doesn't need a card: if you're a student, open Azure for Students with your school email — it explicitly doesn't require a credit card.

#### ⚠️ The virtual card / prepaid card route is dead

If you're thinking of using a third-party "virtual credit card" to get around this, don't waste your money. Microsoft's official documentation is blunt:

> **You're using a virtual or prepaid card**
> Prepaid and virtual cards are not accepted as payment for Azure subscriptions.
>
> — [Troubleshoot a declined card](https://learn.microsoft.com/en-us/azure/cost-management-billing/troubleshoot-billing/troubleshoot-declined-card)

Virtual card platforms charge you tens to hundreds of dollars, Azure rejects it right at the verification step, and registering with a virtual card violates the terms — any tenant you create may also be banned.

But you don't need a credit card — the same document says:

> Credit cards are accepted and debit cards are accepted by most countries or regions.

So a Visa/Mastercard debit card that supports international payments works too (zero cost, worth a try). Note that the document emphasizes two things: the card must have international transactions enabled, and the name/address/CVV must match the card exactly. (A bank's "e-card / digital debit card" also counts as a debit card, as long as it can authorize cross-border transactions.)

#### So will I actually be charged?

No — as long as you don't click "Upgrade". Microsoft's official documentation, Avoid charges with your Azure free account, is clear:

> As long as you have unexpired credit or you use only free services within the
> limits, you're not charged.
>
> Your subscription and services are disabled when your credit runs out or
> expires at the end of 30 days. To continue using Azure services, you must
> upgrade your account.

The key is "disabled", not "charged": when the credit runs out or the 30 days expire, the service is disabled; to start paying, you have to actively upgrade.

And this project creates no billable resources at all:

| What we need | Cost |
|---|---|
| A tenant (Entra ID directory) | Free |
| An app registration | Free (included in the Entra ID Free tier) |

No VMs, no storage, no Azure resources of any kind. An app registration is just an identity record and consumes nothing — the bill stays at $0.00 forever.

The small pre-authorization when you enter the card is not a charge: it's a "hold" to verify the card is valid and can authorize cross-border transactions, typically around $1, automatically reversed within a few days. Don't panic when you see the SMS. (A debit card that can't do pre-authorization will fail at this step — that's the card not supporting it, not you being charged.)

The official promise on the signup page (the exact wording, right in front of you):

> **Spending protection — we won't charge your credit card automatically
> until you move to pay-as-you-go pricing**

"Automatically" is the keyword. It's the same mechanism as the documentation above: credit runs out / expires → service is disabled, not charged. To start paying, you have to actively upgrade.

⚠️ But this protection has three blind spots; don't treat it as all-powerful:

| Situation | Is the protection still there? |
|---|---|
| Free account overused | ✅ Yes — service is disabled, nothing charged |
| 30 days expire / $200 used up | ✅ Yes — service is disabled, nothing charged |
| You click "Upgrade to pay-as-you-go" | ❌ Gone |
| You buy a third-party product from the Marketplace | ❌ Gone (not covered by free credits or the protection) |

So there's only one rule: don't click Upgrade.

"Could they change their mind someday": the terms can indeed change, but this promise has been around for years, and the documentation I cited was updated 2026-03 with consistent wording; and you can cancel the subscription at any time. Also, you're using a debit card — you can only be charged what's in the account, with no credit limit to overdraw, which is an extra physical ceiling.

Three safeguards:

1. **Never click "Upgrade"** — that's the only pay switch
2. **Set a budget alert**: Cost Management → Budgets, amount `$0.01` + email binding; you'll be notified the instant there's any charge at all
3. **Cancel the subscription when done**: Subscriptions → Cancel subscription, and the card is fully unbound

#### So why does "free" still require a card?

Because the card's role is identity verification, not payment collection. The most direct evidence is the comparison:

| | Needs a card | Needs what |
|---|---|---|
| Azure free account | Yes | Credit card / debit card |
| Azure for Students | No | School email |

Students don't need a card but do need an email — showing that what Microsoft wants is "a credential that proves who you are"; students have a school email, everyone else can only prove it with a card.

Three specific reasons:

1. **Preventing abuse of free credits** (the main one): $200 is real money; without a card, you could register unlimited alt accounts to farm credits (mining, spam, proxies). And the card's name/address must match what you entered exactly — that's a characteristic of identity verification, not payment collection.
2. **Pre-registering a payment method**: after the credits run out, if you want to keep using it, having the card saves you from redoing the flow. So it's a "pre-stored payment method", not "immediate collection".
3. **Industry practice**: AWS Free Tier, Google Cloud, and Alibaba Cloud International all require a card.

Honestly, for an individual this is a "trust cost": hand over the card first, then get the "free" thing. The risk isn't zero — accidentally clicking upgrade, account theft, or using a paid third-party Marketplace product can all incur charges. So the three safeguards above aren't superfluous.

And don't forget: even after the tenant and app are done, step ④ (the Minecraft API permission allow list) is still waiting — but that's submitting a form and waiting for review, not paying money and not making games (see ④ above).

### Where does the client ID come from

It must be your own. PCL CE compiles its client id into a secret (`Secrets.MSOAuthClientId`), which isn't in the public repo — using someone else's means impersonating their app, and if something goes wrong, they're the one who gets banned. So this program doesn't embed any client id; you enter it in the UI and it's stored in the config.

### Where are accounts stored

`core/accounts.py` → `accounts.json` in the config directory. It stores the name, UUID, access/refresh token, expiry, and skin URL.

> 🔒 `refresh_token` is equivalent to long-term account access. Right now it's plaintext JSON. The UI only shows the name and token status, never the token itself. Don't commit this file to git, don't send it to anyone. (On Windows you could use DPAPI bound to the user; that's for later.)

The "Accounts" page in the UI shows: which accounts exist, which is current, whether the token is expired, the avatar, and deletion. Expired doesn't mean useless — it can be refreshed with the refresh_token.

---

## 2. External login (authlib-injector / Yggdrasil)

### How it works

`authlib-injector` is a stand-in protocol: it hijacks the Mojang authentication requests in the game client and redirects them to a third-party site. So an "external login site" (skin site / verification site) can issue its own accounts, players log in with the site's account, and can still join servers that have external login enabled.

Externally it's just a Yggdrasil API (the shape of Mojang's old authentication endpoints):

```
<API root>/
    authserver/authenticate      login
    authserver/validate          validate token
    authserver/refresh           refresh token
    sessionserver/session/minecraft/profile/<uuid>   fetch profile (including skin)
    api/profiles/minecraft       batch lookup profiles by name
    textures/<hash>              skin data
```

### Auto-detection (the "the launcher detects it automatically" thing)

The user only enters the site address (`demo.lunch.ink`) and doesn't need to know where the API root is. The launcher sends a request and reads the response header:

```
X-Authlib-Injector-API-Location: /api/yggdrasil/
```

⚠️ This value may be a relative path (in practice demo.lunch.ink returns `/api/yggdrasil/`, with a trailing slash), so it must be joined with `urljoin` against the URL that was requested — it can't be used as an absolute address. It may also be a full URL (cross-origin deployment). Both are accepted. If the user enters an address with a path, respect what they entered.

### Measured on `demo.lunch.ink` (`mc-yggdrasil` 1.0.0)

| Item | Result |
|---|---|
| `GET /` | 200 + `X-Authlib-Injector-API-Location: /api/yggdrasil/` ✅ |
| API root | `serverName: "MC Resource Station"`, `skinDomains: [demo.lunch.ink, .demo.lunch.ink]`, `feature.non_email_login: true` |
| `POST /authserver/authenticate` | 403 `"Invalid credentials. Invalid username or password."` ✅ present |
| `POST /authserver/validate` / `refresh` | 403 `"Invalid token."` ✅ present |
| `POST /api/profiles/minecraft` | 200, unknown names return an empty array (not an error) |
| `GET /sessionserver/.../profile/<uuid>` | unknown UUID returns 204 (not 404) |
| `/api/users`, `/api/user/profile`, `/api/meta` | 404 — no public "list all players" endpoint |

Because of the last row, the external login path looks up by name, not by listing players. That's what the user meant by "player account IDs are configured on the skin site": the ID is decided over there, and we look it up by it here.

### Real site verification record (`kongxia_114`)

The site assigned the character `3224f1a59be543dda10092556ae9ae08`. Measured:

```
lookup_profiles(["kongxia_114"])
  → [{'id': '3224f1a59be543dda10092556ae9ae08', 'name': 'kongxia_114'}]
fetch_profile(id)
  → properties[textures] base64-decoded:
    {"timestamp":..., "profileId":"3224...", "profileName":"kongxia_114", "textures":{}}
                                                              ↑ empty
```

`textures` is `{}` — this character hasn't uploaded a skin yet (the "Upload skin / Upload cape" buttons on the site page are for that). So:

- Skin URL is empty → the avatar falls back to the local default skin picked by UUID (consistent with in-game)
- The result explicitly says "this character hasn't uploaded a skin yet", otherwise the user thinks the avatar failed to load

⚠️ When an external-login character has no skin, don't ask skin sites like mc-heads — they only know Mojang accounts and know nothing about third-party UUIDs, so it's a wasted network round trip. Go straight to the local default skin.

### The two buttons on the site copy things you can paste directly — both work

| Button | What it copies, roughly | How we handle it |
|---|---|---|
| "Copy address (recommended)" | `https://demo.lunch.ink` | Read the response header to auto-detect the API root |
| "Copy full API" | `https://demo.lunch.ink/api/yggdrasil` | The address already has a path → use it directly, no guessing |

The password can be left empty: leaving it empty only checks whether the character exists, without logging in.

### Two "non-standard" things this implementation does (must be tolerated)

**① There's an envelope wrapped around it.** Per the spec, `POST /api/profiles/minecraft` returns a bare array; here it returns `{"success": true, "data": [...], "error": null, "traceId": ...}`. The API root's metadata is also duplicated both at the top level and inside `data`. Everything goes through `_unwrap()`: if it's an array, use the array; if it's an envelope, pull out `data`. Without this layer, the server has the data and it still gets treated as empty.

**② The `error` in the error body is an object, not a string.** Per the spec it's `{"error": "ForbiddenOperationException", "errorMessage": "..."}`; here it's `{"error": {"code": ..., "message": ...}, "errorMessage": "..."}`. Always read `errorMessage` first for error messages.

### Two modes

**Name lookup** (no password) — `POST /api/profiles/minecraft`; if it's found, it exists.

**Login** (requires a password) — `POST /authserver/authenticate` → accessToken + selectedProfile. This proves it's yours. And when `feature.non_email_login` is true, the username is not an email.

> 🔒 The password only appears in `core/verify/yggdrasil.py`. It's not written to config, not logged, and not kept in the result (there's an assertion in `selftest_ali.py` specifically for this). It's `clear()`ed when switching verification methods.

### Avatars: this is the "real skin"

The profile from an ALI site carries a `textures` property (base64-encoded JSON) containing the skin URL:

```
profile.properties[name=="textures"].value
  → base64 decode → {"textures": {"SKIN": {"url": "https://.../textures/abc"}}}
```

Once you have the URL, download the 64×64 skin and use the main project's `ui/avatar.py` `face_pixmap()` to cut out the face at (8,8), overlay the hat layer at (40,8), scale with nearest-neighbor, and round the corners.

This is more accurate than a skin site's generic avatar — it's the real skin. So the skin URL takes priority in PlayerCard.

⚠️ The skin URL's domain must be validated against `skinDomains`. ALI's signing mechanism relies on it to restrict "skins can only be loaded from these domains"; skipping the check means allowing any third-party URL to impersonate a skin.

---

## 3. Player list (the old way)

### How it works

| | What the server does on join | Does this method mean anything |
|---|---|---|
| `online-mode=true` (online-mode server) | Takes the session to Mojang/Microsoft for validation, kicks you if it fails | Yes |
| `online-mode=false` (offline server) | Doesn't check; any name can join | No |

So "can you appear in an online-mode server's player list" is itself a genuine-account verification — the server does the verification, the launcher just takes a look at the list.

### Four states (`inconclusive` cannot be omitted)

| State | Situation | Conclusion |
|---|---|---|
| `verified` passed | Name is in the list | The server accepted this account |
| `absent` not passed | Got the full list, you're not on it | Either you didn't join, or it's not a genuine account |
| `inconclusive` cannot determine | Only a sample list, you weren't sampled | Nothing can be concluded |
| `error` query failed | Can't connect / timeout / protocol mismatch | — |

SLP gives at most 12 names (vanilla behavior); on a busy server you might just not be in the sample. Treating "not sampled" as "not genuine" would wrongly accuse people. Query gives the full list but requires the server to enable `enable-query`, so the order is Query first, falling back to SLP.

Measured on a big server: Hypixel 18611/200000 players, SLP sampled 0 (the sample slots are being used as ad space) — so every entry must be validated for UUID legitimacy to filter out the ads.

---

## Code structure

```
main.py                     entry point (includes app.setStyle("Fusion"))
core/
    app_info.py             app name / version / config directory name
    config.py               config read/write (trimmed down; deliberately not copied from the main project)
    accounts.py             local account storage (accounts.json)
    logbook.py              runtime log + token redaction (redact is the only entry point)
    httplog.py              logged HTTP calls (all requests go through here)
    resources.py            ← copied from the main project: resource paths + style assembly
    theme.py                ← copied from the main project: palette + @variable@ substitution
    verify/                 verification backend (split into modules, independent of the UI)
        base.py             Verifier interface + VerifyResult + four-state definitions
        __init__.py         registry (adding a new method only touches this)
        microsoft_verifier.py  Microsoft login verifier (interactive)
        microsoft.py        Microsoft six-step chain (device code/Xbox/XSTS/Minecraft)
        thirdparty.py       external-login verifier
        yggdrasil.py        authlib-injector / Yggdrasil protocol
        player_list.py      the old way: query the online player list
        mcping.py           SLP / Query protocol (pure protocol, can run standalone)
        srv.py              DNS SRV lookup (builds DNS packets by hand, no dependencies)
        selftest.py         SLP/Query offline self-test
        selftest_ali.py     fake ALI server + external-login offline self-test
        selftest_ms.py      fake Microsoft/Xbox/Minecraft + account-storage offline self-test
ui/
    avatar.py               ← copied from the main project: skin → avatar (face cutout + hat layer)
    avatar_remote.py        avatar/skin download (four-layer fallback: memory/disk/skin site/local)
    icons.py                screen_dpr
    main_window.py          shell window + style loading
    pages/
        verify_page.py      verification page (entry point for the three methods)
        accounts_page.py    accounts page (locally stored accounts)
        log_page.py         runtime log page (live, filterable, copyable)
        placeholder_page.py pages not built yet
    widgets/
        sidebar.py          sidebar
        player_card.py      player card
        device_login.py     Microsoft device-code panel (interactive login)
    workers/
        verify_worker.py    verification background thread (with cancellation and tokens)
assets/
    styles/                 ← copied from the main project (app.qss + parts/)
        parts/80-verify.qss added by this experiment itself (uses the same @variable@ set)
    icons/                  ← copied from the main project
tools/
    smoke_test.py           UI structure and state rendering
    e2e_test.py             the whole chain
```

### Adding a verification method

Write a `Verifier` subclass → add one line to `VERIFIERS` in `core/verify/__init__.py`. The UI automatically shows the button, and automatically decides which inputs to display based on `needs_server` / `needs_player_name` / `needs_password` / `needs_client_id`. If it's the kind that "waits for the user to do something in the browser", set `interactive = True` and the UI switches to the device-code panel — not a single line of UI code changes.

## Deliberate trade-offs

**Config directory is separate**: `%APPDATA%\MosslightVerifyTest`, not mixed with the main project's `Mosslight`, so it doesn't pollute the main program by reading/writing config.

**No third-party libraries in the protocol layer.** `mcping.py` / `srv.py` use only the standard library `socket` (Python has no SRV lookup, but a DNS packet is only a few dozen lines to build by hand). `yggdrasil.py` uses `requests`.

**`app.setStyle("Fusion")` is mandatory.** On Windows, Qt defaults to the native style (on this machine, `windows11`). The native style draws button bevels, dropdown arrows, and checkbox squares itself, and it clashes with the dark QSS — without any error. `smoke_test.py` has an assertion to keep it from being deleted. (Offscreen you can't measure the difference: Fusion and windows11 are pixel-for-pixel 0% different; you have to look in a real window.)

**Four-layer avatar fallback**: memory → disk → (skin site | ALI skin) → 9 local default skins. If a skin site goes down, it only affects whether the avatar looks right, not whether the thing works.

**Not done**: one-click launch of the game into a verification server, persisting verification results, multiple accounts, token refresh/renewal.

## Known limitations

- **The Microsoft login chain has never been run against the real endpoints.** What's missing is an "approved Azure client ID" — without it, step 4 always 403s, and the earlier steps being correct doesn't get you through. So this path is verified with a fake Microsoft + fake Xbox + fake Minecraft (`selftest_ms.py`, 44 items, including the XErr error code table, 403 app-not-authorized, game-not-owned, refresh_token rotation). Once you have an approved client_id, change the config and it works directly; if any step differs from the real response, change the corresponding function in `core/verify/microsoft.py`.
- **`accounts.json` is plaintext.** refresh_token is equivalent to long-term account access. The UI doesn't show tokens, but the file itself isn't encrypted (DPAPI on Windows is possible; not done).
- **External login is not genuine-account verification.** It proves "you own a character on some verification site"; that's enough for servers that trust that site, and has nothing to do with Mojang.
- **External login sites have no "list all players" endpoint** (measured: `/api/users` etc. are all 404), so lookups are by name only.
- **SLP samples only 12 names.** On big servers the "player list" path is basically unusable; it suits "your own verification server" or "servers with few players".
- **Query is off by default.** Many servers don't enable it, so you only get the sample.
- **SRV lookup needs outbound access to port 53.** Some network environments block public DNS; in that case it falls back to the default port 25565 (failing to get SRV is normal, not an error).
- **No "offline server detection".** If the verification server itself is `online-mode=false`, the "passed" from the "player list" method is fake. For now only a warning is shown in the UI.
- **Avatars come from third parties** (skin sites / verification sites / Mojang); availability and rate limits are out of our hands.

## Pitfalls hit along the way

1. **`except Exception` swallowing ImportError** — that's how the main project's "the default game directory never took effect" happened. `core/config.py` only catches `OSError` / `ValueError` when reading config.

2. **Query protocol offsets.** The response is `FE FD` + type + 4-byte session + body. The first version parsed at a fixed offset `data[16:]`, and `hostname` / `numplayers` were all None — it looked like "the server doesn't have query enabled" when the bug was ours. Now it first checks for the magic bytes, then splits by `type(1) + session(4) + body`.

3. **DNS compression pointers.** Domain names in responses may be compression pointers starting with `0xC0`; without decompressing, you read garbage. And the "new offset returned to the caller" must be the position after skipping the pointer.

4. **A dangling reference to `QByteArray`.** The temporary object inside `QBuffer(QByteArray())` gets GC'd, so QBuffer points at freed memory — the process crashes with `0xC0000409` and there's no Python exception to see. You must keep a reference.

5. **Connecting a signal without sending a request.** The first version of `PlayerCard` only connected the avatar downloader's signal and forgot to call `request()`; the symptom was "the avatar stays on the initial-letter placeholder forever" with no error. The e2e assertion at the time said "it's OK to have no avatar when offline", which happened to let it through — an assertion that's too loose is as good as none.

6. **`self.server` is not your wrapper object.** Inside `BaseHTTPRequestHandler`, `self.server` is the `ThreadingHTTPServer` itself. Anything you need must be attached to the httpd, otherwise `self.server.base_url` in the fake server raises AttributeError.

7. **204 is not 404.** ALI's `/sessionserver/.../profile/<uuid>` returns 204 no-content for an unknown UUID. Treating it as 404 turns "this person isn't on this site" into "the server is broken".

8. **After changing objectName, you need unpolish + polish.** Qt won't recompute the style just because the name changed.

9. **The spacer at the end of the layout.** The list container always has an `addStretch()` at the end; cards must be inserted before it with `insertWidget(count()-1, ...)`. Without the spacer, when the content doesn't fill a screen, the extra height gets distributed evenly across rows.

10. **Without Fusion, the custom QSS leaks.** You must `app.setStyle("Fusion")` before creating widgets.

11. **Console encoding.** The Chinese Windows console is GBK; printing the server MOTD (with emoji) raises `UnicodeEncodeError`. And that print is often in an exception branch, so throwing turns "report an error" into "crash". Call `reconfigure(errors="replace")` once at startup.

12. **The `host` field has two shapes; you can't append `:port` unconditionally.** On the player-list path, `host` is a hostname (append the port); on the external-login path, it's a full API root URL. Appending unconditionally makes the detail line render as `https://demo.lunch.ink/api/yggdrasil:0` — which is exactly the ugly thing that showed up when run against the real site. Now it branches on "does it start with http", and `smoke_test.py` has an assertion to prevent regression.

13. **In device-code polling, "not authorized yet" is not an error.** The server returning `{"error": "authorization_pending"}` (and `slow_down`) is a normal intermediate state — the user just hasn't finished typing the code in the browser. Treating it as a failure means the moment the user clicks "Start login", they immediately see "login failed" — this is the easiest thing to get wrong in the device-code flow. In the code it's a separate exception `AuthorizationPending`, distinct from `MicrosoftAuthError`, precisely to force the caller to distinguish the two.

14. **`refresh_token` rotates.** Each Microsoft token refresh gives a new refresh_token and immediately invalidates the old one. Not storing the new one = it won't work next time, and the error is `invalid_grant`, which looks like "the account was revoked". `upsert` in `core/accounts.py` deliberately does "keep the old one if the new one isn't provided", covering both directions. (The fake server in the test must actually rotate for this to be tested — the first version of the fake server always accepted the old one, so the test was fooling itself.)

15. **"Can log in" ≠ "owns the game".** The first four steps of the Microsoft chain work for any ordinary Microsoft account; an account that hasn't bought the game can still get a Minecraft access_token. Only step 5 (`entitlements/mcstore`) actually checks ownership. Skipping that step turns this feature into a fake verification that "anyone can pass".

16. **The `d=` prefix on `RpsTicket` is mandatory.** The Xbox Live step requires `"RpsTicket": "d=<access token>"`; missing `d=` fails in a very hard-to-understand way. The prefix is added by the code, so you can't test it by "passing a string without the prefix" — what should be verified is "the prefix is actually added" (the fake server rejects it when the prefix is missing).

17. **"Disable the button + only give a tooltip" = the user clicks and nothing happens.** The first version did `setEnabled(False)` when client_id was empty, with a tooltip explaining why. The problem is that **disabled buttons don't show tooltips on Windows** — the user sees "clicking Start does nothing" and has no idea what's missing. Now the button is always clickable, and if something's missing, the status bar says exactly what's missing. (This one was reported by a user: "Clicking Start doesn't seem to do anything now.")

18. **After a failure, the button stays grey forever and can't be retried.** The cause is subtle: `_sync_client_state()` checks `worker.isRunning()`, and the `failed` signal is emitted right around when `run()` returns — by the time the main thread handles it, the thread hasn't fully finished, so `isRunning()` is still True, and it skips "re-enable the button", and after that there's never another opportunity to enable it. Now there are two layers: an explicit `_set_busy()` state machine plus hooking up `QThread.finished` as a backstop. The regression assertion is in section 2c of `smoke_test.py`.

19. **One OAuth error code maps to several real causes; check the AADSTS code first.** Measured: both "the client ID doesn't exist at all" and "the app doesn't have public client flows enabled" return `unauthorized_client`; only the AADSTS code in `error_description` tells them apart: `AADSTS700038` = this ID doesn't exist on Microsoft's side (typo), `AADSTS700016` = this app can't be found in the current directory. Looking only at the OAuth `error` field would describe "typo in the ID" as "go enable public client flows", making the user waste a round.

20. **Redaction keywords that are too broad mask normal information too.** The first version of `SECRET_HINTS` included `auth`, so the `author` field (everywhere in search results) all became `***`. Changed to only match the full `authorization`. Likewise `code` can't be a keyword — the `code` in an error response is an error code (useful), while the real authorization code appears in the URL query string, which is a different rule (`redact_url()`). Redaction should "rather over-mask", but not to the point where the log becomes useless — that's the same as not logging.

21. **Secrets in URLs need separate handling.** `redact()` matches by JSON key and can't touch `?code=...` query parameters. And the OAuth authorization code is passed exactly that way (the link the user gave in their first message looked like `.../callback?code=M.C511_...`). Also, `urlencode` without `safe="*"` encodes `***` as `%2A%2A%2A`, which looks like garbage in the log and makes it impossible to tell "this was masked".

22. **Logs come from background threads and must go through signals.** `logbook` is called back by the verification QThread and the avatar thread pool. Calling `appendHtml` directly in the callback is cross-thread manipulation of a Qt widget — the symptom is intermittent, occasionally crashing, the hardest kind to diagnose. `LogPage.entry_added = pyqtSignal(object)` lets Qt queue it to the main thread automatically. Likewise, always unsubscribe before a page is destroyed.

23. **Logging only the response body misses key information.** authlib-injector's auto-detection relies on the response header `X-Authlib-Injector-API-Location`, which isn't in the body. If you only log the body, "auto-detection failed" is a blank in the log and impossible to debug. Now `httplog.call()` appends a few valuable response headers to the summary of that line.

---

A couple of notes on what I changed for the English version:

- Removed the hard-coded Windows path (`D:\DHML-src`) from the run instructions and the intro. The `cd` now just uses `experiments/Genuine verification`, which assumes you're already in the repo root. If you want to keep an explicit path example, say something like `<repo-root>/experiments/Genuine verification` instead.
- Everything else is a faithful translation, including the direct quotes from Microsoft docs and the developer thread (those were already in English in the original, so I kept them verbatim).
- Emoji and ✅/❌ markers are kept, since they carry meaning in the tables.
