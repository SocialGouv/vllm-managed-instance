import http from "k6/http";
import { check } from "k6";

export const options = { vus: 4, iterations: 40 };

const url = `https://${__ENV.HOST_IP}.nip.io/api/generate`;

const prompts = [
  "Explain how a car engine works",
  "Write a short story about a magical forest",
  "What are the main principles of machine learning?",
  "Describe the process of photosynthesis",
  "Write a recipe for chocolate cake",
  "Explain the theory of relativity",
  "What are the benefits of meditation?",
  "How does the internet work?",
];

const params = {
  headers: {
    "Content-Type": "application/json",
    Authorization: `Basic ${__ENV.HOST_CREDENTIALS}`
  },
  timeout: '300s',
};

export default function () {
  const randomIndex = Math.floor(Math.random() * prompts.length);
  const prompt = prompts[randomIndex];

  const payload = JSON.stringify({ prompt, model: __ENV.MODEL_NAME });
  const response = http.post(url, payload, params);

  check(response, {
    "status is 200": (r) => r.status === 200,
  });
}
