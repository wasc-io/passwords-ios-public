import BitwardenKit
import Foundation

// wasc passwords: the self-hosted Vaultwarden server used as the default environment.
public extension EnvironmentURLData {
    /// The default URLs for wasc passwords (self-hosted Vaultwarden).
    static let defaultWasc = EnvironmentURLData(base: URL(string: "https://passwords.wasc.me")!)
}
