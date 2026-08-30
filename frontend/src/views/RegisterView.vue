<script setup lang="ts">
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const form = reactive({
  username: '',
  password: '',
  confirm: '',
  email: '',
  display_name: '',
})

const rules: FormRules = {
  username: [
    { required: true, message: '请输入用户名', trigger: 'blur' },
    { min: 3, max: 64, message: '用户名长度 3~64 位', trigger: 'blur' },
    { pattern: /^[a-zA-Z0-9_]+$/, message: '仅支持字母、数字、下划线', trigger: 'blur' },
  ],
  password: [
    { required: true, message: '请输入密码', trigger: 'blur' },
    { min: 6, max: 128, message: '密码长度 6~128 位', trigger: 'blur' },
  ],
  confirm: [
    { required: true, message: '请再次输入密码', trigger: 'blur' },
    {
      validator: (_rule, value, cb) => (value === form.password ? cb() : cb(new Error('两次密码不一致'))),
      trigger: 'blur',
    },
  ],
  email: [{ type: 'email', message: '邮箱格式不正确', trigger: 'blur' }],
}

async function onSubmit() {
  if (!formRef.value) return
  await formRef.value.validate(async (valid) => {
    if (!valid) return
    loading.value = true
    try {
      await auth.register({
        username: form.username,
        password: form.password,
        email: form.email || undefined,
        display_name: form.display_name || undefined,
      })
      ElMessage.success('注册成功')
      router.push('/dashboard')
    } catch (e: any) {
      ElMessage.error(e?.response?.data?.detail || '注册失败')
    } finally {
      loading.value = false
    }
  })
}
</script>

<template>
  <div class="page-centered auth-bg">
    <el-card class="auth-card" shadow="always">
      <div class="brand">
        <span class="brand-logo">文</span>
        <h1 class="brand-title">创建账号</h1>
        <p class="brand-sub">开启你的 AI 协同创作之旅</p>
      </div>

      <el-form ref="formRef" :model="form" :rules="rules" size="large" label-position="top" @submit.prevent="onSubmit">
        <el-form-item label="用户名" prop="username">
          <el-input v-model="form.username" placeholder="3~64 位，字母/数字/下划线" autocomplete="username" clearable />
        </el-form-item>
        <el-form-item label="密码" prop="password">
          <el-input v-model="form.password" type="password" placeholder="6~128 位" autocomplete="new-password" show-password />
        </el-form-item>
        <el-form-item label="确认密码" prop="confirm">
          <el-input v-model="form.confirm" type="password" placeholder="再次输入密码" autocomplete="new-password" show-password />
        </el-form-item>
        <el-form-item label="邮箱（可选）" prop="email">
          <el-input v-model="form.email" placeholder="用于找回密码等" autocomplete="email" clearable />
        </el-form-item>
        <el-form-item label="昵称（可选）" prop="display_name">
          <el-input v-model="form.display_name" placeholder="展示名，默认使用用户名" clearable />
        </el-form-item>
        <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="onSubmit">
          注 册
        </el-button>
      </el-form>

      <div class="auth-footer">
        已有账号？
        <router-link to="/login">返回登录</router-link>
      </div>
    </el-card>
  </div>
</template>

<style scoped>
.auth-bg {
  background: linear-gradient(135deg, #eef2ff 0%, #e0e7ff 100%);
}

.auth-card {
  width: 400px;
  border-radius: 12px;
}

.brand {
  text-align: center;
  margin-bottom: 20px;
}

.brand-logo {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  border-radius: 12px;
  background: var(--brand);
  color: #fff;
  font-family: Georgia, serif;
  font-size: 24px;
  font-weight: bold;
}

.brand-title {
  margin: 12px 0 4px;
  font-size: 22px;
  color: #1f2937;
}

.brand-sub {
  margin: 0;
  font-size: 13px;
  color: #6b7280;
}

.submit-btn {
  width: 100%;
  margin-top: 4px;
}

.auth-footer {
  margin-top: 16px;
  text-align: center;
  font-size: 13px;
  color: #6b7280;
}

.auth-footer a {
  color: var(--brand);
  text-decoration: none;
}
</style>
