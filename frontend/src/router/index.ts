import { createRouter, createWebHistory } from 'vue-router'
import DashboardView from '../views/DashboardView.vue'
import ModelLibraryView from '../views/ModelLibraryView.vue'
import TaskCreateView from '../views/TaskCreateView.vue'
import TaskDetailView from '../views/TaskDetailView.vue'
import TaskPipelineView from '../views/TaskPipelineView.vue'
import TasksView from '../views/TasksView.vue'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'dashboard', component: DashboardView },
    { path: '/tasks', name: 'tasks', component: TasksView },
    { path: '/tasks/pipeline', name: 'task-pipeline', component: TaskPipelineView },
    { path: '/tasks/new', name: 'task-create', component: TaskCreateView },
    { path: '/tasks/:id', name: 'task-detail', component: TaskDetailView, props: true },
    { path: '/models', name: 'model-library', component: ModelLibraryView }
  ]
})

export default router
