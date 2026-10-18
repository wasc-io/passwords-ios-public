"""App Store Connect helpers for wasc-release.yml (CI key with the Developer role: read-only here).

  asc.py app-id <bundle id>
      Appends _ASC_APP_ID=<numeric id> to $GITHUB_ENV; fails if the app record is missing.
  asc.py profiles <Local xcconfig> <ExportOptions.plist>
      Downloads, per target, the newest ACTIVE IOS_APP_STORE profile named "wasc passwords AppStore *"
      (created and regenerated outside CI, see wasc/README.md), installs it, appends the
      PROVISIONING_PROFILE_SPECIFIER* lines to the xcconfig and writes the ExportOptions.plist.

Env: _ASC_KEY_ID, _ASC_ISSUER_ID, _ASC_KEY_P8, _APPLE_TEAM_ID, and _DIST_CERT_SHA1 (every profile
must contain that certificate; CI always sets it, it is optional only for local runs).
"""
import base64, hashlib, json, os, plistlib, sys, time, urllib.error, urllib.parse, urllib.request

import jwt

API = "https://api.appstoreconnect.apple.com"
PREFIX = "wasc passwords AppStore "
# Bundle ID -> the xcconfig variable its target reads (see Configs/*.xcconfig and upstream
# Scripts/select_variant.sh; the main app reads PROVISIONING_PROFILE_SPECIFIER directly).
TARGETS = {
    "me.wasc.passwords": "PROVISIONING_PROFILE_SPECIFIER",
    "me.wasc.passwords.autofill": "PROVISIONING_PROFILE_SPECIFIER_AUTOFILL_EXTENSION",
    "me.wasc.passwords.find-login-action-extension": "PROVISIONING_PROFILE_SPECIFIER_ACTION_EXTENSION",
    "me.wasc.passwords.share-extension": "PROVISIONING_PROFILE_SPECIFIER_SHARE_EXTENSION",
    "me.wasc.passwords.notification": "PROVISIONING_PROFILE_SPECIFIER_NOTIFICATION_EXTENSION",
    "me.wasc.passwords.watchkitapp": "PROVISIONING_PROFILE_SPECIFIER_WATCH_APP",
    "me.wasc.passwords.watchkitapp.widget-extension": "PROVISIONING_PROFILE_SPECIFIER_WATCH_WIDGET_EXTENSION",
}
# Xcode 16+ reads the first; the second is the legacy location, kept in case a tool still reads it.
PROFILE_DIRS = ["~/Library/Developer/Xcode/UserData/Provisioning Profiles", "~/Library/MobileDevice/Provisioning Profiles"]


def fail(msg):
    print(f"::error::{msg}")
    raise SystemExit(1)


def get(path):
    now = int(time.time())
    token = jwt.encode(
        {"iss": os.environ["_ASC_ISSUER_ID"], "iat": now, "exp": now + 600, "aud": "appstoreconnect-v1"},
        os.environ["_ASC_KEY_P8"],
        algorithm="ES256",
        headers={"kid": os.environ["_ASC_KEY_ID"], "typ": "JWT"},
    )
    req = urllib.request.Request(path if path.startswith("https://") else API + path,
                                 headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except urllib.error.HTTPError as e:  # Apple's error JSON says why (role, agreement, filter)
        fail(f"App Store Connect GET {path}: HTTP {e.code} {e.read().decode(errors='replace')[:500]}")


def app_id(bundle_id):
    apps = [a for a in get("/v1/apps?" + urllib.parse.urlencode({"filter[bundleId]": bundle_id}))["data"]
            if a["attributes"]["bundleId"] == bundle_id]
    if not apps:
        fail(f"No App Store Connect app record for {bundle_id}. Create it first (see wasc/README.md).")
    app = apps[0]
    print(f"App Store Connect app {app['attributes']['name']} has id {app['id']}")
    with open(os.environ["GITHUB_ENV"], "a") as env:
        env.write(f"_ASC_APP_ID={app['id']}\n")


def newest_profiles():
    """identifier -> newest ACTIVE wasc App Store profile (metadata only)."""
    page = get("/v1/profiles?" + urllib.parse.urlencode({
        "filter[profileType]": "IOS_APP_STORE", "filter[profileState]": "ACTIVE", "include": "bundleId",
        "fields[profiles]": "name,createdDate,bundleId", "fields[bundleIds]": "identifier", "limit": 200}))
    newest, idents = {}, {}
    while True:
        idents.update({b["id"]: b["attributes"]["identifier"] for b in page.get("included", [])})
        for p in page["data"]:
            ident = idents.get(p["relationships"]["bundleId"]["data"]["id"])
            if ident in TARGETS and p["attributes"]["name"].startswith(PREFIX):
                if ident not in newest or p["attributes"]["createdDate"] > newest[ident]["attributes"]["createdDate"]:
                    newest[ident] = p
        if not page["links"].get("next"):
            return newest
        page = get(page["links"]["next"])


def profiles(xcconfig, export_options):
    newest = newest_profiles()
    if missing := sorted(set(TARGETS) - set(newest)):
        fail(f"No ACTIVE '{PREFIX}*' App Store profile for {', '.join(missing)}. Regenerate the profiles (wasc/README.md).")
    cert_sha1 = os.environ.get("_DIST_CERT_SHA1", "").upper()
    dirs = [os.path.expanduser(d) for d in PROFILE_DIRS]
    for d in dirs:
        os.makedirs(d, exist_ok=True)
    uuids, problems = {}, []
    for ident, p in sorted(newest.items()):
        content = base64.b64decode(get(f"/v1/profiles/{p['id']}?fields[profiles]=profileContent")
                                   ["data"]["attributes"]["profileContent"])
        # The profile is a CMS envelope around a plain XML plist.
        info = plistlib.loads(content[content.index(b"<?xml"):content.index(b"</plist>") + len(b"</plist>")])
        ent = info["Entitlements"]
        if cert_sha1 and cert_sha1 not in {hashlib.sha1(c).hexdigest().upper() for c in info["DeveloperCertificates"]}:
            problems.append(f"{info['Name']} does not contain the DIST_CERT_P12_BASE64 certificate")
        # An enabled capability with nothing assigned in the portal shows up as an empty list.
        for key in ("com.apple.security.application-groups", "com.apple.developer.ubiquity-container-identifiers"):
            if key in ent and not ent[key]:
                problems.append(f"{info['Name']} has {key} enabled but empty (portal assignment missing)")
        for d in dirs:
            with open(os.path.join(d, f"{info['UUID']}.mobileprovision"), "wb") as f:
                f.write(content)
        uuids[ident] = info["UUID"]  # unambiguous even if two profiles share a name
        print(f"{ident}: {info['Name']} ({info['UUID']}, expires {info['ExpirationDate']:%Y-%m-%d})")
    if problems:
        fail("; ".join(problems) + ". Fix in the portal and regenerate the profiles (wasc/README.md).")

    with open(xcconfig, "a") as f:
        f.writelines(f"{TARGETS[ident]} = {uuid}\n" for ident, uuid in sorted(uuids.items()))
    with open(export_options, "wb") as f:
        plistlib.dump({
            "method": "app-store-connect",
            "destination": "export",
            "signingStyle": "manual",
            "signingCertificate": "Apple Distribution",
            "teamID": os.environ["_APPLE_TEAM_ID"],
            "provisioningProfiles": uuids,
            "manageAppVersionAndBuildNumber": False,
            "uploadSymbols": False,
        }, f)


if __name__ == "__main__":
    match sys.argv[1:]:
        case ["app-id", bundle_id]:
            app_id(bundle_id)
        case ["profiles", xcconfig, export_options]:
            profiles(xcconfig, export_options)
        case _:
            print(__doc__, file=sys.stderr)
            raise SystemExit(2)
