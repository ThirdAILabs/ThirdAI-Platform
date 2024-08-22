export const demoSearchParam = "demo";

interface DemoConfig {
    name: string;
    modelService: string;
    exampleQueries: string[];
}

const mastercard: DemoConfig = {
    name: "MasterCard",
    modelService: "https://neuraldbapp.azurewebsites.net",
    exampleQueries: [
        "What is the MasterCard dispute resolution process for chargebacks?",
        "Does the same surcharge apply to all Mastercard credit card transactions of the same product type?",
        "Can a merchant express a preference for a specific payment application?",
        "What is the purpose of preparing internal reports for mastercard staff management?",
        "What are some of the safeguards a digital activity customer and staged dwo must maintain?",
    ],
};

const rice: DemoConfig = {
    name: "Rice University",
    modelService: "https://prodneuraldbapp.azurewebsites.net",
    exampleQueries: [
        "How to setup Passwordless SSH (SSH Keys) on the Clusters?",
        "What is Duo?",
        "How do I use Rice’s VPN system?",
    ],
};

export const demos = {
    mastercard,
    rice,
};
