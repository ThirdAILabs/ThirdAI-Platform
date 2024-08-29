// app/endpoints/generate-data-token-classification/route.ts
import { NextRequest, NextResponse } from 'next/server';
import OpenAI from 'openai';

const openai = new OpenAI({
  apiKey: process.env.NEXT_PUBLIC_OPENAI_API_KEY,
});

const generateSentences = async (prompt: string) => {
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
    .map(sentence => sentence.trim().replace(/^[\d.-]+\s*/, ''))
    .filter(sentence => sentence)
    .slice(-10); // Only keep the last 10 templates
};

const filterTemplates = (templates: string[], categories: { name: string }[]) => {
  const categoryNames = categories.map(category => `[${category.name}]`);
  const categoryNamesSet = new Set(categoryNames);

  return templates.filter(template => {
    const presentTags = categoryNames.filter(tag => template.includes(tag));
    const allTags = template.match(/\[[^\]]+\]/g) || [];
    const hasOnlyRequestedTags = allTags.every(tag => categoryNamesSet.has(tag));
    return presentTags.length > 0 && hasOnlyRequestedTags;
  });
};

const generateRealValues = async (entityValuePrompt: string) => {
  const response = await openai.chat.completions.create({
    model: 'gpt-3.5-turbo',
    messages: [
      {
        role: 'system',
        content: entityValuePrompt,
      },
    ],
  });
  const content = response.choices?.[0]?.message?.content;
  if (!content) {
    throw new Error('No content returned from OpenAI');
  }

  return content
    .split(';')
    .map(value => value.trim())
    .filter(value => value);
};

const generateSyntheticSentence = (template: string, realValuesMap: { [key: string]: string[] }) => {
  let syntheticSentence = template;
  let entityReplacements: { placeholder: string, value: string, category: string }[] = [];

  for (const [category, values] of Object.entries(realValuesMap)) {
    const placeholder = `[${category}]`;
    while (syntheticSentence.includes(placeholder)) {
      const value = values[Math.floor(Math.random() * values.length)];
      syntheticSentence = syntheticSentence.replace(placeholder, value);
      entityReplacements.push({ placeholder, value, category });
    }
  }

  const tokens = syntheticSentence.split(' ');
  const nerData = tokens.map(token => {
    let tag = 'O';
    for (const { placeholder, value, category } of entityReplacements) {
      const valueWords = value.split(' ');
      for (const valueWord of valueWords) {
        if (token.includes(valueWord)) {
          tag = category;
          break;
        }
      }
    }
    return tag;
  });

  return { sentence: syntheticSentence, nerData };
};

export const POST = async (req: NextRequest) => {
  const apiKey = process.env.NEXT_PUBLIC_OPENAI_API_KEY;

  if (!apiKey) {
    return NextResponse.json({ error: 'API key is not defined' }, { status: 500 });
  }

  const { categories } = await req.json();

  if (!categories) {
    return NextResponse.json({ error: 'Invalid input' }, { status: 400 });
  }

  const categoryNames = categories.map((category: { name: string }) => `[${category.name}]`).join(', ');

  const templatePrompt = `You are a synthetic data generator for the training of a token classification model.
                  To train a token classification model, your job is to generate 10 sentences, each containing all these categories: ${categoryNames}.
                  Instead of using real values, only use the category's placeholder enclosed by brackets.
                  Here are the categories and their examples: ${categories.map((category: { name: string, example: string }) => `[${category.name}]: ${category.name} (example: ${category.example})`).join(', ')}.
                  The examples should be complete sentences without any numeric numbers, bullet points, or any other extraneous content.
                `;

  try {
    let validTemplates: string[] = [];
    let attempts = 0;
    const maxAttempts = 5;

    while (validTemplates.length < 10 && attempts < maxAttempts) {
      console.log(`attempt ${attempts}: have ${validTemplates.length} valid templates, we need 10+`);

      const templates = await generateSentences(templatePrompt);
      validTemplates = validTemplates.concat(filterTemplates(templates, categories));
      attempts++;
    }

    if (validTemplates.length < 10) {
      return NextResponse.json({ error: 'Generating templates has failed' }, { status: 500 });
    }

    const realValuesMap: { [key: string]: string[] } = {};
    const entityValuePrompts: { [key: string]: string } = {};
    for (const category of categories) {
      realValuesMap[category.name] = [];
      attempts = 0;

      const entityValuePrompt = `Generate 10 different real values for the category [${category.name}] for [${category.description}] with examples like ${category.example}. Each value should be plain, without any preceding numbers or bullet points, and separated by a semicolon.`;
      entityValuePrompts[category.name] = entityValuePrompt;

      while (realValuesMap[category.name].length < 10 && attempts < maxAttempts) {
        console.log(`attempt ${attempts}: [${category.name}] have ${realValuesMap[category.name].length} valid real values, we need 10+`);

        const values = await generateRealValues(entityValuePrompts[category.name]);
        realValuesMap[category.name] = realValuesMap[category.name].concat(values);

        attempts++;
      }

      if (realValuesMap[category.name].length < 10) {
        return NextResponse.json({ error: `Generating real values for category [${category.name}] has failed` }, { status: 500 });
      }
    }

    const syntheticDataPairs = validTemplates.map(template => generateSyntheticSentence(template, realValuesMap));

    return NextResponse.json({ syntheticDataPairs, prompts: { templatePrompt, entityValuePrompts } });
  } catch (error) {
    console.error('Error generating data:', error);
    alert('Error generating data:' + error)
    return NextResponse.json({ error: 'Error generating data' }, { status: 500 });
  }
};
