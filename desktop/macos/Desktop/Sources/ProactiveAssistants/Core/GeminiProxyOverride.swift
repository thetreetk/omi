import Foundation

/// XAT: redirects every Gemini-proxy call (generateContent, embedContent, batchEmbedContents, screen-task
/// extraction) to a local service, and lifts the free-plan gate that only guards Omi's own paid proxy.
/// Active only when OMI_GEMINI_PROXY_URL is a loopback http URL, e.g. http://127.0.0.1:8790
enum GeminiProxyOverride {
  /// Base URL with a trailing slash, or nil when the override is off or not loopback.
  static var baseURL: String? {
    guard let raw = ProcessInfo.processInfo.environment["OMI_GEMINI_PROXY_URL"]?
      .trimmingCharacters(in: .whitespacesAndNewlines), !raw.isEmpty,
      let components = URLComponents(string: raw), components.scheme?.lowercased() == "http",
      let host = components.host, ["127.0.0.1", "localhost", "::1"].contains(host)
    else { return nil }
    return raw.hasSuffix("/") ? raw : raw + "/"
  }

  static var isActive: Bool { baseURL != nil }
}
