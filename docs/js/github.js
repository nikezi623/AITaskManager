/**
 * GitHub Contents API wrapper.
 *
 * The only module that talks to the network. Everything it throws is a
 * GitHubError with a `kind` the UI can switch on, because the difference
 * between "your token died" and "the train went into a tunnel" decides whether
 * the user sees a banner or nothing at all.
 *
 * Depends on CORS being open on api.github.com. Verified: an OPTIONS preflight
 * for PUT returns 204 with `access-control-allow-origin: *` and
 * `access-control-allow-methods: GET, POST, PATCH, PUT, DELETE`.
 */

export const REPO = 'nikezi623/ATM-data';
export const FILE_PATH = 'atm-state.json';
export const BRANCH = 'main';
const API = 'https://api.github.com';

export const ErrorKind = {
  NOT_FOUND: 'not_found',   // file (or repo) missing -- expected on first run
  CONFLICT: 'conflict',     // stale sha: another device pushed. Normal, retry.
  AUTH: 'auth',             // 401 -- token expired or revoked
  FORBIDDEN: 'forbidden',   // 403 without rate-limit headers -- wrong scopes
  RATE_LIMIT: 'rate_limit',
  NETWORK: 'network',
  UNKNOWN: 'unknown',
};

export class GitHubError extends Error {
  constructor(kind, message, status = 0, resetAt = 0) {
    super(message);
    this.name = 'GitHubError';
    this.kind = kind;
    this.status = status;
    this.resetAt = resetAt;
  }
}

function classify(status, message, headers) {
  if (status === 404) return ErrorKind.NOT_FOUND;
  if (status === 401) return ErrorKind.AUTH;
  if (status === 409 || status === 422) return ErrorKind.CONFLICT;
  if (status === 403) {
    return headers.get('x-ratelimit-remaining') === '0'
      ? ErrorKind.RATE_LIMIT
      : ErrorKind.FORBIDDEN;
  }
  return ErrorKind.UNKNOWN;
}

async function request(url, token, options = {}) {
  let response;
  try {
    response = await fetch(url, {
      ...options,
      headers: {
        Authorization: `Bearer ${token}`,
        Accept: 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        ...(options.body ? { 'Content-Type': 'application/json' } : {}),
        ...options.headers,
      },
      // Never send cookies: the API returns `Access-Control-Allow-Origin: *`,
      // and credentials mode 'include' is incompatible with a wildcard origin.
      credentials: 'omit',
    });
  } catch (cause) {
    throw new GitHubError(ErrorKind.NETWORK, String(cause), 0);
  }

  if (response.ok) return response.json();

  let message = `HTTP ${response.status}`;
  try {
    message = (await response.json()).message || message;
  } catch {
    /* keep the status line */
  }
  const reset = Number(response.headers.get('x-ratelimit-reset') || 0) * 1000;
  throw new GitHubError(classify(response.status, message, response.headers),
    message, response.status, reset);
}

/** base64 helpers that survive non-ASCII. btoa() alone throws on CJK. */
function encodeBase64(text) {
  const bytes = new TextEncoder().encode(text);
  let binary = '';
  for (const byte of bytes) binary += String.fromCharCode(byte);
  return btoa(binary);
}

function decodeBase64(base64) {
  // The API wraps content at 60 chars; atob tolerates that but strip anyway.
  const binary = atob(base64.replace(/\s/g, ''));
  const bytes = Uint8Array.from(binary, (ch) => ch.charCodeAt(0));
  return new TextDecoder().decode(bytes);
}

/**
 * Read the state file.
 * @returns {Promise<{text: string|null, sha: string|null}>} text is null when
 *          the file does not exist yet (first run) -- not an error.
 */
export async function getFile(token, { repo = REPO, path = FILE_PATH, branch = BRANCH } = {}) {
  const url = `${API}/repos/${repo}/contents/${path}?ref=${encodeURIComponent(branch)}`;
  try {
    const payload = await request(url, token);
    return { text: decodeBase64(payload.content || ''), sha: payload.sha || null };
  } catch (error) {
    if (error instanceof GitHubError && error.kind === ErrorKind.NOT_FOUND) {
      return { text: null, sha: null };
    }
    throw error;
  }
}

/**
 * Commit the state file. Omit `sha` to create it.
 * @returns {Promise<{sha: string}>}
 * @throws {GitHubError} kind === 'conflict' when `sha` is stale.
 */
export async function putFile(token, text, sha, message,
  { repo = REPO, path = FILE_PATH, branch = BRANCH } = {}) {
  const body = { message, content: encodeBase64(text), branch };
  if (sha) body.sha = sha;
  const payload = await request(`${API}/repos/${repo}/contents/${path}`, token, {
    method: 'PUT',
    body: JSON.stringify(body),
  });
  return { sha: payload.content?.sha || null };
}
