# wasc passwords (iOS)

A rebranded build of [bitwarden/ios](https://github.com/bitwarden/ios) (Password Manager only),
preconfigured for our self-hosted Vaultwarden at **https://passwords.wasc.me** and shipped through
TestFlight under Apple team `KQB68F43PW`.

Branches: `main` mirrors upstream, and `wasc` (the default branch) is upstream plus the patch below.
The current upstream base is in [`upstream-tag`](upstream-tag).

## The patch

Keep it this small. Everything else, including the in-app "Bitwarden" strings, stays upstream.

| Change | Where |
|---|---|
| Identifiers, team, display name, `WASC_NO_CRASHLYTICS` flag | [`wasc-bwpm.xcconfig`](wasc-bwpm.xcconfig), included at the end of `Configs/Common-bwpm.xcconfig` |
| Watch app, AutoFill extension (the name in iOS Settings > AutoFill) and notification extension display names use `$(BMPW_BUNDLE_DISPLAY_NAME)` | `BitwardenWatchApp/Info.plist`, `BitwardenAutoFillExtension/Application/Support/Info.plist`, `BitwardenNotificationExtension/Application/Support/Info.plist` |
| Bitwarden's associated domains removed (`*.bitwarden.com` webcredentials/applinks) | `Bitwarden/Application/Support/Bitwarden.entitlements` |
| Firebase/Crashlytics off (otherwise the placeholder `GoogleService-Info.plist` crashes Release at launch) | `Bitwarden/Application/Services/ErrorReporter/ErrorReporterFactory.swift`, `BitwardenWatchApp/ExtensionDelegate.swift` |
| Default server `https://passwords.wasc.me` (`EnvironmentURLData.defaultWasc`, initial region `.selfHosted`); the region picker still offers bitwarden.com/.eu/other self-hosted servers | `BitwardenShared/Core/Platform/Models/Domain/EnvironmentURLData+Wasc.swift`, `BitwardenShared/Core/Platform/Services/EnvironmentService.swift`, `BitwardenShared/UI/Auth/Utilities/RegionHelper.swift` |
| Placeholder icon (app + watch, 1024px) | [`brand/`](brand) (`render-icons.sh` needs ImageMagick 7) |
| CI | `.github/workflows/wasc-release.yml`, `.github/workflows/wasc-maintenance.yml`, `.github/workflows/wasc-verify.yml`, `.github/workflows/wasc-guard.yml` |

Override order of the xcconfigs: upstream `Common-bwpm.xcconfig` < `wasc/wasc-bwpm.xcconfig` <
`Configs/Local-bwpm.xcconfig` (git-ignored; CI writes `DEVELOPMENT_TEAM`, `CODE_SIGN_STYLE = Automatic` and
`CODE_SIGN_IDENTITY = Apple Distribution` there, the last one overriding the `Apple Development` that
`Configs/Bitwarden-Release.xcconfig` sets). `wasc-bwpm.xcconfig` sets `DEVELOPMENT_TEAM = KQB68F43PW` for local builds.

All bundle IDs, app groups and keychain groups are derived from `BASE_BUNDLE_ID = me.wasc.passwords`.

Build-time changes made only in CI (not committed):
- `aps-environment` = `production`, matching the distribution profile (the passwords-push relay sends standard Bitwarden background
  pushes to topic `me.wasc.passwords`; the notification extension and the `remote-notification`
  background mode stay as upstream has them).
- Bitwarden's `ITSEncryptionExportComplianceCode` is removed from `Info.plist`. If the repo variable
  `WASC_EXPORT_COMPLIANCE_CODE` is set, CI writes that value instead. `ITSAppUsesNonExemptEncryption`
  stays `YES` as upstream has it, so without our own code each build needs the export compliance
  question answered in App Store Connect. The legal answer is the owner's call.
- `MARKETING_VERSION` comes from `upstream-tag` (`v2026.10.0-bwpm` becomes `2026.10.0`), and
  `CURRENT_PROJECT_VERSION` is run number * 10 + run attempt + 100, so re-runs get a new number (it
  can be overridden on dispatch).

Decisions (coordinator defaults, can be revisited): the watch app is **kept**, Bitwarden's
associated domains are **dropped**, and the region picker is kept.

Not changed, but worth knowing:
- Dropping the associated domains only matters for the **cloud regions** (bitwarden.com / bitwarden.eu):
  there, SSO and Duo lose their HTTPS (universal link) callbacks and WebAuthn/passkey 2FA does not work,
  because both rely on Bitwarden's `*.bitwarden.com` associated domains. Self-hosted servers
  (including passwords.wasc.me) use the `bitwarden://` callback and are unaffected.
- The `bitwarden://` URL scheme (used for SSO/Duo/WebAuthn callbacks when self-hosted) and the
  `otpauth` scheme are the same as in the official app. If both apps are installed, iOS may route
  callbacks to either.
- Fallback links (`vault.bitwarden.com/#/tools/import`, `send.bitwarden.com`, fill-assist rules,
  App Store review link for Bitwarden's app) and `api.pwnedpasswords.com` are unchanged.
- The Rust SDK (`bitwarden/sdk-swift`) is a binary from Bitwarden's blob store, which we take under
  GPL-3.0.

## Known failing upstream unit tests

These fail because they assert the US default, which is deliberate:
- `BitwardenShared/Core/Platform/Services/EnvironmentServiceTests.swift`: `defaultUrls`,
  `loadURLsForActiveAccount_noAccount`
- `BitwardenShared/UI/Auth/Utilities/RegionHelperTests.swift`: `test_loadRegion_nil`

Upstream test workflows are disabled in this fork, so nothing runs them.

## Apple prerequisites (one-time, by the account holder)

Identifiers (developer.apple.com > Certificates, Identifiers & Profiles):

| Bundle ID | Capabilities |
|---|---|
| `me.wasc.passwords` | App Groups (`group.me.wasc.passwords`, `group.me.wasc.passwords.authenticator`), AutoFill Credential Provider, Push Notifications, NFC Tag Reading, iCloud (iCloud Documents, container `iCloud.me.wasc.passwords`) |
| `me.wasc.passwords.autofill` | App Groups (`group.me.wasc.passwords`), AutoFill Credential Provider |
| `me.wasc.passwords.find-login-action-extension` | App Groups (`group.me.wasc.passwords`) |
| `me.wasc.passwords.share-extension` | App Groups (`group.me.wasc.passwords`) |
| `me.wasc.passwords.notification` | App Groups (`group.me.wasc.passwords`) |
| `me.wasc.passwords.watchkitapp` | none |
| `me.wasc.passwords.watchkitapp.widget-extension` | none |

App groups to register: `group.me.wasc.passwords` and `group.me.wasc.passwords.authenticator`
(the second is upstream's Bitwarden Authenticator sharing group, used only by the main app).
The iCloud container `iCloud.me.wasc.passwords` must also be registered. Keychain sharing
(`$(AppIdentifierPrefix)me.wasc.passwords`) needs no portal entry. Associated Domains is **not**
needed. Frameworks (`me.wasc.bitwarden-kit`, `me.wasc.bitwarden-resources`,
`me.wasc.authenticator-bridge-kit`, `me.wasc.passwords.bitwarden-shared`) need no portal entry.

Then create the App Store Connect app record "wasc passwords" for bundle `me.wasc.passwords`.

## Upstream sync

Upstream sync is **not** done by CI. A monthly T3 Code scheduled task in Nicolai's compose-services
thread (`wasc-passwords-monthly-sync-v1`, every 30 days; see `list_scheduled_tasks`) does it:

1. Fetch upstream tags into `refs/upstream-tags/*`, never `refs/tags`, so they cannot collide with
   the fork's own `wasc-v*` release tags.
2. Merge the newest `v*-bwpm` tag into a `sync/<tag>` branch, resolve conflicts (keep upstream's
   code plus the patch above; always keep the fork's `Icon-1024.png` files) and bump
   `wasc/upstream-tag`.
3. Push the branch, run wasc-guard.yml right away, and open a PR into `wasc`.
4. wasc-verify.yml builds the PR; the task fixes build breaks on the branch.
5. If the build is green and the review is clean, the task merges (merge commit, never squash) and
   dispatches wasc-release.yml (once the App Store Connect app record exists). Otherwise it leaves
   the PR open for Nicolai.

It pushes with Nicolai's `gh` auth, which needs the `workflow` scope because upstream merges change
`.github/workflows/*`. That push triggers `on: push` workflows, so a brand-new upstream workflow can
run once on the sync branch before the guard disables it; without Bitwarden's secrets it fails.
No `ANTHROPIC_API_KEY` or `WASC_SYNC_TOKEN` is needed.

## CI

Secrets: `APPLE_TEAM_ID`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8` (release and stale check).
Variable: `WASC_EXPORT_COMPLIANCE_CODE` (optional).

- **wasc-release.yml** runs on `workflow_dispatch` or a pushed `wasc-v*` tag. It generates the
  projects with XcodeGen, archives the `Bitwarden` scheme (Release) with **automatic signing**
  (`-allowProvisioningUpdates` plus the ASC API key), exports it for `app-store-connect` and uploads
  it with `xcrun altool --apple-id <id>`. When uploading, it first looks up the numeric App Store
  Connect app id for `me.wasc.passwords` through the ASC API (without `--apple-id`, altool on Xcode 26
  can upload to the wrong app or fail silently) and fails before archiving if the app record is
  missing. The `.ipa` is kept as an artifact for 14 days. Untick *upload* for a dry run.
  - It fails until the identifiers, app groups, iCloud container and app record above exist. That is
    expected.
  - The current API key (`ZZ8H45VBNS`) has the **Developer** role. Xcode can only reuse existing
    identifiers with it. Cloud-managed signing also needs access to the cloud-managed
    distribution/development certificates, which normally means an **Admin** key. If archive or export
    fails with a certificate or profile permission error after the identifiers exist, create an Admin
    API key and replace the `ASC_*` secrets.
- **wasc-verify.yml** builds the app for the simulator (`./Scripts/build.sh project-pm.yml Bitwarden
  Simulator`) on every PR into `wasc` and on `workflow_dispatch`. It only builds and fails on errors;
  it never pushes.
- **wasc-guard.yml** disables every workflow whose file is not `wasc-*`. Upstream workflows need
  Bitwarden's Azure secrets, and new ones arrive (enabled) with every merge. It runs on every push to
  `wasc` (so a merged sync PR is cleaned up at once), on `workflow_dispatch`, and is called daily by
  wasc-maintenance.yml.
- **wasc-maintenance.yml** runs daily. It does three things:
  - It keeps its own schedule alive: GitHub disables scheduled workflows in public repos after 60 days
    without repository activity, and this schedule is what stops TestFlight builds from expiring. The
    `keepalive` job calls `PUT /repos/{repo}/actions/workflows/wasc-maintenance.yml/enable` (needs
    `actions: write`), which resets the inactivity timer without commits. This is what
    `liskin/gh-workflow-keepalive` does; it is inlined rather than used as an action. GitHub does not
    document the reset explicitly, so if the workflow ever shows as disabled, re-enable it in the Actions
    tab (and check that the 75-day stale check still has time before the 90-day expiry).
  - It runs wasc-guard.yml.
  - If at least one TestFlight build exists and the newest is 75+ days old, it dispatches
    `wasc-release.yml` (TestFlight builds expire after 90 days). Before the first build it does
    nothing; the first release is dispatched by hand.

Token permissions: every job declares its own `permissions:` (workflow-level is `{}` or
`contents: read`). The repository default for `GITHUB_TOKEN` is **read**, and *Allow GitHub Actions to
create and approve pull requests* is **off** (`can_approve_pull_request_reviews=false`; it is one
setting for both). Decision: keep it off, so no workflow can open or approve a PR; sync PRs are
opened by the scheduled task with Nicolai's `gh` auth.

When Nicolai merges a sync PR by hand, run *wasc release (TestFlight)* afterwards.
