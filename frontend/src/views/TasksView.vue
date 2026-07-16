<template>
  <div class="page">
    <div class="page-title">
      <div>
        <h1>测试任务</h1>
        <p>管理联网搜索型 Agent 的配置测试任务。</p>
      </div>
      <RouterLink class="button primary" to="/tasks/new">新建任务</RouterLink>
    </div>

    <SectionPanel title="任务列表">
      <table>
        <thead>
          <tr>
            <th>名称</th>
            <th>关注点</th>
            <th>状态</th>
            <th>更新时间</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="task in tasks" :key="task.id">
            <td>{{ task.name }}</td>
            <td class="muted max-cell">{{ task.focus_points || '未填写' }}</td>
            <td><StatusBadge :status="task.status" /></td>
            <td>{{ formatTime(task.updated_at) }}</td>
            <td class="actions">
              <RouterLink :to="`/tasks/${task.id}`">进入</RouterLink>
              <button class="button small danger" @click="archive(task.id)">删除</button>
            </td>
          </tr>
        </tbody>
      </table>
    </SectionPanel>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import SectionPanel from '../components/SectionPanel.vue'
import StatusBadge from '../components/StatusBadge.vue'
import { deleteTask, listTasks } from '../api/platform'
import type { Task } from '../types'
import { formatTime } from '../utils/format'

const tasks = ref<Task[]>([])

onMounted(async () => {
  tasks.value = await listTasks()
})

async function archive(taskId: number) {
  if (!window.confirm('删除后任务会被归档，历史数据不会被物理移除。确定删除吗？')) return
  await deleteTask(taskId)
  tasks.value = await listTasks()
}
</script>
