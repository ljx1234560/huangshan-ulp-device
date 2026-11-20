import { createRouter, createWebHistory } from 'vue-router'
import AdminLayout from './layouts/AdminLayout.vue'
import { useAdminAuth } from './stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login', name: 'admin-login', component: () => import('./pages/LoginPage.vue'), meta: { public: true } },
    {
      path: '/',
      component: AdminLayout,
      children: [
        { path: '', name: 'overview', component: () => import('./pages/OverviewPage.vue') },
        { path: 'users', name: 'users', component: () => import('./pages/UsersPage.vue') },
        { path: 'devices', name: 'devices', component: () => import('./pages/DevicesPage.vue') },
        { path: 'ai-services', name: 'ai-services', component: () => import('./pages/AIStatsPage.vue') },
        { path: 'analytics', name: 'analytics', component: () => import('./pages/AnalyticsPage.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAdminAuth()
  await auth.initialize()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'admin-login' }
  if (to.meta.public && auth.isAuthenticated) return { name: 'overview' }
  return true
})

export default router
