export interface TokenPair {
  access_token: string
  refresh_token: string
  token_type: string
}

export interface UserOut {
  id: number
  username: string
  email: string | null
  display_name: string | null
  is_active: boolean
}

export interface RegisterRequest {
  username: string
  password: string
  email?: string
  display_name?: string
}

export interface LoginRequest {
  username: string
  password: string
}
