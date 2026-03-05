import { NextRequest, NextResponse } from 'next/server';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  if (error) {
    return NextResponse.redirect(
      new URL(`/dashboard?error=${encodeURIComponent(error)}`, request.url)
    );
  }

  if (!code) {
    return NextResponse.redirect(
      new URL('/dashboard?error=no_code', request.url)
    );
  }

  try {
    // Store code in URL for client-side handling
    // Since we can't access localStorage in API routes, redirect to a client component
    return NextResponse.redirect(
      new URL(`/dashboard/linkedin-callback?code=${code}`, request.url)
    );

  } catch (error) {
    console.error('LinkedIn callback error:', error);
    return NextResponse.redirect(
      new URL('/dashboard?error=callback_failed', request.url)
    );
  }
}
