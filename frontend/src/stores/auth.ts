import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { authApi } from '@/api/auth'
import type { RegisterRequest, TokenPair, UserOut } from '@/types/auth'

const TOKEN_KEY = 'access_token'
const REFRESH_KEY = 'refresh_token'

export const useAuthStore = defineStore('auth', () => {
  const accessToken = ref(localStorage.getItem(TOKEN_KEY) ?? '')
  const refreshToken = ref(localStorage.getItem(REFRESH_KEY) ?? '')
  const user = ref<UserOut | null>(null)

  const isAuthenticated = computed(() => Boolean(accessToken.value))

  function setTokens(t: TokenPair) {
    accessToken.value = t.access_token
    refreshToken.value = t.refresh_token
    localStorage.setItem(TOKEN_KEY, t.access_token)
    localStorage.setItem(REFRESH_KEY, t.refresh_token)
  }

  async function login(username: string, password: string) {
    const tokens = await authApi.login({ username, password })
    setTokens(tokens)
    await fetchMe()
  }

  async function register(payload: RegisterRequest) {
    const tokens = await authApi.register(payload)
    setTokens(tokens)
    await fetchMe()
  }

  async function fetchMe() {
    user.value = await authApi.me()
  }

  function logout() {
    accessToken.value = ''
    refreshToken.value = ''
    user.value = null
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  }

  return { accessToken, refreshToken, user, isAuthenticated, setTokens, login, register, fetchMe, logout }
})
