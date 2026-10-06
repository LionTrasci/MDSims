export async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch('/api' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: {'Content-Type': 'application/json', 'X-Portal-Request': '1'},
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok) {
    const message = Array.isArray(data.detail)
      ? data.detail.map((e: {loc: string[]; msg: string}) => `${e.loc.slice(1).join('.')}: ${e.msg}`).join('; ')
      : data.detail;
    throw new Error(message || 'The request failed');
  }
  return data as T;
}
