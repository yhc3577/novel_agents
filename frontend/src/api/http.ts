import axios, { AxiosError, type InternalAxiosRequestConfig } from 'axios'

const TOKEN_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export const http = axios.create({
  baseURL: '/api',
  timeout: 30_000,
})

// 请求拦截：自动携带 access token
http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 401 时用 refresh token 换新 access token，再重放原请求（单飞，避免并发重复刷新）
let refreshing: Promise<string> | null = null

function refreshAccessToken(): Promise<string> {
  const refreshToken = localStorage.getItem(REFRESH_KEY)
  if (!refreshToken) {
    return Promise.reject(new Error('no refresh token'))
  }
  // 用裸 axios，避免再次进入拦截器
  return axios
    .post('/api/auth/refresh', { refresh_token: refreshToken })
    .then((res) => {
      localStorage.setItem(TOKEN_KEY, res.data.access_token)
      localStorage.setItem(REFRESH_KEY, res.data.refresh_token)
      return res.data.access_token as string
    })
}

function forceLogout() {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(REFRESH_KEY)
  window.location.href = '/login'
}

// 统一解包：直接返回响应体 data
http.interceptors.response.use(
  (r) => r.data,
  async (error: AxiosError) => {
    const { response, config } = error
    if (response?.status !== 401 || !config) {
      throw error
    }
    const original = config as InternalAxiosRequestConfig & { _retried?: boolean }
    if (original._retried || original.url?.includes('/auth/refresh')) {
      forceLogout()
      throw error
    }
    original._retried = true
    try {
      refreshing = refreshing ?? refreshAccessToken()
      const token = await refreshing
      original.headers.Authorization = `Bearer ${token}`
      // 重放原请求，成功返回已解包的响应体
      return http(original) as never
    } catch (e) {
      forceLogout()
      throw e
    } finally {
      refreshing = null
    }
  },
)
