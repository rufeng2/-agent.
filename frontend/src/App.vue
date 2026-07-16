<template>
  <router-view v-if="route.meta.public" />
  <div v-else class="app-shell">
    <aside
      class="app-sidebar"
      :class="{ open: mobileOpen, collapsed }"
      :style="{ width: sidebarWidth + 'px', flexBasis: sidebarWidth + 'px' }"
    >
      <div class="brand">
        <span class="brand-mark">E</span>
        <div class="sidebar-copy">
          <strong>智能电商运营 Agent 平台</strong>
          <small>Agent Workspace</small>
        </div>
      </div>
      <nav>
        <router-link to="/agent" title="运营执行助手"><el-icon><ChatDotRound /></el-icon><span class="sidebar-copy">运营执行助手</span></router-link>
        <router-link to="/dashboard" title="经营数据"><el-icon><DataBoard /></el-icon><span class="sidebar-copy">经营数据</span></router-link>
        <router-link to="/products" title="商品分析"><el-icon><Goods /></el-icon><span class="sidebar-copy">商品分析</span></router-link>
      </nav>
      <div class="account">
        <div class="avatar">{{ auth.username.slice(0, 1).toUpperCase() }}</div>
        <div class="account-copy sidebar-copy"><strong>{{ auth.username }}</strong><small>{{ roleName }}</small></div>
        <el-dropdown trigger="click">
          <el-button text circle title="账号菜单"><el-icon><MoreFilled /></el-icon></el-button>
          <template #dropdown>
            <el-dropdown-menu>
              <el-dropdown-item @click="logout">退出登录</el-dropdown-item>
            </el-dropdown-menu>
          </template>
        </el-dropdown>
      </div>

      <button class="collapse-handle" type="button" :title="collapsed ? '展开导航' : '折叠导航'" @click="toggleCollapsed">
        <el-icon><ArrowRight v-if="collapsed" /><ArrowLeft v-else /></el-icon>
      </button>
      <div
        v-if="!collapsed"
        class="resize-handle"
        title="拖动调整导航宽度"
        @pointerdown="startResize"
      ></div>
    </aside>

    <div v-if="mobileOpen" class="shell-mask" @click="mobileOpen = false"></div>
    <main class="app-main">
      <header class="mobile-header">
        <el-button text circle @click="mobileOpen = true"><el-icon><Menu /></el-icon></el-button>
        <strong>智能电商运营</strong><span></span>
      </header>
      <router-view />
    </main>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from "vue"
import { useRoute, useRouter } from "vue-router"
import { useAuthStore } from "@/store/auth"

const route = useRoute()
const router = useRouter()
const auth = useAuthStore()
const mobileOpen = ref(false)
const savedWidth = Number(localStorage.getItem("sidebar-width") || 204)
const sidebarWidth = ref(Math.min(280, Math.max(150, savedWidth)))
const previousWidth = ref(sidebarWidth.value)
const collapsed = ref(localStorage.getItem("sidebar-collapsed") === "true")
if (collapsed.value) sidebarWidth.value = 64

const roleName = computed(() => ({ admin: "运营管理员", editor: "运营编辑", viewer: "只读用户", user: "运营用户" } as any)[auth.role] || auth.role)
watch(() => route.path, () => { mobileOpen.value = false })

function toggleCollapsed() {
  collapsed.value = !collapsed.value
  if (collapsed.value) {
    previousWidth.value = sidebarWidth.value
    sidebarWidth.value = 64
  } else {
    sidebarWidth.value = Math.max(150, previousWidth.value || 204)
  }
  localStorage.setItem("sidebar-collapsed", String(collapsed.value))
}

function startResize(event: PointerEvent) {
  if (window.innerWidth <= 760) return
  event.preventDefault()
  const startX = event.clientX
  const startWidth = sidebarWidth.value
  document.body.classList.add("resizing-sidebar")

  const move = (moveEvent: PointerEvent) => {
    sidebarWidth.value = Math.min(280, Math.max(150, startWidth + moveEvent.clientX - startX))
  }
  const stop = () => {
    previousWidth.value = sidebarWidth.value
    localStorage.setItem("sidebar-width", String(sidebarWidth.value))
    document.body.classList.remove("resizing-sidebar")
    window.removeEventListener("pointermove", move)
    window.removeEventListener("pointerup", stop)
  }
  window.addEventListener("pointermove", move)
  window.addEventListener("pointerup", stop, { once: true })
}

onBeforeUnmount(() => document.body.classList.remove("resizing-sidebar"))

function logout() {
  auth.logout()
  router.push("/")
}
</script>
