import { NextRequest, NextResponse } from 'next/server';
import { promises as fs } from 'fs';
import path from 'path';

// Helper function to update .env file
async function updateEnvFile(newApiKey: string) {
  const envPath = path.resolve(process.cwd(), '.env');
  let envContent = await fs.readFile(envPath, 'utf8');

  // Replace the existing NEXT_PUBLIC_OPENAI_API_KEY with the new one
  if (envContent.includes('NEXT_PUBLIC_OPENAI_API_KEY')) {
    envContent = envContent.replace(
      /NEXT_PUBLIC_OPENAI_API_KEY=.*/,
      `NEXT_PUBLIC_OPENAI_API_KEY=${newApiKey}`
    );
  } else {
    envContent += `\nNEXT_PUBLIC_OPENAI_API_KEY=${newApiKey}`;
  }

  await fs.writeFile(envPath, envContent);
}

export async function POST(req: NextRequest) {
  const { newApiKey } = await req.json();

  if (!newApiKey || !newApiKey.startsWith('sk-')) {
    return NextResponse.json({ error: 'Invalid API Key format' }, { status: 400 });
  }

  try {
    await updateEnvFile(newApiKey);
    return NextResponse.json({ success: true }, { status: 200 });
  } catch (error) {
    return NextResponse.json({ error: 'Failed to update the .env file' }, { status: 500 });
  }
}
