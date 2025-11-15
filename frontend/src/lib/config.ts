import { StartScreenPrompt } from "@openai/chatkit";

export const CHATKIT_API_URL =
  import.meta.env.VITE_CHATKIT_API_URL ?? "/chatkit";

/**
 * ChatKit still expects a domain key at runtime. Use any placeholder locally,
 * but register your production domain at
 * https://platform.openai.com/settings/organization/security/domain-allowlist
 * and deploy the real key.
 */
export const CHATKIT_API_DOMAIN_KEY =
  import.meta.env.VITE_CHATKIT_API_DOMAIN_KEY ?? "domain_pk_localhost_dev";

export const FACTS_API_URL = import.meta.env.VITE_FACTS_API_URL ?? "/facts";

export const THEME_STORAGE_KEY = "chatkit-boilerplate-theme";

export const GREETING = "Welcome to Event Planner";

export const STARTER_PROMPTS: StartScreenPrompt[] = [
  {
    label: "I want to plan a hackathon",
    prompt: "I want to plan a hackathon",
    icon: "circle-question",
  },
  {
    label: "What information do you need?",
    prompt: "What information do you need to help me plan my event?",
    icon: "book-open",
  },
  {
    label: "What's the weather in Paris?",
    prompt: "What's the weather in Paris?",
    icon: "search",
  },
  {
    label: "Change the theme to dark mode",
    prompt: "Change the theme to dark mode",
    icon: "sparkle",
  },
];

export const PLACEHOLDER_INPUT = "Tell me about your event...";
