import AVFoundation
import CoreGraphics
import ImageIO
import Foundation

// Use Apple's video color management for iPhone HLG / Dolby Vision sources.
// Export a color-managed sRGB JPEG rather than treating HDR sample values as SDR.
@main
struct VideoPoster {
    static func main() async throws {
        guard CommandLine.arguments.count == 3 else {
            throw NSError(domain: "VideoPoster", code: 1, userInfo: [NSLocalizedDescriptionKey: "Usage: video-poster input-video output.jpg"])
        }
        let asset = AVURLAsset(url: URL(fileURLWithPath: CommandLine.arguments[1]))
        let generator = AVAssetImageGenerator(asset: asset)
        generator.appliesPreferredTrackTransform = true
        generator.maximumSize = CGSize(width: 1280, height: 1280)
        generator.requestedTimeToleranceBefore = .zero
        generator.requestedTimeToleranceAfter = .zero
        if #available(macOS 15.0, *) {
            generator.dynamicRangePolicy = .forceSDR
        }
        // Match the first frame shown when the reader starts playback.
        let frame = try await generator.image(at: .zero).image
        guard let colorSpace = CGColorSpace(name: CGColorSpace.sRGB),
              let context = CGContext(data: nil, width: frame.width, height: frame.height,
                                      bitsPerComponent: 8, bytesPerRow: 0, space: colorSpace,
                                      bitmapInfo: CGImageAlphaInfo.noneSkipLast.rawValue) else {
            throw NSError(domain: "VideoPoster", code: 2, userInfo: [NSLocalizedDescriptionKey: "Cannot create sRGB context"])
        }
        context.draw(frame, in: CGRect(x: 0, y: 0, width: frame.width, height: frame.height))
        let output = URL(fileURLWithPath: CommandLine.arguments[2])
        guard let image = context.makeImage(),
              let destination = CGImageDestinationCreateWithURL(output as CFURL, "public.jpeg" as CFString, 1, nil) else {
            throw NSError(domain: "VideoPoster", code: 3, userInfo: [NSLocalizedDescriptionKey: "Cannot create JPEG"])
        }
        CGImageDestinationAddImage(destination, image, [kCGImageDestinationLossyCompressionQuality: 0.9] as CFDictionary)
        guard CGImageDestinationFinalize(destination) else {
            throw NSError(domain: "VideoPoster", code: 4, userInfo: [NSLocalizedDescriptionKey: "Cannot write JPEG"])
        }
    }
}
