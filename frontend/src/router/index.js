import { createRouter, createWebHistory } from 'vue-router'
import Home from '../views/Home.vue'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: Home
  },
  {
    path: '/process/:projectId',
    name: 'Process',
    component: () => import('../views/MainView.vue'),
    props: true
  },
  {
    path: '/simulation/:simulationId',
    name: 'Simulation',
    component: () => import('../views/SimulationView.vue'),
    props: true
  },
  {
    path: '/simulation/:simulationId/start',
    name: 'SimulationRun',
    component: () => import('../views/SimulationRunView.vue'),
    props: true
  },
  {
    path: '/report/:reportId',
    name: 'Report',
    component: () => import('../views/ReportView.vue'),
    props: true
  },
  {
    path: '/interaction/:reportId',
    name: 'Interaction',
    component: () => import('../views/InteractionView.vue'),
    props: true
  },
  {
    path: '/replay/:simulationId',
    name: 'Replay',
    component: () => import('../views/ReplayView.vue'),
    props: true
  },
  {
    path: '/compare/:id1?/:id2?',
    name: 'Compare',
    component: () => import('../views/ComparisonView.vue'),
    props: true
  },
  {
    // B2B email copy variant testing — run multiple email variants against synthetic ICP personas
    path: '/variant-test',
    name: 'VariantTest',
    component: () => import('../views/VariantTestView.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
