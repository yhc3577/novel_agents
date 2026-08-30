import { http } from './http'
import type { LoginRequest, RegisterRequest, TokenPair, UserOut } from '@/types/auth'

export const authApi = {
  register: (payload: RegisterRequest) => http.post('/auth/register', payload) as Promise<TokenPair>,
  login: (payload: LoginRequest) => http.post('/auth/login', payload) as Promise<TokenPair>,
  refresh: (refreshToken: string) => http.post('/auth/refresh', { refresh_token: refreshToken }) as Promise<TokenPair>,
  me: () => http.get('/auth/me') as Promise<UserOut>,
}
