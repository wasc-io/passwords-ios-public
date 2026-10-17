import FirebaseCore
import WatchKit

class ExtensionDelegate: NSObject, WKExtensionDelegate {
    func applicationDidFinishLaunching() {
        #if !DEBUG && !WASC_NO_CRASHLYTICS
        FirebaseApp.configure()
        #endif
    }
}
