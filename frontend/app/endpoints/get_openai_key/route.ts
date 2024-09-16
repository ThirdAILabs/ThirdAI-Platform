import { NextRequest, NextResponse } from 'next/server';

export async function GET() {
  const apiKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY;

  if (apiKey) {
    const maskedApiKey = `sk-...${apiKey.slice(-4)}`; // Mask all but the last 4 digits
    return NextResponse.json({ apiKey: maskedApiKey }, { status: 200 });
  }

  return NextResponse.json({ error: 'API Key not found' }, { status: 404 });
}
