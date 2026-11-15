// Cliente da API local. Todas as requisições que alteram estado levam o
// cabeçalho X-Xiaomi1C exigido pelo backend (proteção CSRF).
export class ApiError extends Error {
  constructor(public status: number, message: string, public reason?: string) { super(message); }
}

async function request<T>(method: string, url: string, body?: unknown): Promise<T> {
  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json", "X-Xiaomi1C": "1" },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : null;
  if (!res.ok) {
    const d = data?.detail;
    const msg = typeof d === "string" ? d : d?.message ?? `HTTP ${res.status}`;
    throw new ApiError(res.status, msg, typeof d === "object" ? d?.reason : undefined);
  }
  return data as T;
}

export const api = {
  get: <T,>(url: string) => request<T>("GET", url),
  post: <T,>(url: string, body: unknown = {}) => request<T>("POST", url, body),
  put: <T,>(url: string, body: unknown) => request<T>("PUT", url, body),
  del: <T,>(url: string) => request<T>("DELETE", url),
  command: (id: string, params: Record<string, unknown> = {}, confirm = false) =>
    request<{ ok: boolean; simulated: boolean; response: unknown; sent: unknown; note: string }>(
      "POST", `/api/commands/${id}`, { params, confirm }),
};
