// Independent QR decoder check using macOS CoreImage (optional developer check).
import Foundation
import CoreImage
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let expected = CommandLine.arguments[2]
guard let image = CIImage(contentsOf: url),
      let detector = CIDetector(ofType: CIDetectorTypeQRCode,
          context: CIContext(options: [.useSoftwareRenderer: true]),
          options: [CIDetectorAccuracy: CIDetectorAccuracyHigh]) else { exit(2) }
let found = detector.features(in: image).compactMap { ($0 as? CIQRCodeFeature)?.messageString }
guard found.contains(expected) else { print("QR decode failed: \(found)"); exit(1) }
print("CoreImage decoded expected QR payload")
