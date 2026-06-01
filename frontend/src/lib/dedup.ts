import type { PlanRequest } from "../api";

function hashContent(value: string): string {
  let hash = 2166136261;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 16777619);
  }
  return (hash >>> 0).toString(36);
}

export function sessionNonce(): string {
  return Math.random().toString(36).slice(2, 10);
}

export function planDedupKey(nonce: string, request: PlanRequest): string {
  const fields = Object.keys(request.fields)
    .sort()
    .map((name) => `${name}=${request.fields[name]}`)
    .join("&");
  const canonical = `${request.workflow}|${request.instruction}|${fields}`;
  return `plan:${nonce}:${hashContent(canonical)}`;
}
