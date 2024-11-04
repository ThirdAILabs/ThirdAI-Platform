// app/api/check-openai-key/route.ts
import { NextRequest, NextResponse } from 'next/server';

export async function GET(req: NextRequest) {
  const hasKey = !!process.env.NEXT_PUBLIC_OPENAI_API_KEY;
  return NextResponse.json({ hasKey });
}
