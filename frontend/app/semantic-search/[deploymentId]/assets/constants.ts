export const lorem = [
  {
    id: 0,
    sourceName: 'thirdai.com',
    sourceURL: 'https://www.thirdai.com',
    content:
      'Build Your Own LLMs. Personalized. Private. Affordable. The ThirdAI engine makes it easy to build and deploy billion parameter models on just CPUs. No configs. No GPUs. No latency. Get Started For Free',
  },
  {
    id: 1,
    sourceName: 'thirdai.com',
    sourceURL: 'https://www.thirdai.com',
    content:
      'The Third AI Difference: Pre-train on your data instead of just using public models. Currently, most developers just use pre-trained models like RoBERTa and T5 because of the cost & complexity of training models from scratch. But with Third AI you can pre-train on your data easily and achieve much higher accuracy and personalization',
  },
  {
    id: 2,
    sourceName: 'thirdai.com',
    sourceURL: 'https://www.thirdai.com',
    content:
      'Unified Interference Our Universal Deep Transformers (UDT) library for AutoML can tackle a broad range of machine learning tasks and data modalities all through the same unified API.',
  },
];

export const exampleQueries = [
  'What is the MasterCard dispute resolution process for chargebacks?',
  'Does the same surcharge apply to all Mastercard credit card transactions of the same product type?',
  'Can a merchant express a preference for a specific payment application?',
  'What is the purpose of preparing internal reports for mastercard staff management?',
  'What are some of the safeguards a digital activity customer and staged dwo must maintain?',
];

export const generatedAnswerWords =
  "[THIS IS A MOCK, NOT ACTUALLY GENERATED] To hire and onboard a student, you should first familiarize yourself with the basics of student employment by reviewing the Student Employment Folder. Once you have done so, you can proceed with the following steps:\n1. Verify the student's I-9 status in iO.\n2. If the student is eligible for student employment, take note of their Person Number.\n3. If the student is not eligible for student employment, they may be hired as a temporary or staff employee instead. Follow the instructions in the iO Training Catalog on how to hire a temporary employee or staff member.\n4. Once step 3 is completed and approved, the student can begin working. It is important to note that this information is based on the provided context and may be subject to change".split(
    ' '
  );

export const numAnswerWords = generatedAnswerWords.length;

export const numReferencesFirstLoad = 5;

export const numReferencesLoadMore = 5;
