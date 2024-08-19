// app/api/which-nlp-use-case/route.ts
import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.OPENAI_API_KEY,
});

export const POST = async (req: NextRequest) => {
  const apiKey = process.env.OPENAI_API_KEY;

  if (!apiKey) {
    return NextResponse.json({ error: 'API key is not defined' }, { status: 500 });
  }

  const { question } = await req.json();

  if (!question) {
    return NextResponse.json({ error: 'Question is not valid' }, { status: 400 });
  }

  const prompt = `
    You are a machine learning use case expert. I will provide a customer's problem statement.
    Your job is to:
    1. Classify which of the following solution toolkits the customer could use.
    2. Provide why this solution toolkit can be useful to solve this problem.
    3. If none of the solution toolkits is feasible to solve the problem, simply return N/A.
    We support 2 different types of solution toolkits:
    1. Sentence classification (a ML model that translates a sentence to pre-defined categories)
    2. Token classification (a ML model that translates tokens within a sentence to pre-defined categories)
    Formulate your answer as follows:
    1. Which solution toolkit to use
    2. Why that toolkit would help solve the user's problem.
    Notice that the toolkit can be a partial solution instead of a complete solution.
    Here is customer's problem statement: ${question}
  `;

  try {
    const chatCompletion = await openai.chat.completions.create({
      model: 'gpt-3.5-turbo',
      messages: [{ role: 'user', content: prompt }],
    });

    const answerContent = chatCompletion.choices[0]?.message?.content;
    if (!answerContent) {
      throw new Error('No content returned from OpenAI');
    }

    return NextResponse.json({ answer: answerContent });
  } catch (error) {
    console.error('Error during fetch:', error);
    return NextResponse.json({ error: 'Error during fetch: ' + error }, { status: 500 });
  }
};
