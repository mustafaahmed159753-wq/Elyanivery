import { NextResponse } from 'next/server';

export async function GET() {
  const assetLinks = [
    {
      relation: ['delegate_permission/common.handle_all_urls'],
      target: {
        namespace: 'android_app',
        package_name: 'com.elyanivery.app',
        sha256_cert_fingerprints: [
          '14:6D:E9:7D:0F:52:72:E8:B8:5E:2B:A5:9D:E4:F6:94:28:6A:B7:9F:7C:E6:0B:4D:2E:39:6C:5A:F3:6E:9B:41'
        ]
      }
    },
    {
      relation: ['delegate_permission/common.handle_all_urls'],
      target: {
        namespace: 'android_app',
        package_name: 'app.elyanivery.delivery',
        sha256_cert_fingerprints: [
          '14:6D:E9:7D:0F:52:72:E8:B8:5E:2B:A5:9D:E4:F6:94:28:6A:B7:9F:7C:E6:0B:4D:2E:39:6C:5A:F3:6E:9B:41'
        ]
      }
    }
  ];

  return NextResponse.json(assetLinks, {
    headers: {
      'Content-Type': 'application/json',
      'Cache-Control': 'public, max-age=86400, must-revalidate',
    },
  });
}
