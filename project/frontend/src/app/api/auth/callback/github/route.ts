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

  // GitHub App sends installation_id alongside code
  const installationId = searchParams.get('installation_id');
  // state carries the existing JWT when linking GitHub to a Google-logged-in user
  const state = searchParams.get('state');

  try {
    // Send code + installation_id to backend to exchange for tokens
    const tokenResponse = await fetch(`${BACKEND_URL}/api/auth/github/callback`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        code,
        installation_id: installationId ? parseInt(installationId, 10) : null,
        link_token: state || undefined,
      }),
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
