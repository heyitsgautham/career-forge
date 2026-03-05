import { NextResponse } from 'next/server';

// NextAuth stub - app uses custom backend authentication
export async function GET() {
  return NextResponse.json({ error: 'NextAuth not configured - use custom backend auth' }, { status: 404 });
}

export async function POST() {
  return NextResponse.json({ error: 'NextAuth not configured - use custom backend auth' }, { status: 404 });
}
