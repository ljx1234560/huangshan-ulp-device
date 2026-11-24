import { createRouter, createWebHistory } from 'vue-router'
import UserLayout from './layouts/UserLayout.vue'
import { useAuthStore } from './stores/auth'

const router = createRouter({
  history: createWebHistory(),
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    { path: '/login', name: 'login', component: () => import('./pages/LoginPage.vue'), meta: { public: true } },
    { path: '/register', name: 'register', component: () => import('./pages/RegisterPage.vue'), meta: { public: true } },
    {
      path: '/',
      component: UserLayout,
      children: [
        { path: '', name: 'dashboard', component: () => import('./pages/DashboardPage.vue') },
        { path: 'activity', name: 'activity', component: () => import('./pages/ActivityPage.vue') },
        { path: 'coach', name: 'coach', component: () => import('./pages/CoachPage.vue') },
        { path: 'pet-studio', name: 'pet-studio', component: () => import('./pages/PetStudioPage.vue') },
        { path: 'pet', name: 'pet', component: () => import('./pages/PetGrowthPage.vue') },
        { path: 'devices', name: 'devices', component: () => import('./pages/DevicePage.vue') },
        { path: 'profile', name: 'profile', component: () => import('./pages/ProfilePage.vue') },
      ],
    },
    { path: '/:pathMatch(.*)*', redirect: '/' },
  ],
})

router.beforeEach(async (to) => {
  const auth = useAuthStore()
  await auth.initialize()
  if (!to.meta.public && !auth.isAuthenticated) return { name: 'login', query: { redirect: to.fullPath } }
  if (to.meta.public && auth.isAuthenticated && (to.name === 'login' || to.name === 'register')) return { name: 'dashboard' }
  return true
})

export default router
