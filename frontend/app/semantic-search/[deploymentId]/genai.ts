import { ReferenceInfo } from "./modelServices";

export function genaiQuery(
    question: string,
    references: ReferenceInfo[],
    genaiPrompt: string,
) {
    // OpenAI accepts less than 4000 tokens. 2000 words gives us around 3000+ tokens.
    const context = references
        .map((ref) => {
            const lowerCaseSourceName = ref.sourceName.toLowerCase();
            if (
                lowerCaseSourceName.endsWith(".docx") ||
                lowerCaseSourceName.endsWith(".pdf")
            ) {
                return `(From file "${ref.sourceName}") ${ref.content}`;
            }
            if ("title" in ref.metadata) {
                return `(From "${ref.metadata["title"]}") ${ref.content}`;
            }
            return `(From a webpage) ${ref.content}`;
        })
        .join("\n\n")
        .split(" ")
        .slice(0, 2000)
        .join(" ");
    return `${genaiPrompt}\n\nContext: '${context}'\nQuery: '${question}'\nAnswer: `;
}
