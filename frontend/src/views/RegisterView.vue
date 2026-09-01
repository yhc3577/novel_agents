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
  <div class="auth-split">
    <!-- 左：品牌面板 -->
    <div class="auth-brand">
      <div class="brand-decor d1" />
      <div class="brand-decor d2" />
      <div class="brand-decor d3" />
      <div class="brand-logo">
        <el-icon :size="28"><EditPen /></el-icon>
      </div>
      <h1 class="brand-title">Novel Agents</h1>
      <p class="brand-slogan">AI 多智能体协同小说创作系统</p>
      <ul class="brand-features">
        <li>多智能体编排：写作 · 审查 · 去味 · 拆文 · 扫榜</li>
        <li>三阶段开书流水线，层层约束剧情连贯</li>
        <li>多模型三档，国产大模型一键接入</li>
      </ul>
    </div>
    <!-- 右：表单 -->
    <div class="auth-panel">
      <div class="auth-card">
        <h2 class="auth-card-title">注册</h2>
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
          <el-button type="primary" size="large" class="submit-btn" :loading="loading" @click="onSubmit">注 册</el-button>
        </el-form>
        <div class="auth-footer">已有账号？<router-link to="/login">返回登录</router-link></div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.auth-split { display: flex; min-height: 100vh; }
.auth-brand {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 0 64px;
  color: #fff;
  background: linear-gradient(135deg, #0e42d2 0%, #165dff 50%, #4080ff 100%);
}
.brand-decor {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.04);
}
.brand-decor.d1 { width: 360px; height: 360px; top: -80px; right: -60px; }
.brand-decor.d2 { width: 240px; height: 240px; bottom: -60px; left: 120px; }
.brand-decor.d3 { width: 160px; height: 160px; bottom: 40px; right: 80px; background: rgba(255,255,255,0.05); }
.brand-logo {
  width: 56px; height: 56px;
  border-radius: var(--radius-lg);
  background: rgba(255, 255, 255, 0.2);
  backdrop-filter: blur(10px);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 24px;
}
.brand-title { font-size: var(--font-size-3xl); margin: 0 0 8px; letter-spacing: 1px; }
.brand-slogan { font-size: var(--font-size-lg); opacity: 0.85; margin: 0 0 32px; }
.brand-features { list-style: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 12px; }
.brand-features li {
  background: rgba(255, 255, 255, 0.1);
  border-radius: var(--radius-md);
  padding: 12px 16px;
  backdrop-filter: blur(5px);
  font-size: var(--font-size-sm);
  width: fit-content;
}
.auth-panel {
  width: 480px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-bg-card);
  padding: var(--space-lg);
}
.auth-card { width: 100%; max-width: 380px; }
.auth-card-title { font-size: var(--font-size-2xl); margin: 0 0 24px; color: var(--color-text-primary); }
.submit-btn { width: 100%; margin-top: 8px; }
.auth-footer { margin-top: 16px; font-size: var(--font-size-sm); color: var(--color-text-secondary); text-align: center; }
.auth-footer a { color: var(--color-primary); text-decoration: none; }
</style>
