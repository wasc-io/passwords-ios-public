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
| Watch app display name uses `$(BMPW_BUNDLE_DISPLAY_NAME)` | `BitwardenWatchApp/Info.plist` |
| Bitwarden's associated domains removed (`*.bitwarden.com` webcredentials/applinks) | `Bitwarden/Application/Support/Bitwarden.entitlements` |
| Firebase/Crashlytics off (otherwise the placeholder `GoogleService-Info.plist` crashes Release at launch) | `Bitwarden/Application/Services/ErrorReporter/ErrorReporterFactory.swift`, `BitwardenWatchApp/ExtensionDelegate.swift` |
| Default server `https://passwords.wasc.me` (`EnvironmentURLData.defaultWasc`, initial region `.selfHosted`); the region picker still offers bitwarden.com/.eu/other self-hosted servers | `BitwardenShared/Core/Platform/Models/Domain/EnvironmentURLData+Wasc.swift`, `BitwardenShared/Core/Platform/Services/EnvironmentService.swift`, `BitwardenShared/UI/Auth/Utilities/RegionHelper.swift` |
| Placeholder icon (app + watch, 1024px) | [`brand/`](brand) (`render-icons.sh` needs ImageMagick 7) |
| CI | `.github/workflows/wasc-release.yml`, `.github/workflows/wasc-sync.yml` |

Override order of the xcconfigs: upstream `Common-bwpm.xcconfig` < `wasc/wasc-bwpm.xcconfig` <
`Configs/Local-bwpm.xcconfig` (git-ignored; CI writes `DEVELOPMENT_TEAM` and `CODE_SIGN_STYLE` there).

All bundle IDs, app groups and keychain groups are derived from `BASE_BUNDLE_ID = me.wasc.passwords`.

Build-time changes made only in CI (not committed):
- `aps-environment` = `production` (the passwords-push relay sends standard Bitwarden background
  pushes to topic `me.wasc.passwords`; the notification extension and the `remote-notification`
  background mode stay as upstream has them).
- Bitwarden's `ITSEncryptionExportComplianceCode` is removed from `Info.plist`. If the repo variable
  `WASC_EXPORT_COMPLIANCE_CODE` is set, CI writes that value instead. `ITSAppUsesNonExemptEncryption`
  stays `YES` as upstream has it, so without our own code each build needs the export compliance
  question answered in App Store Connect. The legal answer is the owner's call.
- `MARKETING_VERSION` comes from `upstream-tag` (`v2026.10.0-bwpm` becomes `2026.10.0`), and
  `CURRENT_PROJECT_VERSION` is the run number + 100 (it can be overridden on dispatch).

Decisions (coordinator defaults, can be revisited): the watch app is **kept**, Bitwarden's
associated domains are **dropped**, and the region picker is kept.

Not changed, but worth knowing:
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

## CI

Secrets: `APPLE_TEAM_ID`, `ASC_KEY_ID`, `ASC_ISSUER_ID`, `ASC_KEY_P8` (release and stale check),
`ANTHROPIC_API_KEY` (sync), and optionally `WASC_SYNC_TOKEN`. Variable: `WASC_EXPORT_COMPLIANCE_CODE`
(optional).

- **wasc-release.yml** runs on `workflow_dispatch` or a pushed `wasc-v*` tag. It generates the
  projects with XcodeGen, archives the `Bitwarden` scheme (Release) with **automatic signing**
  (`-allowProvisioningUpdates` plus the ASC API key), exports it for `app-store-connect` and uploads
  it with `xcrun altool`. The `.ipa` is kept as an artifact for 14 days. Untick *upload* for a dry run.
  - It fails until the identifiers, app groups, iCloud container and app record above exist. That is
    expected.
  - The current API key (`ZZ8H45VBNS`) has the **Developer** role. Xcode can only reuse existing
    identifiers with it. Cloud-managed signing also needs access to the cloud-managed
    distribution/development certificates, which normally means an **Admin** key. If archive or export
    fails with a certificate or profile permission error after the identifiers exist, create an Admin
    API key and replace the `ASC_*` secrets.
- **wasc-sync.yml** runs daily. It does three things:
  - It disables every workflow that is not `wasc-*`. Upstream workflows need Bitwarden's Azure
    secrets, and new ones arrive with every merge.
  - If the newest TestFlight build is 75+ days old, it dispatches `wasc-release.yml` (TestFlight
    builds expire after 90 days).
  - If upstream has a newer `v*-bwpm` tag than `upstream-tag`, it merges that tag into
    `sync/<tag>`, lets Claude resolve any conflicts, bumps `upstream-tag` and opens a PR against
    `wasc`. A macOS job then builds that branch for the simulator. If the build fails, Claude
    attempts a fix and pushes it to the PR.

  Upstream merges usually change `.github/workflows/*`, and `GITHUB_TOKEN` may not push those. Set
  `WASC_SYNC_TOKEN` (a fine-grained PAT on this repo with Contents, Pull requests and Workflows write)
  if the push is rejected. GitHub also pauses scheduled workflows after 60 days without repository
  activity.

After a sync PR is merged, run *wasc release (TestFlight)*.
