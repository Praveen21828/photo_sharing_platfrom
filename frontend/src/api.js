const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '/api/v1').replace(/\/$/, '');
const SESSION_KEY = 'photo-sharing-session';

export class ApiError extends Error {
  constructor(message, { status = 0, code = 'request_failed', details = {}, cause } = {}) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.details = details;
    this.cause = cause;
  }
}

let refreshPromise = null;

function readSession() {
  try {
    return JSON.parse(sessionStorage.getItem(SESSION_KEY) || 'null');
  } catch {
    sessionStorage.removeItem(SESSION_KEY);
    return null;
  }
}

function writeSession(session) {
  if (session?.access) sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
  else sessionStorage.removeItem(SESSION_KEY);
}

function messageFromPayload(payload, status) {
  if (payload?.message) return payload.message;
  if (payload?.detail) return typeof payload.detail === 'string' ? payload.detail : 'The request was rejected.';
  if (status === 400) return 'Please check the highlighted information and try again.';
  if (status === 401) return 'Your session has expired. Please sign in again.';
  if (status === 403) return 'You do not have permission to perform this action.';
  if (status === 404) return 'The requested resource could not be found.';
  if (status >= 500) return 'The service is temporarily unavailable. Please try again later.';
  return 'Something went wrong. Please try again.';
}

async function parseResponse(response) {
  const text = await response.text();
  if (!text) return {};
  try { return JSON.parse(text); } catch { return { message: text }; }
}

async function refreshAccessToken() {
  const session = readSession();
  if (!session?.refresh) throw new ApiError('Your session has expired. Please sign in again.', { status: 401, code: 'session_expired' });
  if (!refreshPromise) {
    refreshPromise = fetch(`${API_BASE_URL}/auth/refresh/`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh: session.refresh }),
    }).then(async (response) => {
      const payload = await parseResponse(response);
      if (!response.ok) throw new ApiError(messageFromPayload(payload, response.status), { status: response.status, code: payload.code || 'refresh_failed', details: payload.details || {} });
      const tokens = payload.data ?? payload;
      const nextSession = { ...session, access: tokens.access, refresh: tokens.refresh || session.refresh };
      writeSession(nextSession);
      return nextSession.access;
    }).catch((error) => {
      writeSession(null);
      throw error instanceof ApiError ? error : new ApiError('Your session has expired. Please sign in again.', { status: 401, code: 'session_expired', cause: error });
    }).finally(() => { refreshPromise = null; });
  }
  return refreshPromise;
}

async function request(path, options = {}, token = null, hasRetried = false) {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData)) headers.set('Content-Type', 'application/json');
  if (token) headers.set('Authorization', `Bearer ${token}`);
  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  } catch (cause) {
    throw new ApiError('Unable to reach the service. Check your connection and try again.', { code: 'network_error', cause });
  }
  const payload = await parseResponse(response);
  if (response.status === 401 && token && !hasRetried) {
    const refreshedToken = await refreshAccessToken();
    return request(path, options, refreshedToken, true);
  }
  if (!response.ok) {
    throw new ApiError(messageFromPayload(payload, response.status), {
      status: response.status,
      code: payload.code || (response.status === 401 ? 'not_authenticated' : 'request_failed'),
      details: payload.details || payload,
    });
  }
  return payload.data ?? payload;
}

async function uploadToStorage(uploadUrl, file) {
  let response;
  try {
    response = await fetch(uploadUrl, { method: 'PUT', headers: { 'Content-Type': file.type }, body: file });
  } catch (cause) {
    throw new ApiError('The photo could not reach object storage. Check your connection and try again.', { code: 'upload_network_error', cause });
  }
  if (!response.ok) throw new ApiError('Object storage rejected this upload. Please try again.', { status: response.status, code: 'upload_failed' });
}

export const api = {
  getSession: readSession,
  clearSession: () => writeSession(null),
  login: (credentials) => request('/auth/login/', { method: 'POST', body: JSON.stringify(credentials) }),
  me: (token) => request('/auth/me/', {}, token),
  refresh: refreshAccessToken,
  logout: (refresh, token) => request('/auth/logout/', { method: 'POST', body: JSON.stringify({ refresh }) }, token),
  events: (token) => request('/events/', {}, token),
  event: (eventId, token) => request(`/events/${eventId}/`, {}, token),
  createEvent: (event, token) => request('/events/', { method: 'POST', body: JSON.stringify(event) }, token),
  members: (eventId, token) => request(`/events/${eventId}/members/`, {}, token),
  addMember: (eventId, userId, token) => request(`/events/${eventId}/members/`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }, token),
  photos: async (eventId, token) => {
    const result = await request(`/photos/events/${eventId}/`, {}, token);
    return result.results ?? result;
  },
  photoUpload: (eventId, metadata, token) => request(`/photos/events/${eventId}/`, { method: 'POST', body: JSON.stringify(metadata) }, token),
  uploadPhoto: async (eventId, file, token, onProgress) => {
    const metadata = await api.photoUpload(eventId, { filename: file.name, file_size: file.size, content_type: file.type }, token);
    onProgress?.(25);
    await uploadToStorage(metadata.upload_url, file);
    onProgress?.(75);
    const completed = await request(`/photos/${metadata.photo.id}/upload-complete/`, { method: 'POST' }, token);
    onProgress?.(100);
    return completed;
  },
  galleries: (eventId, token) => request(`/galleries/events/${eventId}/`, {}, token),
  createGallery: (eventId, pin, token) => request(`/galleries/events/${eventId}/`, { method: 'POST', body: JSON.stringify({ pin }) }, token),
  gallery: (galleryId, token) => request(`/galleries/${galleryId}/`, {}, token),
  selectPhoto: (galleryId, photoId, token) => request(`/galleries/${galleryId}/photos/`, { method: 'POST', body: JSON.stringify({ photo_id: photoId }) }, token),
  deselectPhoto: (galleryId, photoId, token) => request(`/galleries/${galleryId}/photos/${photoId}/`, { method: 'DELETE' }, token),
  publishGallery: (galleryId, token) => request(`/galleries/${galleryId}/publish/`, { method: 'POST' }, token),
  verifyGalleryPin: (identifier, pin) => request(`/public/galleries/${encodeURIComponent(identifier)}/verify-pin/`, { method: 'POST', body: JSON.stringify({ pin }) }),
  publicGallery: (identifier, galleryToken) => request(`/public/galleries/${encodeURIComponent(identifier)}/`, { headers: { 'X-Gallery-Token': galleryToken } }),
  publicPhotoUrl: (identifier, photoId, galleryToken) => request(`/public/galleries/${encodeURIComponent(identifier)}/photos/${photoId}/url/`, { headers: { 'X-Gallery-Token': galleryToken } }),
};

export function getHealth() { return request('/health/'); }
