from deployment_job.chat.openai import OnPremChat, OpenAIChat

llm_providers = {"openai": OpenAIChat, "on-prem": OnPremChat}
