// app/endpoints/generate-data-sentence-classification/route.ts
import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.NEXT_PUBLIC_OPENAI_API_KEY,
});

const generateExamples = async (prompt: string) => {
  const response = await openai.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [
      {
        role: 'system',
        content: prompt,
      },
    ],
  });
  const content = response.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error('No content returned from OpenAI');
  }

  return content
    .split('\n')
    .map(example => example.trim().replace(/^[\d.-]+\s*/, ''))
    .filter(example => example);
};

export const POST = async (req: NextRequest) => {
  const apiKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY;

  if (!apiKey) {
    return NextResponse.json({ error: 'API key is not defined' }, { status: 500 });
  }

  const { question, answer, categories } = await req.json();

  if (!question || !answer || !categories) {
    return NextResponse.json({ error: 'Invalid input' }, { status: 400 });
  }

  const prompts: [string, string][] = [];
  const generatedExamples: { category: string, examples: string[] }[] = [];
  const promises = categories.map(async (category: { name: string, example: string }) => {
    const prompt = `
      You are a synthetic data generator for the training of a sentence classification model.
      Specifically, our customer has a problem: ${question}.
      Our solution is ${answer}.
      To train a sentence classification model, your job is to come up with 10 example data points
      that are diverse in format, but similar in nature to this category "${category.name}".
      One such example is "${category.example}".
      The examples should be complete sentences without any numeric numbers, bullet points, or any other extraneous content.
    `;

    prompts.push([prompt, category.name]);

    try {
      const examples = await generateExamples(prompt);
      generatedExamples.push({ category: category.name, examples });
    } catch (error) {
      console.error(`Error during fetch for category ${category.name}:`, error);
      alert(`Error during fetch for category ${category.name}:` + error)
      throw error;
    }
  });

  try {
    await Promise.all(promises);
    return NextResponse.json({ generatedExamples, prompts });
  } catch (error) {
    return NextResponse.json({ error: 'Error generating data' }, { status: 500 });
  }
};
