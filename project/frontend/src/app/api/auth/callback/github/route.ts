import { NextRequest, NextResponse } from 'next/server';

const BACKEND_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams;
  const code = searchParams.get('code');
  const error = searchParams.get('error');

  if (error) {
    console.error('GitHub OAuth error:', error);
    return NextResponse.redirect(new URL('/dashboard?error=github_auth_failed', request.url));
  }

  if (!code) {
    return NextResponse.redirect(new URL('/dashboard?error=no_code', request.url));
  }

  try {
    // Send code to backend to exchange for tokens
    const tokenResponse = await fetch(`${BACKEND_URL}/api/auth/github/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ code }),
    });

    if (!tokenResponse.ok) {
      const errorData = await tokenResponse.json();
      console.error('Backend OAuth error:', errorData);
      return NextResponse.redirect(new URL('/dashboard?error=token_exchange_failed', request.url));
    }

    const tokenData = await tokenResponse.json();
    const accessToken = tokenData.access_token;

    // Redirect to dashboard with token in URL (it will be stored in localStorage)
    const response = NextResponse.redirect(
      new URL(`/dashboard?github=connected&token=${accessToken}`, request.url)
    );

    return response;
  } catch (err) {
    console.error('GitHub OAuth callback error:', err);
    return NextResponse.redirect(new URL('/dashboard?error=callback_failed', request.url));
  }
}
