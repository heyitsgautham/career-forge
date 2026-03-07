import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  if (error) {
    console.error('Cognito OAuth error:', error, searchParams.get('error_description'));
    return NextResponse.redirect(new URL('/login?error=cognito_auth_failed', request.url));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/login?error=no_code', request.url));
  }

  try {
    const tokenResponse = await fetch(`${BACKEND_URL}/api/auth/cognito/callback`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ code }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.json();
      console.error('Backend Cognito callback error:', errorData);
      return NextResponse.redirect(new URL('/login?error=token_exchange_failed', request.url));
    }

    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.access_token;

    // Store token via redirect — dashboard's useEffect picks it up from query params
    return NextResponse.redirect(
      new URL(`/dashboard?google=connected&token=${accessToken}`, request.url)
    );
  } catch (err) {
    console.error('Cognito callback error:', err);
    return NextResponse.redirect(new URL('/login?error=callback_failed', request.url));
  }
}
